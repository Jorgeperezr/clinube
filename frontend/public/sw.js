/*
 * Service worker del panel instalable (la app del personal).
 *
 * Qué guarda en el dispositivo: SOLO el envoltorio del panel —las páginas
 * estáticas, el JS y el CSS de Next, las fuentes y los iconos—, para que
 * la app abra al instante y diga algo útil sin conexión.
 *
 * Qué NO guarda nunca: nada de /api/, /media/ ni /admin/. Ahí van datos
 * de salud, y un teléfono o una tableta de recepción se pierde, se presta
 * o lo usa más de una persona. Esas peticiones ni siquiera pasan por aquí:
 * van directas a la red, como si no hubiera service worker.
 *
 * Estrategias:
 *   · /_next/static/, /fonts/, /icons/  → primero la caché. Llevan un
 *     hash en el nombre o no cambian: si el nombre es el mismo, el
 *     contenido también.
 *   · páginas (navegación)              → primero la red, para que cada
 *     despliegue se vea en cuanto hay conexión; sin red, la copia
 *     guardada de esa página, y si no la hay, /sin-conexion/.
 *
 * Al cambiar algo de este archivo, subir VERSION: el navegador instala el
 * nuevo y el «activate» borra las cachés de la versión anterior.
 */

const VERSION = "v1";
const ENVOLTORIO = `clinube-envoltorio-${VERSION}`;
const ESTATICOS = `clinube-estaticos-${VERSION}`;
const MAX_ESTATICOS = 300;
const PRECARGA = ["/sin-conexion/", "/icons/icon-192.png", "/manifest.webmanifest"];
const NUNCA = ["/api/", "/media/", "/admin/", "/whatsapp/", "/static/"];

self.addEventListener("install", (evento) => {
  evento.waitUntil(
    caches.open(ENVOLTORIO).then((c) => c.addAll(PRECARGA)).then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches.keys()
      .then((nombres) => Promise.all(
        nombres.filter((n) => n.startsWith("clinube-") && n !== ENVOLTORIO && n !== ESTATICOS)
          .map((n) => caches.delete(n)),
      ))
      .then(() => self.clients.claim()),
  );
});

async function recortar(cache) {
  const claves = await cache.keys();
  for (const vieja of claves.slice(0, Math.max(0, claves.length - MAX_ESTATICOS))) {
    await cache.delete(vieja);
  }
}

async function primeroCache(peticion) {
  const cache = await caches.open(ESTATICOS);
  const guardada = await cache.match(peticion);
  if (guardada) return guardada;
  const respuesta = await fetch(peticion);
  if (respuesta.ok) {
    await cache.put(peticion, respuesta.clone());
    recortar(cache);
  }
  return respuesta;
}

// La página se guarda sin la consulta: /panel/paciente/?id=… es el mismo
// HTML para todos los pacientes (los datos llegan después, por la API), y
// guardar una copia por paciente llenaría la caché de duplicados.
async function primeroRed(peticion) {
  const cache = await caches.open(ENVOLTORIO);
  const clave = new URL(peticion.url).pathname;
  try {
    const respuesta = await fetch(peticion);
    if (respuesta.ok) await cache.put(clave, respuesta.clone());
    return respuesta;
  } catch {
    return (await cache.match(clave))
      || (await cache.match("/sin-conexion/"))
      || Response.error();
  }
}

self.addEventListener("fetch", (evento) => {
  const peticion = evento.request;
  if (peticion.method !== "GET") return;
  const url = new URL(peticion.url);
  if (url.origin !== self.location.origin) return;
  if (NUNCA.some((p) => url.pathname.startsWith(p))) return;

  if (peticion.mode === "navigate") {
    evento.respondWith(primeroRed(peticion));
  } else if (/^\/(_next\/static|fonts|icons)\//.test(url.pathname)) {
    evento.respondWith(primeroCache(peticion));
  }
});
