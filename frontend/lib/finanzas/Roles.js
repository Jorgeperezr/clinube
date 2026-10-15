"use client";

/**
 * Rol de pagos del mes para quien está en relación de dependencia.
 * «Generar» crea un borrador por persona con 30 días trabajados; en cada
 * uno se ajustan días, horas extra, anticipos o préstamos del IESS y se
 * recalcula. Pagado, queda como egreso de sueldos.
 */

import { useCallback, useEffect, useState } from "react";

import { api, readList } from "../api";
import { useConfirm } from "../ConfirmDialog";
import { hoyISO } from "../fechas.mjs";
import { abrirPdf, Aviso, botonFila, dinero, enviar, FORMAS_PAGO, nombreMes, rejillaFormulario } from "./comunes";

const CAMPOS = [
  ["dias_trabajados", "Días trabajados", "1"],
  ["horas_suplementarias", "Horas suplementarias (50 %)", "0.5"],
  ["horas_extraordinarias", "Horas extraordinarias (100 %)", "0.5"],
  ["horas_extra", "Otras horas extra (USD)", "0.01"],
  ["otros_ingresos", "Otros ingresos (USD)", "0.01"],
  ["anticipos", "Otros anticipos (USD)", "0.01"],
  ["prestamos_iess", "Préstamos IESS (USD)", "0.01"],
  ["otros_descuentos", "Otros descuentos (USD)", "0.01"],
];

