"use client";

/**
 * Piezas de la identidad visual de una clínica: su paleta, sus tres
 * logotipos y las muestras de sus temas.
 *
 * Las usan el alta de clínicas (Plataforma → Clínicas), Configuración →
 * Identidad visual y Mis preferencias (elegir tema). Los temas los genera
 * el servidor a partir de la paleta (apps/configuration/temas_clinica.py);
 * aquí solo se piden y se enseñan, para que el panel, la app y los PDF
 * vean los mismos colores.
 */

import { useEffect, useRef, useState } from "react";

import { api, apiErrorMessage } from "./api";
import { ensureAccessiblePrimary, logoSrc } from "./theme";
import { colorHex, leerPaleta, MAX_COLORES } from "./temas.mjs";

/* ───────────── Muestra de un tema ───────────── */

/**
 * Una miniatura del panel con ese tema: la barra lateral con su píldora,
 * un botón y el segundo color. El botón lleva el principal ya ajustado
 * para el texto blanco, como lo pinta el panel de verdad.
 */
export function TarjetaTema({ tema, activo = false, onClick, etiquetaExtra }) {
  const principal = ensureAccessiblePrimary(tema.primary) || tema.primary;
  const Elemento = onClick ? "button" : "div";
  return (
    <Elemento type={onClick ? "button" : undefined}
              className={`tema-tarjeta${activo ? " tema-tarjeta--activa" : ""}`}
              aria-pressed={onClick ? activo : undefined}
              onClick={onClick} title={tema.descripcion || tema.nombre}>
      <span className="tema-muestra" aria-hidden="true">
        <span className="tema-muestra-lateral">
          <span className="tema-muestra-pildora" style={{ background: principal }} />
          <span className="tema-muestra-linea" />
          <span className="tema-muestra-linea tema-muestra-linea--corta" />
        </span>
        <span className="tema-muestra-lienzo">
          <span className="tema-muestra-boton" style={{ background: principal }} />
          <span className="tema-muestra-chip" style={{ background: tema.secondary }} />
        </span>
      </span>
      <span className="tema-nombre">
        {tema.nombre}
        {etiquetaExtra && <span className="tema-etiqueta">{etiquetaExtra}</span>}
      </span>
      {tema.descripcion && <span className="tema-descripcion">{tema.descripcion}</span>}
    </Elemento>
  );
}

/** Las muestras de varios temas, sin elegir nada (vista previa). */
export function VistaTemas({ temas, vacio = "Añade al menos un color para ver los temas." }) {
  if (!temas?.length) return <p className="identidad-ayuda">{vacio}</p>;
  return (
    <div className="tema-rejilla">
      {temas.map((t, i) => (
        <TarjetaTema key={t.clave} tema={t} etiquetaExtra={i === 0 ? "De la clínica" : ""} />
      ))}
    </div>
  );
}

/* ───────────── Paleta ───────────── */

/**
 * Los colores de la marca, el primero el principal. Cada uno con su
 * selector y su código; se pueden pegar varios de golpe («#0e7490,
 * #f59e0b»), que es como suelen llegar de quien hizo el logotipo.
 */
export function EditorPaleta({ colores, onChange, deshabilitado = false, accionExtra = null }) {
  const [pegado, setPegado] = useState("");
  const [aviso, setAviso] = useState("");
  const lleno = colores.length >= MAX_COLORES;

  function cambiar(i, valor) {
    const color = colorHex(valor);
    if (!color) return;
    onChange(colores.map((c, j) => (j === i ? color : c)));
  }

  function anadirPegados() {
    const { colores: leidos, malos } = leerPaleta(pegado);
    const juntos = [...colores, ...leidos.filter((c) => !colores.includes(c))].slice(0, MAX_COLORES);
    onChange(juntos);
    setAviso(malos.length
      ? `No son colores: ${malos.join(", ")}. Escríbelos como #RRGGBB.`
      : (colores.length + leidos.length > MAX_COLORES ? `Caben ${MAX_COLORES} colores; el resto no se añadió.` : ""));
    if (!malos.length) setPegado("");
  }

  return (
    <div>
      <div className="paleta-fila">
        {colores.map((c, i) => (
          <div key={`${c}-${i}`} className="paleta-color">
            <input type="color" value={c} disabled={deshabilitado}
                   aria-label={i === 0 ? "Color principal" : `Color ${i + 1}`}
                   onChange={(e) => cambiar(i, e.target.value)} />
            <span className="paleta-codigo tabular">{c}</span>
            {i === 0 && <span className="paleta-principal">Principal</span>}
            <button type="button" className="paleta-quitar" disabled={deshabilitado}
                    aria-label={`Quitar ${c}`} title="Quitar"
                    onClick={() => onChange(colores.filter((_, j) => j !== i))}>×</button>
          </div>
        ))}
        {!lleno && (
          <button type="button" className="btn btn-ghost" disabled={deshabilitado}
                  style={{ fontSize: 13, alignSelf: "center" }}
                  onClick={() => onChange([...colores, colores.length ? "#9ca3af" : "#0e7490"])}>
            + Color
          </button>
        )}
      </div>
      <div className="paleta-pegar">
        <input value={pegado} onChange={(e) => setPegado(e.target.value)} disabled={deshabilitado || lleno}
               placeholder="O pega los códigos: #0E7490, #F59E0B"
               onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); anadirPegados(); } }} />
        <button type="button" className="btn btn-ghost" style={{ fontSize: 13 }}
                disabled={deshabilitado || lleno || !pegado.trim()} onClick={anadirPegados}>Añadir</button>
        {accionExtra}
      </div>
      {aviso && <p className="identidad-ayuda" style={{ color: "var(--amber)" }}>{aviso}</p>}
    </div>
  );
}

