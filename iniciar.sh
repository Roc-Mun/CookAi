#!/bin/bash
# Script para iniciar CookAI automáticamente (macOS/Linux)

cd "$(dirname "$0")"

echo "============================================"
echo "      INICIANDO COOKAI"
echo "============================================"
echo ""

echo "[1/2] Activando entorno virtual..."
source venv/bin/activate

echo "[2/2] Iniciando servidor en http://localhost:8000..."
echo "Abre en navegador: http://localhost:8000"
echo ""

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
