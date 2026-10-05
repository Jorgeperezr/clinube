"use client";

/**
 * El panel como app instalable (la app del personal en Android e iOS).
 *
 * Dos cosas, las dos al cargar cualquier página:
 *
 *   1. Registra el service worker (public/sw.js) — solo en la compilación
 *      de producción. En desarrollo guardaría páginas viejas y haría
 *      creer que un cambio no funciona.
 *   2. Guarda el aviso de instalación que Chrome y Edge lanzan UNA vez
 *      (`beforeinstallprompt`). Si nadie lo captura en ese momento se
 *      pierde, y el botón «Instalar» de Mis preferencias ya no podría
 *      abrirlo. Safari no lo lanza nunca: en iPhone y iPad se instala
 *      desde «Compartir → Añadir a pantalla de inicio».
 */

import { useEffect, useState } from "react";

export default function AppInstalable() {
  useEffect(() => {
    if (process.env.NODE_ENV === "production" && "serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
    const guardar = (e) => {
      e.preventDefault();
      window.__avisoInstalacion = e;
      window.dispatchEvent(new Event("instalacion-disponible"));
    };
    const instalada = () => {
      window.__avisoInstalacion = null;
      window.dispatchEvent(new Event("instalacion-disponible"));
    };
    window.addEventListener("beforeinstallprompt", guardar);
    window.addEventListener("appinstalled", instalada);
    return () => {
      window.removeEventListener("beforeinstallprompt", guardar);
      window.removeEventListener("appinstalled", instalada);
    };
  }, []);
  return null;
}

/** ¿Se está usando ya como app instalada? */
export function esAppInstalada() {
  if (typeof window === "undefined") return false;
  return window.matchMedia?.("(display-mode: standalone)").matches || window.navigator.standalone === true;
}

/** Cómo se puede instalar en este navegador: "aviso", "ios", "instalada" o null. */
export function useInstalacion() {
  const [estado, setEstado] = useState(null);
  useEffect(() => {
    const calcular = () => {
      if (esAppInstalada()) return setEstado("instalada");
      if (window.__avisoInstalacion) return setEstado("aviso");
      const ua = navigator.userAgent;
      const ios = /iPad|iPhone|iPod/.test(ua) || (ua.includes("Macintosh") && navigator.maxTouchPoints > 1);
      setEstado(ios ? "ios" : null);
    };
    calcular();
    window.addEventListener("instalacion-disponible", calcular);
    return () => window.removeEventListener("instalacion-disponible", calcular);
  }, []);
  return estado;
}

/** Abre el aviso de instalación de Chrome/Edge. Devuelve true si se aceptó. */
export async function instalar() {
  const aviso = window.__avisoInstalacion;
  if (!aviso) return false;
  aviso.prompt();
  const { outcome } = await aviso.userChoice;
  window.__avisoInstalacion = null;
  window.dispatchEvent(new Event("instalacion-disponible"));
  return outcome === "accepted";
}
