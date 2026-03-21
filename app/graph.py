from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.database import get_driver
from app.models import GraphNode, GraphEdge, GraphResponse

router = APIRouter()


@router.get("/graph", response_model=GraphResponse)
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
