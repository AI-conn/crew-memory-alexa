#!/usr/bin/env bash
# One-command demo: MCP server + seed (first run only) + simulated Alexa+ UI.
#   bash run_all.sh
# Then open http://127.0.0.1:5000
set -e
cd "$(dirname "$0")"
PY=.venv/bin/python
[ -x "$PY" ] || PY=python3
export CREW_MEMORY_DB="${CREW_MEMORY_DB:-crew_memory.db}"
FRESH=0
[ -f "$CREW_MEMORY_DB" ] || FRESH=1

"$PY" mcp_server.py --port 8000 &
SRV=$!
trap 'kill $SRV 2>/dev/null || true' EXIT
for i in $(seq 1 30); do
  curl -sf http://127.0.0.1:8000/ >/dev/null && break || sleep 1
done
if [ "$FRESH" = "1" ]; then
  "$PY" seed_demo.py
fi
echo "MCP server:  http://127.0.0.1:8000/mcp"
echo "Alexa+ sim:  http://127.0.0.1:5000"
MCP_URL=http://127.0.0.1:8000/mcp SIM_PORT=5000 "$PY" alexa_sim.py
