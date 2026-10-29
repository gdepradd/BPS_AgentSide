CREATE EXTENSION IF NOT EXISTS pg_trgm;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_ro') THEN
    CREATE ROLE agent_ro LOGIN PASSWORD 'GANTI_PASSWORD_RO';
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS wilayah (
  id            SERIAL PRIMARY KEY,
  nama          TEXT NOT NULL,
  level         TEXT NOT NULL CHECK (level IN ('provinsi','kabkota','kecamatan','desa')),
  kode_bps      TEXT,
  is_published  BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS indikator (
  id            SERIAL PRIMARY KEY,
  nama          TEXT NOT NULL,
  sinonim       TEXT[] NOT NULL DEFAULT '{}',
  satuan        TEXT,
  deskripsi     TEXT,
  is_published  BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS data_indikator (
  id              SERIAL PRIMARY KEY,
  indikator_id    INT  NOT NULL REFERENCES indikator(id),
  wilayah_id      INT  NOT NULL REFERENCES wilayah(id),
  periode         TEXT NOT NULL,
  periode_tipe    TEXT NOT NULL DEFAULT 'tahunan',
  nilai           NUMERIC NOT NULL,
  sumber          TEXT,
  catatan         TEXT,
  is_published    BOOLEAN NOT NULL DEFAULT TRUE,
  diperbarui_pada TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (indikator_id, wilayah_id, periode, periode_tipe)
);

CREATE TABLE IF NOT EXISTS pertanyaan_tak_terjawab (
  id         SERIAL PRIMARY KEY,
  pertanyaan TEXT NOT NULL,
  alasan     TEXT,
  ref        TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

GRANT USAGE ON SCHEMA public TO agent_ro;
GRANT SELECT ON wilayah, indikator, data_indikator TO agent_ro;
GRANT INSERT ON pertanyaan_tak_terjawab TO agent_ro;
GRANT USAGE, SELECT ON SEQUENCE pertanyaan_tak_terjawab_id_seq TO agent_ro;

REVOKE UPDATE, DELETE ON wilayah, indikator, data_indikator FROM agent_ro;
REVOKE UPDATE, DELETE ON pertanyaan_tak_terjawab FROM agent_ro;

CREATE INDEX IF NOT EXISTS idx_indikator_nama_trgm ON indikator USING gin (nama gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_wilayah_nama_trgm   ON wilayah  USING gin (nama gin_trgm_ops);