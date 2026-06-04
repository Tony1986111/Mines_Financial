from __future__ import annotations

import json
import os

from psycopg import Connection as PgConnection
from psycopg.rows import dict_row as pg_dict_row


def _db_url() -> str:
    return os.getenv("DATABASE_URL", "")


def setup_progress_table() -> None:
    with PgConnection.connect(_db_url(), autocommit=True, prepare_threshold=0) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS graph_progress (
                    thread_id   TEXT    NOT NULL,
                    turn_index  INTEGER NOT NULL,
                    cards       JSONB   NOT NULL,
                    created_at  TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (thread_id, turn_index)
                )
            """)


def save_progress(thread_id: str, turn_index: int, cards: list) -> None:
    with PgConnection.connect(_db_url(), autocommit=True, prepare_threshold=0) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO graph_progress (thread_id, turn_index, cards)
                VALUES (%s, %s, %s)
                ON CONFLICT (thread_id, turn_index)
                DO UPDATE SET cards = EXCLUDED.cards
                """,
                (thread_id, turn_index, json.dumps(cards)),
            )


def get_progress(thread_id: str) -> list[dict]:
    with PgConnection.connect(
        _db_url(), autocommit=True, prepare_threshold=0, row_factory=pg_dict_row
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT turn_index, cards FROM graph_progress
                WHERE thread_id = %s
                ORDER BY turn_index
                """,
                (thread_id,),
            )
            return [{"turn_index": row["turn_index"], "cards": row["cards"]} for row in cur.fetchall()]


def delete_progress(thread_id: str) -> None:
    with PgConnection.connect(_db_url(), autocommit=True, prepare_threshold=0) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM graph_progress WHERE thread_id = %s", (thread_id,))
