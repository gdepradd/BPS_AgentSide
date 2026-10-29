$ErrorActionPreference = "Continue"
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "   OPENCLAW DIAGNOSTIC TOOL" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# 1. Cek Versi & Config
Write-Host "`n[1] VERSI & LOKASI CONFIG" -ForegroundColor Yellow
openclaw --version
openclaw config file

# 2. Validasi JSON
Write-Host "`n[2] VALIDASI openclaw.json" -ForegroundColor Yellow
$configPath = "agent\openclaw.json"
if (Test-Path $configPath) {
    try {
        $json = Get-Content $configPath -Raw | ConvertFrom-Json
        Write-Host "JSON VALID." -ForegroundColor Green
        
        Write-Host "  -> Model : $($json.agents.defaults.model)"
        Write-Host "  -> BaseUrl Ollama : $($json.models.providers.ollama.baseUrl)"
        if ($json.mcp.servers.bps) {
            Write-Host "  -> MCP 'bps' TERDAFTAR." -ForegroundColor Green
        } else {
            Write-Host "  -> MCP 'bps' TIDAK TERDAFTAR." -ForegroundColor Red
        }
    } catch {
        Write-Host "JSON RUSAK: $_" -ForegroundColor Red
    }
} else {
    Write-Host "File openclaw.json tidak ditemukan!" -ForegroundColor Red
}

# 3. Cek Port & Proses
Write-Host "`n[3] STATUS PORT 18789 & PROSES NODE" -ForegroundColor Yellow
$portCheck = Get-NetTCPConnection -LocalPort 18789 -State Listen -ErrorAction SilentlyContinue
if ($portCheck) {
    Write-Host "Port 18789 SEDANG DIPAKAI oleh PID: $($portCheck.OwningProcess)" -ForegroundColor Red
} else {
    Write-Host "Port 18789 BEBAS." -ForegroundColor Green
}
$nodeProcs = Get-Process -Name node -ErrorAction SilentlyContinue
if ($nodeProcs) {
    Write-Host "Proses Node berjalan: $($nodeProcs.Id -join ', ')"
} else {
    Write-Host "Tidak ada proses Node yang berjalan." -ForegroundColor Green
}

# 4. Cek Log Error Terakhir
Write-Host "`n[4] LOG ERROR TERAKHIR (Temp OpenClaw)" -ForegroundColor Yellow
$tempDir = "$env:LOCALAPPDATA\Temp\openclaw"
if (Test-Path $tempDir) {
    $latestLog = Get-ChildItem $tempDir -Filter "*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latestLog) {
        Write-Host "Membaca file: $($latestLog.Name)" -ForegroundColor Gray
        Write-Host "--- 15 baris terakhir ---" -ForegroundColor DarkGray
        Get-Content $latestLog.FullName -Tail 15 | ForEach-Object { Write-Host $_ -ForegroundColor Gray }
        Write-Host "-------------------------" -ForegroundColor DarkGray
    }
} else {
    Write-Host "Folder log tidak ditemukan." -ForegroundColor Red
}

# 5. Cek Koneksi API Ollama (Ping URL)
Write-Host "`n[5] TES KONEKSI KE API OLLAMA" -ForegroundColor Yellow
if ($json -and $json.models.providers.ollama.baseUrl) {
    $apiUrl = $json.models.providers.ollama.baseUrl
    Write-Host "Mencoba ping ke: $apiUrl ..." -ForegroundColor Gray
    try {
        $response = Invoke-RestMethod -Uri "$apiUrl/api/tags" -Method Get -TimeoutSec 5 -ErrorAction Stop
        Write-Host "API MERESPONS! Model yang tersedia:" -ForegroundColor Green
        $response.models | Select-Object -ExpandProperty name | ForEach-Object { Write-Host "  - $_" }
    } catch {
        Write-Host "GAGAL KONEKSI KE API: $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host "`n==============================================" -ForegroundColor Cyan
Write-Host "   DIAGNOSTIK SELESAI" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan