import os
import json
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

    # Ambil riwayat percakapan sebelumnya untuk sender ini (multi-turn context)
    messages_payload = []
    try:
        with psycopg.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT user_message, agent_reply 
                    FROM log_percakapan 
                    WHERE sender = %s 
                    ORDER BY id DESC 
                    LIMIT 6
                    """,
                    (sender,)
                )
                past_logs = cur.fetchall()
                # Balikkan urutan agar kronologis dari yang terlama ke terbaru
                for u_msg, a_reply in reversed(past_logs):
                    if u_msg:
                        messages_payload.append({"role": "user", "content": u_msg})
                    if a_reply:
                        messages_payload.append({"role": "assistant", "content": a_reply})
    except Exception as hist_err:
        print(f"[{sender}] Gagal membaca riwayat percakapan: {hist_err}")

    # Tambahkan pesan saat ini
    messages_payload.append({"role": "user", "content": message})

    payload = {
        "model": "openclaw:main",
        "messages": messages_payload,
        "stream": False,
    }

    reply_text = ""
    kategori = "Umum"

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            print(f"[{sender}] Memanggil OpenClaw dengan {len(messages_payload)} pesan konteks...")
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
            if "tidak ditemukan" in reply_lower or "maaf" in reply_lower:
                kategori = "Tidak Terjawab"
            elif "drive.google.com" in reply_text or "tabel" in reply_lower:
                kategori = "Data Tabel"
            elif any(w in msg_lower for w in ["penduduk", "inflasi", "miskin", "pdrb", "ipm"]):
                kategori = "Data Statistik"

            # Tentukan perihal
            perihal = "Pertanyaan Umum"
            if any(w in msg_lower for w in ["minta", "file", "unduh", "link", "gdrive", "download", "excel", "spreadsheet"]):
                perihal = "Permintaan File Data"
            elif any(w in msg_lower for w in ["honor", "pml", "keperluan", "nama saya"]):
                perihal = "Permintaan File Data"
            elif any(w in msg_lower for w in ["kegiatan", "acara", "upacara", "agenda", "alamat", "jam", "kantor"]):
                perihal = f"Informasi Layanan/Kegiatan ({message[:25]}...)"
            elif any(w in msg_lower for w in ["penduduk", "inflasi", "miskin", "pdrb", "ipm"]):
                perihal = f"Tanya Data ({message[:25]}...)"

            # Simpan log ke database
            try:
                with psycopg.connect(DB_URL) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO log_percakapan (sender, pushname, perihal, user_message, agent_reply, kategori_permintaan) "
                            "VALUES (%s, %s, %s, %s, %s, %s)",
                            (sender, pushname, perihal, message, reply_text, kategori)
                        )
                    conn.commit()
                print(f"[{sender}] Log percakapan tersimpan ke DB (Perihal: {perihal}).")
            except Exception as db_err:
                print(f"[{sender}] Gagal simpan ke DB: {db_err}")

            # Kirim balasan ke Fonnte
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
