import re
from ..db import get_conn


def _extract_keywords(text: str) -> list[str]:
    """Ekstrak kata kunci penting dari teks, mengabaikan kata penghubung/stopwords."""
    stopwords = {
        "ada", "apa", "dan", "di", "ini", "itu", "ke", "dari", "pada", "yang",
        "untuk", "dengan", "saya", "mau", "minta", "tolong", "bisa", "boleh",
        "hari", "kemarin", "depan", "data", "tabel", "file", "link", "gdrive",
        "mohon", "kasih", "terima", "terkait", "tentang", "adakah", "ingin"
    }
    words = re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower())
    return [w for w in words if len(w) >= 2 and w not in stopwords]


def cari_data_tabel(kata_kunci: str, limit: int = 5) -> dict:
    """
    Mencari dataset tabel statistik berdasarkan kata kunci nama atau deskripsi.
    Mengembalikan metadata dan preview data tabel baris & kolom.
    """
    if not kata_kunci:
        return {"status": "error", "message": "Kata kunci tidak boleh kosong."}

    try:
        with get_conn() as cur:
            # 1. Coba pencarian langsung (substring)
            search_pattern = f"%{kata_kunci}%"
            query = """
                SELECT id, nama, deskripsi, jumlah_baris, jumlah_kolom, isi_data 
                FROM data_tabel 
                WHERE is_published = TRUE 
                AND (nama ILIKE %s OR deskripsi ILIKE %s)
                LIMIT %s;
            """
            cur.execute(query, (search_pattern, search_pattern, limit))
            results = cur.fetchall()

            # 2. Jika tidak ada hasil langsung, coba cari berdasarkan kata kunci penting
            if not results:
                tokens = _extract_keywords(kata_kunci)
                if tokens:
                    conditions = []
                    params = []
                    for t in tokens:
                        pattern = f"%{t}%"
                        conditions.append("(nama ILIKE %s OR deskripsi ILIKE %s)")
                        params.extend([pattern, pattern])
                    where_clause = " OR ".join(conditions)
                    fallback_query = f"""
                        SELECT id, nama, deskripsi, jumlah_baris, jumlah_kolom, isi_data 
                        FROM data_tabel 
                        WHERE is_published = TRUE 
                        AND ({where_clause})
                        LIMIT %s;
                    """
                    params.append(limit)
                    cur.execute(fallback_query, tuple(params))
                    results = cur.fetchall()

            if not results:
                return {
                    "status": "success",
                    "jumlah_ditemukan": 0,
                    "message": f"Tidak ada data tabel yang cocok dengan kata kunci '{kata_kunci}'."
                }

            return {
                "status": "success",
                "jumlah_ditemukan": len(results),
                "data": results
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def ambil_link_gdrive(nama_tabel: str, nama_pemohon: str = None, keperluan: str = None) -> dict:
    """
    Mengambil link GDrive berdasarkan nama tabel atau deskripsi data, HANYA JIKA nama_pemohon dan keperluan sudah diisi.
    """
    if not nama_pemohon or not keperluan:
        return {
            "status": "butuh_info",
            "message": "Mohon maaf, untuk pendataan layanan BPS, boleh sebutkan nama lengkap dan keperluan Anda menggunakan data tersebut?"
        }

    try:
        with get_conn() as cur:
            # 1. Coba pencarian langsung
            search_pattern = f"%{nama_tabel}%"
            query = """
                SELECT id, nama, deskripsi, link_gdrive 
                FROM data_tabel 
                WHERE is_published = TRUE 
                AND (nama ILIKE %s OR deskripsi ILIKE %s)
                LIMIT 1;
            """
            cur.execute(query, (search_pattern, search_pattern))
            result = cur.fetchone()

            # 2. Jika tidak ditemukan langsung, cari dengan kata kunci pecahan
            if not result:
                tokens = _extract_keywords(nama_tabel)
                if tokens:
                    conditions = []
                    params = []
                    for t in tokens:
                        pattern = f"%{t}%"
                        conditions.append("(nama ILIKE %s OR deskripsi ILIKE %s)")
                        params.extend([pattern, pattern])
                    where_clause = " OR ".join(conditions)
                    fallback_query = f"""
                        SELECT id, nama, deskripsi, link_gdrive 
                        FROM data_tabel 
                        WHERE is_published = TRUE 
                        AND ({where_clause})
                        LIMIT 1;
                    """
                    cur.execute(fallback_query, tuple(params))
                    result = cur.fetchone()

            if result and result.get("link_gdrive"):
                # Catat ke tabel permintaan_data untuk rekapitulasi dasbor
                try:
                    cur.execute(
                        """
                        INSERT INTO permintaan_data (data_tabel_id, nama_data, nama_pemohon, keperluan, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, NOW(), NOW())
                        """,
                        (result["id"], result["nama"], nama_pemohon, keperluan),
                    )
                except Exception as log_err:
                    print(f"Catatan: Gagal mencatat permintaan_data: {log_err}")

                return {
                    "status": "success",
                    "nama_tabel": result["nama"],
                    "link_gdrive": result["link_gdrive"],
                    "pesan_agent": f"Halo {nama_pemohon}, berikut adalah link Google Drive untuk data {result['nama']} sesuai keperluan Anda ({keperluan}): {result['link_gdrive']}"
                }
            elif result:
                return {
                    "status": "not_found",
                    "message": f"Data tabel '{result['nama']}' belum tersedia link Google Drive-nya."
                }
            else:
                return {
                    "status": "not_found",
                    "message": f"Data tabel terkait '{nama_tabel}' tidak ditemukan di sistem."
                }

    except Exception as e:
        return {"status": "error", "message": str(e)}
