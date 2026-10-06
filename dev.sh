#!/usr/bin/env bash
# Tilas dev launcher — venv python langsung, tanpa activate

ROOT="/home/agiel-fernanda/hackaton-ibm-hackactive8/project"
VENV="$ROOT/.venv"

echo ">>> Killing old processes..."
pkill -9 -f "uvicorn timbang" 2>/dev/null || true
pkill -9 -f "vite" 2>/dev/null || true
pkill -9 -f "npm run dev" 2>/dev/null || true
sleep 2

if ss -tln 2>/dev/null | grep -q ":8000 "; then
    echo "❌ Port 8000 masih dipakai. Kill manual:"
    ss -tlnp 2>/dev/null | grep ":8000 "
    exit 1
fi
if ss -tln 2>/dev/null | grep -q ":5173 "; then
    echo "❌ Port 5173 masih dipakai. Kill manual:"
    ss -tlnp 2>/dev/null | grep ":5173 "
    exit 1
fi

trap 'echo ""; echo ">>> Shutting down..."; pkill -9 -f "uvicorn timbang" 2>/dev/null; pkill -9 -f vite 2>/dev/null; exit 0' INT TERM

echo ">>> Starting backend on :8000 (venv: $VENV)"
(
    cd "$ROOT"
    exec "$VENV/bin/python" -m uvicorn timbang.main:app --app-dir backend/src --port 8000
) &

sleep 3

echo ">>> Starting frontend on :5173"
(
    cd "$ROOT/frontend"
    exec npm run dev
) &

echo ""
echo "=========================================="
echo "  Backend : http://127.0.0.1:8000/health"
echo "  Frontend: http://localhost:5173/maker"
echo "  Ctrl+C to stop both"
echo "=========================================="
echo ""

wait
