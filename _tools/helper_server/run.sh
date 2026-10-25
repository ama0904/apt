#!/bin/bash
# apetto helper on ws1. Keeps the tunnel (tailscaled) and the helper server running.
# Safe to run any time; cron runs it every 5 minutes. /tmp2 can be wiped by the lab, so the
# big files there (node_modules, model, tailscale binaries) are re-created when missing.
set -u
APP="$HOME/apetto-helper"
RT="/tmp2/$USER-apetto"
PORT=18787
mkdir -p "$RT/logs" "$APP/logs" "$APP/ts"
# lock so two runs never overlap; children must not inherit it (9>&-), or the lock stays held forever
exec 9>"$RT/.run.lock"; flock -n 9 || exit 0
say() { echo "$(date '+%F %T') $*" >> "$APP/logs/run.log"; }
# keep logs small (home quota is 200 MB)
for f in "$APP/logs/run.log" "$RT/logs/"*.log; do [ -f "$f" ] && [ "$(stat -c %s "$f")" -gt 5000000 ] && tail -c 1000000 "$f" > "$f.tmp" && mv "$f.tmp" "$f"; done

# 1. node packages (in /tmp2, linked from the app folder)
if [ ! -d "$RT/node_modules/@huggingface/transformers" ] || ! cmp -s "$APP/package.json" "$RT/package.json"; then
  cp "$APP/package.json" "$RT/package.json"
  (cd "$RT" && npm install 9>&- --omit=dev --no-audit --no-fund >> "$RT/logs/npm.log" 2>&1) && say "npm install ok" || say "npm install failed"
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
    >> "$RT/logs/tailscaled.log" 2>&1 < /dev/null 9>&- &
  say "tailscaled started"
fi

# 3. small AI model for chat (llama.cpp, CPU only, 12 threads, low priority)
LLAMA_TAG=b11539
GGUF="$RT/models-gguf/Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
if [ ! -x "$RT/llm/llama/llama-server" ]; then
  mkdir -p "$RT/llm" && rm -rf "$RT/llm/llama" "$RT/llm/llama-$LLAMA_TAG"
  if curl -fsSL "https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA_TAG/llama-$LLAMA_TAG-bin-ubuntu-x64.tar.gz" | tar xz -C "$RT/llm"; then
    mv "$RT/llm/llama-$LLAMA_TAG" "$RT/llm/llama"; say "llama.cpp $LLAMA_TAG installed"
  else say "llama.cpp download failed"; fi
fi
ln -sfn llama-server "$RT/llm/llama/apetto-llm"   # a clear process name for the lab admins
if [ ! -s "$GGUF" ]; then
  mkdir -p "$RT/models-gguf"
  curl -fsSL -o "$GGUF.part" https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf \
    && mv "$GGUF.part" "$GGUF" && say "AI model downloaded" || say "AI model download failed"
fi
if [ -s "$GGUF" ] && [ -x "$RT/llm/llama/llama-server" ] && ! pgrep -u "$USER" -x apetto-llm > /dev/null; then
  LD_LIBRARY_PATH="$RT/llm/llama" nohup nice -n 10 "$RT/llm/llama/apetto-llm" -m "$GGUF" -t 12 -c 16384 -np 1 \
    --host 127.0.0.1 --port 18788 --no-webui >> "$RT/logs/llm.log" 2>&1 < /dev/null 9>&- &
  say "AI model started"
fi

# 4. helper server
if ! pgrep -u "$USER" -f "apetto-helper/server.mjs" > /dev/null && ! pgrep -u "$USER" -x apetto-helper > /dev/null; then
  APP="$APP" RT="$RT" PORT=$PORT nohup nice -n 5 node "$APP/server.mjs" >> "$RT/logs/server.log" 2>&1 < /dev/null 9>&- &
  say "server started"
fi

# 5. FitStudio (AI fitting room) bridge, only if it has been set up in ~/apetto-fit:
#    code in ~/apetto-fit/src (settings in its .env), browser profile, photos and logs in /tmp2.
#    The Google login is imported from ~/apetto-fit/state.json when /tmp2 lost the profile.
FIT="$HOME/apetto-fit"; FRT="/tmp2/$USER-fit"
if [ -f "$FIT/src/server.js" ] && [ -f "$FIT/src/.env" ]; then
  mkdir -p "$FRT/logs" && chmod 700 "$FRT"
  if [ ! -d "$FRT/node_modules/playwright" ] || ! cmp -s "$FIT/src/package-lock.json" "$FRT/package-lock.json"; then
    cp "$FIT/src/package.json" "$FIT/src/package-lock.json" "$FRT/"
    (cd "$FRT" && npm ci 9>&- --omit=dev --no-audit --no-fund >> "$FRT/logs/npm.log" 2>&1) && say "fit npm ok" || say "fit npm failed"
  fi
  ln -sfn "$FRT/node_modules" "$FIT/src/node_modules"
  # Playwright catches SIGTERM (it only closes the browsers), so the node process needs SIGKILL after that
  fit_stop() { kill "$1" 2>/dev/null; sleep 5; kill -9 "$1" 2>/dev/null; }
  FPID=$(pgrep -u "$USER" -f "apetto-fit/src/server.js" | head -1)
  if [ -n "$FPID" ]; then
    # restart it if it stops answering for 3 runs in a row (15 minutes)
    if curl -fsS -m 20 http://127.0.0.1:18789/api/health > /dev/null; then rm -f "$FRT/.bad"
    else echo x >> "$FRT/.bad"; [ "$(wc -l < "$FRT/.bad")" -ge 3 ] && rm -f "$FRT/.bad"; fit_stop "$FPID"; say "fit server hung, restarted"; FPID=""; fi
  fi
  if [ -z "$FPID" ]; then
    pkill -u "$USER" -f "$FRT/playwright_session" 2>/dev/null
    # exec, and the lock closed for the whole subshell: a waiting shell copy would hold the lock forever
    (cd "$FIT/src" && exec nohup nice -n 5 node "$FIT/src/server.js") >> "$FRT/logs/server.log" 2>&1 < /dev/null 9>&- &
    say "fit server started"
  fi
fi
