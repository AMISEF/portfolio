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

# ---- بازنشست‌کردن اپ pm2 قدیمیِ پورتفولیو (به نام «cryptosmart») ----
# نسخهٔ قبلی پورتفولیو زیر pm2 با نام cryptosmart روی همان پورت 8000 اجرا می‌شد و
# مانع راه‌اندازی اپ جدید می‌شد. فقط همین اپ حذف می‌شود؛ به اپ‌های دیگر (tj-backend,
# tj-frontend و هر سرویس دیگری روی سرور) دست زده نمی‌شود.
if command -v pm2 >/dev/null 2>&1; then
  if pm2 describe cryptosmart >/dev/null 2>&1; then
    echo "حذف اپ pm2 قدیمی «cryptosmart» برای آزادسازی پورت 8000…"
    pm2 delete cryptosmart 2>/dev/null || true
  fi
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

# ---- بررسی وضعیت pm2 اپ جدید (نباید errored باشد) ----
sleep 3
PM2_STATUS="$(pm2 jlist 2>/dev/null | python3 -c "import sys,json;
apps=json.load(sys.stdin)
m=[a for a in apps if a.get('name')=='$APP_NAME']
print(m[0]['pm2_env']['status'] if m else 'missing')" 2>/dev/null || echo unknown)"
echo "وضعیت pm2 برای $APP_NAME: $PM2_STATUS"
if [ "$PM2_STATUS" = "errored" ] || [ "$PM2_STATUS" = "missing" ]; then
  echo "❌ اپ جدید بالا نیامد ($PM2_STATUS). آخرین لاگ‌ها:"
  pm2 logs "$APP_NAME" --lines 50 --nostream || true
  exit 1
fi

# ---- بررسی سلامت HTTP ----
for i in 1 2 3 4 5; do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "✅ بررسی سلامت موفق بود (تلاش $i)."
    curl -fsS http://127.0.0.1:8000/health || true; echo
    git -C "$APP_DIR" log --oneline -1 2>/dev/null || true
    exit 0
  fi
  echo "… انتظار برای بالا آمدن سرویس (تلاش $i)…"
  sleep 2
done

echo "❌ سرویس پاسخ /health نداد. آخرین لاگ‌های pm2:"
pm2 logs "$APP_NAME" --lines 50 --nostream || true
exit 1
