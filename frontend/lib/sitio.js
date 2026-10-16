"use client";

/**
 * Direcciones de la página pública.
 *
 * La portada vive en el dominio raíz (clinube.com) y la app en
 * app.clinube.com. Son orígenes distintos —la sesión de uno no vale en
 * el otro—, así que «Entrar» lleva siempre al de la app. En local, o
 * entrando ya por app.*, se queda en el mismo sitio.
 */

import { useEffect, useState } from "react";

export const TIENDA_IOS = process.env.NEXT_PUBLIC_URL_APP_STORE || "";
export const TIENDA_ANDROID = process.env.NEXT_PUBLIC_URL_GOOGLE_PLAY || "";
export const CORREO_CONTACTO = process.env.NEXT_PUBLIC_CORREO_CONTACTO || "support.clinube@gmail.com";

export function urlApp(ruta = "/login/") {
  if (typeof window === "undefined") return ruta;
  const { hostname, protocol } = window.location;
  const esDominio = /^(www\.)?[a-z0-9-]+\.[a-z]{2,}$/i.test(hostname);
  if (!esDominio) return ruta;               // localhost, una IP o ya en app.*
  return `${protocol}//app.${hostname.replace(/^www\./, "")}${ruta}`;
}

/** La dirección de la app, resuelta ya en el navegador (el HTML se genera sin él). */
export function useUrlApp(ruta = "/login/") {
  const [url, setUrl] = useState(ruta);
  useEffect(() => { setUrl(urlApp(ruta)); }, [ruta]);
  return url;
}
