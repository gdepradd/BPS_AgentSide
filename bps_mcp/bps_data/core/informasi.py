import re
from ..db import get_conn


def _clean_html(raw_html: str) -> str:
    """Bersihkan tag HTML seperti <p>, </p>, <br> dari teks."""
    if not raw_html:
        return ""
    clean = re.sub(r"<[^>]+>", " ", raw_html)
    return " ".join(clean.split())


def _extract_keywords(text: str) -> list[str]:
    """Ekstrak kata kunci penting dari teks pertanyaan."""
    stopwords = {
        "ada", "apa", "dan", "di", "ini", "itu", "ke", "dari", "pada", "yang",
        "untuk", "dengan", "saya", "mau", "nanya", "hari", "kemarin", "depan",
        "kantor", "bps", "kabupaten", "batanghari", "apakah", "bisa", "tolong",
        "seputar", "tentang"
    }
    words = re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower())
    return [w for w in words if len(w) >= 2 and w not in stopwords]


def cari_informasi(kata_kunci: str) -> dict:
    if not kata_kunci or len(kata_kunci) > 200:
        return {"status": "error", "pesan": "kata_kunci tidak valid"}

    try:
        with get_conn() as cur:
            # 1. Coba pencarian langsung (substring)
            sql = """
                SELECT judul, konten 
                FROM data_informasi 
                WHERE is_published = TRUE 
                  AND (judul ILIKE %s OR konten ILIKE %s)
                LIMIT 3
            """
            search_term = f"%{kata_kunci}%"
            cur.execute(sql, (search_term, search_term))
            rows = cur.fetchall()

            # 2. Jika tidak ditemukan, coba cari dengan kata kunci pecahan
            if not rows:
                tokens = _extract_keywords(kata_kunci)
                if tokens:
                    conditions = []
                    params = []
                    for t in tokens:
                        pattern = f"%{t}%"
                        conditions.append("(judul ILIKE %s OR konten ILIKE %s)")
                        params.extend([pattern, pattern])
                    where_clause = " OR ".join(conditions)
                    fallback_sql = f"""
                        SELECT judul, konten 
                        FROM data_informasi 
                        WHERE is_published = TRUE 
                          AND ({where_clause})
                        LIMIT 3
                    """
                    cur.execute(fallback_sql, tuple(params))
                    rows = cur.fetchall()

            if not rows:
                return {"status": "tidak_ditemukan", "pesan": "Informasi tidak ditemukan."}

            return {
                "status": "ok",
                "data": [
                    {
                        "judul": r["judul"],
                        "konten": _clean_html(r["konten"])
                    }
                    for r in rows
                ]
            }
    except Exception as e:
        return {"status": "error", "pesan": str(e)}
