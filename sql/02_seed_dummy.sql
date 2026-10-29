INSERT INTO wilayah (id, nama, level, is_published) VALUES
  (1, 'Jambi',        'provinsi', TRUE),
  (2, 'Batanghari',   'kabkota',  TRUE),
  (3, 'Muaro Jambi',  'kabkota',  TRUE),
  (4, 'Kota Jambi',   'kabkota',  TRUE)
ON CONFLICT (id) DO NOTHING;

INSERT INTO indikator (id, nama, sinonim, satuan, is_published) VALUES
  (12, 'Jumlah Penduduk',
       ARRAY['jml penduduk','penduduk','populasi'], 'jiwa', TRUE),
  (15, 'Indeks Pembangunan Manusia',
       ARRAY['lpp','ipm','indeks pembangunan'], 'indeks', TRUE),
  (31, 'Jumlah Penduduk Miskin',
       ARRAY['penduduk miskin','jumlah penduduk miskin','miskin'], 'jiwa', TRUE),
  (32, 'Persentase Penduduk Miskin',
       ARRAY['penduduk miskin','persentase penduduk miskin','miskin'], 'persen', TRUE),
  (99, 'Indikator Internal (tidak dipublikasikan)',
       ARRAY['internal'], 'unit', FALSE)
ON CONFLICT (id) DO NOTHING;

INSERT INTO data_indikator (indikator_id, wilayah_id, periode, periode_tipe, nilai, sumber, is_published) VALUES
  (12, 2, '2024', 'tahunan', 313200,  'BPS, Proyeksi Penduduk', TRUE),
  (12, 2, '2025', 'tahunan', 317000,  'BPS, Proyeksi Penduduk', FALSE),
  (12, 1, '2024', 'tahunan', 3500000, 'BPS, Proyeksi Penduduk', TRUE),
  (15, 2, '2024', 'tahunan', 71.5,    'BPS, IPM',               TRUE),
  (31, 2, '2024', 'tahunan', 25000,   'BPS, SUSENAS',           TRUE),
  (32, 2, '2024', 'tahunan', 7.8,     'BPS, SUSENAS',           TRUE),
  (99, 2, '2024', 'tahunan', 12345,   'Internal',               FALSE)
ON CONFLICT (indikator_id, wilayah_id, periode, periode_tipe) DO NOTHING;

SELECT setval(pg_get_serial_sequence('wilayah','id'),   (SELECT max(id) FROM wilayah));
SELECT setval(pg_get_serial_sequence('indikator','id'), (SELECT max(id) FROM indikator));