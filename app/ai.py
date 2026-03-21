import json
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.auth import get_current_user
from app.config import OLLAMA_BASE
from app.database import get_driver
from app.models import AskRequest

router = APIRouter()


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


@router.get("/ollama/models")
async def list_ollama_models():
    """Fetch available models from local Ollama instance."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(f"{OLLAMA_BASE}/api/tags")
            data = res.json()
            models = [m["name"] for m in data.get("models", [])]
            return {"models": models}
    except Exception:
        return {"models": [], "error": "Could not connect to Ollama"}


@router.post("/ask")
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
                f"{OLLAMA_BASE}/api/chat",
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