export default function Roles({ mes, equipo, irA }) {
  const [confirmar, ConfirmUI] = useConfirm();
  const [roles, setRoles] = useState(null);
  const [ajustando, setAjustando] = useState(null);
  const [abierto, setAbierto] = useState(null);
  const [pagando, setPagando] = useState(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const enDependencia = equipo.filter((p) => p.modalidad === "dependencia");

  const cargar = useCallback(() => {
    api(`/finanzas/roles/?mes=${mes}`).then(readList).then(setRoles).catch((e) => setError(e.message));
  }, [mes]);
  useEffect(() => { setRoles(null); setOk(""); setError(""); cargar(); }, [cargar]);

  async function generar() {
    setError(""); setOk("");
    try {
      const r = await enviar("/finanzas/roles/generar/", { mes });
      setOk(r.creados ? `${r.creados} rol${r.creados === 1 ? "" : "es"} en borrador.` : "Ya estaban todos generados.");
      cargar();
    } catch (e) { setError(e.message); }
  }

  async function recalcular(ev) {
    ev.preventDefault();
    setError("");
    try {
      const { empleado, empleado_nombre: nombre } = ajustando;
      const cuerpo = { empleado, mes };
      for (const [k] of CAMPOS) cuerpo[k] = ajustando[k] === "" ? "0" : ajustando[k];
      await enviar("/finanzas/roles/", cuerpo);
      setAjustando(null); setOk(`Rol de ${nombre} recalculado.`); cargar();
    } catch (e) { setError(e.message); }
  }

  async function pagar(ev) {
    ev.preventDefault();
    try {
      await enviar(`/finanzas/roles/${pagando.id}/pagar/`, { forma_pago: pagando.forma_pago, fecha: pagando.fecha });
      setPagando(null); setOk("Pago registrado. Ya aparece en los egresos como sueldos."); cargar();
    } catch (e) { setError(e.message); }
  }

  async function anular(r) {
    const si = await confirmar({
      title: `Anular el rol de ${r.empleado_nombre}`,
      message: r.estado === "pagado" ? "Ya estaba pagado: su egreso también se anula." : "Después se puede volver a generar.",
      confirmLabel: "Anular", danger: true,
    });
    if (!si) return;
    try { await enviar(`/finanzas/roles/${r.id}/anular/`); setOk("Rol anulado."); cargar(); }
    catch (e) { setError(e.message); }
  }

  async function pdf(r) {
    setError("");
    try { await abrirPdf(`/finanzas/roles/${r.id}/pdf/`); } catch (e) { setError(e.message); }
  }

  if (!enDependencia.length && roles && !roles.length) {
    return (
      <div className="card">
        <div className="empty">
          Nadie del equipo está en relación de dependencia.
          <div style={{ marginTop: 10 }}>
            <button type="button" className="btn btn-primary" onClick={() => irA("equipo")}>Definir cómo se le paga a cada uno</button>
          </div>
        </div>
      </div>
    );
  }

  const totalNeto = (roles || []).reduce((s, r) => s + Number(r.neto), 0);
  const totalCosto = (roles || []).reduce((s, r) => s + Number(r.costo_empleador), 0);

  return (
    <div>
      {ConfirmUI}
      <div className="barra-herramientas" style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <span style={{ fontSize: 14, color: "var(--ink-soft)" }}>
          Rol de <strong style={{ color: "var(--ink)" }}>{nombreMes(mes)}</strong>
        </span>
        <button type="button" className="btn btn-primary" style={{ marginLeft: "auto" }} onClick={generar}>
          Generar los roles del mes
        </button>
      </div>
      <Aviso error={error} ok={ok} />

      {ajustando && (
        <form className="card" onSubmit={recalcular}>
          <h3 style={{ marginBottom: 12 }}>{ajustando.empleado_nombre}</h3>
          <div style={rejillaFormulario}>
            {CAMPOS.map(([k, t, paso]) => (
              <div className="field" key={k}>
                <label>{t}</label>
                <input type="number" min="0" max={k === "dias_trabajados" ? 30 : undefined} step={paso} value={ajustando[k]}
                       onChange={(e) => setAjustando({ ...ajustando, [k]: e.target.value })} />
              </div>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-primary">Recalcular</button>
            <button type="button" className="btn btn-ghost" onClick={() => setAjustando(null)}>Cancelar</button>
          </div>
        </form>
      )}

      {pagando && (
        <form className="card" onSubmit={pagar} style={{ display: "flex", gap: 10, alignItems: "end", flexWrap: "wrap" }}>
          <strong style={{ flex: "1 1 100%" }}>Pagar {dinero(pagando.neto)} a {pagando.empleado_nombre}</strong>
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
        {!roles ? <div className="empty">Cargando…</div> : roles.length === 0 ? (
          <div className="empty">Aún no hay roles de este mes. Usa «Generar los roles del mes».</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead><tr><th>Persona</th><th>Días</th><th style={{ textAlign: "right" }}>Ingresos</th>
                <th style={{ textAlign: "right" }}>Descuentos</th><th style={{ textAlign: "right" }}>Neto a recibir</th>
                <th style={{ textAlign: "right" }}>Costo para la clínica</th><th>Estado</th><th /></tr></thead>
              <tbody>
                {roles.map((r) => (
                  <FilaRol key={r.id} r={r} abierto={abierto === r.id}
                           alAbrir={() => setAbierto(abierto === r.id ? null : r.id)}
                           alAjustar={() => { setOk(""); setAjustando({ ...r }); }}
                           alPagar={() => setPagando({ ...r, forma_pago: "transferencia", fecha: hoyISO() })}
                           alAnular={() => anular(r)} alPdf={() => pdf(r)} />
                ))}
                <tr>
                  <td colSpan={4} style={{ fontWeight: 700 }}>Total</td>
                  <td className="tabular" style={{ textAlign: "right", fontWeight: 700 }}>{dinero(totalNeto)}</td>
                  <td className="tabular" style={{ textAlign: "right", fontWeight: 700 }}>{dinero(totalCosto)}</td>
                  <td colSpan={2} />
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </div>
      <p style={{ fontSize: 12, color: "var(--ink-faint)" }}>
        El costo para la clínica suma el aporte patronal y lo que se va acumulando para décimos, fondos de reserva y vacaciones.
        Los porcentajes y el salario básico se cambian en Ajustes.
      </p>
    </div>
  );
}

function FilaRol({ r, abierto, alAbrir, alAjustar, alPagar, alAnular, alPdf }) {
  const c = r.calculo || {};
  return (
    <>
      <tr>
        <td>
          <button type="button" onClick={alAbrir} style={{ border: "none", background: "none", padding: 0, cursor: "pointer",
                                                            fontWeight: 600, color: "var(--ink)", textAlign: "left" }}>
            {abierto ? "▾" : "▸"} {r.empleado_nombre}
          </button>
        </td>
        <td className="tabular">{r.dias_trabajados}</td>
        <td className="tabular" style={{ textAlign: "right" }}>{dinero(c.total_ingresos)}</td>
        <td className="tabular" style={{ textAlign: "right" }}>{dinero(c.total_descuentos)}</td>
        <td className="tabular" style={{ textAlign: "right", fontWeight: 700 }}>{dinero(r.neto)}</td>
        <td className="tabular" style={{ textAlign: "right" }}>{dinero(r.costo_empleador)}</td>
        <td><span className={`badge ${r.estado === "pagado" ? "badge-ok" : "badge-warn"}`}>{r.estado_nombre}</span></td>
        <td style={{ whiteSpace: "nowrap" }}>
          <button type="button" className="btn btn-ghost" style={botonFila} onClick={alPdf}>PDF</button>
          {r.estado === "borrador" && (
            <>
              <button type="button" className="btn btn-ghost" style={botonFila} onClick={alAjustar}>Ajustar</button>
              <button type="button" className="btn btn-ghost" style={botonFila} onClick={alPagar}>Pagar</button>
            </>
          )}
          <button type="button" className="btn btn-ghost" style={{ ...botonFila, color: "var(--red)" }} onClick={alAnular}>Anular</button>
        </td>
      </tr>
      {abierto && (
        <tr>
          <td colSpan={8} style={{ background: "var(--paper)" }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 18, fontSize: 13 }}>
              <Detalle titulo="Ingresos" filas={c.ingresos} />
              <Detalle titulo="Descuentos" filas={c.descuentos} />
              <Detalle titulo="A cargo de la clínica"
                       filas={[{ concepto: `Aporte patronal ${String(c.aporte_patronal_porcentaje || "").replace(".", ",")} %`, valor: c.aporte_patronal },
                               ...(c.provisiones || [])]} />
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function Detalle({ titulo, filas }) {
  return (
    <div>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{titulo}</div>
      {(filas || []).map((f) => (
        <div key={f.concepto} style={{ display: "flex", justifyContent: "space-between", padding: "2px 0" }}>
          <span>{f.concepto}</span><span className="tabular">{dinero(f.valor)}</span>
        </div>
      ))}
    </div>
  );
}
