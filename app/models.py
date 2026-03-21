from pydantic import BaseModel


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


class BulkDeleteRequest(BaseModel):
    titles: list[str]


class AskRequest(BaseModel):
    question: str
    provider: str = "ollama"
    model: str = ""
    api_key: str = ""
