#!/usr/bin/env bash
# به‌روزرسانی روی سرور — توسط GitHub Actions از طریق SSH (کاربر root) اجرا می‌شود.
# کد قبلاً با rsync روی سرور قرار گرفته؛ این اسکریپت محیط را آماده، سرویس pm2 را
# (در صورت نبود) راه‌اندازی و سپس بارگذاری مجدد می‌کند. idempotent است.
#
# نکتهٔ مهم: این اسکریپت فقط به اپ «portfolio» کار دارد و به دو سایت دیگر روی
# سرور (cryptosmart.site و trading-journal) و پیکربندی Nginx آن‌ها دست نمی‌زند.
set -euo pipefail

APP_DIR="/var/www/portfolio"
APP_NAME="cryptosmart-portfolio"
cd "$APP_DIR"

# ---- محیط مجازی پایتون ----
if [ ! -d ".venv" ]; then
  echo "ایجاد محیط مجازی پایتون…"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
deactivate

# ---- غیرفعال‌کردن سرویس systemd قدیمی (اگر از فاز قبل باقی مانده) ----
if systemctl list-unit-files 2>/dev/null | grep -q '^cryptosmart-hub.service'; then
  echo "غیرفعال‌سازی سرویس systemd قدیمی…"
  sudo systemctl stop cryptosmart-hub 2>/dev/null || true
  sudo systemctl disable cryptosmart-hub 2>/dev/null || true
fi

# ---- اطمینان از نصب pm2 ----
if ! command -v pm2 >/dev/null 2>&1; then
  if command -v npm >/dev/null 2>&1; then
    echo "نصب pm2 (سراسری)…"
    npm install -g pm2
  else
    echo "❌ Node/npm روی سرور نصب نیست. یک‌بار نصب کنید: 'apt-get install -y nodejs npm' سپس دوباره دیپلوی کنید."
    exit 1
  fi
fi

# ---- راه‌اندازی/بارگذاری مجدد اپ زیر pm2 ----
# startOrReload هم اولین اجرا را پوشش می‌دهد هم به‌روزرسانی بدون قطعی را.
pm2 startOrReload ecosystem.config.js --update-env
pm2 save
# فعال‌سازی اجرای خودکار pm2 پس از ری‌استارت سرور (بی‌خطر اگر قبلاً تنظیم شده)
pm2 startup systemd -u root --hp /root >/dev/null 2>&1 || true

# ---- بررسی سلامت ----
sleep 3
for i in 1 2 3 4 5; do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "✅ بررسی سلامت موفق بود (تلاش $i)."
    git -C "$APP_DIR" log --oneline -1 2>/dev/null || true
    pm2 describe "$APP_NAME" | grep -E 'status|uptime' || true
    exit 0
  fi
  echo "… انتظار برای بالا آمدن سرویس (تلاش $i)…"
  sleep 2
done

echo "❌ سرویس پس از بارگذاری مجدد پاسخ /health نداد. آخرین لاگ‌های pm2:"
pm2 logs "$APP_NAME" --lines 40 --nostream || true
exit 1
