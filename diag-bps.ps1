# diag-bps.ps1 - kumpulkan info diagnostik proyek AI-Agent BPS
#
# SIFAT: hanya MEMBACA. Tidak mengubah file, tidak mematikan proses, tidak menulis ke database
#        (uji tulis ke DB selalu di-rollback). Rahasia (password, token, API key, DATABASE_URL)
#        di-mask pada output. Tetap cek sekilas diag-output.txt sebelum dikirim.
#
# CARA PAKAI (di PowerShell EKSTERNAL, bukan terminal VS Code):
#   cd -LiteralPath "D:\Prakom's Projek\AI-Agent Side"
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\diag-bps.ps1
#
# HASIL: diag-output.txt di folder root proyek (sekitar 1-3 menit, ada uji generate singkat ke Ollama).

$ErrorActionPreference = 'Continue'
$Root = (Get-Location).ProviderPath
$Out  = Join-Path $Root 'diag-output.txt'
Set-Content -LiteralPath $Out -Value '' -Encoding UTF8

# ---------------------------------------------------------------- helper
function W([string]$s) { Add-Content -LiteralPath $Out -Value $s -Encoding UTF8 }
function Sec([string]$title) { W ''; W ('=' * 72); W ('## ' + $title); W ('=' * 72) }

$SecretPattern = '(?i)(api[_-]?key|token|passw|secret|credential|database_url|dsn|conn(ection)?[_-]?str)'
function Mask-Line([string]$line) {
  if ($null -eq $line) { return '' }
  $line = $line -replace "`0", ''
  $line = $line -replace '(://)[^/@\s]+@', '$1***@'
  if ($line -match '(?i)max_?tokens|contextwindow') { return $line }
  if ($line -match $SecretPattern) {
    $i = $line.IndexOfAny([char[]]@(':', '='))
    if ($i -ge 0) { return $line.Substring(0, $i + 1) + ' ***MASKED***' }
    return '***BARIS-DIMASK***'
  }
  return $line
}

function Show-File([string]$path, [int]$max = 200) {
  if (-not (Test-Path -LiteralPath $path)) { W ('(tidak ada) ' + $path); return }
  $fi = Get-Item -LiteralPath $path
  $all = @(Get-Content -LiteralPath $path -ErrorAction SilentlyContinue)
  W ('[{0}] {1} bytes, {2} baris, diubah {3}' -f $path.Replace($Root, '.'), $fi.Length, $all.Count, $fi.LastWriteTime)
  $n = 0
  foreach ($l in $all) {
    if ($n -ge $max) { W ('  | ... (dipotong di ' + $max + ' baris)'); break }
    W ('  | ' + (Mask-Line $l)); $n++
  }
}

function Capture([string]$label, [scriptblock]$sb) {
  W ''; W ('# ' + $label)
  try {
    $r = & $sb 2>&1 | Out-String -Width 220
    foreach ($l in ($r -split "`r?`n")) { if ($l.Trim() -ne '') { W ('  ' + (Mask-Line $l)) } }
  } catch { W ('  ERROR: ' + $_.Exception.Message) }
}

# Jalankan perintah CLI dengan batas waktu (agar tidak menggantung bila menunggu input)
function Run-Cmd([string]$cmd, [int]$timeoutSec = 30) {
  W ''; W ('$ ' + $cmd)
  $job = Start-Job -ScriptBlock {
    param($dir, $c)
    Set-Location -LiteralPath $dir
    try { Invoke-Expression $c 2>&1 | Out-String -Width 220 } catch { 'ERROR: ' + $_.Exception.Message }
  } -ArgumentList $Root, $cmd
  if (Wait-Job $job -Timeout $timeoutSec) {
    $res = Receive-Job $job
    foreach ($l in ($res -split "`r?`n")) { if ($l.Trim() -ne '') { W ('  ' + (Mask-Line $l)) } }
  } else {
    W ('  !! TIMEOUT setelah ' + $timeoutSec + ' detik (kemungkinan hang atau menunggu input)')
    Stop-Job $job
  }
  Remove-Job $job -Force -ErrorAction SilentlyContinue
}

