from ..db import get_conn


def cari_wilayah(kata_kunci: str, level: str | None = None, limit: int = 5) -> dict:
    if not kata_kunci or len(kata_kunci) > 200:
        return {"status": "error", "pesan": "kata_kunci wajib (maks 200 karakter)"}
    limit = max(1, min(int(limit), 20))

    sql = (
        "SELECT id, nama, level, similarity(nama, %s) AS skor "
        "FROM wilayah WHERE is_published = TRUE"
    )
    params: list = [kata_kunci]
    if level:
        sql += " AND level = %s"
        params.append(level)
    sql += " ORDER BY skor DESC LIMIT %s"
    params.append(limit)

    with get_conn() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    if not rows or rows[0]["skor"] < 0.3:
        return {"status": "tidak_ditemukan",
                "pesan": f"Wilayah tidak ditemukan untuk '{kata_kunci}'."}
    top = rows[0]
    return {"status": "ok",
            "data": {"id": top["id"], "nama": top["nama"],
                     "level": top["level"], "skor": round(top["skor"], 3)}}