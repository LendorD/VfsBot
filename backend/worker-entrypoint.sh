#!/bin/sh
# Запуск воркера с ВИДИМЫМ браузером в контейнере через виртуальный дисплей.
# Браузер рисуется в Xvfb (:99), x11vnc отдаёт его по VNC, websockify/noVNC —
# в веб. Смотреть: http://localhost:7900/vnc.html
set -e

rm -f /tmp/.X99-lock 2>/dev/null || true
Xvfb :99 -screen 0 1600x900x24 -nolisten tcp &
export DISPLAY=:99
sleep 1

fluxbox >/dev/null 2>&1 &
x11vnc -display :99 -forever -nopw -shared -rfbport 5900 -bg -quiet
websockify --web=/usr/share/novnc 7900 localhost:5900 >/dev/null 2>&1 &

echo "noVNC: открой http://localhost:7900/vnc.html чтобы видеть браузер"
exec uvicorn worker_app:app --host 0.0.0.0 --port 8800
