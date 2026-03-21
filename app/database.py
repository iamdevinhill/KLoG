from neo4j import GraphDatabase

from app.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

driver = None


def get_driver():
    global driver
    if driver is None:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return driver


def close_driver():
    global driver
    if driver:
        driver.close()
        driver = None


def ensure_fulltext_index():
    d = get_driver()
    with d.session() as session:
        result = session.run("SHOW INDEXES YIELD name RETURN name")
        existing = {r["name"] for r in result}
        if "page_fulltext" not in existing:
            session.run(
                "CREATE FULLTEXT INDEX page_fulltext FOR (p:Page) ON EACH [p.title, p.content]"
            )
