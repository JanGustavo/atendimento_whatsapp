const CACHE = 'fortgiro-contingencia-v1'

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.add('/contingencia.html')))
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim())
})

self.addEventListener('fetch', (event) => {
  if (event.request.mode !== 'navigate') return
  event.respondWith((async () => {
    try {
      const response = await fetch(event.request)
      if (response.status < 500) return response
    } catch (_) {
      // O túnel ou a Internet pode estar indisponível.
    }
    return (await caches.match('/contingencia.html')) || Response.error()
  })())
})
