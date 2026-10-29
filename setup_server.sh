#!/bin/bash
# Installs the bot on a fresh Ubuntu server and keeps it running forever.
set -e
REPO=https://github.com/ahmadalasady2002-del/-new-project
BRANCH=claude/trading-bot
DIR=/opt/bot

apt-get update -y
apt-get install -y python3 git nano curl

if [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull
else
  git clone -b "$BRANCH" "$REPO" "$DIR"
fi
[ -f "$DIR/.env" ] || cp "$DIR/.env.example" "$DIR/.env"
chmod 600 "$DIR/.env"

cat > /etc/systemd/system/bot.service <<EOF
[Unit]
Description=Crypto trading bot
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=$DIR
ExecStart=/usr/bin/python3 -m bot.main
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Short commands for the phone
cat > /usr/local/bin/bot-report <<EOF
#!/bin/bash
cd $DIR && python3 -m bot.main --report
EOF
cat > /usr/local/bin/bot-log <<EOF
#!/bin/bash
tail -n 30 $DIR/bot.log
EOF
cat > /usr/local/bin/bot-live <<EOF
#!/bin/bash
set -e
read -p "Bybit API Key: " K
read -p "Bybit API Secret: " S
cd $DIR
sed -i "s|^BYBIT_API_KEY=.*|BYBIT_API_KEY=\$K|; s|^BYBIT_API_SECRET=.*|BYBIT_API_SECRET=\$S|; s|^LIVE_TRADING=.*|LIVE_TRADING=yes|" .env
[ -f state.json ] && mv state.json "state_paper_\$(date +%s).json"
systemctl restart bot
sleep 15
tail -n 8 bot.log
EOF
cat > /usr/local/bin/bot-update <<EOF
#!/bin/bash
git -C $DIR pull -q && systemctl restart bot && echo "bot updated and restarted"
EOF
cat > /usr/local/bin/bot-test <<'EOF'
#!/bin/bash
cd /opt/bot && python3 -m bot.backtest "$@"
EOF
cat > /usr/local/bin/bot-telegram <<'EOF'
#!/bin/bash
# Connects Telegram alerts: asks for the BotFather token, then finds your chat id.
set -e
read -p "Telegram bot token: " T
echo "Now open your bot in Telegram, press Start and send it any message. Waiting..."
ID=""
for i in $(seq 1 60); do
  ID=$(curl -s "https://api.telegram.org/bot$T/getUpdates" | python3 -c "
import sys, json
r = json.load(sys.stdin).get('result', [])
msgs = [u['message'] for u in r if 'message' in u]
print(msgs[-1]['chat']['id'] if msgs else '')" 2>/dev/null || true)
  [ -n "$ID" ] && break
  sleep 3
done
if [ -z "$ID" ]; then echo "No message received. Run bot-telegram again."; exit 1; fi
cd /opt/bot
for kv in "TELEGRAM_TOKEN=$T" "TELEGRAM_CHAT_ID=$ID"; do
  k="${kv%%=*}"
  if grep -q "^$k=" .env; then sed -i "s|^$k=.*|$kv|" .env; else echo "$kv" >> .env; fi
done
systemctl restart bot
echo "OK: Telegram connected. You will get a message now."
EOF
cat > /usr/local/bin/bot-stop <<EOF
#!/bin/bash
systemctl stop bot && echo "bot stopped (open positions stay as they are)"
EOF
chmod +x /usr/local/bin/bot-report /usr/local/bin/bot-log /usr/local/bin/bot-live /usr/local/bin/bot-stop /usr/local/bin/bot-update /usr/local/bin/bot-test /usr/local/bin/bot-telegram

systemctl daemon-reload
systemctl enable bot
systemctl restart bot

echo
if curl -sf -m 10 https://api.bybit.com/v5/market/time >/dev/null; then
  echo "OK: Bybit reachable. Bot is running in PAPER mode."
else
  echo "WARNING: this server cannot reach Bybit. Make a server in another country."
fi
