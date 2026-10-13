"use client";

/**
 * Piezas que comparten las pestañas de Finanzas: formato de dinero, el
 * selector de mes, abrir un PDF y descargar el Excel.
 */

import { api, apiErrorMessage } from "../api";
import { fechaISO } from "../fechas.mjs";

export const FORMAS_PAGO = {
  efectivo: "Efectivo", transferencia: "Transferencia", tarjeta: "Tarjeta", cheque: "Cheque",
};

const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
  "septiembre", "octubre", "noviembre", "diciembre"];

/** 1234.5 → «$1.234,50», como se escribe en Ecuador. */
export function dinero(valor, decimales = 2) {
  const n = Number(valor || 0);
  const texto = Math.abs(n).toLocaleString("es-EC", {
    minimumFractionDigits: decimales, maximumFractionDigits: decimales,
  });
  return `${n < 0 ? "−" : ""}$${texto}`;
}

/** «2026-10-02» → «02/10/2026», como se lee aquí. */
export function fecha(iso) {
  const [a, m, d] = (iso || "").slice(0, 10).split("-");
  return d ? `${d}/${m}/${a}` : "";
}

/** Botón pequeño de las filas de una tabla. */
export const botonFila = { fontSize: 12, padding: "4px 10px", minHeight: 0 };

export function mesActual() {
  return fechaISO().slice(0, 7);
}

/** «2026-10» → «octubre 2026». */
export function nombreMes(mes) {
  const [a, m] = (mes || "").split("-").map(Number);
  return m ? `${MESES[m - 1]} ${a}` : "";
}

export function mesCorto(mes) {
  const [, m] = (mes || "").split("-").map(Number);
  return m ? MESES[m - 1].slice(0, 3) : "";
}

/** Primer y último día de un mes «2026-10», como AAAA-MM-DD. */
export function limitesDelMes(mes) {
  const [a, m] = mes.split("-").map(Number);
  return [fechaISO(new Date(a, m - 1, 1)), fechaISO(new Date(a, m, 0))];
}

function moverMes(mes, delta) {
  const [a, m] = mes.split("-").map(Number);
  return fechaISO(new Date(a, m - 1 + delta, 1)).slice(0, 7);
}

/** «‹ octubre 2026 ›» — no deja pasar del mes en curso. */
export function SelectorMes({ mes, alCambiar }) {
  const ultimo = mes >= mesActual();
  return (
    <div className="navegador-fecha" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <button type="button" className="btn btn-ghost" aria-label="Mes anterior"
              onClick={() => alCambiar(moverMes(mes, -1))}>‹</button>
      <strong style={{ minWidth: 130, textAlign: "center", textTransform: "capitalize" }}>{nombreMes(mes)}</strong>
      <button type="button" className="btn btn-ghost" aria-label="Mes siguiente" disabled={ultimo}
              onClick={() => alCambiar(moverMes(mes, 1))}>›</button>
    </div>
  );
}

/** El PDF se pide con la sesión y se abre en otra pestaña. */
export async function abrirPdf(ruta) {
  // La pestaña se abre antes de la petición: si se abre después, Safari
  // la toma por una ventana emergente y la bloquea.
  const pestana = window.open("", "_blank");
  const resp = await api(ruta);
  if (!resp.ok) {
    pestana?.close();
    throw new Error(await apiErrorMessage(resp));
  }
  const url = URL.createObjectURL(await resp.blob());
  if (pestana) pestana.location.href = url;
  else window.location.href = url;
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

export async function descargar(ruta, nombre) {
  const resp = await api(ruta);
  if (!resp.ok) throw new Error(await apiErrorMessage(resp));
  const url = URL.createObjectURL(await resp.blob());
  const a = document.createElement("a");
  a.href = url; a.download = nombre; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

/** POST/PATCH con JSON que lanza el mensaje del servidor si falla. */
export async function enviar(ruta, cuerpo, metodo = "POST") {
  const resp = await api(ruta, { method: metodo, body: JSON.stringify(cuerpo || {}) });
  if (!resp.ok) throw new Error(await apiErrorMessage(resp));
  return resp.json().catch(() => ({}));
}

export function Cifra({ titulo, valor, nota, color, alerta }) {
  return (
    <div className="card" style={{ padding: "14px 16px", marginBottom: 0 }}>
      <div style={{ fontSize: 12, color: "var(--ink-soft)", fontWeight: 600 }}>{titulo}</div>
      <div className="tabular" style={{ fontSize: 24, fontWeight: 700, color: color || "var(--ink)", margin: "2px 0" }}>
        {valor}
      </div>
      {nota && (
        <div style={{ fontSize: 12, color: alerta ? "var(--red)" : "var(--ink-soft)" }}>{nota}</div>
      )}
    </div>
  );
}

export const rejillaCifras = {
  display: "grid", gap: 12, marginBottom: 18,
  gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
};

export const rejillaFormulario = {
  display: "grid", gap: "0 12px", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
};

export function Aviso({ error, ok }) {
  return (
    <>
      {error && <div className="error-box">{error}</div>}
      {ok && <div className="success-box">✓ {ok}</div>}
    </>
  );
}
