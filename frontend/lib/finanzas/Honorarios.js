"use client";

/**
 * Liquidación de honorarios: primero se ve el cálculo (lo cobrado a sus
 * pacientes, su parte, lo que se le descuenta y la retención) y solo
 * entonces se guarda. Guardada, se paga —y queda como egreso— o se anula.
 */

import { useCallback, useEffect, useState } from "react";

import { api, apiErrorMessage, readList } from "../api";
import { useConfirm } from "../ConfirmDialog";
import { hoyISO } from "../fechas.mjs";
import {
  abrirPdf, Aviso, botonFila, dinero, enviar, fecha, FORMAS_PAGO, limitesDelMes, rejillaFormulario,
} from "./comunes";

const ESTADO = { borrador: "badge-warn", pagada: "badge-ok", anulada: "" };

export default function Honorarios({ mes, equipo, irA }) {
  const [confirmar, ConfirmUI] = useConfirm();
  const conHonorarios = equipo.filter((p) => p.modalidad === "honorarios");
  const [desde, hasta] = limitesDelMes(mes);
  const [form, setForm] = useState({ profesional: "", desde, hasta, ajustes: "", nota: "" });
  const [previa, setPrevia] = useState(null);
  const [lista, setLista] = useState(null);
  const [pagando, setPagando] = useState(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const cargar = useCallback(() => {
    api("/finanzas/liquidaciones/").then(readList).then(setLista).catch((e) => setError(e.message));
  }, []);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => { setForm((f) => ({ ...f, desde, hasta })); setPrevia(null); }, [desde, hasta]);
  const primero = conHonorarios[0]?.id;
  useEffect(() => {
    if (!form.profesional && primero) setForm((f) => ({ ...f, profesional: primero }));
  }, [primero, form.profesional]);

  const cambia = (campo) => (ev) => { setPrevia(null); setForm({ ...form, [campo]: ev.target.value }); };

  async function calcular(ev) {
    ev.preventDefault();
    setError(""); setOk("");
    const q = new URLSearchParams({ ...form, ajustes: form.ajustes || "0" });
    q.delete("nota");
    try {
      const resp = await api(`/finanzas/liquidaciones/previa/?${q}`);
      if (!resp.ok) throw new Error(await apiErrorMessage(resp));
      setPrevia(await resp.json());
    } catch (e) { setError(e.message); }
  }

  async function guardar() {
    setError("");
    try {
      const liq = await enviar("/finanzas/liquidaciones/", { ...form, ajustes: form.ajustes || "0" });
      setOk(`Liquidación N.º ${String(liq.numero).padStart(5, "0")} guardada. Queda pendiente de pago.`);
      setPrevia(null);
      setForm((f) => ({ ...f, ajustes: "", nota: "" }));
      cargar();
    } catch (e) { setError(e.message); }
  }

  async function pagar(ev) {
    ev.preventDefault();
    setError("");
    try {
      await enviar(`/finanzas/liquidaciones/${pagando.id}/pagar/`, { forma_pago: pagando.forma_pago, fecha: pagando.fecha });
      setOk("Pago registrado. Ya aparece en los egresos del mes como honorarios.");
      setPagando(null); cargar();
    } catch (e) { setError(e.message); }
  }

  async function anular(l) {
    const si = await confirmar({
      title: `Anular la liquidación N.º ${String(l.numero).padStart(5, "0")}`,
      message: l.estado === "pagada"
        ? "Ya estaba pagada: el egreso que generó también se anula. Después se puede rehacer el período."
        : "Después se puede volver a liquidar ese período.",
      confirmLabel: "Anular", danger: true,
    });
    if (!si) return;
    try { await enviar(`/finanzas/liquidaciones/${l.id}/anular/`); setOk("Liquidación anulada."); cargar(); }
    catch (e) { setError(e.message); }
  }

  async function pdf(l) {
    setError("");
    try { await abrirPdf(`/finanzas/liquidaciones/${l.id}/pdf/`); } catch (e) { setError(e.message); }
  }

  if (!conHonorarios.length) {
    return (
      <div className="card">
        <div className="empty">
          Nadie del equipo está marcado como profesional por honorarios.
          <div style={{ marginTop: 10 }}>
            <button type="button" className="btn btn-primary" onClick={() => irA("equipo")}>Definir cómo se le paga a cada uno</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      {ConfirmUI}
      <Aviso error={error} ok={ok} />

      <form className="card" onSubmit={calcular}>
        <h3 style={{ marginBottom: 12 }}>Nueva liquidación</h3>
        <div style={rejillaFormulario}>
          <div className="field">
            <label>Profesional</label>
            <select value={form.profesional} onChange={cambia("profesional")}>
              {conHonorarios.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Desde</label>
            <input type="date" required value={form.desde} onChange={cambia("desde")} />
          </div>
          <div className="field">
            <label>Hasta</label>
            <input type="date" required value={form.hasta} onChange={cambia("hasta")} />
          </div>
          <div className="field">
            <label>Ajuste (USD)</label>
            <input type="number" step="0.01" value={form.ajustes} onChange={cambia("ajustes")} placeholder="Bono +, anticipo −" />
          </div>
        </div>
        <div className="field">
          <label>Nota (sale en el documento)</label>
          <input maxLength={300} value={form.nota} onChange={(e) => setForm({ ...form, nota: e.target.value })} />
        </div>
        <button className="btn btn-primary">Calcular</button>
      </form>

      {previa && <Previa previa={previa} alGuardar={guardar} />}

      {pagando && (
        <form className="card" onSubmit={pagar} style={{ display: "flex", gap: 10, alignItems: "end", flexWrap: "wrap" }}>
          <strong style={{ flex: "1 1 100%" }}>Pagar {dinero(pagando.a_pagar)} a {pagando.profesional_nombre}</strong>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Fecha</label>
            <input type="date" value={pagando.fecha} onChange={(e) => setPagando({ ...pagando, fecha: e.target.value })} />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Forma de pago</label>
            <select value={pagando.forma_pago} onChange={(e) => setPagando({ ...pagando, forma_pago: e.target.value })}>
              {Object.entries(FORMAS_PAGO).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <button className="btn btn-primary">Registrar pago</button>
          <button type="button" className="btn btn-ghost" onClick={() => setPagando(null)}>Cancelar</button>
        </form>
      )}

      <div className="card" style={{ padding: 0 }}>
        <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--line)" }}><strong>Liquidaciones</strong></div>
        {!lista ? <div className="empty">Cargando…</div> : lista.length === 0 ? <div className="empty">Aún no hay liquidaciones.</div> : (
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead><tr><th>N.º</th><th>Profesional</th><th>Período</th><th style={{ textAlign: "right" }}>Honorario</th>
                <th style={{ textAlign: "right" }}>Retención</th><th style={{ textAlign: "right" }}>A pagar</th><th>Estado</th><th /></tr></thead>
              <tbody>
                {lista.map((l) => (
                  <tr key={l.id} style={l.estado === "anulada" ? { opacity: 0.55 } : undefined}>
                    <td className="tabular">{String(l.numero).padStart(5, "0")}</td>
                    <td>{l.profesional_nombre}</td>
                    <td className="tabular" style={{ fontSize: 13 }}>{fecha(l.desde)} a {fecha(l.hasta)}</td>
                    <td className="tabular" style={{ textAlign: "right" }}>{dinero(l.honorario)}</td>
                    <td className="tabular" style={{ textAlign: "right" }}>{Number(l.retencion) ? dinero(l.retencion) : "—"}</td>
                    <td className="tabular" style={{ textAlign: "right", fontWeight: 700 }}>{dinero(l.a_pagar)}</td>
                    <td><span className={`badge ${ESTADO[l.estado]}`}>{l.estado_nombre}</span></td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      <button type="button" className="btn btn-ghost" style={botonFila} onClick={() => pdf(l)}>PDF</button>
                      {l.estado === "borrador" && (
                        <button type="button" className="btn btn-ghost" style={botonFila}
                                onClick={() => setPagando({ ...l, forma_pago: "transferencia", fecha: hoyISO() })}>Pagar</button>
                      )}
                      {l.estado !== "anulada" && (
                        <button type="button" className="btn btn-ghost" style={{ ...botonFila, color: "var(--red)" }} onClick={() => anular(l)}>Anular</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function Previa({ previa, alGuardar }) {
  const fijo = previa.detalle.modalidad === "fijo";
  const filas = [
    ...(fijo ? [] : [["Cobrado a sus pacientes", previa.base]]),
    [fijo ? "Honorario fijo" : `Su parte (${Number(previa.porcentaje)} %)`, previa.honorario],
    ...(Number(previa.descuentos) ? [["− Descuentos (laboratorio, materiales…)", -previa.descuentos]] : []),
    ...(Number(previa.ajustes) ? [["± Ajuste", previa.ajustes]] : []),
    ...(Number(previa.retencion) ? [[`− Retención IR ${Number(previa.retencion_porcentaje)} %`, -previa.retencion]] : []),
  ];
  return (
    <div className="card" style={{ borderColor: "var(--petrol)" }}>
      <h3 style={{ marginBottom: 12 }}>Así queda</h3>
      {filas.map(([t, v]) => (
        <div key={t} style={{ display: "flex", justifyContent: "space-between", fontSize: 14, padding: "3px 0" }}>
          <span>{t}</span><span className="tabular">{dinero(v)}</span>
        </div>
      ))}
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 17, fontWeight: 700, borderTop: "1px solid var(--line)",
                    marginTop: 6, paddingTop: 8 }}>
        <span>A pagar</span><span className="tabular">{dinero(previa.a_pagar)}</span>
      </div>
      {!fijo && previa.detalle.cobros.length > 0 && (
        <details style={{ marginTop: 10, fontSize: 13 }}>
          <summary style={{ cursor: "pointer", color: "var(--ink-soft)" }}>Cobros incluidos ({previa.detalle.cobros.length})</summary>
          {previa.detalle.cobros.map((c, i) => (
            <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "3px 0" }}>
              <span>{fecha(c.fecha)} · {c.paciente} · {c.forma}{c.atrasado ? " · de antes del período" : ""}</span>
              <span className="tabular">{dinero(c.monto)}</span>
            </div>
          ))}
        </details>
      )}
      {!fijo && previa.detalle.cobros.length === 0 && (
        <p style={{ fontSize: 13, color: "var(--ink-soft)", marginTop: 8 }}>
          No hay cobros atribuidos a este profesional en el período. Revisa la pestaña Cobros.
        </p>
      )}
      <div style={{ marginTop: 14 }}>
        <button type="button" className="btn btn-primary" onClick={alGuardar}>Guardar liquidación</button>
      </div>
    </div>
  );
}
