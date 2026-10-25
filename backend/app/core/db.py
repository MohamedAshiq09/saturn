"""
FalkorDB connection module.
Single FalkorDB client shared across the app.
Uses the official falkordb-py client.
"""
import asyncio
import threading
from functools import lru_cache
from typing import Optional

import falkordb
from app.core.config import settings


# Thread-safe singleton
_db_client: Optional[falkordb.FalkorDB] = None
_lock = threading.Lock()


def get_client() -> falkordb.FalkorDB:
    """Return the global FalkorDB client (thread-safe singleton)."""
    global _db_client
    if _db_client is None:
        with _lock:
            if _db_client is None:
                if settings.FALKORDB_URL:
                    _db_client = falkordb.FalkorDB.from_url(settings.FALKORDB_URL)
                else:
                    kwargs = {
                        "host": settings.FALKORDB_HOST,
                        "port": settings.FALKORDB_PORT,
                    }
                    if settings.FALKORDB_PASSWORD:
                        kwargs["password"] = settings.FALKORDB_PASSWORD
                    if settings.FALKORDB_USERNAME:
                        kwargs["username"] = settings.FALKORDB_USERNAME
                    if settings.FALKORDB_SSL:
                        kwargs["ssl"] = True
                    _db_client = falkordb.FalkorDB(**kwargs)
    return _db_client


def reset_client():
    """Reset the global client on connection drops."""
    global _db_client
    with _lock:
        _db_client = None


def get_graph(graph_name: str = None) -> falkordb.Graph:
    """Return a Graph object for the given graph name."""
    name = graph_name or settings.FALKORDB_GRAPH_NAME
    return get_client().select_graph(name)


async def init_db():
    """Create indexes and constraints on startup."""
    try:
        graph = get_graph()

        # Indexes for fast lookup — FalkorDB uses CREATE INDEX FOR
        index_queries = [
            "CREATE INDEX FOR (p:Person) ON (p.id)",
            "CREATE INDEX FOR (p:Person) ON (p.name)",
            "CREATE INDEX FOR (t:Team) ON (t.id)",
            "CREATE INDEX FOR (s:System) ON (s.id)",
            "CREATE INDEX FOR (s:System) ON (s.name)",
            "CREATE INDEX FOR (d:Document) ON (d.id)",
            "CREATE INDEX FOR (d:Document) ON (d.valid_from)",
            "CREATE INDEX FOR (d:Document) ON (d.valid_to)",
            "CREATE INDEX FOR (dc:Decision) ON (dc.id)",
            "CREATE INDEX FOR (dc:Decision) ON (dc.status)",
            "CREATE INDEX FOR (dc:Decision) ON (dc.valid_from)",
            "CREATE INDEX FOR (tk:Ticket) ON (tk.id)",
            "CREATE INDEX FOR (m:Message) ON (m.id)",
            "CREATE INDEX FOR (pr:Project) ON (pr.id)",
        ]

        for q in index_queries:
            try:
                graph.query(q)
            except Exception as e:
                # Index may already exist — that's fine
                if "already indexed" not in str(e).lower() and "equivalent index" not in str(e).lower():
                    print(f"  [warn] Index creation: {e}")

        print("✅ FalkorDB indexes initialized")
    except Exception as e:
        reset_client()
        print(f"⚠️ [warn] FalkorDB connection failed during startup: {e}. Running in degraded mode.")


def ping() -> bool:
    """Check if FalkorDB is reachable."""
    try:
        get_client().connection.ping()
        return True
    except Exception:
        return False
