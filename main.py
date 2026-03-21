import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from fastapi import HTTPException

from app.config import CORS_ORIGINS, warn_default_secret
from app.database import get_driver, close_driver, ensure_fulltext_index
from app.auth import hash_password, verify_password, create_token
from app.models import AuthRequest, AuthResponse
from app.pages import router as pages_router
from app.graph import router as graph_router
from app.ai import router as ai_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    warn_default_secret()
    get_driver()
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
    close_driver()


app = FastAPI(title="KLoG", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Context-Pages"],
)


# --- Health check ---

@app.get("/health")
def health_check():
    """Health check endpoint for monitoring and Docker healthchecks."""
    try:
        d = get_driver()
        with d.session() as session:
            session.run("RETURN 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail={"status": "unhealthy", "database": str(e)})


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
        from datetime import datetime, timezone
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


# --- Routers ---

app.include_router(pages_router)
app.include_router(graph_router)
app.include_router(ai_router)

# Serve static frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")
