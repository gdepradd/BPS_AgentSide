# 📋 TASK.md — Agent-Side (BPS_AgentSide)
## Sistem CP-BPS Agent — OpenClaw & FastMCP WhatsApp Agent

> [!NOTE] 
> **Arsitektur Riil Proyek:**
> - **Kanal WhatsApp**: Fonnte Webhook ➡️ `bridge/main.py` (FastAPI).
> - **AI Engine**: OpenClaw LLM (`http://127.0.0.1:18789`).
> - **Tools & Database**: FastMCP Server di `bps_mcp/bps_data/server.py` membaca PostgreSQL (`data_tabel`, `data_informasi`, `log_percakapan`).
> - **Instruksi Persona**: `agent/workspace/AGENTS.md`.

---

## 🔴 FASE 1 — FastMCP Tool: Data Tabel Baru

### TASK-A01 · Buat Core Handler `bps_mcp/bps_data/core/tabel.py`
Buat file handler query untuk membaca tabel `data_tabel`:
```python
def cari_data_tabel(kata_kunci: str, limit: int = 5) -> dict:
    """
    Mencari dataset tabel statistik berdasarkan kata kunci nama atau deskripsi.
    Mengembalikan metadata dan preview data tabel baris & kolom.
    """
    # SELECT id, nama, deskripsi, jumlah_baris, jumlah_kolom, isi_data 
    # FROM data_tabel 
    # WHERE is_published = TRUE AND (nama ILIKE %kw% OR deskripsi ILIKE %kw%)
```

### TASK-A02 · Daftarkan Tool `cari_data_tabel` di FastMCP Server
**File:** `bps_mcp/bps_data/server.py`
```python
@mcp.tool()
def cari_data_tabel(kata_kunci: str) -> dict:
    """Gunakan tool ini jika pengguna menanyakan data statistik berbentuk tabel, dataset, jumlah baris/kolom, atau preview data."""
    return core_tabel.cari_data_tabel(kata_kunci)
```

---

## 🔴 FASE 2 — Alur Permintaan File & Link GDrive

> [!IMPORTANT]
> **Aturan Wajib:** Jika user meminta file/tabel atau link data, Agent **HARUS** menanyakan **Nama** dan **Keperluan** terlebih dahulu sebelum memberikan link Google Drive.

### TASK-A03 · Buat Tool `ambil_link_gdrive` di FastMCP
**File:** `bps_mcp/bps_data/core/tabel.py` & `server.py`
```python
@mcp.tool()
def ambil_link_gdrive(nama_tabel: str, nama_pemohon: str, keperluan: str) -> dict:
    """
    Gunakan tool ini HANYA JIKA pengguna sudah memberikan Nama dan Keperluannya untuk meminta file data.
    Parameter:
    - nama_tabel: nama dataset yang diminta
    - nama_pemohon: nama lengkap pengguna
    - keperluan: tujuan/kebutuhan penggunaan data
    """
```
- Tool ini mengambil `link_gdrive` dari tabel `data_tabel`.
- Jika belum ada `nama_pemohon` atau `keperluan`, kembalikan pesan peringatan agar agent menanyakannya terlebih dahulu.

### TASK-A04 · Perbarui Prompt & SOP di `agent/workspace/AGENTS.md`
Tambahkan aturan baru pada Alur Kerja di `AGENTS.md`:
```markdown
## Alur Permintaan File Data (WAJIB IKUTI)
1. Jika pengguna meminta file, download data, atau link spreadsheet/excel:
   - **JANGAN** langsung memberikan link.
   - **Tanyakan terlebih dahulu nama lengkap dan keperluan meminta data tersebut.**
   - Contoh respon: "Tentu, untuk pendataan layanan data statistik BPS, boleh sebutkan nama lengkap dan keperluan Anda menggunakan data tersebut?"
2. Setelah pengguna menyebutkan nama dan keperluannya:
   - Panggil tool `ambil_link_gdrive(nama_tabel=..., nama_pemohon=..., keperluan=...)`.
   - Berikan link Google Drive tersebut dengan sopan kepada pengguna.
```

---

## 🟡 FASE 3 — Logging Percakapan & Kolom `perihal`

### TASK-A05 · Perbarui Query `INSERT INTO log_percakapan` di `bridge/main.py`
Kolom `perihal` sudah siap di tabel database PostgreSQL. Perbarui fungsi simpan di `bridge/main.py`:

```python
# Tentukan ringkasan 'perihal' dari interaksi user
perihal = "Pertanyaan Umum"
if "minta" in message.lower() or "file" in message.lower() or "unduh" in message.lower():
    perihal = "Permintaan File Data"
elif "penduduk" in message.lower() or "inflasi" in message.lower() or "miskin" in message.lower():
    perihal = f"Tanya Data ({message[:30]}...)"

cur.execute(
    "INSERT INTO log_percakapan (sender, pushname, perihal, user_message, agent_reply, kategori_permintaan, created_at) "
    "VALUES (%s, %s, %s, %s, %s, %s, NOW())",
    (sender, pushname, perihal, message, reply_text, kategori)
)
```

---

## 🟢 FASE 4 — Pengujian & Validasi End-to-End

### TASK-A06 · Uji Menjawab Berdasarkan `data_informasi`
- Chat: *"Upacara apa yang baru saja diadakan BPS Batanghari?"*
- Agent memanggil tool `cari_informasi("Upacara")`
- Menjawab: Berdasarkan info BPS, Upacara Peringatan Sumpah Pemuda diadakan 28 Oktober 2026.

### TASK-A07 · Uji Menjawab Berdasarkan `data_tabel`
- Chat: *"Ada dataset apa saja terkait data netto?"*
- Agent memanggil tool `cari_data_tabel("netto")`
- Menjawab: Menampilkan deskripsi, 264 baris, 3 kolom, dan contoh preview.

### TASK-A08 · Uji Alur Minta File (Nama & Keperluan)
1. User: *"Bisa minta file Excel-nya?"*
2. Agent: *"Tentu, untuk pendataan layanan BPS, boleh sebutkan nama lengkap dan keperluan Anda?"*
3. User: *"Nama saya Rudi, untuk keperluan analisis skripsi"*
4. Agent memanggil `ambil_link_gdrive(nama_tabel="...", nama_pemohon="Rudi", keperluan="analisis skripsi")`
5. Agent membalas dengan link Google Drive.
6. Cek dashboard website: log percakapan tercatat lengkap dengan kolom **Perihal: Permintaan File Data**.
