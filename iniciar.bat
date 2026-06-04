@echo off
REM Script para iniciar CookAI automáticamente

cd /d c:\Users\rocio\Downloads\cookai

echo ============================================
echo      INICIANDO COOKAI
echo ============================================
echo.

echo [1/2] Activando entorno virtual...
call venv\Scripts\activate.bat

echo [2/2] Iniciando servidor en http://localhost:8000...
echo.
echo Abre en navegador: http://localhost:8000
echo.

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
