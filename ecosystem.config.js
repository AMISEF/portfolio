// پیکربندی pm2 برای CryptoSmart Hub.
// اپ پایتون (uvicorn) زیر pm2 اجرا می‌شود و روی 127.0.0.1:8000 می‌نشیند تا
// Nginx به آن پراکسی کند. راه‌اندازی:  pm2 start ecosystem.config.js
module.exports = {
  apps: [
    {
      name: "cryptosmart-portfolio",
      // از پایتون محیط مجازی پروژه استفاده می‌شود (مسیر مطلق روی سرور)
      script: ".venv/bin/uvicorn",
      args: "app.main:app --host 127.0.0.1 --port 8000 --workers 2",
      cwd: "/var/www/portfolio",
      interpreter: "none",
      env: { PYTHONUNBUFFERED: "1" },
      autorestart: true,
      max_restarts: 10,
      watch: false,
    },
  ],
};
