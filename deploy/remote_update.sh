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

# ---- بازنشست‌کردن نسخهٔ قبلی پورتفولیو و آزادسازی قطعی پورت 8000 ----
# نسخهٔ قبلی پورتفولیو زیر pm2 با نام cryptosmart (و با چند worker) روی پورت 8000
# اجرا می‌شد و پروسه‌های فرزند یتیم، پورت را اشغال نگه می‌داشتند. این اپ و اپ جدید
# هر دو حذف و سپس از نو ساخته می‌شوند. فقط پورت 8000 (مختص پورتفولیو) آزاد می‌شود؛
# اپ‌های tj-backend و tj-frontend روی پورت‌های دیگر دست‌نخورده می‌مانند.
if command -v pm2 >/dev/null 2>&1; then
  pm2 delete cryptosmart 2>/dev/null || true
  pm2 delete "$APP_NAME" 2>/dev/null || true
fi

# آزادسازی هر پروسه‌ای که هنوز روی پورت 8000 گوش می‌دهد (فقط همین پورت).
# نکته: «|| true» و if لازم‌اند تا با set -euo pipefail، نبودِ پروسه (خروجی خالی
# grep) اسکریپت را متوقف نکند.
free_port_8000() {
  local pids p
  pids="$(ss -lptnH 'sport = :8000' 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u || true)"
  if [ -n "$pids" ]; then for p in $pids; do kill "$p" 2>/dev/null || true; done; fi
  sleep 1
  pids="$(ss -lptnH 'sport = :8000' 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u || true)"
  if [ -n "$pids" ]; then for p in $pids; do kill -9 "$p" 2>/dev/null || true; done; fi
  return 0
}
echo "آزادسازی پورت 8000…"
free_port_8000
sleep 1

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

# ---- راه‌اندازی اپ زیر pm2 (پس از حذف نسخه‌های قبلی، شروع تمیز) ----
pm2 start ecosystem.config.js --update-env
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
