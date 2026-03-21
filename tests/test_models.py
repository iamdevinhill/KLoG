"""Tests for Pydantic models."""

from app.models import (
    AuthRequest,
    AuthResponse,
    PageCreate,
    PageUpdate,
    PageResponse,
    PageListItem,
    GraphNode,
    GraphEdge,
    GraphResponse,
    AskRequest,
)


class TestAuthModels:
    def test_auth_request(self):
        req = AuthRequest(username="alice", password="pass123")
        assert req.username == "alice"
        assert req.password == "pass123"

    def test_auth_response(self):
        resp = AuthResponse(token="abc123", username="alice")
        assert resp.token == "abc123"


class TestPageModels:
    def test_page_create_defaults(self):
        page = PageCreate(title="Test")
        assert page.title == "Test"
        assert page.content == ""

    def test_page_create_with_content(self):
        page = PageCreate(title="Test", content="Hello [[world]]")
        assert page.content == "Hello [[world]]"

    def test_page_update(self):
        update = PageUpdate(content="New content")
        assert update.content == "New content"

    def test_page_response_defaults(self):
        resp = PageResponse(
            title="Test", content="Hello", createdAt="2026-01-01", updatedAt="2026-01-01"
        )
        assert resp.backlinks == []
        assert resp.links == []


class TestGraphModels:
    def test_graph_node_defaults(self):
        node = GraphNode(id="test", title="Test")
        assert node.connections == 0

    def test_graph_response(self):
        resp = GraphResponse(
            nodes=[GraphNode(id="a", title="A", connections=1)],
            edges=[GraphEdge(source="a", target="b")],
        )
        assert len(resp.nodes) == 1
        assert len(resp.edges) == 1


class TestAskRequest:
    def test_defaults(self):
        req = AskRequest(question="What did I do today?")
        assert req.provider == "ollama"
        assert req.model == ""
        assert req.api_key == ""
