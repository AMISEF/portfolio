// پیکربندی pm2 برای CryptoSmart Hub.
// اپ پایتون (uvicorn) زیر pm2 اجرا می‌شود و روی 127.0.0.1:8001 می‌نشیند تا
// Nginx به آن پراکسی کند. راه‌اندازی:  pm2 start ecosystem.config.js
// پورت 8001 تا با سایت اصلی cryptosmart.site (پورت 8000) تداخل نداشته باشد.
module.exports = {
  apps: [
    {
      name: "cryptosmart-portfolio",
      // از پایتون محیط مجازی پروژه استفاده می‌شود (مسیر مطلق روی سرور).
      // تک‌پروسه (بدون --workers) تا pm2 دقیقاً یک PID را مدیریت کند و هنگام
      // ری‌استارت، پروسهٔ فرزند یتیم روی پورت ۸۰۰۱ باقی نماند.
      script: ".venv/bin/uvicorn",
      args: "app.main:app --host 127.0.0.1 --port 8001",
      cwd: "/var/www/portfolio",
      interpreter: "none",
      env: { PYTHONUNBUFFERED: "1" },
      autorestart: true,
      max_restarts: 10,
      kill_timeout: 5000,
      watch: false,
    },
  ],
};
