import argparse
import json
import re
import subprocess
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import yaml

def run_question(q: dict) -> dict:
    session_name = f"eval-{q['id']}-{int(time.time())}"
    cmd = [
        "cmd", "/c", "ops\\bps-claw.bat",
        "agent", "-m", q["pertanyaan"],
        "--thinking", "off", "--json",
        "--session-key", session_name,
    ]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        stdout = proc.stdout
    except subprocess.TimeoutExpired:
        return {"stdout": "TIMEOUT", "durasi_s": 120, "rc": -1}

    # Ekstraksi jawaban yang super aman
    jawaban = ""
    # 1. Cari awal JSON
    start_idx = stdout.find("{")
    if start_idx != -1:
        try:
            # 2. Parse seluruh JSON
            data = json.loads(stdout[start_idx:])
            
            # 3. Cari teks jawabannya
            if "terminalReply" in data and "text" in data["terminalReply"]:
                jawaban = data["terminalReply"]["text"]
            elif "finalAssistantVisibleText" in data:
                jawaban = data["finalAssistantVisibleText"]
            else:
                jawaban = str(data) # Fallback
        except json.JSONDecodeError:
            jawaban = "JSON Error: " + stdout[:100]
    else:
        jawaban = "No JSON: " + stdout[:100]

    return {
        "stdout": jawaban,
        "stderr": "",
        "rc": proc.returncode,
        "durasi_s": round(time.time() - t0, 2),
    }
def check(answer: str, q: dict) -> dict:
    checks: dict[str, bool] = {}
    for t in q.get("harus_memuat", []):
        checks[f"harus:{t}"] = t.lower() in answer.lower()
    for t in q.get("tidak_boleh_memuat", []):
        checks[f"tidak:{t}"] = t.lower() not in answer.lower()
    if q.get("harus_ada_sumber"):
        checks["sumber"] = bool(re.search(r"\bBPS\b", answer, re.IGNORECASE))
    return checks

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--questions", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    qs = yaml.safe_load(Path(args.questions).read_text(encoding="utf-8"))
    results = []
    
    print(f"Memulai evaluasi untuk model: {args.model}")
    print(f"Total pertanyaan: {len(qs)}\n")

    for q in qs:
        run = run_question(q)
        
        # Ekstrak jawaban dari format JSON OpenClaw
        jawaban = ""
        try:
            data = json.loads(run["stdout"])
            jawaban = data.get("finalAssistantVisibleText", "")
            # Jika kosong, coba ambil dari raw text
            if not jawaban:
                jawaban = data.get("finalAssistantRawText", "")
        except Exception:
            jawaban = run["stdout"] # Fallback jika bukan JSON

        checks = check(jawaban, q)
        lulus = all(checks.values()) if checks else True
        
        results.append({
            "id": q["id"], 
            "kategori": q["kategori"],
            "pertanyaan": q["pertanyaan"],
            "jawaban": jawaban,
            "durasi_s": run["durasi_s"],
            "lulus": lulus, 
            "checks": checks,
        })
        
        status = "✅ LULUS" if lulus else "❌ GAGAL"
        print(f"[{q['id']}] {q['kategori']:22} {status} ({run['durasi_s']:6.1f}s)")
        
        # Jeda 2 detik antar pertanyaan agar tidak kena rate limit Cloud
        time.sleep(2)

    # Simpan hasil
    out = args.out or f"eval/results/gemma4-31b-{datetime.now():%Y%m%d-%H%M%S}.json"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    # Cetak Ringkasan
    by_cat = defaultdict(lambda: {"lulus": 0, "total": 0})
    for r in results:
        by_cat[r["kategori"]]["total"] += 1
        if r["lulus"]:
            by_cat[r["kategori"]]["lulus"] += 1
            
    print("\n" + "="*40)
    print("RINGKASAN EVALUASI")
    print("="*40)
    for cat, v in by_cat.items():
        print(f"  {cat:22} : {v['lulus']}/{v['total']} lulus")
        
    ds = sorted(r["durasi_s"] for r in results)
    n = len(ds)
    print(f"\nLatensi Median : {ds[n//2]:.1f} detik")
    print(f"Latensi P95    : {ds[min(n-1, int(n*0.95))]:.1f} detik")
    print(f"Hasil disimpan di: {out}")

if __name__ == "__main__":
    main()