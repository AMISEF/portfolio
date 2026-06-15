# راهنمای استقرار روی سرور — portfolio.cryptosmart.site

سرور: `38.252.8.195` (همان سرور cryptosmart.site و trading-journal)
زیردامنه: `portfolio.cryptosmart.site`
فرض: اوبونتو/دبیان با Nginx نصب‌شده (چون دو سایت دیگر روی همین سرورند).

---

## ۰) رکورد DNS
در پنل مدیریت دامنه، یک رکورد **A** بسازید:

```
نوع: A    نام: portfolio    مقدار: 38.252.8.195    TTL: خودکار
```

با `ping portfolio.cryptosmart.site` صحت اتصال را بررسی کنید.

---

## ۱) دریافت کد روی سرور

```bash
sudo mkdir -p /var/www/portfolio
sudo chown -R $USER:$USER /var/www/portfolio
git clone https://github.com/AMISEF/portfolio.git /var/www/portfolio
cd /var/www/portfolio
```

> اگر ریپو **private** شد (توصیه‌شده)، هنگام clone نام کاربری `AMISEF` و
> به‌جای رمز، **توکن گیت‌هاب** را وارد کنید (یا از deploy key استفاده کنید).

---

## ۲) محیط پایتون و وابستگی‌ها

```bash
sudo apt update && sudo apt install -y python3-venv python3-pip
cd /var/www/portfolio
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## ۳) فایل کلیدها (.env)

`.env` در گیت نیست (امنیت). آن را دستی بسازید:

```bash
cp .env.example .env
nano .env   # کلیدهای واقعی CryptoRank / Toobit / Tabdeal / SourceArena را وارد کنید
```

تست سریع:

```bash
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
# در ترمینال دیگر:  curl http://127.0.0.1:8000/health
```

---

## ۴) سرویس دائمی (systemd)

```bash
sudo cp deploy/cryptosmart-hub.service /etc/systemd/system/
sudo chown -R www-data:www-data /var/www/portfolio
sudo systemctl daemon-reload
sudo systemctl enable --now cryptosmart-hub
sudo systemctl status cryptosmart-hub    # باید active (running) باشد
```

لاگ‌ها:  `journalctl -u cryptosmart-hub -f`

---

## ۵) Nginx (ریورس‌پراکسی)

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/portfolio.cryptosmart.site
sudo ln -s /etc/nginx/sites-available/portfolio.cryptosmart.site /etc/nginx/sites-enabled/
sudo nginx -t          # تست صحت پیکربندی
sudo systemctl reload nginx
```

---

## ۶) گواهی SSL (HTTPS)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d portfolio.cryptosmart.site
```

certbot به‌صورت خودکار بلوک HTTPS را اضافه و ریدایرکت ۸۰→۴۴۳ را تنظیم می‌کند.
حالا `https://portfolio.cryptosmart.site` باید بالا باشد. ✅

---

## ۷) به‌روزرسانی در آینده

هر بار که کد جدید push شد:

```bash
cd /var/www/portfolio
git pull
source .venv/bin/activate && pip install -r requirements.txt
sudo systemctl restart cryptosmart-hub
```

---

## نکات

* **بودجهٔ کردیت CryptoRank** خودکار کنترل می‌شود؛ فایل شمارنده در مسیر کار ذخیره می‌شود.
* اگر صفحه دادهٔ «نمونه» نشان داد یعنی سرور به آن API وصل نشده — فایروال/خروجی سرور
  و صحت کلید را بررسی کنید (`curl` مستقیم به همان API از روی سرور).
* فایل `.env` را هرگز commit نکنید (در `.gitignore` هست).

---

## ۸) CI/CD — استقرار خودکار (GitHub Actions)

با این روش، هر بار که کد روی `main` push شود، GitHub به‌صورت خودکار کد را روی سرور
می‌ریزد و سرویس را ری‌استارت می‌کند. دیگر نیازی به `git pull` دستی روی سرور نیست
(و سرور هم نیازی به دسترسی گیت‌هاب ندارد).

فایل گردش‌کار: `.github/workflows/deploy.yml`

### گام ۸-۱: ساخت کلید SSH روی سرور
روی سرور (به‌عنوان root) این دستورها را بزنید:

```bash
ssh-keygen -t ed25519 -f ~/deploy_key -N ""
cat ~/deploy_key.pub >> ~/.ssh/authorized_keys   # اجازهٔ ورود به GitHub Actions
chmod 600 ~/.ssh/authorized_keys
cat ~/deploy_key                                 # این «کلید خصوصی» را کامل کپی کنید
```

> خروجی `cat ~/deploy_key` از خط `-----BEGIN ...` تا `-----END ...` را کامل کپی کنید.

### گام ۸-۲: افزودن Secret در گیت‌هاب
در ریپو: **Settings → Secrets and variables → Actions → New repository secret**

| نام | مقدار |
|---|---|
| `DEPLOY_SSH_KEY` | همان کلید خصوصی که کپی کردید |

### گام ۸-۳: پاک‌کردن کلید خصوصی از سرور (امنیت)
```bash
rm ~/deploy_key
```

### گام ۸-۴: راه‌اندازی اولیهٔ یک‌بار روی سرور
چون CI کد را می‌ریزد ولی `.env` و سرویس را نمی‌سازد، یک‌بار این‌ها را انجام دهید:

```bash
sudo mkdir -p /var/www/portfolio && cd /var/www/portfolio
# اولین push را در گیت‌هاب اجرا کنید تا کد اینجا rsync شود، سپس:
cp .env.example .env && nano .env        # کلیدهای واقعی
sudo cp deploy/cryptosmart-hub.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now cryptosmart-hub
# Nginx و SSL طبق گام‌های ۵ و ۶
```

> برای اینکه `systemctl restart` بدون رمز در CI کار کند، چون کاربر `root` است مشکلی نیست.
> اگر کاربر غیر-root شد، باید یک قانون sudoers بدون رمز برای ری‌استارت سرویس اضافه شود.

بعد از این، هر `git push` روی `main` ⟵ استقرار خودکار. ✅
