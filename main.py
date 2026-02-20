import os
import re
import json
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from typing import Optional

import bcrypt
import jwt
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4jpassword")
JWT_SECRET = os.getenv("JWT_SECRET", "kg_log_secret_change_me_in_production")

driver = None

WIKILINK_PATTERN = re.compile(r"\[\[(.+?)\]\]")


def get_driver():
    global driver
    if driver is None:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return driver


def ensure_fulltext_index():
    d = get_driver()
    with d.session() as session:
        result = session.run("SHOW INDEXES YIELD name RETURN name")
        existing = {r["name"] for r in result}
        if "page_fulltext" not in existing:
            session.run(
                "CREATE FULLTEXT INDEX page_fulltext FOR (p:Page) ON EACH [p.title, p.content]"
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    import time
    get_driver()
    # Retry for up to 30s while Neo4j starts
    for attempt in range(15):
        try:
            ensure_fulltext_index()
            break
        except Exception:
            if attempt < 14:
                time.sleep(2)
            else:
                raise
    yield
    if driver:
        driver.close()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Context-Pages"],
)


# --- Pydantic models ---

class AuthRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    token: str
    username: str


class PageCreate(BaseModel):
    title: str
    content: str = ""


class PageUpdate(BaseModel):
    content: str


class PageResponse(BaseModel):
    title: str
    content: str
    createdAt: str
    updatedAt: str
    backlinks: list[str] = []
    links: list[str] = []


class PageListItem(BaseModel):
    title: str
    updatedAt: str


class GraphNode(BaseModel):
    id: str
    title: str
    connections: int = 0


class GraphEdge(BaseModel):
    source: str
    target: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class AskRequest(BaseModel):
    question: str
    provider: str = "ollama"  # "ollama", "openai", "anthropic"
    model: str = ""
    api_key: str = ""


