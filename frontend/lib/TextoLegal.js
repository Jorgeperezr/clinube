"use client";

/**
 * Textos legales (aviso de privacidad y condiciones de uso).
 *
 * El texto NO está aquí: lo da la API (`/legal/<doc>/`, ver
 * django-api/apps/common/legal.py), porque lo que se registra es que
 * alguien leyó o aceptó una versión concreta, y esa versión tiene que ser
 * la misma en el panel, en la app y en el servidor.
 */

import { useEffect, useState } from "react";

import { apiBase } from "./api";
import { LogoClinube } from "./marca";
import { initColorMode } from "./theme";

/** Pide el documento sin sesión: los dos textos son públicos. */
export function useTextoLegal(doc) {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    fetch(`${apiBase()}/api/v1/legal/${doc}/`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setDatos)
      .catch(() => setError("No se pudo cargar el texto. Vuelve a intentarlo en un momento."));
  }, [doc]);
  return { datos, error };
}

/** Página de lectura: la marca arriba y el texto a un ancho cómodo. */
export function PaginaLegal({ children }) {
  useEffect(() => initColorMode(), []);
  return (
    <div className="legal">
      <header className="legal-cabecera">
        <a href="/" aria-label="Inicio"><LogoClinube alto={30} tinta="#ffffff" acento="var(--mint)" /></a>
      </header>
      <main className="legal-cuerpo">{children}</main>
    </div>
  );
}

export default function TextoLegal({ datos, error }) {
  if (error) return <div className="error-box">{error}</div>;
  if (!datos) return <div className="empty">Cargando…</div>;
  return (
    <article>
      <h1>{datos.titulo}</h1>
      <p className="legal-version">Versión {datos.version} · vigente desde el {datos.vigente_desde}</p>
      {datos.secciones.map((s) => (
        <section key={s.titulo}>
          <h2>{s.titulo}</h2>
          {s.parrafos.map((p) => <p key={p}>{p}</p>)}
        </section>
      ))}
    </article>
  );
}
