const CACHE_NAME = 'koba-app-v3';
const ASSETS_TO_CACHE = [
    '/',
    '/static/manifest.json',
    '/static/img/icons/icon-192x192.png',
    '/static/img/icons/icon-512x512.png',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'
];

self.addEventListener('install', (event) => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => cache.addAll(ASSETS_TO_CACHE))
            .catch((err) => console.log('SW install cache error ignored:', err))
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cache) => {
                    if (cache !== CACHE_NAME) {
                        return caches.delete(cache);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    // Si la petición NO es GET (ej. POST/PUT/DELETE para guardar productos, subir fotos, facturar),
    // el Service Worker NUNCA debe interceptarla. Pasa directo a la red.
    if (event.request.method !== 'GET') {
        return;
    }

    const url = new URL(event.request.url);

    // No interceptar peticiones a esquemas no-http/https
    if (!url.protocol.startsWith('http')) {
        return;
    }

    // No interceptar ni almacenar en caché rutas dinámicas ni formularios de la aplicación
    const isDynamicRoute = url.pathname.startsWith('/inventory') ||
                          url.pathname.startsWith('/admin') ||
                          url.pathname.startsWith('/sales') ||
                          url.pathname.startsWith('/traslados') ||
                          url.pathname.startsWith('/puntos') ||
                          url.pathname.startsWith('/gastos') ||
                          url.pathname.startsWith('/proveedores') ||
                          url.pathname.startsWith('/bodega') ||
                          url.pathname.startsWith('/asesores') ||
                          url.pathname.startsWith('/arqueo');

    if (isDynamicRoute) {
        return;
    }

    event.respondWith(
        fetch(event.request)
            .then((response) => {
                if (response && response.status === 200 && response.type === 'basic') {
                    const responseClone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseClone);
                    });
                }
                return response;
            })
            .catch(() => {
                return caches.match(event.request);
            })
    );
});
