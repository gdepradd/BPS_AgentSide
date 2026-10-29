from ..db import get_conn

def cari_informasi(kata_kunci: str) -> dict:
    if not kata_kunci or len(kata_kunci) > 200:
        return {"status": "error", "pesan": "kata_kunci tidak valid"}
        
    sql = """
        SELECT judul, konten 
        FROM data_informasi 
        WHERE is_published = TRUE 
          AND (judul ILIKE %s OR konten ILIKE %s)
        LIMIT 3
    """
    search_term = f"%{kata_kunci}%"
    
    with get_conn() as cur:
        cur.execute(sql, (search_term, search_term))
        rows = cur.fetchall()

    if not rows:
        return {"status": "tidak_ditemukan", "pesan": "Informasi tidak ditemukan."}

    return {
        "status": "ok", 
        "data": [{"judul": r["judul"], "konten": r["konten"]} for r in rows]
    }