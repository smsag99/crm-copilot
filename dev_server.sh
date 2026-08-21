#!/usr/bin/env bash
# راه‌اندازی مطمئن سرور برای آزمون — پروسهٔ قبلی را می‌کشد و منتظر آماده‌شدن می‌ماند.
cd "$(dirname "$0")" || exit 1
pkill -f "uvicorn app:app" 2>/dev/null
sleep 1
setsid python -m uvicorn app:app --port 8000 --host 127.0.0.1 > server.log 2>&1 < /dev/null &
for _ in $(seq 1 60); do
  sleep 1
  if curl -sf -o /dev/null http://127.0.0.1:8000/api/health; then echo "آماده"; exit 0; fi
done
echo "سرور بالا نیامد"; tail -20 server.log; exit 1
