from ..db import get_conn

AMBANG_MIN = 0.3
AMBANG_AMBIGU = 0.05


def cari_indikator(kata_kunci: str, limit: int = 5) -> dict:
    if not kata_kunci or len(kata_kunci) > 200:
        return {"status": "error", "pesan": "kata_kunci wajib (maks 200 karakter)"}
    limit = max(1, min(int(limit), 20))

    sql = """
        SELECT i.id, i.nama, i.sinonim, i.satuan,
               GREATEST(
                 similarity(i.nama, %s),
                 COALESCE((SELECT MAX(similarity(s, %s)) FROM unnest(i.sinonim) s), 0)
               ) AS skor
        FROM indikator i
        WHERE i.is_published = TRUE
        ORDER BY skor DESC
        LIMIT %s
    """
    with get_conn() as cur:
        cur.execute(sql, (kata_kunci, kata_kunci, limit))
        rows = cur.fetchall()

    if not rows or rows[0]["skor"] < AMBANG_MIN:
        return {
            "status": "tidak_ditemukan",
            "pesan": f"Indikator tidak ditemukan untuk '{kata_kunci}'.",
        }

    peak = rows[0]["skor"]
    if len(rows) >= 2 and rows[1]["skor"] >= peak - AMBANG_AMBIGU:
        kandidat = [
            {"id": r["id"], "nama": r["nama"], "satuan": r["satuan"],
             "skor": round(r["skor"], 3)}
            for r in rows if r["skor"] >= peak - AMBANG_AMBIGU
        ]
        return {
            "status": "ambigu",
            "pesan": "Ada beberapa indikator yang cocok. Pilih salah satu.",
            "kandidat": kandidat,
        }

    top = rows[0]
    return {
        "status": "ok",
        "data": {"id": top["id"], "nama": top["nama"],
                 "satuan": top["satuan"], "skor": round(top["skor"], 3)},
    }