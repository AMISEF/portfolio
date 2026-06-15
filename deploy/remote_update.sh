#!/usr/bin/env bash
# اسکریپت به‌روزرسانی روی سرور — توسط GitHub Actions از طریق SSH اجرا می‌شود.
# کد قبلاً با rsync روی سرور قرار گرفته؛ این اسکریپت فقط محیط را آماده و سرویس را
# ری‌استارت می‌کند. idempotent است (اجرای چندباره مشکلی ندارد).
set -euo pipefail

APP_DIR="/var/www/portfolio"
cd "$APP_DIR"

# ساخت محیط مجازی اگر وجود نداشت
if [ ! -d ".venv" ]; then
  echo "ایجاد محیط مجازی پایتون…"
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# ری‌استارت سرویس (اگر هنوز نصب نشده، پیام راهنما)
if systemctl list-unit-files | grep -q '^cryptosmart-hub.service'; then
  sudo systemctl restart cryptosmart-hub
  echo "✅ سرویس cryptosmart-hub ری‌استارت شد."
else
  echo "⚠️ سرویس systemd هنوز نصب نشده. یک‌بار راه‌اندازی اولیه را طبق DEPLOY.md انجام دهید."
fi
