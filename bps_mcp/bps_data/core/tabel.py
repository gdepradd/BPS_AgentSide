# bps_mcp/bps_data/core/tabel.py
import psycopg2
from psycopg2.extras import RealDictCursor

# Sesuaikan konfigurasi database dengan file .env Anda
DB_CONFIG = {
    "dbname": "nama_database_anda",
    "user": "user_anda",
    "password": "password_anda",
    "host": "localhost",
    "port": "5432"
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

def cari_data_tabel(kata_kunci: str, limit: int = 5) -> dict:
    """
    Mencari dataset tabel statistik berdasarkan kata kunci nama atau deskripsi.
    Mengembalikan metadata dan preview data tabel baris & kolom.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT id, nama, deskripsi, jumlah_baris, jumlah_kolom, isi_data 
            FROM data_tabel 
            WHERE is_published = TRUE 
            AND (nama ILIKE %s OR deskripsi ILIKE %s)
            LIMIT %s;
        """
        search_pattern = f"%{kata_kunci}%"
        cur.execute(query, (search_pattern, search_pattern, limit))
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        
        if not results:
            return {"status": "success", "message": f"Tidak ada data tabel yang cocok dengan kata kunci '{kata_kunci}'."}
            
        return {
            "status": "success",
            "jumlah_ditemukan": len(results),
            "data": results
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
def ambil_link_gdrive(nama_tabel: str, nama_pemohon: str = None, keperluan: str = None) -> dict:
    """
    Mengambil link GDrive berdasarkan nama tabel, HANYA JIKA nama_pemohon dan keperluan sudah diisi.
    """
    if not nama_pemohon or not keperluan:
        return {
            "status": "butuh_info",
            "message": "Mohon maaf, untuk pendataan layanan BPS, boleh sebutkan nama lengkap dan keperluan Anda menggunakan data tersebut?"
        }
        
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Asumsi tabel data_tabel memiliki kolom link_gdrive
        query = """
            SELECT nama, link_gdrive 
            FROM data_tabel 
            WHERE nama ILIKE %s AND is_published = TRUE
            LIMIT 1;
        """
        search_pattern = f"%{nama_tabel}%"
        cur.execute(query, (search_pattern,))
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if result and result['link_gdrive']:
            return {
                "status": "success",
                "nama_tabel": result['nama'],
                "link_gdrive": result['link_gdrive'],
                "pesan_agent": f"Halo {nama_pemohon}, berikut adalah link Google Drive untuk data {result['nama']} sesuai keperluan Anda: {keperluan}."
            }
        else:
            return {"status": "not_found", "message": f"Data tabel '{nama_tabel}' belum tersedia link GDrive-nya."}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}