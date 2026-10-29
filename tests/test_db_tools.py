import psycopg
import pytest


def test_agent_ro_cannot_insert_data(urls):
    with psycopg.connect(urls["ro"]) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO data_indikator "
                    "(indikator_id, wilayah_id, periode, nilai) "
                    "VALUES (12, 2, '2099', 1)"
                )


def test_agent_ro_cannot_delete_data(urls):
    with psycopg.connect(urls["ro"]) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.cursor() as cur:
                cur.execute("DELETE FROM data_indikator WHERE indikator_id = 12")


def test_agent_ro_can_insert_tak_terjawab(urls):
    with psycopg.connect(urls["ro"]) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pertanyaan_tak_terjawab (pertanyaan) "
                "VALUES ('unit test') RETURNING id"
            )
            new_id = cur.fetchone()[0]
        conn.commit()
    # cleanup lewat admin karena ro tidak boleh DELETE
    with psycopg.connect(urls["admin"]) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM pertanyaan_tak_terjawab WHERE id = %s", (new_id,))
        conn.commit()


def test_unpublished_data_filtered(urls):
    with psycopg.connect(urls["ro"]) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM data_indikator "
                "WHERE indikator_id = 12 AND periode = '2025' AND is_published = TRUE"
            )
            assert cur.fetchone()[0] == 0
            cur.execute(
                "SELECT count(*) FROM data_indikator "
                "WHERE indikator_id = 99 AND is_published = TRUE"
            )
            assert cur.fetchone()[0] == 0