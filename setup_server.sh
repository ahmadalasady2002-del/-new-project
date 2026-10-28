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
cat > /usr/local/bin/bot-stop <<EOF
#!/bin/bash
systemctl stop bot && echo "bot stopped (open positions stay as they are)"
EOF
chmod +x /usr/local/bin/bot-report /usr/local/bin/bot-log /usr/local/bin/bot-live /usr/local/bin/bot-stop

systemctl daemon-reload
systemctl enable --now bot

echo
if curl -sf -m 10 https://api.bybit.com/v5/market/time >/dev/null; then
  echo "OK: Bybit reachable. Bot is running in PAPER mode."
else
  echo "WARNING: this server cannot reach Bybit. Make a server in another country."
fi
