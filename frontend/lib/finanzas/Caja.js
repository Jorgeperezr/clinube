"use client";

/**
 * Cierre de caja del día: lo que debería haber en efectivo (lo que quedó
 * del cierre anterior + lo cobrado en efectivo − lo pagado en efectivo)
 * frente a lo que de verdad se cuenta. La diferencia queda anotada.
 */

import { useCallback, useEffect, useState } from "react";

import { api, readObject } from "../api";
import { hoyISO } from "../fechas.mjs";
import { Aviso, dinero, enviar, fecha, rejillaFormulario } from "./comunes";

export default function Caja() {
  const [dia, setDia] = useState(hoyISO());
  const [datos, setDatos] = useState(null);
  const [form, setForm] = useState({ contado: "", retirado: "", observaciones: "" });
  const [corrigiendo, setCorrigiendo] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const cargar = useCallback(() => {
    api(`/finanzas/caja/?fecha=${dia}`).then(readObject).then((d) => {
      setDatos(d);
      setCorrigiendo(false);
      setForm(d.cierre
        ? { contado: d.cierre.contado, retirado: d.cierre.retirado, observaciones: d.cierre.observaciones }
        : { contado: "", retirado: "", observaciones: "" });
    }).catch((e) => setError(e.message));
  }, [dia]);

  useEffect(() => { setDatos(null); setError(""); setOk(""); cargar(); }, [cargar]);

  async function cerrar(ev) {
    ev.preventDefault();
    setError(""); setOk("");
    try {
      await enviar("/finanzas/caja/", { fecha: dia, ...form, retirado: form.retirado || "0" });
      setOk("Caja cerrada.");
      cargar();
    } catch (e) { setError(e.message); }
  }

  const contado = Number(form.contado || 0);
  const diferencia = datos && form.contado !== "" ? contado - Number(datos.esperado) : null;

  return (
    <div>
      <div className="barra-herramientas" style={{ display: "flex", gap: 10, alignItems: "end", flexWrap: "wrap" }}>
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Día</label>
          <input type="date" value={dia} max={hoyISO()} onChange={(e) => e.target.value && setDia(e.target.value)} />
        </div>
      </div>
      <Aviso error={error} ok={ok} />
      {!datos ? <div className="card"><div className="empty">Cargando…</div></div> : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 18, alignItems: "start" }}>
          <div className="card">
            <h3 style={{ marginBottom: 12 }}>Efectivo del día</h3>
            <Linea texto={datos.viene_del_cierre ? `Quedó en caja (cierre del ${fecha(datos.viene_del_cierre)})` : "Saldo inicial"}
                   valor={datos.saldo_inicial} />
            <Linea texto="+ Cobrado en efectivo" valor={datos.cobros_efectivo} />
            <Linea texto="− Pagado en efectivo" valor={datos.egresos_efectivo} />
            <div style={{ borderTop: "1px solid var(--line)", margin: "8px 0" }} />
            <Linea texto="Debería haber" valor={datos.esperado} fuerte />
            {Number(datos.otros_cobros) > 0 && (
              <p style={{ fontSize: 12, color: "var(--ink-soft)", marginTop: 10 }}>
                Además entraron {dinero(datos.otros_cobros)} por transferencia o tarjeta, que no pasan por la caja.
              </p>
            )}
            {datos.movimientos.length > 0 && (
              <details style={{ marginTop: 10, fontSize: 13 }}>
                <summary style={{ cursor: "pointer", color: "var(--ink-soft)" }}>Ver movimientos ({datos.movimientos.length})</summary>
                {datos.movimientos.map((m, i) => (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
                    <span>{m.tipo === "cobro" ? "Cobro" : "Pago"} · {m.detalle}</span>
                    <span className="tabular" style={{ color: m.tipo === "cobro" ? "var(--green)" : "var(--red)" }}>
                      {m.tipo === "cobro" ? "+" : "−"}{dinero(m.monto)}
                    </span>
                  </div>
                ))}
              </details>
            )}
          </div>

          <div className="card">
            {datos.cierre && !corrigiendo ? (
              <>
                <h3 style={{ marginBottom: 12 }}>Caja cerrada</h3>
                {datos.desactualizado && (
                  <div className="error-box" style={{ background: "var(--amber-soft)", color: "var(--amber)" }}>
                    Después del cierre se registró un cobro o un pago en efectivo de este día: ahora debería haber {dinero(datos.esperado)}.
                    Vuelve a cerrar la caja con el conteo actualizado.
                  </div>
                )}
                <Linea texto="Contado" valor={datos.cierre.contado} />
                <Linea texto="Diferencia" valor={datos.cierre.diferencia} color={Number(datos.cierre.diferencia) === 0 ? null
                  : Number(datos.cierre.diferencia) < 0 ? "var(--red)" : "var(--amber)"} />
                <Linea texto="Retirado o depositado" valor={datos.cierre.retirado} />
                <Linea texto="Queda para mañana" valor={Number(datos.cierre.contado) - Number(datos.cierre.retirado)} fuerte />
                {datos.cierre.observaciones && <p style={{ fontSize: 13, marginTop: 8 }}>{datos.cierre.observaciones}</p>}
                <p style={{ fontSize: 12, color: "var(--ink-soft)", marginTop: 8 }}>
                  Cerró {datos.cierre.cerrado_por_nombre || "—"}.
                </p>
                <button type="button" className="btn btn-ghost" onClick={() => setCorrigiendo(true)}>Corregir el cierre</button>
              </>
            ) : (
              <form onSubmit={cerrar}>
                <h3 style={{ marginBottom: 12 }}>Cerrar la caja</h3>
                <div style={rejillaFormulario}>
                  <div className="field">
                    <label>Efectivo contado *</label>
                    <input type="number" step="0.01" min="0" required autoFocus value={form.contado}
                           onChange={(e) => setForm({ ...form, contado: e.target.value })} />
                  </div>
                  <div className="field">
                    <label>Retirado o depositado</label>
                    <input type="number" step="0.01" min="0" value={form.retirado}
                           onChange={(e) => setForm({ ...form, retirado: e.target.value })} placeholder="0.00" />
                  </div>
                </div>
                {diferencia !== null && Math.abs(diferencia) >= 0.005 && (
                  <div className="error-box" style={diferencia > 0 ? { background: "var(--amber-soft)", color: "var(--amber)" } : undefined}>
                    {diferencia < 0 ? `Faltan ${dinero(-diferencia)}` : `Sobran ${dinero(diferencia)}`}. Si no aparece, anota el motivo.
                  </div>
                )}
                {diferencia !== null && Math.abs(diferencia) < 0.005 && <div className="success-box">✓ Cuadra.</div>}
                <div className="field">
                  <label>Observaciones</label>
                  <input maxLength={300} value={form.observaciones}
                         onChange={(e) => setForm({ ...form, observaciones: e.target.value })} />
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button className="btn btn-primary">Cerrar caja</button>
                  {corrigiendo && <button type="button" className="btn btn-ghost" onClick={() => setCorrigiendo(false)}>Cancelar</button>}
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {datos?.ultimos?.length > 0 && (
        <div className="card" style={{ padding: 0 }}>
          <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--line)" }}><strong>Últimos cierres</strong></div>
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead><tr><th>Día</th><th style={{ textAlign: "right" }}>Esperado</th><th style={{ textAlign: "right" }}>Contado</th>
                <th style={{ textAlign: "right" }}>Diferencia</th><th>Cerró</th></tr></thead>
              <tbody>
                {datos.ultimos.map((c) => (
                  <tr key={c.id} onClick={() => setDia(c.fecha)} style={{ cursor: "pointer" }}>
                    <td className="tabular">{fecha(c.fecha)}</td>
                    <td className="tabular" style={{ textAlign: "right" }}>{dinero(c.esperado)}</td>
                    <td className="tabular" style={{ textAlign: "right" }}>{dinero(c.contado)}</td>
                    <td className="tabular" style={{ textAlign: "right", color: Number(c.diferencia) < 0 ? "var(--red)" : undefined }}>
                      {Number(c.diferencia) === 0 ? "—" : dinero(c.diferencia)}
                    </td>
                    <td>{c.cerrado_por_nombre}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function Linea({ texto, valor, fuerte, color }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "3px 0", fontSize: fuerte ? 16 : 14,
                  fontWeight: fuerte ? 700 : 400 }}>
      <span>{texto}</span>
      <span className="tabular" style={color ? { color } : undefined}>{dinero(valor)}</span>
    </div>
  );
}
