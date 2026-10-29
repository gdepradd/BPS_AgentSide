import psycopg
import pytest
from bps_mcp.bps_data import db
from bps_mcp.bps_data.config import load_db_url
from bps_mcp.bps_data.core import indikator, wilayah, data, tak_terjawab


@pytest.fixture(scope="session", autouse=True)
def _pool():
    url = load_db_url().replace("/bps_agent", "/bps_agent_test")
    db._pool = None
    db.init_pool(url)
    yield
    if db._pool:
        db._pool.close()


@pytest.mark.parametrize("kata,expected_id", [
    ("jml penduduk", 12),
    ("pendudk", 12),          # typo tetap cocok via trigram
    ("lpp", 15),
])
def test_cari_indikator_ok(kata, expected_id):
    r = indikator.cari_indikator(kata)
    assert r["status"] == "ok" and r["data"]["id"] == expected_id


def test_cari_indikator_ambigu():
    r = indikator.cari_indikator("penduduk miskin")
    assert r["status"] == "ambigu"
    assert {k["id"] for k in r["kandidat"]} >= {31, 32}


def test_cari_indikator_ngawur():
    assert indikator.cari_indikator("xyzxyz ngawur")["status"] == "tidak_ditemukan"


def test_cari_indikator_hidden():
    # 99 tidak boleh muncul sebagai kandidat
    r = indikator.cari_indikator("internal")
    assert all(k["id"] != 99 for k in r.get("kandidat", []))
    if r["status"] == "ok":
        assert r["data"]["id"] != 99


def test_cari_wilayah_batanghari():
    r = wilayah.cari_wilayah("batanghari")
    assert r["status"] == "ok" and r["data"]["id"] == 2


def test_ambil_data_ok():
    r = data.ambil_data(12, 2, "2024")
    assert r["status"] == "ok"
    assert int(r["data"]["nilai"]) == 313200
    assert "Proyeksi Penduduk" in r["data"]["sumber"]


def test_ambil_data_unpublished_period():
    r = data.ambil_data(12, 2, "2025")
    assert r["status"] == "tidak_tersedia"
    assert r["saran"]["periode_terakhir"] == "2024"


def test_ambil_data_hidden():
    r = data.ambil_data(99, 2, "2024")
    assert r["status"] == "tidak_tersedia"


def test_daftar_periode_tanpa_2025():
    r = data.daftar_periode_tersedia(12, 2)
    assert "2025" not in r["data"]["periode"]


def test_param_invalid():
    assert data.ambil_data(-1, 2, "2024")["status"] == "error"
    assert data.ambil_data(12, 2, "")["status"] == "error"


def test_sql_injection():
    r = indikator.cari_indikator("'; drop table data_indikator; --")
    # harus tetap jalan tanpa error, status tidak_ditemukan
    assert r["status"] in ("tidak_ditemukan", "ambigu", "ok")


def test_catat_tak_terjawab(urls=None):
    r = tak_terjawab.catat_tak_terjawab("test tools", alasan="unit")
    assert r["status"] == "ok" and r["data"]["id"] > 0