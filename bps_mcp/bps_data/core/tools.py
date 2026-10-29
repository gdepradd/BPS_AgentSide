import logging
from typing import Optional
from ..db import pool

logger = logging.getLogger(__name__)

def cari_indikator(kata_kunci: str, limit: int = 5) -> dict:
    """Mencari indikator statistik BPS berdasarkan nama atau sinonim. Gunakan saat pengguna menanyakan topik data tertentu."""
    if not isinstance(kata_kunci, str) or not (2 <= len(kata_kunci.strip()) <= 100):
        return {"status": "error", "pesan": "Parameter kata_kunci harus berupa teks (2-100 karakter)."}
    if not isinstance(limit, int) or not (1 <= limit <= 20):
        return {"status": "error", "pesan": "Parameter limit harus berupa angka bulat antara 1 hingga 20."}

    kata = kata_kunci.strip().lower()
    try:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT id, nama, satuan, sinonim,
                       GREATEST(
                           similarity(lower(nama), %s),
                           COALESCE((SELECT MAX(similarity(lower(s), %s)) FROM unnest(sinonim) AS s), 0)
                       ) AS skor
                FROM indikator
                WHERE is_published = TRUE
                ORDER BY skor DESC, id ASC
                LIMIT %s
            """, (kata, kata, limit))
            rows = cur.fetchall()

            if not rows or float(rows[0]["skor"]) < 0.3:
                return {"status": "tidak_ditemukan", "pesan": f"Indikator '{kata_kunci}' tidak ditemukan."}

            peak = float(rows[0]["skor"])
            kandidat = [
                {"id": r["id"], "nama": r["nama"], "satuan": r["satuan"], "skor": round(float(r["skor"]), 3)}
                for r in rows if float(r["skor"]) >= 0.3
            ]

            if len(kandidat) > 1 and kandidat[1]["skor"] >= round(peak - 0.1, 3):
                return {
                    "status": "ambigu",
                    "pesan": "Ditemukan beberapa indikator yang mirip. Silakan pilih salah satu.",
                    "kandidat": [k for k in kandidat if k["skor"] >= round(peak - 0.1, 3)]
                }

            return {"status": "ok", "data": kandidat[0], "kandidat": kandidat}
    except Exception as e:
        logger.error(f"Error cari_indikator: {e}")
        return {"status": "error", "pesan": "Terjadi kesalahan saat mencari indikator."}


def cari_wilayah(kata_kunci: str, level: Optional[str] = None, limit: int = 5) -> dict:
    """Mencari kode dan nama wilayah administratif (provinsi/kabupaten/kecamatan). Gunakan untuk memetakan nama daerah ke wilayah_id."""
    if not isinstance(kata_kunci, str) or not (2 <= len(kata_kunci.strip()) <= 100):
        return {"status": "error", "pesan": "Parameter kata_kunci harus berupa teks (2-100 karakter)."}
    if not isinstance(limit, int) or not (1 <= limit <= 20):
        return {"status": "error", "pesan": "Parameter limit harus antara 1 hingga 20."}

    kata = kata_kunci.strip().lower()
    kata_norm = kata.replace(" ", "")
    try:
        with pool.connection() as conn, conn.cursor() as cur:
            if level:
                cur.execute("""
                    SELECT id, nama, level,
                           GREATEST(similarity(lower(nama), %s), similarity(replace(lower(nama), ' ', ''), %s)) AS skor
                    FROM wilayah
                    WHERE lower(level) = lower(%s)
                    ORDER BY skor DESC, id ASC
                    LIMIT %s
                """, (kata, kata_norm, level.strip(), limit))
            else:
                cur.execute("""
                    SELECT id, nama, level,
                           GREATEST(similarity(lower(nama), %s), similarity(replace(lower(nama), ' ', ''), %s)) AS skor
                    FROM wilayah
                    ORDER BY skor DESC, id ASC
                    LIMIT %s
                """, (kata, kata_norm, limit))
            rows = cur.fetchall()

            if not rows or float(rows[0]["skor"]) < 0.3:
                return {"status": "tidak_ditemukan", "pesan": f"Wilayah '{kata_kunci}' tidak ditemukan."}

            hasil = [{"id": r["id"], "nama": r["nama"], "level": r["level"], "skor": round(float(r["skor"]), 3)} for r in rows if float(r["skor"]) >= 0.3]
            return {"status": "ok", "data": hasil[0], "kandidat": hasil}
    except Exception as e:
        logger.error(f"Error cari_wilayah: {e}")
        return {"status": "error", "pesan": "Terjadi kesalahan saat mencari wilayah."}


def daftar_periode_tersedia(indikator_id: int, wilayah_id: Optional[int] = None) -> dict:
    """Melihat daftar tahun/periode data yang sudah dipublikasikan untuk suatu indikator dan wilayah."""
    if not isinstance(indikator_id, int) or indikator_id <= 0:
        return {"status": "error", "pesan": "indikator_id harus berupa angka positif."}
    if wilayah_id is not None and (not isinstance(wilayah_id, int) or wilayah_id <= 0):
        return {"status": "error", "pesan": "wilayah_id harus berupa angka positif."}

    try:
        with pool.connection() as conn, conn.cursor() as cur:
            if wilayah_id is not None:
                cur.execute("""
                    SELECT DISTINCT d.periode
                    FROM data_indikator d
                    JOIN indikator i ON i.id = d.indikator_id
                    WHERE d.indikator_id = %s AND d.wilayah_id = %s
                      AND d.is_published = TRUE AND i.is_published = TRUE
                    ORDER BY d.periode ASC
                """, (indikator_id, wilayah_id))
            else:
                cur.execute("""
                    SELECT DISTINCT d.periode
                    FROM data_indikator d
                    JOIN indikator i ON i.id = d.indikator_id
                    WHERE d.indikator_id = %s
                      AND d.is_published = TRUE AND i.is_published = TRUE
                    ORDER BY d.periode ASC
                """, (indikator_id,))
            rows = cur.fetchall()
            periode_list = [r["periode"] for r in rows]
            if not periode_list:
                return {"status": "tidak_ditemukan", "pesan": "Tidak ada periode tersedia.", "periode_tersedia": []}
            return {"status": "ok", "periode_tersedia": periode_list, "periode_terakhir": periode_list[-1]}
    except Exception as e:
        logger.error(f"Error daftar_periode_tersedia: {e}")
        return {"status": "error", "pesan": "Terjadi kesalahan saat mengambil daftar periode."}


def ambil_data(indikator_id: int, wilayah_id: int, periode: str, periode_tipe: str = "tahunan") -> dict:
    """Mengambil nilai angka statistik untuk indikator, wilayah, dan periode tertentu yang telah dipublikasikan."""
    if not isinstance(indikator_id, int) or indikator_id <= 0:
        return {"status": "error", "pesan": "indikator_id tidak valid."}
    if not isinstance(wilayah_id, int) or wilayah_id <= 0:
        return {"status": "error", "pesan": "wilayah_id tidak valid."}
    if not isinstance(periode, str) or not (1 <= len(periode.strip()) <= 20):
        return {"status": "error", "pesan": "periode tidak boleh kosong."}

    periode_clean = periode.strip()
    try:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT i.nama AS indikator, w.nama AS wilayah, d.periode, d.nilai,
                       i.satuan, i.sumber, i.catatan, d.diperbarui_pada
                FROM data_indikator d
                JOIN indikator i ON i.id = d.indikator_id
                JOIN wilayah w ON w.id = d.wilayah_id
                WHERE d.indikator_id = %s AND d.wilayah_id = %s
                  AND d.periode = %s AND d.periode_tipe = %s
                  AND d.is_published = TRUE AND i.is_published = TRUE
            """, (indikator_id, wilayah_id, periode_clean, periode_tipe))
            row = cur.fetchone()

            if row:
                nilai_num = float(row["nilai"]) if row["nilai"] is not None else None
                if nilai_num is not None and nilai_num.is_integer():
                    nilai_num = int(nilai_num)
                return {
                    "status": "ok",
                    "indikator": row["indikator"],
                    "wilayah": row["wilayah"],
                    "periode": row["periode"],
                    "nilai": nilai_num,
                    "satuan": row["satuan"],
                    "sumber": row["sumber"],
                    "catatan": row["catatan"],
                    "diperbarui_pada": row["diperbarui_pada"].isoformat() if row["diperbarui_pada"] else None
                }

            # Cek apakah indikatornya memang ada dan dipublikasikan, lalu cari periode yang tersedia
            cur.execute("""
                SELECT d.periode
                FROM data_indikator d
                JOIN indikator i ON i.id = d.indikator_id
                WHERE d.indikator_id = %s AND d.wilayah_id = %s
                  AND d.is_published = TRUE AND i.is_published = TRUE
                ORDER BY d.periode ASC
            """, (indikator_id, wilayah_id))
            avail = [r["periode"] for r in cur.fetchall()]

            if avail:
                terakhir = avail[-1]
                return {
                    "status": "tidak_tersedia",
                    "pesan": f"Periode {periode_clean} belum tersedia. Periode terakhir: {terakhir}.",
                    "saran": {"periode_terakhir": terakhir, "periode_tersedia": avail}
                }

            return {"status": "tidak_ditemukan", "pesan": "Data atau indikator tidak ditemukan."}
    except Exception as e:
        logger.error(f"Error ambil_data: {e}")
        return {"status": "error", "pesan": "Terjadi kesalahan saat mengambil data."}


def catat_tak_terjawab(pertanyaan: str, alasan: Optional[str] = None, ref: Optional[str] = None) -> dict:
    """Mencatat pertanyaan pengguna yang tidak dapat dijawab karena data tidak tersedia atau di luar cakupan."""
    if not isinstance(pertanyaan, str) or not (3 <= len(pertanyaan.strip()) <= 500):
        return {"status": "error", "pesan": "Pertanyaan harus berupa teks (3-500 karakter)."}

    try:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO log_tak_terjawab (pertanyaan, alasan, ref)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (pertanyaan.strip(), alasan, ref))
            row = cur.fetchone()
            conn.commit()
            return {"status": "ok", "id": row["id"], "pesan": "Pertanyaan berhasil dicatat."}
    except Exception as e:
        logger.error(f"Error catat_tak_terjawab: {e}")
        return {"status": "error", "pesan": "Gagal mencatat pertanyaan."}