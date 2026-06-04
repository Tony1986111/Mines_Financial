"""Run once to create the checkpointer tables in PostgreSQL.

Usage:
    uv run python db/checkpointer.py
"""
import os
from dotenv import load_dotenv
from langgraph.checkpoint.postgres import PostgresSaver

load_dotenv()

if __name__ == "__main__":
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    with PostgresSaver.from_conn_string(database_url) as checkpointer:
        checkpointer.setup()

    print("Checkpointer tables created.")