# Samakan environment OpenClaw dengan konvensi proyek bila belum diset
$stateNote = '(dari environment)'; $cfgNote = '(dari environment)'
if (-not $env:OPENCLAW_STATE_DIR)  { $env:OPENCLAW_STATE_DIR  = Join-Path $Root 'agent\.openclaw_state'; $stateNote = '(DISET oleh diag-bps.ps1)' }
if (-not $env:OPENCLAW_CONFIG_PATH) { $env:OPENCLAW_CONFIG_PATH = Join-Path $Root 'agent\openclaw.json';   $cfgNote   = '(DISET oleh diag-bps.ps1)' }

# ---------------------------------------------------------------- 0
Sec '0. INFO DASAR'
W ('Waktu        : ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'))
W ('User / Host  : ' + $env:USERNAME + ' @ ' + $env:COMPUTERNAME)
try { $os = Get-CimInstance Win32_OperatingSystem; W ('OS           : ' + $os.Caption + ' ' + $os.Version) } catch { W 'OS           : (gagal dibaca)' }
W ('PowerShell   : ' + $PSVersionTable.PSVersion)
W ('Root         : ' + $Root)
W ('Panjang path : ' + $Root.Length + ' | mengandung spasi: ' + $Root.Contains(' ') + ' | mengandung apostrof: ' + $Root.Contains("'"))
W ('OPENCLAW_STATE_DIR  : ' + $env:OPENCLAW_STATE_DIR + ' ' + $stateNote)
W ('OPENCLAW_CONFIG_PATH: ' + $env:OPENCLAW_CONFIG_PATH + ' ' + $cfgNote)
Capture 'CPU / RAM / Disk' {
  $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
  'CPU : ' + $cpu.Name + ' | core ' + $cpu.NumberOfCores + ' | thread ' + $cpu.NumberOfLogicalProcessors
  $cs = Get-CimInstance Win32_ComputerSystem
  'RAM : ' + [math]::Round($cs.TotalPhysicalMemory / 1GB, 1) + ' GB'
  $drv = (Get-Item -LiteralPath $Root).PSDrive
  'Disk: drive ' + $drv.Name + ' bebas ' + [math]::Round($drv.Free / 1GB, 1) + ' GB'
}
Capture 'GPU' {
  Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name + ' | driver ' + $_.DriverVersion }
  if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv }
}

# ---------------------------------------------------------------- 1
Sec '1. VERSI TOOL'
foreach ($c in @('node -v', 'npm -v', 'openclaw --version', 'python --version', 'git --version', 'ollama --version', 'psql --version', 'docker --version', 'where.exe openclaw', 'where.exe node', 'wsl -l -v')) {
  Run-Cmd $c 20
}

# ---------------------------------------------------------------- 2
Sec '2. ENVIRONMENT VARIABLE (nama-nama relevan)'
Get-ChildItem Env: | Where-Object { $_.Name -match '^(OPENCLAW|OLLAMA|PROJECT_ROOT|VIRTUAL_ENV|PG|NODE_|PYTHON)' } | Sort-Object Name | ForEach-Object {
  $v = $_.Value
  if ($_.Name -match $SecretPattern) { $v = '***MASKED***' }
  W ('  ' + $_.Name + ' = ' + $v)
}

# ---------------------------------------------------------------- 3
Sec '3. STRUKTUR FOLDER (tanpa .venv, node_modules, .git, isi .openclaw_state)'
Get-ChildItem -LiteralPath $Root -Recurse -File -Force -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -notmatch '\\(\.venv|node_modules|\.git|\.openclaw_state)\\' } |
  ForEach-Object { W ('  {0,-60} {1,9} B  {2}' -f $_.FullName.Substring($Root.Length + 1), $_.Length, $_.LastWriteTime.ToString('yyyy-MM-dd HH:mm')) }