/**
 * Los temas que saldrían de una paleta, pedidos al servidor mientras se
 * edita (sin guardar nada). Espera a que se deje de tocar para no pedir
 * uno por cada movimiento del selector de color.
 */
export function usePrevisualizacion(colores) {
  const [estado, setEstado] = useState({ temas: [], error: "" });
  const clave = colores.join(",");
  useEffect(() => {
    if (!colores.length) { setEstado({ temas: [], error: "" }); return; }
    let vivo = true;
    const t = setTimeout(async () => {
      try {
        const r = await api("/config/temas/previsualizar/", {
          method: "POST", body: JSON.stringify({ paleta: colores }),
        });
        if (!r.ok) throw new Error(await apiErrorMessage(r));
        const d = await r.json();
        if (vivo) setEstado({ temas: d.temas || [], error: "" });
      } catch (e) {
        if (vivo) setEstado({ temas: [], error: e.message });
      }
    }, 350);
    return () => { vivo = false; clearTimeout(t); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave]);
  return estado;
}

/** Los colores de un logotipo (sin guardarlo), para usarlos de paleta. */
export async function coloresDelLogotipo(archivo) {
  const fd = new FormData();
  fd.append("logo", archivo);
  const r = await api("/config/temas/previsualizar/", { method: "POST", body: fd });
  if (!r.ok) throw new Error(await apiErrorMessage(r));
  const d = await r.json();
  return d.paleta || [];
}

/* ───────────── Logotipos ───────────── */

export const LOGOS = [
  { campo: "logo", url: "logo_url", etiqueta: "Logotipo",
    ayuda: "El de siempre, para fondo claro: barra lateral y documentos." },
  { campo: "logo_oscuro", url: "logo_oscuro_url", etiqueta: "Para fondo oscuro",
    ayuda: "Opcional. El panel lo usa en modo oscuro; si no hay, usa el de arriba.", oscuro: true },
  { campo: "icono", url: "icono_url", etiqueta: "Ícono",
    ayuda: "Opcional, cuadrado: barra plegada, teléfono y pestaña del navegador." },
];

/**
 * Un logotipo: lo que hay (o lo elegido, aún sin subir) sobre el fondo
 * en el que se va a ver, y los botones para cambiarlo o quitarlo.
 */
export function SelectorLogo({ definicion, url, version, archivo, quitado, onArchivo, onQuitar, deshabilitado }) {
  const [local, setLocal] = useState(null);
  const entrada = useRef(null);
  useEffect(() => {
    if (!archivo) { setLocal(null); return; }
    const u = URL.createObjectURL(archivo);
    setLocal(u);
    return () => URL.revokeObjectURL(u);
  }, [archivo]);
  const visible = local || (!quitado && url ? logoSrc(url, version) : null);
  return (
    <div className="logo-selector">
      <div className={`logo-caja${definicion.oscuro ? " logo-caja--oscura" : ""}`}>
        {visible
          ? <img src={visible} alt={`Vista previa: ${definicion.etiqueta}`} />
          : <span>Sin {definicion.etiqueta.toLowerCase()}</span>}
      </div>
      <div style={{ minWidth: 0 }}>
        <strong style={{ fontSize: 13.5 }}>{definicion.etiqueta}</strong>
        <span className="identidad-ayuda" style={{ display: "block", margin: "2px 0 6px" }}>{definicion.ayuda}</span>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <button type="button" className="btn btn-ghost" style={{ fontSize: 12.5, padding: "4px 10px" }}
                  disabled={deshabilitado} onClick={() => entrada.current?.click()}>
            {visible ? "Cambiar" : "Elegir imagen"}
          </button>
          {visible && (
            <button type="button" className="btn btn-ghost"
                    style={{ fontSize: 12.5, padding: "4px 10px", color: "var(--red)" }}
                    disabled={deshabilitado} onClick={onQuitar}>Quitar</button>
          )}
        </div>
        <input ref={entrada} type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden
               onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) onArchivo(f); }} />
      </div>
    </div>
  );
}
