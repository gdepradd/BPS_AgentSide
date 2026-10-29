from ..db import get_conn


def catat_tak_terjawab(pertanyaan: str, alasan: str | None = None, ref: str | None = None) -> dict:
    if not pertanyaan or len(pertanyaan) > 2000:
        return {"status": "error", "pesan": "pertanyaan wajib (maks 2000 karakter)"}

    with get_conn() as cur:
        cur.execute(
            "INSERT INTO pertanyaan_tak_terjawab (pertanyaan, alasan, ref) "
            "VALUES (%s, %s, %s) RETURNING id",
            (pertanyaan, alasan, ref or "unknown"),
        )
        new_id = cur.fetchone()["id"]
    return {"status": "ok", "data": {"id": new_id}}
