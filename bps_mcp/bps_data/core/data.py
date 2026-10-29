from ..db import get_conn


def _valid_periode(p) -> bool:
    return isinstance(p, str) and p.strip() != "" and len(p) <= 20


def daftar_periode_tersedia(indikator_id: int, wilayah_id: int | None = None) -> dict:
    if not isinstance(indikator_id, int) or indikator_id <= 0:
        return {"status": "error", "pesan": "indikator_id tidak valid"}
    sql = (
        "SELECT DISTINCT d.periode FROM data_indikator d "
        "JOIN indikator i ON i.id = d.indikator_id "
        "WHERE d.indikator_id = %s AND d.is_published = TRUE AND i.is_published = TRUE"
    )
    params: list = [indikator_id]
    if wilayah_id is not None:
        if not isinstance(wilayah_id, int) or wilayah_id <= 0:
            return {"status": "error", "pesan": "wilayah_id tidak valid"}
        sql += " AND d.wilayah_id = %s"
        params.append(wilayah_id)
    sql += " ORDER BY d.periode DESC"

    with get_conn() as cur:
        cur.execute(sql, params)
        periods = [r["periode"] for r in cur.fetchall()]
    return {"status": "ok",
            "data": {"indikator_id": indikator_id, "periode": periods}}


def ambil_data(indikator_id: int, wilayah_id: int, periode: str,
               periode_tipe: str = "tahunan") -> dict:
    if not isinstance(indikator_id, int) or indikator_id <= 0:
        return {"status": "error", "pesan": "indikator_id tidak valid"}
    if not isinstance(wilayah_id, int) or wilayah_id <= 0:
        return {"status": "error", "pesan": "wilayah_id tidak valid"}
    if not _valid_periode(periode):
        return {"status": "error", "pesan": "periode tidak valid"}

    sql = """
        SELECT d.nilai, i.satuan, d.sumber, d.catatan, d.diperbarui_pada,
               i.nama AS indikator, w.nama AS wilayah, d.periode
        FROM data_indikator d
        JOIN indikator i ON i.id = d.indikator_id
        JOIN wilayah  w ON w.id = d.wilayah_id
        WHERE d.indikator_id = %s AND d.wilayah_id = %s
          AND d.periode = %s AND d.periode_tipe = %s
          AND d.is_published = TRUE
          AND i.is_published = TRUE
          AND w.is_published = TRUE
    """
    with get_conn() as cur:
        cur.execute(sql, (indikator_id, wilayah_id, periode, periode_tipe))
        row = cur.fetchone()
        if row:
            return {"status": "ok", "data": row}

        cur.execute(
            "SELECT DISTINCT periode FROM data_indikator "
            "WHERE indikator_id = %s AND wilayah_id = %s AND is_published = TRUE "
            "ORDER BY periode DESC",
            (indikator_id, wilayah_id),
        )
        periods = [r["periode"] for r in cur.fetchall()]

    if periods:
        return {
            "status": "tidak_tersedia",
            "pesan": f"Periode {periode} belum tersedia. Periode terakhir: {periods[0]}.",
            "saran": {"periode_terakhir": periods[0],
                      "periode_tersedia": periods[:5]},
        }
    return {"status": "tidak_tersedia",
            "pesan": "Data tidak tersedia untuk kombinasi ini."}