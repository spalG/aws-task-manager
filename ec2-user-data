#!/bin/bash
# ─────────────────────────────────────────────────────────────
# TaskFlow — EC2 User Data Bootstrap Script
# Amazon Linux 2023 | Python 3.11 | Flask + Gunicorn + Nginx
# ─────────────────────────────────────────────────────────────
set -euxo pipefail
LOG=/var/log/taskflow-bootstrap.log
exec > >(tee -a $LOG) 2>&1

echo "=== TaskFlow Bootstrap starting $(date) ==="

# ── System packages ──────────────────────────────────────────
dnf update -y
dnf install -y python3.11 python3.11-pip python3.11-devel \
               nginx git gcc mysql curl

# ── App user ─────────────────────────────────────────────────
useradd -r -s /bin/false taskflow || true
mkdir -p /opt/taskflow
chown taskflow:taskflow /opt/taskflow

# ── Clone / copy application ──────────────────────────────────
# Replace with your actual repo URL
# git clone https://github.com/YOUR_ORG/taskflow.git /opt/taskflow
# -- OR -- use S3 artifact:
# aws s3 cp s3://YOUR_BUCKET/taskflow.zip /tmp/taskflow.zip
# unzip /tmp/taskflow.zip -d /opt/taskflow

# For now, assume files are already in /opt/taskflow/
# (CodeDeploy / S3 / SSM will place them)

# ── Python virtual environment ────────────────────────────────
python3.11 -m venv /opt/taskflow/venv
/opt/taskflow/venv/bin/pip install --upgrade pip
/opt/taskflow/venv/bin/pip install -r /opt/taskflow/backend/requirements.txt

# ── Environment file ──────────────────────────────────────────
# Pull secrets from SSM Parameter Store
DB_HOST=$(aws ssm get-parameter --name /taskflow/DB_HOST --query Parameter.Value --output text --region us-east-1)
DB_PASSWORD=$(aws ssm get-parameter --name /taskflow/DB_PASSWORD --with-decryption --query Parameter.Value --output text --region us-east-1)

cat > /opt/taskflow/backend/.env <<EOF
FLASK_ENV=production
PORT=5000
DB_HOST=${DB_HOST}
DB_PORT=3306
DB_USER=admin
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=taskflow
DB_SSL_DISABLED=false
EOF

chmod 600 /opt/taskflow/backend/.env
chown taskflow:taskflow /opt/taskflow/backend/.env

# ── Initialize DB schema ──────────────────────────────────────
mysql -h "$DB_HOST" -u admin -p"$DB_PASSWORD" taskflow \
  < /opt/taskflow/backend/schema.sql || echo "Schema already up to date"

# ── Systemd service ───────────────────────────────────────────
cat > /etc/systemd/system/taskflow.service <<'UNIT'
[Unit]
Description=TaskFlow Flask Application
After=network.target

[Service]
User=taskflow
Group=taskflow
WorkingDirectory=/opt/taskflow/backend
EnvironmentFile=/opt/taskflow/backend/.env
ExecStart=/opt/taskflow/venv/bin/gunicorn \
    --config /opt/taskflow/backend/gunicorn.conf.py \
    app:app
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=taskflow

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable taskflow
systemctl start taskflow

# ── Nginx reverse proxy ───────────────────────────────────────
cat > /etc/nginx/conf.d/taskflow.conf <<'NGINX'
server {
    listen 80;
    server_name _;

    # Serve frontend static files
    root /opt/taskflow/frontend;
    index index.html;

    # Proxy API calls to Gunicorn
    location /api/ {
        proxy_pass         http://127.0.0.1:5000;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }

    location /health {
        proxy_pass http://127.0.0.1:5000;
    }

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Security headers
    add_header X-Frame-Options       DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection      "1; mode=block";

    # Gzip
    gzip on;
    gzip_types text/plain text/css application/json application/javascript;
}
NGINX

nginx -t && systemctl enable nginx && systemctl restart nginx

echo "=== Bootstrap complete $(date) ==="
