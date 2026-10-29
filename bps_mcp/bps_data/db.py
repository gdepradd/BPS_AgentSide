from contextlib import contextmanager
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

_pool: ConnectionPool | None = None


def init_pool(db_url: str) -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            db_url,
            min_size=1,
            max_size=3,
            kwargs={
                "row_factory": dict_row,
                "options": "-c statement_timeout=5000",
            },
            open=True,
        )
    return _pool


@contextmanager
def get_conn():
    if _pool is None:
        raise RuntimeError("Pool belum diinisialisasi")
    with _pool.connection() as conn:
        with conn.cursor() as cur:
            yield cur