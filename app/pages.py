import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends

from app.auth import get_current_user
from app.database import get_driver
from app.models import PageCreate, PageUpdate, PageResponse, PageListItem, BulkDeleteRequest

router = APIRouter()

WIKILINK_PATTERN = re.compile(r"\[\[(.+?)\]\]")


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
                   p.color AS color,
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
            color=record["color"] or "#00e5ff",
            links=[link for link in record["links"] if link],
            backlinks=[b for b in record["backlinks"] if b],
        )


@router.get("/pages", response_model=list[PageListItem])
def list_pages(username: str = Depends(get_current_user)):
    d = get_driver()
    with d.session() as session:
        result = session.run(
            "MATCH (u:User {username: $username})-[:OWNS]->(p:Page) RETURN p.title AS title, p.updatedAt AS updatedAt ORDER BY p.updatedAt DESC",
            username=username,
        )
        return [PageListItem(title=r["title"], updatedAt=r["updatedAt"]) for r in result]


@router.get("/pages/{title}", response_model=PageResponse)
def get_page(title: str, username: str = Depends(get_current_user)):
    return _get_page(username, title)


@router.post("/pages", response_model=PageResponse, status_code=201)
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
                SET p.content = $content, p.color = $color, p.createdAt = $now, p.updatedAt = $now
                """,
                username=username, title=page.title, content=page.content, color=page.color, now=now,
            )
            sync_links(tx, username, page.title, page.content)

        session.execute_write(_create)
    return _get_page(username, page.title)


@router.put("/pages/{title}", response_model=PageResponse)
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
            set_clause = "SET p.content = $content, p.updatedAt = $now"
            params = dict(username=username, title=title, content=page.content, now=now)
            if page.color is not None:
                set_clause += ", p.color = $color"
                params["color"] = page.color
            tx.run(
                f"MATCH (u:User {{username: $username}})-[:OWNS]->(p:Page {{title: $title}}) {set_clause}",
                **params,
            )
            sync_links(tx, username, title, page.content)

        session.execute_write(_update)
    return _get_page(username, title)


@router.delete("/pages/{title}", status_code=204)
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


@router.post("/pages/bulk-delete", status_code=200)
def bulk_delete_pages(req: BulkDeleteRequest, username: str = Depends(get_current_user)):
    if not req.titles:
        raise HTTPException(status_code=400, detail="No pages specified")
    d = get_driver()
    with d.session() as session:
        result = session.run(
            """
            UNWIND $titles AS title
            MATCH (u:User {username: $username})-[:OWNS]->(p:Page {title: title})
            DETACH DELETE p
            RETURN count(p) AS deleted
            """,
            titles=req.titles, username=username,
        )
        record = result.single()
        deleted = record["deleted"] if record else 0
    return {"deleted": deleted}
