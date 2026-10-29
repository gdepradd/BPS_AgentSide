from ..db import get_conn

def alihkan_ke_petugas(pertanyaan: str, ref: str) -> dict:
    """Mencatat bahwa percakapan dialihkan ke petugas manusia."""
    if not pertanyaan or not ref:
        return {"status": "error", "pesan": "pertanyaan dan ref wajib diisi"}
        
    with get_conn() as cur:
        # Catat sebagai pertanyaan tak terjawab dengan alasan "dialihkan ke petugas"
        cur.execute(
            "INSERT INTO pertanyaan_tak_terjawab (pertanyaan, alasan, ref) "
            "VALUES (%s, 'dialihkan_ke_petugas', %s) RETURNING id",
            (pertanyaan, ref),
        )
        new_id = cur.fetchone()["id"]
        
    return {
        "status": "ok", 
        "pesan": "Pertanyaan berhasil dialihkan ke petugas. Beritahu pengguna untuk menunggu.",
        "data": {"id": new_id}
    }