# --- Auth helpers ---

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def get_current_user(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization[7:]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# --- Auth endpoints ---

@app.post("/signup", response_model=AuthResponse)
def signup(req: AuthRequest):
    if len(req.username) < 2:
        raise HTTPException(status_code=400, detail="Username must be at least 2 characters")
    if len(req.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
    d = get_driver()
    with d.session() as session:
        existing = session.run("MATCH (u:User {username: $username}) RETURN u", username=req.username).single()
        if existing:
            raise HTTPException(status_code=409, detail="Username already taken")
        session.run(
            "CREATE (u:User {username: $username, password: $password, createdAt: $now})",
            username=req.username,
            password=hash_password(req.password),
            now=datetime.now(timezone.utc).isoformat(),
        )
    return AuthResponse(token=create_token(req.username), username=req.username)


@app.post("/login", response_model=AuthResponse)
def login(req: AuthRequest):
    d = get_driver()
    with d.session() as session:
        result = session.run("MATCH (u:User {username: $username}) RETURN u.password AS password", username=req.username).single()
        if not result or not verify_password(req.password, result["password"]):
            raise HTTPException(status_code=401, detail="Invalid username or password")
    return AuthResponse(token=create_token(req.username), username=req.username)


# --- Helper functions ---

def parse_wikilinks(content: str) -> list[str]:
    return list(set(WIKILINK_PATTERN.findall(content)))


def sync_links(tx, username: str, source_title: str, content: str):
    """Delete old LINKS_TO from source and create new ones based on content."""
    tx.run(
        "MATCH (u:User {username: $username})-[:OWNS]->(s:Page {title: $title})-[r:LINKS_TO]->() DELETE r",
        username=username, title=source_title,
    )
    linked_titles = parse_wikilinks(content)
    now = datetime.now(timezone.utc).isoformat()
    for target_title in linked_titles:
        tx.run(
            """
            MATCH (u:User {username: $username})
            MERGE (u)-[:OWNS]->(t:Page {title: $target})
            ON CREATE SET t.content = '', t.createdAt = $now, t.updatedAt = $now
            WITH t
            MATCH (u2:User {username: $username})-[:OWNS]->(s:Page {title: $source})
            MERGE (s)-[:LINKS_TO]->(t)
            """,
            username=username,
            source=source_title,
            target=target_title,
            now=now,
        )


# --- Page endpoints (user-scoped) ---

@app.get("/pages", response_model=list[PageListItem])
def list_pages(username: str = Depends(get_current_user)):
    d = get_driver()
    with d.session() as session:
        result = session.run(
            "MATCH (u:User {username: $username})-[:OWNS]->(p:Page) RETURN p.title AS title, p.updatedAt AS updatedAt ORDER BY p.updatedAt DESC",
            username=username,
        )
        return [PageListItem(title=r["title"], updatedAt=r["updatedAt"]) for r in result]


def _get_page(username: str, title: str):
    d = get_driver()
    with d.session() as session:
        result = session.run(
            """
            MATCH (u:User {username: $username})-[:OWNS]->(p:Page {title: $title})
            OPTIONAL MATCH (p)-[:LINKS_TO]->(linked:Page)
            OPTIONAL MATCH (backlinker:Page)-[:LINKS_TO]->(p)
            RETURN p.title AS title, p.content AS content,
                   p.createdAt AS createdAt, p.updatedAt AS updatedAt,
                   collect(DISTINCT linked.title) AS links,
                   collect(DISTINCT backlinker.title) AS backlinks
            """,
            username=username, title=title,
        )
        record = result.single()
        if not record or record["title"] is None:
            raise HTTPException(status_code=404, detail="Page not found")
        return PageResponse(
            title=record["title"],
            content=record["content"] or "",
            createdAt=record["createdAt"],
            updatedAt=record["updatedAt"],
            links=[l for l in record["links"] if l],
            backlinks=[b for b in record["backlinks"] if b],
        )


@app.get("/pages/{title}", response_model=PageResponse)
def get_page(title: str, username: str = Depends(get_current_user)):
    return _get_page(username, title)


@app.post("/pages", response_model=PageResponse, status_code=201)
def create_page(page: PageCreate, username: str = Depends(get_current_user)):
    d = get_driver()
    now = datetime.now(timezone.utc).isoformat()
    with d.session() as session:
        existing = session.run(
            "MATCH (u:User {username: $username})-[:OWNS]->(p:Page {title: $title}) RETURN p",
            username=username, title=page.title,
        ).single()
        if existing and (existing["p"]["content"] or ""):
            raise HTTPException(status_code=409, detail="Page already exists with content")

        def _create(tx):
            tx.run(
                """
                MATCH (u:User {username: $username})
                MERGE (u)-[:OWNS]->(p:Page {title: $title})
                SET p.content = $content, p.createdAt = $now, p.updatedAt = $now
                """,
                username=username, title=page.title, content=page.content, now=now,
            )
            sync_links(tx, username, page.title, page.content)

        session.execute_write(_create)
    return _get_page(username, page.title)


@app.put("/pages/{title}", response_model=PageResponse)
def update_page(title: str, page: PageUpdate, username: str = Depends(get_current_user)):
    d = get_driver()
    now = datetime.now(timezone.utc).isoformat()
    with d.session() as session:
        existing = session.run(
            "MATCH (u:User {username: $username})-[:OWNS]->(p:Page {title: $title}) RETURN p",
            username=username, title=title,
        ).single()
        if not existing:
            raise HTTPException(status_code=404, detail="Page not found")

        def _update(tx):
            tx.run(
                "MATCH (u:User {username: $username})-[:OWNS]->(p:Page {title: $title}) SET p.content = $content, p.updatedAt = $now",
                username=username, title=title, content=page.content, now=now,
            )
            sync_links(tx, username, title, page.content)

        session.execute_write(_update)
    return _get_page(username, title)


@app.delete("/pages/{title}", status_code=204)
def delete_page(title: str, username: str = Depends(get_current_user)):
    d = get_driver()
    with d.session() as session:
        existing = session.run(
            "MATCH (u:User {username: $username})-[:OWNS]->(p:Page {title: $title}) RETURN p",
            username=username, title=title,
        ).single()
        if not existing:
            raise HTTPException(status_code=404, detail="Page not found")
        session.run(
            "MATCH (u:User {username: $username})-[:OWNS]->(p:Page {title: $title}) DETACH DELETE p",
            username=username, title=title,
        )


@app.get("/graph", response_model=GraphResponse)
def get_graph(username: str = Depends(get_current_user)):
    d = get_driver()
    with d.session() as session:
        nodes_result = session.run(
            """
            MATCH (u:User {username: $username})-[:OWNS]->(p:Page)
            OPTIONAL MATCH (p)-[r:LINKS_TO]-()
            RETURN p.title AS title, count(r) AS connections
            """,
            username=username,
        )
        nodes = []
        for r in nodes_result:
            nodes.append(GraphNode(id=r["title"], title=r["title"], connections=r["connections"]))

        edges_result = session.run(
            """
            MATCH (u:User {username: $username})-[:OWNS]->(a:Page)-[:LINKS_TO]->(b:Page)
            RETURN a.title AS source, b.title AS target
            """,
            username=username,
        )
        edges = [GraphEdge(source=r["source"], target=r["target"]) for r in edges_result]

    return GraphResponse(nodes=nodes, edges=edges)


# --- AI Assistant: multi-provider ---

def _resolve_date_pages(question: str) -> list[str]:
    """Map natural language date references to daily page titles."""
    q = question.lower()
    today = datetime.now(timezone.utc).date()
    pages = []
    if "today" in q:
        pages.append(today.isoformat())
    if "yesterday" in q:
        pages.append((today - timedelta(days=1)).isoformat())
    if "this week" in q:
        for i in range(today.weekday() + 1):
            pages.append((today - timedelta(days=i)).isoformat())
    return pages


def _build_context(username: str, question: str):
    """Gather relevant page context for the AI prompt."""
    d = get_driver()
    context_titles = []
    context_text = ""

    with d.session() as session:
        date_pages = _resolve_date_pages(question)
        if date_pages:
            result = session.run(
                "UNWIND $titles AS t MATCH (u:User {username: $username})-[:OWNS]->(p:Page {title: t}) WHERE p.content <> '' RETURN p.title AS title, p.content AS content",
                titles=date_pages, username=username,
            )
            for r in result:
                context_titles.append(r["title"])
                context_text += f"\n\n--- {r['title']} ---\n{r['content']}"

        try:
            result = session.run(
                """
                CALL db.index.fulltext.queryNodes('page_fulltext', $query)
                YIELD node, score
                MATCH (u:User {username: $username})-[:OWNS]->(node)
                RETURN node.title AS title, node.content AS content, score
                ORDER BY score DESC LIMIT 5
                """,
                query=question, username=username,
            )
            for r in result:
                if r["content"] and r["title"] not in context_titles:
                    context_titles.append(r["title"])
                    context_text += f"\n\n--- {r['title']} ---\n{r['content']}"
        except Exception:
            result = session.run(
                "MATCH (u:User {username: $username})-[:OWNS]->(p:Page) WHERE p.content <> '' RETURN p.title AS title, p.content AS content LIMIT 5",
                username=username,
            )
            for r in result:
                if r["title"] not in context_titles:
                    context_titles.append(r["title"])
                    context_text += f"\n\n--- {r['title']} ---\n{r['content']}"

    today_str = datetime.now(timezone.utc).date().isoformat()
    system_prompt = f"""You are a helpful AI assistant for a knowledge graph note-taking app.
Today's date is {today_str}. Daily journal pages are titled by date (e.g. "2026-02-19").
Answer questions using the following context from the user's notes. If the context doesn't contain
relevant information, say so and answer based on your general knowledge.

Context from notes:{context_text}"""

    return system_prompt, context_titles


@app.get("/ollama/models")
async def list_ollama_models():
    """Fetch available models from local Ollama instance."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get("http://localhost:11434/api/tags")
            data = res.json()
            models = [m["name"] for m in data.get("models", [])]
            return {"models": models}
    except Exception:
        return {"models": [], "error": "Could not connect to Ollama"}


@app.post("/ask")
async def ask_question(req: AskRequest, username: str = Depends(get_current_user)):
    system_prompt, context_titles = _build_context(username, req.question)
    provider = req.provider
    model = req.model
    api_key = req.api_key

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": req.question},
    ]

    async def stream_ollama():
        yield json.dumps({"type": "context", "pages": context_titles}) + "\n"
        ollama_model = model or "qwen3:8b"
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                "http://localhost:11434/api/chat",
                json={
                    "model": ollama_model,
                    "messages": messages,
                    "stream": True,
                    "options": {"num_ctx": 4096},
                    "think": False,
                },
            ) as response:
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            if "message" in data and "content" in data["message"]:
                                yield json.dumps({"type": "token", "content": data["message"]["content"]}) + "\n"
                            if data.get("done"):
                                yield json.dumps({"type": "done"}) + "\n"
                        except json.JSONDecodeError:
                            pass

    async def stream_openai():
        yield json.dumps({"type": "context", "pages": context_titles}) + "\n"
        if not api_key:
            yield json.dumps({"type": "token", "content": "Error: OpenAI API key is required."}) + "\n"
            yield json.dumps({"type": "done"}) + "\n"
            return
        openai_model = model or "gpt-4o-mini"
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": openai_model, "messages": messages, "stream": True},
            ) as response:
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload == "[DONE]":
                        yield json.dumps({"type": "done"}) + "\n"
                        break
                    try:
                        data = json.loads(payload)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        if "content" in delta and delta["content"]:
                            yield json.dumps({"type": "token", "content": delta["content"]}) + "\n"
                    except json.JSONDecodeError:
                        pass

    async def stream_anthropic():
        yield json.dumps({"type": "context", "pages": context_titles}) + "\n"
        if not api_key:
            yield json.dumps({"type": "token", "content": "Error: Anthropic API key is required."}) + "\n"
            yield json.dumps({"type": "done"}) + "\n"
            return
        claude_model = model or "claude-sonnet-4-5-20250929"
        # Anthropic expects system as a top-level param, not in messages
        user_messages = [{"role": "user", "content": req.question}]
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": claude_model,
                    "max_tokens": 2048,
                    "system": system_prompt,
                    "messages": user_messages,
                    "stream": True,
                },
            ) as response:
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue
                    try:
                        data = json.loads(line[6:])
                        if data.get("type") == "content_block_delta":
                            text = data.get("delta", {}).get("text", "")
                            if text:
                                yield json.dumps({"type": "token", "content": text}) + "\n"
                        elif data.get("type") == "message_stop":
                            yield json.dumps({"type": "done"}) + "\n"
                    except json.JSONDecodeError:
                        pass

    if provider == "openai":
        streamer = stream_openai()
    elif provider == "anthropic":
        streamer = stream_anthropic()
    else:
        streamer = stream_ollama()

    return StreamingResponse(
        streamer,
        media_type="application/x-ndjson",
        headers={"X-Context-Pages": json.dumps(context_titles)},
    )


# Serve static frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")
