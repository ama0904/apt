#!/bin/bash
# apetto helper on ws1. Keeps the tunnel (tailscaled) and the helper server running.
# Safe to run any time; cron runs it every 5 minutes. /tmp2 can be wiped by the lab, so the
# big files there (node_modules, model, tailscale binaries) are re-created when missing.
set -u
APP="$HOME/apetto-helper"
RT="/tmp2/$USER-apetto"
PORT=18787
mkdir -p "$RT/logs" "$APP/logs" "$APP/ts"
exec 9>"$RT/.lock"; flock -n 9 || exit 0
say() { echo "$(date '+%F %T') $*" >> "$APP/logs/run.log"; }
# keep logs small (home quota is 200 MB)
for f in "$APP/logs/run.log" "$RT/logs/"*.log; do [ -f "$f" ] && [ "$(stat -c %s "$f")" -gt 5000000 ] && tail -c 1000000 "$f" > "$f.tmp" && mv "$f.tmp" "$f"; done

# 1. node packages (in /tmp2, linked from the app folder)
if [ ! -d "$RT/node_modules/@huggingface/transformers" ] || ! cmp -s "$APP/package.json" "$RT/package.json"; then
  cp "$APP/package.json" "$RT/package.json"
  (cd "$RT" && npm install --omit=dev --no-audit --no-fund >> "$RT/logs/npm.log" 2>&1) && say "npm install ok" || say "npm install failed"
fi
ln -sfn "$RT/node_modules" "$APP/node_modules"

# 2. tailscale (userspace mode, no root needed)
if [ ! -x "$RT/ts/tailscaled" ]; then
  V=$(curl -fsS 'https://pkgs.tailscale.com/stable/?mode=json' | python3 -c 'import json,sys;print(json.load(sys.stdin)["TarballsVersion"])')
  if [ -n "$V" ] && curl -fsSL "https://pkgs.tailscale.com/stable/tailscale_${V}_amd64.tgz" | tar xz -C "$RT"; then
    rm -rf "$RT/ts"; mv "$RT/tailscale_${V}_amd64" "$RT/ts"; say "tailscale $V installed"
  else say "tailscale download failed"; fi
fi
if ! pgrep -u "$USER" -f "$RT/ts/tailscaled" > /dev/null; then
  nohup "$RT/ts/tailscaled" --tun=userspace-networking --statedir="$APP/ts" --socket="$RT/ts.sock" --port=0 \
    >> "$RT/logs/tailscaled.log" 2>&1 < /dev/null &
  say "tailscaled started"
fi

# 3. helper server
if ! pgrep -u "$USER" -f "apetto-helper/server.mjs" > /dev/null && ! pgrep -u "$USER" -x apetto-helper > /dev/null; then
  APP="$APP" RT="$RT" PORT=$PORT nohup nice -n 5 node "$APP/server.mjs" >> "$RT/logs/server.log" 2>&1 < /dev/null &
  say "server started"
fi
