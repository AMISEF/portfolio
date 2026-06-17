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

# اصلاح مالکیت برای کاربر سرویس (پس از rsync با root)
if id www-data >/dev/null 2>&1; then
  chown -R www-data:www-data "$APP_DIR" 2>/dev/null || true
fi

# ری‌استارت سرویس (اگر هنوز نصب نشده، پیام راهنما)
if systemctl list-unit-files | grep -q '^cryptosmart-hub.service'; then
  sudo systemctl restart cryptosmart-hub
  echo "✅ سرویس cryptosmart-hub ری‌استارت شد."

  # بررسی سلامت: چند ثانیه صبر کن و /health را بزن تا خطای راه‌اندازی پنهان نماند
  sleep 3
  for i in 1 2 3 4 5; do
    if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
      echo "✅ بررسی سلامت موفق بود (تلاش $i)."
      # نمایش کامیت در حال اجرا برای اطمینان از به‌روزرسانی
      git -C "$APP_DIR" log --oneline -1 2>/dev/null || true
      exit 0
    fi
    echo "… انتظار برای بالا آمدن سرویس (تلاش $i)…"
    sleep 2
  done
  echo "❌ سرویس بعد از ری‌استارت پاسخ /health نداد. آخرین لاگ‌ها:"
  sudo journalctl -u cryptosmart-hub -n 40 --no-pager || true
  exit 1
else
  echo "⚠️ سرویس systemd هنوز نصب نشده. یک‌بار راه‌اندازی اولیه را طبق DEPLOY.md انجام دهید."
fi
