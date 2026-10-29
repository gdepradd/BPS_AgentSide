from pathlib import Path
from dotenv import dotenv_values


def load_db_url() -> str:
    # cari .env di cwd dulu (wrapper tidak cd), lalu fallback ke project root
    candidates = [Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"]
    for path in candidates:
        if path.exists():
            values = dotenv_values(path)
            url = values.get("DB_AGENT_RO_URL")
            if url:
                return url
    raise RuntimeError("DB_AGENT_RO_URL tidak ditemukan di .env")