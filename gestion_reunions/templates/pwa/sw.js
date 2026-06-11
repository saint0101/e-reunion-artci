// Service Worker — eRéunion ARTCI
const CACHE_NAME = 'ereunion-v1';
const OFFLINE_URL = '/offline/';

// Ressources à mettre en cache lors de l'installation
const PRECACHE_URLS = [
    '/',
    '/mes-diligences/',
    '/reunions/',
    'https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/css/bootstrap.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/js/bootstrap.bundle.min.js',
];

// Installation : précache des ressources critiques
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(PRECACHE_URLS)).then(() => self.skipWaiting())
    );
});

// Activation : nettoyage des anciens caches
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        ).then(() => self.clients.claim())
    );
});

// Fetch : stratégie Network-first pour les pages, Cache-first pour les assets statiques
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);

    // Ne pas intercepter les requêtes admin ou API (POST)
    if (event.request.method !== 'GET') return;
    if (url.pathname.startsWith('/admin/')) return;
    if (url.pathname.startsWith('/api/')) return;

    // Assets statiques (CSS, JS, fonts) → Cache-first
    if (
        url.pathname.startsWith('/static/') ||
        url.hostname.includes('cdnjs.cloudflare.com') ||
        url.hostname.includes('cdn.jsdelivr.net')
    ) {
        event.respondWith(
            caches.match(event.request).then(cached =>
                cached || fetch(event.request).then(response => {
                    if (response.ok) {
                        const clone = response.clone();
                        caches.open(CACHE_NAME).then(c => c.put(event.request, clone));
                    }
                    return response;
                })
            )
        );
        return;
    }

    // Pages HTML → Network-first, fallback cache, puis offline
    event.respondWith(
        fetch(event.request)
            .then(response => {
                if (response.ok) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(c => c.put(event.request, clone));
                }
                return response;
            })
            .catch(() => caches.match(event.request))
    );
});
