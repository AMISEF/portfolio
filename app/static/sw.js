/*
 * Service Worker اپ ALGO HUB (دامنهٔ کامل — هم مدیریت سرمایه و هم /journal).
 *
 *   /app-icon    → آیکن اپ با پس‌زمینهٔ آبی
 *   /app-splash  → لوگوی شفافِ صفحهٔ شروع
 *
 * آیکن و منیفست عمداً کش نمی‌شوند: سرور خودش نسخه‌گذاری می‌کند و هر
 * تصویرِ تازه‌ای که آپلود شود باید بلافاصله دیده شود.
 */
const VERSION = "algohub-v4";
const STATIC_CACHE = VERSION + "-static";
const OFFLINE_URL = "/static/offline.html";

const PRECACHE = [OFFLINE_URL];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((c) => c.addAll(PRECACHE))
      .catch(() => undefined)
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== STATIC_CACHE).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

// فقط دارایی‌های بدون‌تغییر، آیکن و منیفست در این فهرست نیستند.
function isStatic(url) {
  return (
    url.pathname.startsWith("/static/") ||
    url.pathname.startsWith("/journal/_next/static/") ||
    url.pathname.startsWith("/_next/static/")
  );
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return;
  // آیکن/اسپلش/منیفست همیشه مستقیم از شبکه گرفته می‌شوند.
  if (
    url.pathname === "/app-icon" ||
    url.pathname === "/app-splash" ||
    url.pathname === "/manifest.webmanifest"
  ) {
    return;
  }

  if (isStatic(url)) {
    event.respondWith(
      caches.match(req).then((hit) => {
        const network = fetch(req)
          .then((res) => {
            if (res && res.status === 200) {
              const copy = res.clone();
              caches.open(STATIC_CACHE).then((c) => c.put(req, copy)).catch(() => undefined);
            }
            return res;
          })
          .catch(() => hit);
        return hit || network;
      })
    );
    return;
  }

  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).catch(() =>
        caches.match(OFFLINE_URL).then((r) => r || new Response("offline", { status: 503 }))
      )
    );
  }
});

self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch (e) {
    payload = { body: event.data ? event.data.text() : "" };
  }
  const title = payload.title || "ALGO HUB";
  const options = {
    body: payload.body || "",
    icon: "/app-icon?size=192",
    badge: "/app-icon?size=96",
    dir: "rtl",
    lang: "fa",
    tag: payload.tag || "algohub",
    data: { url: payload.url || "/" },
    vibrate: [80, 40, 80],
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if ("focus" in client) {
          client.navigate(target).catch(() => undefined);
          return client.focus();
        }
      }
      return self.clients.openWindow(target);
    })
  );
});

self.addEventListener("message", (event) => {
  if (event.data === "skip-waiting") self.skipWaiting();
});
