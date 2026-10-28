#!/bin/sh
# يشغل البوت ويرجعه يشتغل بروحه إذا طفى
cd "$(dirname "$0")"
while true; do
  python3 -m bot.main
  echo "bot stopped, restarting in 30s..."
  sleep 30
done
