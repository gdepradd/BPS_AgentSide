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

# --- TAMBAHKAN URL DB UNTUK BRIDGE ---
# (Pastikan user 'postgres' atau user bridge punya akses INSERT ke log_percakapan)
DB_URL = os.getenv("DB_BRIDGE_URL", "postgresql://postgres:postgres1504@localhost:5432/bps_agent")

app = FastAPI()

async def process_and_reply(sender: str, message: str, pushname: str = "Unknown"):
    headers = {
        "Authorization": f"Bearer {GATEWAY_TOKEN}",
        "Content-Type": "application/json",
        "x-openclaw-agent-id": "main",
    }
    payload = {
        "model": "openclaw:main",
        "messages": [{"role": "user", "content": message}],
        "stream": False,
    }

    reply_text = ""
    kategori = "Umum"
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            print(f"[{sender}] Memanggil OpenClaw...")
            resp = await client.post(OPENCLAW_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            try:
                reply_text = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                reply_text = "Maaf, sistem sedang sibuk."

            # Tentukan kategori sederhana (bisa dikembangkan nanti)
            if "tidak ditemukan" in reply_text.lower() or "maaf" in reply_text.lower():
                kategori = "Tidak Terjawab"
            elif "penduduk" in message.lower() or "miskin" in message.lower():
                kategori = "Data Statistik"

            # --- SIMPAN KE DATABASE ---
            try:
                with psycopg.connect(DB_URL) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO log_percakapan (sender, pushname, user_message, agent_reply, kategori_permintaan) "
                            "VALUES (%s, %s, %s, %s, %s)",
                            (sender, pushname, message, reply_text, kategori)
                        )
                    conn.commit()
                print(f"[{sender}] Log percakapan tersimpan ke DB.")
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
        pushname = data.get("pushname", "Unknown") # <-- Ambil nama WA
    except Exception:
        pass

    if sender and message:
        background_tasks.add_task(process_and_reply, sender, message, pushname)

    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)