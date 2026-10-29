from ..db import get_conn


def catat_tak_terjawab(pertanyaan: str, alasan: str, ref: str) -> dict:
    if not pertanyaan or len(pertanyaan) > 2000:
        return {"status": "error", "pesan": "pertanyaan wajib (maks 2000 karakter)"}
    if not ref:
        return {"status": "error", "pesan": "ref (nomor WA) wajib diisi"}
        
    with get_conn() as cur:
        cur.execute(
            "INSERT INTO pertanyaan_tak_terjawab (pertanyaan, alasan, ref) "
            "VALUES (%s, %s, %s) RETURNING id",
            (pertanyaan, alasan, ref),
        )
        new_id = cur.fetchone()["id"]
    return {"status": "ok", "data": {"id": new_id}}