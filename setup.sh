#!/bin/bash
set -e

echo "=== AI Content Fabrique - Server Setup ==="

# 1. Install Docker
echo "[1/4] Installing Docker..."
apt-get update -qq
apt-get install -y -qq ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update -qq
apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 2. Clone repo
echo "[2/4] Cloning repository..."
cd /opt
git clone https://github.com/impowery/AIContentFabrique.git content-factory
cd content-factory

# 3. Create .env file
echo "[3/4] Creating .env file..."
cat > .env << 'EOF'
BOT_TOKEN=
N8N_ENCRYPTION_KEY=$(openssl rand -hex 16)
POSTGRES_PASSWORD=$(openssl rand -base64 32)
POSTIZ_JWT_SECRET=$(openssl rand -hex 32)
N8N_HOST=193.233.19.171
VPS_IP=193.233.19.171
ADMIN_IDS=
LOG_LEVEL=INFO
EOF

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Set your BOT_TOKEN in /opt/content-factory/.env"
echo "2. cd /opt/content-factory && docker compose up -d"
echo "3. Access Postiz: http://193.233.19.171:4007"
echo "4. Access n8n:    http://193.233.19.171:5678"
echo "5. Configure API keys in Postiz UI and n8n UI"
echo ""
