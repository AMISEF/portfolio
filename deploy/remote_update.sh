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

# ---- بازنشست‌کردن نسخهٔ قبلی پورتفولیو و آزادسازی قطعی پورت 8002 ----
# پورتفولیو روی پورت 8002 اجرا می‌شود. پورت‌های اپ‌های دیگر هرگز لمس نمی‌شوند:
#   cryptosmart=3000، tj-frontend=3001، tj-backend=8001.
# فقط اپِ خودِ پورتفولیو حذف/بازسازی می‌شود.
# ⚠️ هرگز اپ‌های pm2 «cryptosmart»، «tj-frontend» یا «tj-backend» حذف نمی‌شوند.
if command -v pm2 >/dev/null 2>&1; then
  pm2 delete "$APP_NAME" 2>/dev/null || true
fi

# آزادسازی هر پروسه‌ای که هنوز روی پورت 8002 گوش می‌دهد (فقط همین پورت).
# ⚠️ هرگز پورت‌های 3000/3001/8001 (مختص اپ‌های دیگر) لمس نمی‌شوند.
# نکته: «|| true» و if لازم‌اند تا با set -euo pipefail، نبودِ پروسه (خروجی خالی
# grep) اسکریپت را متوقف نکند.
free_port_8002() {
  local pids p
  pids="$(ss -lptnH 'sport = :8002' 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u || true)"
  if [ -n "$pids" ]; then for p in $pids; do kill "$p" 2>/dev/null || true; done; fi
  sleep 1
  pids="$(ss -lptnH 'sport = :8002' 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u || true)"
  if [ -n "$pids" ]; then for p in $pids; do kill -9 "$p" 2>/dev/null || true; done; fi
  return 0
}
echo "آزادسازی پورت 8002…"
free_port_8002
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

# ---- به‌روزرسانی پیکربندی Nginx (پورت ۸۰۰۲) ----
# فقط بلوک portfolio لمس می‌شود؛ به دو سایت دیگر کاری نداریم.
if command -v nginx >/dev/null 2>&1; then
  NGINX_SRC="$APP_DIR/deploy/nginx/portfolio.cryptosmart.site.conf"
  NGINX_AVAIL="/etc/nginx/sites-available/portfolio.cryptosmart.site.conf"
  NGINX_LINK_A="/etc/nginx/sites-enabled/portfolio.cryptosmart.site.conf"
  NGINX_LINK_B="/etc/nginx/sites-enabled/portfolio.cryptosmart.site"

  if [ -f "$NGINX_SRC" ]; then
    cp "$NGINX_SRC" "$NGINX_AVAIL"
    # ایجاد symlink در sites-enabled اگر هیچ‌کدام وجود ندارند
    if [ ! -e "$NGINX_LINK_A" ] && [ ! -e "$NGINX_LINK_B" ]; then
      ln -s "$NGINX_AVAIL" "$NGINX_LINK_B"
    fi
    # اگر لینک قدیمی به جای دیگری اشاره داشت، آن را به conf جدید هدایت کن
    for lnk in "$NGINX_LINK_A" "$NGINX_LINK_B"; do
      if [ -L "$lnk" ] && [ "$(readlink -f "$lnk")" != "$(readlink -f "$NGINX_AVAIL")" ]; then
        ln -sf "$NGINX_AVAIL" "$lnk"
      fi
    done
    nginx -t && systemctl reload nginx \
      && echo "✅ Nginx بارگذاری مجدد شد (portfolio → 8002)." \
      || echo "⚠️ Nginx reload ناموفق بود — لاگ nginx را بررسی کنید."
  fi
fi

# ---- بررسی سلامت HTTP ----
for i in 1 2 3 4 5; do
  if curl -fsS http://127.0.0.1:8002/health >/dev/null 2>&1; then
    echo "✅ بررسی سلامت موفق بود (تلاش $i)."
    curl -fsS http://127.0.0.1:8002/health || true; echo
    git -C "$APP_DIR" log --oneline -1 2>/dev/null || true
    exit 0
  fi
  echo "… انتظار برای بالا آمدن سرویس (تلاش $i)…"
  sleep 2
done

echo "❌ سرویس پاسخ /health نداد. آخرین لاگ‌های pm2:"
pm2 logs "$APP_NAME" --lines 50 --nostream || true
exit 1
