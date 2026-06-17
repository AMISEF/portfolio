// پیکربندی pm2 برای CryptoSmart Hub (پورتفولیو).
// اپ پایتون (uvicorn) زیر pm2 اجرا می‌شود و روی 127.0.0.1:8002 می‌نشیند تا
// Nginx به آن پراکسی کند. راه‌اندازی:  pm2 start ecosystem.config.js
// پورت‌های مشغول روی سرور: cryptosmart=3000، tj-frontend=3001، tj-backend=8001.
// پورتفولیو پورت نوِ 8002 را می‌گیرد تا با هیچ‌کدام تداخل نداشته باشد.
module.exports = {
  apps: [
    {
      name: "cryptosmart-portfolio",
      // از پایتون محیط مجازی پروژه استفاده می‌شود (مسیر مطلق روی سرور).
      // تک‌پروسه (بدون --workers) تا pm2 دقیقاً یک PID را مدیریت کند و هنگام
      // ری‌استارت، پروسهٔ فرزند یتیم روی پورت ۸۰۰۲ باقی نماند.
      script: ".venv/bin/uvicorn",
      args: "app.main:app --host 127.0.0.1 --port 8002",
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
