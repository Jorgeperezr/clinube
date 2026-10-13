"use client";

/**
 * Los cobros del mes con el profesional al que se le atribuyen. De esa
 * atribución salen los honorarios, por eso se puede corregir aquí; una
 * vez liquidado el período, la API no deja cambiarla.
 */

import { useCallback, useEffect, useState } from "react";

import { api, readList } from "../api";
import { abrirPdf, Aviso, botonFila, dinero, enviar, fecha } from "./comunes";

export default function Cobros({ mes, equipo }) {
  const [filas, setFilas] = useState(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const cargar = useCallback(() => {
    api(`/finanzas/cobros/?mes=${mes}`).then(readList).then(setFilas).catch((e) => setError(e.message));
  }, [mes]);

  useEffect(() => { setFilas(null); setError(""); setOk(""); cargar(); }, [cargar]);

  async function cambiar(cobro, profesional) {
    setError(""); setOk("");
    try {
      const r = await enviar(`/finanzas/cobros/${cobro.id}/`, { profesional: profesional || null }, "PATCH");
      setFilas((fs) => fs.map((f) => (f.id === cobro.id ? { ...f, ...r } : f)));
      setOk(`El cobro de ${cobro.paciente} queda para ${r.profesional_nombre || "nadie en particular"}.`);
    } catch (e) { setError(e.message); }
  }

  async function comprobante(cobro) {
    setError("");
    try {
      await abrirPdf(`/finanzas/cobros/${cobro.id}/comprobante/`);
      if (!cobro.numero_comprobante) cargar();
    } catch (e) { setError(e.message); }
  }

  if (!filas) return error ? <div className="error-box">{error}</div> : <div className="card"><div className="empty">Cargando…</div></div>;

  const total = filas.reduce((s, f) => s + Number(f.monto), 0);
  const sinProfesional = filas.filter((f) => !f.profesional).length;

  return (
    <div>
      <Aviso error={error} ok={ok} />
      {sinProfesional > 0 && (
        <div className="card" style={{ background: "var(--amber-soft)", borderColor: "transparent", fontSize: 14 }}>
          {sinProfesional === 1 ? "Un cobro no tiene" : `${sinProfesional} cobros no tienen`} profesional asignado.
          Si a alguien se le paga un porcentaje de lo cobrado, esos valores no entran en su liquidación hasta que se asignen.
        </div>
      )}
      <div className="card" style={{ padding: 0 }}>
        <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--line)", display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
          <strong>{filas.length} cobro{filas.length === 1 ? "" : "s"}</strong>
          <span className="tabular" style={{ fontWeight: 700 }}>{dinero(total)}</span>
        </div>
        {filas.length === 0 ? <div className="empty">No hay cobros registrados este mes.</div> : (
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr><th>Fecha</th><th>Paciente</th><th>Forma</th><th style={{ textAlign: "right" }}>Monto</th>
                  <th>Profesional</th><th>Comprobante</th></tr>
              </thead>
              <tbody>
                {filas.map((f) => (
                  <tr key={f.id}>
                    <td className="tabular" style={{ whiteSpace: "nowrap" }}>{fecha(f.fecha)}</td>
                    <td>{f.paciente}</td>
                    <td>{f.forma}</td>
                    <td className="tabular" style={{ textAlign: "right", fontWeight: 600 }}>{dinero(f.monto)}</td>
                    <td style={{ minWidth: 170 }}><div className="field" style={{ marginBottom: 0 }}>
                      <select value={f.profesional || ""} aria-label={`Profesional del cobro de ${f.paciente}`}
                              onChange={(e) => cambiar(f, e.target.value)}>
                        <option value="">Sin asignar</option>
                        {equipo.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                      </select>
                    </div></td>
                    <td>
                      <button type="button" className="btn btn-ghost" style={botonFila} onClick={() => comprobante(f)}>
                        {f.numero_comprobante ? `N.º ${String(f.numero_comprobante).padStart(6, "0")}` : "Emitir"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <p style={{ fontSize: 12, color: "var(--ink-faint)" }}>
        El comprobante de cobro es un recibo interno para el paciente; no reemplaza a la factura electrónica del SRI.
        Su número se asigna la primera vez que se emite y no cambia al reimprimirlo.
      </p>
    </div>
  );
}
