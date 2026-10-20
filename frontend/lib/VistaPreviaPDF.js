"use client";

/**
 * Vista previa de un documento antes de descargarlo o imprimirlo.
 *
 * El PDF se genera en el servidor como siempre; aquí se pide, se muestra
 * y, si el documento tiene partes opcionales (`componentes`), se puede
 * marcar o desmarcar cada una: se vuelve a pedir con `?incluir=a,b` y la
 * vista se actualiza. Lo que se descarga es exactamente lo que se ve.
 *
 * Lo elegido se recuerda por tipo de documento en este navegador: quien
 * nunca entrega los planes de tratamiento no tiene que quitarlos cada vez.
 *
 *   <VistaPreviaPDF titulo="Historia clínica" ruta="/patients/…/export-pdf/"
 *                   nombre="historia.pdf" clave="historia"
 *                   componentes={[{ clave: "datos", etiqueta: "Datos del paciente" }, …]}
 *                   onCerrar={…} />
 *
 * `opciones` se pasa tal cual a `api()`: un documento que se genera con
 * POST (el certificado, con lo escrito en el formulario) también se ve
 * antes de descargarlo.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import Capa from "./Capa";
import { api, apiErrorMessage } from "./api";

function leerElegidos(clave, componentes) {
  const porDefecto = componentes.filter((c) => c.defecto !== false).map((c) => c.clave);
  try {
    const guardado = JSON.parse(localStorage.getItem(`vistaPdf:${clave}`) || "null");
    if (Array.isArray(guardado)) return guardado.filter((k) => componentes.some((c) => c.clave === k));
  } catch { /* sin almacenamiento: lo de siempre */ }
  return porDefecto;
}

export default function VistaPreviaPDF({ titulo, ruta, nombre, clave, componentes = [], opciones, onCerrar }) {
  const [elegidos, setElegidos] = useState(() => leerElegidos(clave || ruta, componentes));
  const [url, setUrl] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  // En el teléfono el documento ocupa la pantalla y el contenido se abre a pedido.
  const [panel, setPanel] = useState(() => typeof window === "undefined" || window.innerWidth > 760);
  const actual = useRef(null);

  const rutaFinal = useMemo(() => {
    if (!componentes.length) return ruta;
    const sep = ruta.includes("?") ? "&" : "?";
    return `${ruta}${sep}incluir=${encodeURIComponent(elegidos.join(","))}`;
  }, [ruta, elegidos, componentes.length]);

  useEffect(() => {
    let cancelado = false;
    const t = setTimeout(async () => {
      setCargando(true); setError("");
      try {
        const resp = await api(rutaFinal, opciones);
        if (!resp.ok) throw new Error(await apiErrorMessage(resp));
        const blob = await resp.blob();
        if (cancelado) return;
        const nueva = URL.createObjectURL(blob);
        if (actual.current) URL.revokeObjectURL(actual.current);
        actual.current = nueva;
        setUrl(nueva);
      } catch (e) {
        if (!cancelado) setError(e.message || "No se pudo generar el documento.");
      } finally {
        if (!cancelado) setCargando(false);
      }
    }, url ? 350 : 0);
    return () => { cancelado = true; clearTimeout(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rutaFinal]);

  useEffect(() => () => { if (actual.current) URL.revokeObjectURL(actual.current); }, []);

  useEffect(() => {
    const tecla = (e) => { if (e.key === "Escape") onCerrar(); };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [onCerrar]);

  function cambiar(k) {
    const nuevos = elegidos.includes(k) ? elegidos.filter((x) => x !== k)
      : componentes.map((c) => c.clave).filter((x) => x === k || elegidos.includes(x));
    setElegidos(nuevos);
    try { localStorage.setItem(`vistaPdf:${clave || ruta}`, JSON.stringify(nuevos)); } catch { /* sin almacenamiento */ }
  }

  function descargar() {
    if (!url) return;
    const a = document.createElement("a");
    a.href = url; a.download = nombre || `${titulo}.pdf`; a.click();
  }

  function imprimir() {
    const marco = document.querySelector(".vista-pdf iframe");
    try { marco?.contentWindow?.print(); } catch { window.open(url, "_blank"); }
  }

  return (
    <Capa>
      <div className="vista-pdf" role="dialog" aria-modal="true" aria-label={`Vista previa: ${titulo}`}>
        <div className="vista-pdf-barra">
          <strong>{titulo}</strong>
          {componentes.length > 0 && (
            <button type="button" className="vista-pdf-boton vista-pdf-solo-movil" onClick={() => setPanel((v) => !v)}>
              {panel ? "Ocultar contenido" : "Elegir contenido"}
            </button>
          )}
          <span className="vista-pdf-espacio" />
          <button type="button" className="vista-pdf-boton vista-pdf-principal" onClick={descargar} disabled={!url || cargando}>
            Descargar PDF
          </button>
          <button type="button" className="vista-pdf-boton" onClick={imprimir} disabled={!url || cargando}>Imprimir</button>
          <button type="button" className="vista-pdf-boton" onClick={() => url && window.open(url, "_blank")}
                  disabled={!url} title="Abrir en una pestaña nueva">Abrir</button>
          <button type="button" className="vista-pdf-boton" onClick={onCerrar} aria-label="Cerrar">✕</button>
        </div>

        <div className="vista-pdf-cuerpo">
          {componentes.length > 0 && panel && (
            <aside className="vista-pdf-panel">
              <h3>Contenido del documento</h3>
              <p>Marca lo que quieres que lleve. La vista se actualiza sola.</p>
              {componentes.map((c) => (
                <label key={c.clave} className="vista-pdf-opcion">
                  <input type="checkbox" checked={elegidos.includes(c.clave)} onChange={() => cambiar(c.clave)} />
                  <span>{c.etiqueta}{c.ayuda && <small>{c.ayuda}</small>}</span>
                </label>
              ))}
              <div className="vista-pdf-atajos">
                <button type="button" onClick={() => { setElegidos(componentes.map((c) => c.clave));
                  try { localStorage.removeItem(`vistaPdf:${clave || ruta}`); } catch { /* nada */ } }}>Todo</button>
                <button type="button" onClick={() => setElegidos([])}>Lo mínimo</button>
              </div>
            </aside>
          )}
          <div className="vista-pdf-hoja">
            {error && <div className="error-box">{error}</div>}
            {cargando && <div className="vista-pdf-cargando">Generando…</div>}
            {url && <iframe title={titulo} src={url} />}
          </div>
        </div>
      </div>
    </Capa>
  );
}
