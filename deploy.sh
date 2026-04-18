#!/bin/bash
set -e

cd /opt
git clone https://github.com/levchlina-dev/lis.git 2>/dev/null || (cd lis && git pull)
cd lis
git checkout claude/setup-code-channels-47WZj
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -q

pkill -f "main.py telegram" 2>/dev/null || true
nohup venv/bin/python main.py telegram > bot.log 2>&1 &
echo "Bot PID: $!"
sleep 2
tail -5 bot.log