W ''
W '# Isi .openclaw_state (maks. kedalaman 3, 80 entri pertama)'
$st = $env:OPENCLAW_STATE_DIR
if (Test-Path -LiteralPath $st) {
  Get-ChildItem -LiteralPath $st -Recurse -Depth 3 -Force -ErrorAction SilentlyContinue | Select-Object -First 80 |
    ForEach-Object { W ('  ' + $_.FullName.Replace($st, '<STATE>') + $(if ($_.PSIsContainer) { '\' } else { '  (' + $_.Length + ' B)' })) }
} else { W ('  (folder state tidak ada: ' + $st + ')') }

# ---------------------------------------------------------------- 4
Sec '4. ISI FILE KUNCI (rahasia di-mask)'
W '# .env (nama kunci; nilai disembunyikan untuk pass/secret/token/key/url)'
$envFile = Join-Path $Root '.env'
if (Test-Path -LiteralPath $envFile) {
  foreach ($l in (Get-Content -LiteralPath $envFile)) {
    if ($l -match '^\s*#' -or $l.Trim() -eq '') { continue }
    $i = $l.IndexOf('=')
    if ($i -lt 1) { W '  (baris bukan format KEY=VALUE)'; continue }
    $k = $l.Substring(0, $i).Trim(); $v = $l.Substring($i + 1).Trim()
    if ($k -match '(?i)pass|pwd|secret|token|key|url|dsn') { $v = '***MASKED*** (panjang ' + $v.Length + ')' }
    W ('  ' + $k + ' = ' + $v)
  }
} else { W '  (.env tidak ada)' }
W ''
foreach ($f in @('agent\openclaw.json', 'agent\PROMPT.md', 'ops\bps-claw.ps1', 'ops\bps-claw.bat', 'mcp\server.py', 'requirements.txt', '.gitignore')) {
  Show-File (Join-Path $Root $f) 220
  W ''
}
foreach ($f in @('sql\01_schema_and_roles.sql', 'sql\02_seed_dummy.sql')) {
  Show-File (Join-Path $Root $f) 40
  W ''
}

# ---------------------------------------------------------------- 5
Sec '5. GIT'
foreach ($c in @('git rev-parse --is-inside-work-tree', 'git status --short', 'git log --oneline -n 8', 'git remote -v', 'git check-ignore -v .env')) { Run-Cmd $c 20 }

# ---------------------------------------------------------------- 6
Sec '6. PROSES DAN PORT'
Capture 'Proses terkait' {
  Get-Process -Name node, ollama, 'ollama app', python, postgres, openclaw -ErrorAction SilentlyContinue |
    Select-Object Id, ProcessName, StartTime, @{n = 'MB'; e = { [int]($_.WorkingSet64 / 1MB) } } | Format-Table -AutoSize
}
Capture 'Command line proses node dan python (dipotong 300 karakter)' {
  Get-CimInstance Win32_Process -Filter "Name='node.exe' OR Name='python.exe'" | ForEach-Object {
    $cl = [string]$_.CommandLine
    if ($cl.Length -gt 300) { $cl = $cl.Substring(0, 300) + '...' }
    'PID ' + $_.ProcessId + ' | ' + $_.Name + ' | ' + $cl
  }
}
Capture 'Port LISTEN (11434 Ollama, 5432 Postgres, 18789 Gateway, 8088 bridge)' {
  Get-NetTCPConnection -State Listen -LocalPort 11434, 5432, 18789, 8088 -ErrorAction SilentlyContinue | ForEach-Object {
    $pn = (Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).ProcessName
    $_.LocalAddress + ':' + $_.LocalPort + '  PID ' + $_.OwningProcess + ' (' + $pn + ')'
  }
}

# ---------------------------------------------------------------- 7
Sec '7. OLLAMA'
foreach ($h in @('localhost', '127.0.0.1', '[::1]')) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri ('http://' + $h + ':11434/api/version') -TimeoutSec 5
    W ('  ' + $h + ' -> HTTP ' + $r.StatusCode + ' ' + $r.Content)
  } catch { W ('  ' + $h + ' -> GAGAL: ' + $_.Exception.Message) }
}
Capture 'Model terpasang (/api/tags)' {
  (Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 10).models |
    Select-Object name, @{n = 'GB'; e = { [math]::Round($_.size / 1GB, 2) } }, @{n = 'param'; e = { $_.details.parameter_size } }, @{n = 'quant'; e = { $_.details.quantization_level } } | Format-Table -AutoSize
}
Run-Cmd 'ollama ps' 15
Run-Cmd 'ollama show qwen3:latest' 20
Capture 'Uji generate singkat (qwen3:latest, num_predict 64, think=false)' {
  $body = @{ model = 'qwen3:latest'; messages = @(@{ role = 'user'; content = 'Balas satu kata saja: siap' }); stream = $false; think = $false; options = @{ num_predict = 64 } } | ConvertTo-Json -Depth 6
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $r = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/chat' -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 180
  $sw.Stop()
  'waktu total (klien)  : ' + [math]::Round($sw.Elapsed.TotalSeconds, 1) + ' detik'
  'load_duration (ms)   : ' + [math]::Round($r.load_duration / 1e6)
  'total_duration (ms)  : ' + [math]::Round($r.total_duration / 1e6)
  'eval_count (token)   : ' + $r.eval_count
  'isi jawaban          : ' + $r.message.content
  'panjang field thinking: ' + ([string]$r.message.thinking).Length
}

# ---------------------------------------------------------------- 8
Sec '8. PYTHON VENV DAN MCP'
$py = Join-Path $Root '.venv\Scripts\python.exe'
Show-File (Join-Path $Root '.venv\pyvenv.cfg') 20
if (Test-Path -LiteralPath $py) {
  Capture 'versi python venv' { & $py --version }
  Capture 'paket terpasang (pip list)' { & $py -m pip list --disable-pip-version-check }
  Capture 'import fastmcp' { & $py -c "import fastmcp; print('fastmcp', getattr(fastmcp, '__version__', '?'))" }
  Capture 'cek sintaks mcp\server.py' {
    & $py -m py_compile (Join-Path $Root 'mcp\server.py')
    if ($LASTEXITCODE -eq 0) { 'OK: sintaks valid' } else { 'GAGAL: lihat pesan di atas' }
  }
} else { W '  (.venv\Scripts\python.exe tidak ada)' }

# ---------------------------------------------------------------- 9
Sec '9. DATABASE (via python venv; tidak menulis apa pun)'
$dbpy = Join-Path $env:TEMP 'diag_db_bps.py'
@'
import os, sys
root = sys.argv[1]
env = {}
p = os.path.join(root, '.env')
if os.path.exists(p):
    for line in open(p, encoding='utf-8-sig'):
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
print('kunci .env terbaca:', ', '.join(sorted(env)) or '(kosong)')

def pick(*names):
    for n in names:
        for k in env:
            if k.lower() == n.lower():
                return env[k]
    return None

dsn = pick('DATABASE_URL', 'AGENT_DATABASE_URL', 'DB_URL')
kw = {}
if dsn:
    print('koneksi dari DATABASE_URL (nilai tidak dicetak)')
else:
    kw = dict(host=pick('PGHOST', 'DB_HOST', 'POSTGRES_HOST') or 'localhost',
              port=pick('PGPORT', 'DB_PORT', 'POSTGRES_PORT') or '5432',
              dbname=pick('PGDATABASE', 'DB_NAME', 'POSTGRES_DB', 'DB_DATABASE'),
              user=pick('PGUSER', 'DB_USER', 'POSTGRES_USER', 'DB_USERNAME'),
              password=pick('PGPASSWORD', 'DB_PASSWORD', 'POSTGRES_PASSWORD'))
    print('koneksi dari komponen:', {k: ('***' if k == 'password' and v else v) for k, v in kw.items()})

def connect():
    try:
        import psycopg as drv
        mode = 'psycopg3'
    except ImportError:
        try:
            import psycopg2 as drv
            mode = 'psycopg2'
        except ImportError:
            return None, 'tidak ada driver psycopg/psycopg2 di venv'
    try:
        if dsn:
            return drv.connect(dsn, connect_timeout=5), mode
        return drv.connect(connect_timeout=5, **{k: v for k, v in kw.items() if v}), mode
    except Exception as e:
        return None, mode + ' gagal konek: ' + type(e).__name__ + ': ' + str(e)[:200]

conn, info = connect()
if conn is None:
    print(info)
    sys.exit(0)
print('driver:', info)
cur = conn.cursor()

def q(sql):
    cur.execute(sql)
    return cur.fetchall()

print('versi      :', q('select version()')[0][0][:90])
me, dbn = q('select current_user, current_database()')[0]
print('user / db  :', me, '/', dbn)
print('ekstensi   :', [r[0] for r in q('select extname from pg_extension')])
print('role proyek:', [r[0] for r in q("select rolname from pg_roles where rolname in ('agent_ro','bridge_rw','embed_worker','web_rw')")])
tabs = q("select table_name from information_schema.tables where table_schema='public' and table_type='BASE TABLE' order by 1")
print('tabel public:', len(tabs))
for (t,) in tabs:
    try:
        n = q('select count(*) from "' + t.replace('"', '') + '"')[0][0]
    except Exception as e:
        conn.rollback()
        n = 'tidak bisa dihitung: ' + type(e).__name__
    print('  %-32s %s' % (t, n))
if me == 'agent_ro':
    try:
        cur.execute('insert into data_indikator default values')
        print('PERINGATAN: agent_ro BERHASIL menulis ke data_indikator (seharusnya ditolak)')
    except Exception as e:
        print('uji tulis agent_ro ke data_indikator ditolak (benar):', type(e).__name__)
    conn.rollback()
conn.rollback()
conn.close()
'@ | Set-Content -LiteralPath $dbpy -Encoding UTF8
if (Test-Path -LiteralPath $py) {
  Capture 'hasil pengecekan database' { & $py $dbpy $Root }
} else { W '  (dilewati: venv tidak ada)' }
Remove-Item -LiteralPath $dbpy -Force -ErrorAction SilentlyContinue

# ---------------------------------------------------------------- 10
Sec '10. OPENCLAW (batas waktu per perintah)'
foreach ($c in @('openclaw --version', 'openclaw config file', 'openclaw config validate', 'openclaw gateway status', 'openclaw models list', 'openclaw models status', 'openclaw mcp list', 'openclaw agent --help')) {
  Run-Cmd $c 40
}
Run-Cmd 'openclaw doctor --non-interactive' 60
Capture 'Log terbaru di state dir (40 baris terakhir dari .log terbaru)' {
  $lg = Get-ChildItem -LiteralPath $env:OPENCLAW_STATE_DIR -Recurse -Filter *.log -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($lg) { 'berkas: ' + $lg.FullName.Replace($env:OPENCLAW_STATE_DIR, '<STATE>') + ' | ' + $lg.LastWriteTime; Get-Content -LiteralPath $lg.FullName -Tail 40 } else { '(tidak ada berkas .log)' }
}

Sec 'SELESAI'
W ('Dibuat: ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
Write-Host ''
Write-Host 'Selesai. Hasil: diag-output.txt (di folder proyek).' -ForegroundColor Green
Write-Host 'Cek sekilas isinya (rahasia sudah di-mask), lalu kirim file txt-nya.'