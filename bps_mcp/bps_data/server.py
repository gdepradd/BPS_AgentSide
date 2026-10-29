import logging
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastmcp import FastMCP

from bps_mcp.bps_data.config import load_db_url
from bps_mcp.bps_data import db
from bps_mcp.bps_data.core import indikator as core_ind
from bps_mcp.bps_data.core import wilayah   as core_wil
from bps_mcp.bps_data.core import data      as core_data
from bps_mcp.bps_data.core import tak_terjawab as core_tt
from bps_mcp.bps_data.core import alihkan as core_alihkan
from bps_mcp.bps_data.core import informasi as core_info

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger("bps_data")

db.init_pool(load_db_url())
mcp = FastMCP("bps_data")
# Tambahkan ini di bagian import

@mcp.tool()
def cari_informasi(kata_kunci: str) -> dict:
    """Gunakan tool ini jika pengguna menanyakan informasi umum BPS (alamat, jam operasional, profil). Bukan untuk data angka."""
    return core_info.cari_informasi(kata_kunci)
# Tambahkan ini di bagian tool
@mcp.tool()
def alihkan_ke_petugas(pertanyaan: str, ref: str) -> dict:
    """Gunakan tool ini jika pengguna meminta bantuan manusia, atau pertanyaannya terlalu rumit. ref adalah nomor WhatsApp pengguna."""
    return core_alihkan.alihkan_ke_petugas(pertanyaan, ref)

@mcp.tool()
def cari_indikator(kata_kunci: str, limit: int = 5) -> dict:
    """Cari indikator BPS berdasarkan nama atau sinonim. Panggil ini lebih dulu untuk mendapatkan indikator_id."""
    return core_ind.cari_indikator(kata_kunci, limit)


@mcp.tool()
def cari_wilayah(kata_kunci: str, level: str | None = None, limit: int = 5) -> dict:
    """Cari wilayah (provinsi/kabkota/kecamatan/desa) berdasarkan nama. Panggil untuk mendapatkan wilayah_id."""
    return core_wil.cari_wilayah(kata_kunci, level, limit)


@mcp.tool()
def daftar_periode_tersedia(indikator_id: int, wilayah_id: int | None = None) -> dict:
    """Daftar periode yang tersedia untuk indikator (dan wilayah opsional). Pakai jika periode belum pasti."""
    return core_data.daftar_periode_tersedia(indikator_id, wilayah_id)


@mcp.tool()
def ambil_data(indikator_id: int, wilayah_id: int, periode: str,
               periode_tipe: str = "tahunan") -> dict:
    """Ambil satu nilai statistik: nilai, satuan, periode, dan sumber. Jangan menebak jika tidak tersedia."""
    return core_data.ambil_data(indikator_id, wilayah_id, periode, periode_tipe)


@mcp.tool()
def catat_tak_terjawab(pertanyaan: str, alasan: str | None = None,
                       ref: str | None = None) -> dict:
    """Catat pertanyaan yang tidak dapat dijawab karena data tidak dipublikasikan atau tidak ditemukan."""
    return core_tt.catat_tak_terjawab(pertanyaan, alasan, ref)


if __name__ == "__main__":
    mcp.run()