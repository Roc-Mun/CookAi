# Script de PowerShell para iniciar CookAI automáticamente

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "      INICIANDO COOKAI" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/2] Activando entorno virtual..." -ForegroundColor Yellow
& "c:\Users\rocio\Downloads\cookai\venv\Scripts\Activate.ps1"

Write-Host "[2/2] Iniciando servidor en http://localhost:8000..." -ForegroundColor Yellow
Write-Host "Abre en navegador: http://localhost:8000" -ForegroundColor Green
Write-Host ""

Set-Location "c:\Users\rocio\Downloads\cookai"
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Read-Host "Presiona Enter para salir"
