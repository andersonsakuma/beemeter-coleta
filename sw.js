// Service worker da Coleta de Campo: guarda a página no aparelho para funcionar sem internet
// (iPhone e Android pelo navegador). Com internet, busca a versão nova; sem internet, usa a guardada.
// Os registros NÃO passam por aqui: ficam no armazenamento do próprio navegador.
const VERSAO = "coleta-1.1";
const ARQUIVOS = ["./", "./index.html", "./manifest.webmanifest", "./icone-192.png", "./icone-512.png",
  "./icone-maskable-512.png", "./apple-touch-icon.png"];

self.addEventListener("install", ev => {
  ev.waitUntil(caches.open(VERSAO).then(c => c.addAll(ARQUIVOS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", ev => {
  ev.waitUntil(caches.keys()
    .then(nomes => Promise.all(nomes.filter(n => n !== VERSAO).map(n => caches.delete(n))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", ev => {
  const req = ev.request;
  if (req.method !== "GET" || new URL(req.url).origin !== self.location.origin) return;
  if (req.mode === "navigate") {
    // página: rede primeiro (pega atualizações), cópia guardada quando não há sinal
    ev.respondWith(fetch(req).then(r => {
      if (r.ok) { const copia = r.clone(); caches.open(VERSAO).then(c => c.put("./index.html", copia)); }
      return r;
    }).catch(() => caches.match("./index.html")));
    return;
  }
  ev.respondWith(caches.match(req, { ignoreSearch: true }).then(r => r || fetch(req)));
});
