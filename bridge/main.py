import os
import json
from datetime import datetime
import httpx
import psycopg
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import load_dotenv

load_dotenv()
FONNTE_TOKEN = os.getenv("FONNTE_TOKEN")
OPENCLAW_URL = "http://127.0.0.1:18789/v1/chat/completions"
GATEWAY_TOKEN = os.getenv("OPENCLAW_GATEWAY_TOKEN")
DB_URL = os.getenv("DB_BRIDGE_URL")

app = FastAPI()


async def process_and_reply(sender: str, message: str, pushname: str = "Unknown"):
    headers = {
        "Authorization": f"Bearer {GATEWAY_TOKEN}",
        "Content-Type": "application/json",
        "x-openclaw-agent-id": "main",
    }

    # 1. Cari apakah ada sesi aktif untuk pengirim ini
    # Syarat sesi aktif:
    # - sender = %s
    # - DATE(created_at) = CURRENT_DATE (hari yang sama)
    # - COALESCE(updated_at, created_at) >= NOW() - INTERVAL '30 minutes' (jeda aktif < 30 menit)
    active_session_id = None
    existing_messages = []
    current_perihal = None
    current_kategori = None

    try:
        with psycopg.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, perihal, kategori_permintaan, messages 
                    FROM log_percakapan 
                    WHERE sender = %s 
                      AND DATE(created_at) = CURRENT_DATE 
                      AND COALESCE(updated_at, created_at) >= NOW() - INTERVAL '30 minutes'
                    ORDER BY id DESC 
                    LIMIT 1
                    """,
                    (sender,)
                )
                row = cur.fetchone()
                if row:
                    active_session_id = row[0]
                    current_perihal = row[1]
                    current_kategori = row[2]
                    # Parse messages JSON array
                    raw_messages = row[3]
                    if isinstance(raw_messages, str):
                        try:
                            existing_messages = json.loads(raw_messages)
                        except Exception:
                            existing_messages = []
                    elif isinstance(raw_messages, list):
                        existing_messages = raw_messages
    except Exception as sess_err:
        print(f"[{sender}] Gagal membaca sesi aktif: {sess_err}")

    # 2. Susun konteks messages untuk dikirim ke OpenClaw
    messages_payload = []
    for turn in existing_messages:
        u_msg = turn.get("user_message")
        a_reply = turn.get("agent_reply")
        if u_msg:
            messages_payload.append({"role": "user", "content": u_msg})
        if a_reply:
            messages_payload.append({"role": "assistant", "content": a_reply})

    # Tambahkan pesan user saat ini
    messages_payload.append({"role": "user", "content": message})

    payload = {
        "model": "openclaw:main",
        "messages": messages_payload,
        "stream": False,
    }

    reply_text = ""
    kategori = current_kategori or "Umum"

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            session_label = f"Sesi #{active_session_id}" if active_session_id else "Sesi Baru"
            print(f"[{sender}] Memanggil OpenClaw dengan {len(messages_payload)} pesan konteks ({session_label})...")
            resp = await client.post(OPENCLAW_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            try:
                reply_text = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                reply_text = "Maaf, sistem sedang sibuk."

            # Tentukan kategori
            reply_lower = reply_text.lower()
            msg_lower = message.lower()
            if "drive.google.com" in reply_text or "tabel" in reply_lower:
                kategori = "Data Tabel"
            elif any(w in msg_lower for w in ["penduduk", "inflasi", "miskin", "pdrb", "ipm"]):
                kategori = "Data Statistik"
            elif "tidak ditemukan" in reply_lower or "maaf" in reply_lower:
                if not current_kategori or current_kategori == "Umum":
                    kategori = "Tidak Terjawab"

            # Tentukan perihal (perbarui jika ada topik yang lebih spesifik)
            perihal = current_perihal or "Pertanyaan Umum"
            if any(w in msg_lower for w in ["minta", "file", "unduh", "link", "gdrive", "download", "excel", "spreadsheet", "honor", "pml"]):
                perihal = "Permintaan File Data"
            elif any(w in msg_lower for w in ["kegiatan", "acara", "upacara", "agenda", "alamat", "jam", "kantor"]):
                perihal = f"Informasi Layanan/Kegiatan ({message[:25]}...)"
            elif any(w in msg_lower for w in ["penduduk", "inflasi", "miskin", "pdrb", "ipm"]):
                perihal = f"Tanya Data ({message[:25]}...)"

            # Buat turn baru
            new_turn = {
                "user_message": message,
                "agent_reply": reply_text,
                "created_at": datetime.now().isoformat(),
            }
            updated_messages = existing_messages + [new_turn]

            # 3. Simpan atau perbarui ke database PostgreSQL
            try:
                with psycopg.connect(DB_URL) as conn:
                    with conn.cursor() as cur:
                        if active_session_id:
                            # Sesi masih aktif: gabungkan pesan ke sesi ini
                            cur.execute(
                                """
                                UPDATE log_percakapan 
                                SET messages = %s,
                                    user_message = %s,
                                    agent_reply = %s,
                                    perihal = %s,
                                    kategori_permintaan = %s,
                                    pushname = COALESCE(%s, pushname),
                                    updated_at = NOW()
                                WHERE id = %s
                                """,
                                (
                                    json.dumps(updated_messages),
                                    message,
                                    reply_text,
                                    perihal,
                                    kategori,
                                    pushname if pushname != "Unknown" else None,
                                    active_session_id,
                                )
                            )
                            print(f"[{sender}] Sesi #{active_session_id} diperbarui ({len(updated_messages)} turn pesan).")
                        else:
                            # Sesi baru (hari baru atau jeda > 30 menit)
                            cur.execute(
                                """
                                INSERT INTO log_percakapan (
                                    sender, pushname, perihal, user_message, agent_reply, 
                                    kategori_permintaan, messages, created_at, updated_at
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                                """,
                                (
                                    sender,
                                    pushname,
                                    perihal,
                                    message,
                                    reply_text,
                                    kategori,
                                    json.dumps(updated_messages),
                                )
                            )
                            print(f"[{sender}] Sesi percakapan baru dibuat (Perihal: {perihal}).")
                    conn.commit()
            except Exception as db_err:
                print(f"[{sender}] Gagal simpan sesi ke DB: {db_err}")

            # 4. Kirim balasan ke Fonnte
            fonnte_payload = {"target": sender, "message": reply_text}
            await client.post(
                "https://api.fonnte.com/send",
                data=fonnte_payload,
                headers={"Authorization": FONNTE_TOKEN},
            )
            print(f"[{sender}] Balasan terkirim ke WhatsApp.")

    except Exception as e:
        print(f"[{sender}] Error: {e}")


@app.post("/webhook")
async def fonnte_webhook(request: Request, background_tasks: BackgroundTasks):
    raw = await request.body()
    sender = None
    message = None
    pushname = "Unknown"

    try:
        data = json.loads(raw)
        sender = data.get("sender")
        message = data.get("message")
        pushname = data.get("pushname", "Unknown")
    except Exception:
        pass

    if sender and message:
        background_tasks.add_task(process_and_reply, sender, message, pushname)

    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
