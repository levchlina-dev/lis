#!/bin/bash
set -e

ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-""}
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:-"8739119459:AAEQfgQ3LOqom0-_P8U9LdwCvsbJppIkLMo"}

cd /opt
git clone https://github.com/levchlina-dev/lis.git 2>/dev/null || (cd lis && git pull)
cd lis
git checkout claude/setup-code-channels-agent-XB4Is

if [ -n "$ANTHROPIC_API_KEY" ]; then
  cat > .env <<EOF
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
EOF
  echo ".env configured"
elif [ ! -f .env ]; then
  echo "ERROR: ANTHROPIC_API_KEY not set and .env not found"
  echo "Run: ANTHROPIC_API_KEY=your-key bash deploy.sh"
  exit 1
else
  echo "Using existing .env"
fi

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -q

pkill -f "main.py telegram" 2>/dev/null || true
nohup venv/bin/python main.py telegram > bot.log 2>&1 &
echo "Bot started, PID: $!"
sleep 2
tail -5 bot.log
