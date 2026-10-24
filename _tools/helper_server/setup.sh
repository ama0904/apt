#!/bin/bash
# One-time setup for the apetto helper on ws1 (run by the account owner).
# 1. public https address through Tailscale Funnel -> the helper server on 127.0.0.1:18787
/tmp2/$USER-apetto/ts/tailscale --socket=/tmp2/$USER-apetto/ts.sock funnel --bg http://127.0.0.1:18787
# 2. self-repair check every 5 minutes and after a reboot
( crontab -l 2>/dev/null | grep -v apetto-helper/run.sh
  echo '*/5 * * * * $HOME/apetto-helper/run.sh >/dev/null 2>&1'
  echo '@reboot $HOME/apetto-helper/run.sh >/dev/null 2>&1' ) | crontab -
echo "--- crontab:"; crontab -l
