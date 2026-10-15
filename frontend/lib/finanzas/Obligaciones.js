"use client";

/**
 * Lo que la clínica paga a terceros por su equipo: la planilla del IESS
 * y las retenciones al SRI de cada mes, y los décimos que se acumulan
 * para quien no los cobra mensualmente. Registrar el pago lo deja como
 * egreso; si se equivocó, se anula ese egreso y vuelve a quedar pendiente.
 */

import { useCallback, useEffect, useState } from "react";

import { api, readObject } from "../api";
import { hoyISO } from "../fechas.mjs";
import { Aviso, botonFila, dinero, enviar, fecha, FORMAS_PAGO, nombreMes } from "./comunes";

function Pago({ texto, alPagar, alCancelar }) {
  const [datos, setDatos] = useState({ fecha: hoyISO(), forma_pago: "transferencia" });
  return (
    <form onSubmit={(e) => { e.preventDefault(); alPagar(datos); }}
          style={{ display: "flex", gap: 10, alignItems: "end", flexWrap: "wrap", marginTop: 12 }}>
      <strong style={{ flex: "1 1 100%", fontSize: 14 }}>{texto}</strong>
      <div className="field" style={{ marginBottom: 0 }}>
        <label>Fecha de pago</label>
        <input type="date" value={datos.fecha} onChange={(e) => setDatos({ ...datos, fecha: e.target.value })} />
      </div>
      <div className="field" style={{ marginBottom: 0 }}>
        <label>Forma de pago</label>
        <select value={datos.forma_pago} onChange={(e) => setDatos({ ...datos, forma_pago: e.target.value })}>
          {Object.entries(FORMAS_PAGO).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      <button className="btn btn-primary">Registrar pago</button>
      <button type="button" className="btn btn-ghost" onClick={alCancelar}>Cancelar</button>
    </form>
  );
}

export default function Obligaciones({ mes }) {
  const [lista, setLista] = useState(null);
  const [pagando, setPagando] = useState(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const cargar = useCallback(() => {
    api(`/finanzas/obligaciones/?mes=${mes}`).then(readObject).then((d) => setLista(d.obligaciones))
      .catch((e) => setError(e.message));
  }, [mes]);
  useEffect(() => { setLista(null); setError(""); setOk(""); setPagando(null); cargar(); }, [cargar]);

  async function pagar(o, datos) {
    setError("");
    try {
      await enviar("/finanzas/obligaciones/", { tipo: o.tipo, mes, ...datos });
      setPagando(null); setOk(`${o.nombre}: pago registrado como egreso.`); cargar();
    } catch (e) { setError(e.message); }
  }

  return (
    <div>
      <Aviso error={error} ok={ok} />
      <h3 style={{ marginBottom: 4 }}>IESS y SRI de {nombreMes(mes)}</h3>
      <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 12 }}>
        Salen de los roles de pagos y de las liquidaciones pagadas en el mes.
      </p>
      {!lista ? <div className="card"><div className="empty">Cargando…</div></div> : lista.length === 0 ? (
        <div className="card"><div className="empty">Nada que pagar al IESS ni al SRI por este mes.</div></div>
      ) : lista.map((o) => {
        const vencida = !o.pagado && o.vence < hoyISO();
        return (
          <div key={o.tipo} className="card">
            <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap", alignItems: "baseline" }}>
              <div>
                <strong>{o.nombre}</strong>
                <div style={{ fontSize: 12, color: "var(--ink-soft)" }}>{o.nota}</div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div className="tabular" style={{ fontSize: 20, fontWeight: 700 }}>{dinero(o.monto)}</div>
                {o.pagado
                  ? <span className="badge badge-ok">Pagado el {fecha(o.fecha_pago)}</span>
                  : <span className={`badge ${vencida ? "badge-danger" : "badge-warn"}`}>
                      {vencida ? "Vencido" : "Vence"} el {fecha(o.vence)}
                    </span>}
              </div>
            </div>
            <div style={{ marginTop: 10, fontSize: 13 }}>
              {o.detalle.map((d) => (
                <div key={d.concepto} style={{ display: "flex", justifyContent: "space-between", padding: "2px 0" }}>
                  <span>{d.concepto}</span><span className="tabular">{dinero(d.valor)}</span>
                </div>
              ))}
            </div>
            {o.pagado && Number(o.diferencia) !== 0 && (
              <p style={{ fontSize: 12, color: "var(--amber)", marginTop: 8 }}>
                Los roles cambiaron después del pago: hay {dinero(o.diferencia)} de diferencia. Anula ese egreso y vuelve a registrarlo.
              </p>
            )}
            {!o.pagado && (pagando === o.tipo
              ? <Pago texto={`Pagar ${dinero(o.monto)}`} alPagar={(d) => pagar(o, d)} alCancelar={() => setPagando(null)} />
              : <button type="button" className="btn btn-ghost" style={{ ...botonFila, marginTop: 10 }}
                        onClick={() => setPagando(o.tipo)}>Registrar el pago</button>)}
          </div>
        );
      })}

      <Decimos />
    </div>
  );
}

function Decimos() {
  const hoy = new Date();
  const [tipo, setTipo] = useState("tercero");
  const [anio, setAnio] = useState(hoy.getFullYear());
  const [datos, setDatos] = useState(null);
  const [pagando, setPagando] = useState(null);   // "todos" | id
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const cargar = useCallback(() => {
    api(`/finanzas/decimos/?tipo=${tipo}&anio=${anio}`).then(readObject).then(setDatos).catch((e) => setError(e.message));
  }, [tipo, anio]);
  useEffect(() => { setDatos(null); setError(""); setOk(""); setPagando(null); cargar(); }, [cargar]);

  async function pagar(extra) {
    setError("");
    try {
      const d = await enviar("/finanzas/decimos/", {
        tipo, anio, ...(pagando !== "todos" ? { empleado: pagando } : {}), ...extra,
      });
      setDatos(d); setPagando(null); setOk("Pago registrado como egreso de sueldos.");
    } catch (e) { setError(e.message); }
  }

  return (
    <div style={{ marginTop: 26 }}>
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", marginBottom: 10 }}>
        <h3 style={{ margin: 0 }}>Décimos acumulados</h3>
        <div className="segmentado" role="group" aria-label="Décimo">
          <button type="button" aria-pressed={tipo === "tercero"} onClick={() => setTipo("tercero")}>Décimo tercero</button>
          <button type="button" aria-pressed={tipo === "cuarto"} onClick={() => setTipo("cuarto")}>Décimo cuarto</button>
        </div>
        <div className="field" style={{ marginBottom: 0 }}>
          <select value={anio} onChange={(e) => setAnio(Number(e.target.value))} aria-label="Año de pago">
            {[hoy.getFullYear() + 1, hoy.getFullYear(), hoy.getFullYear() - 1].map((a) => <option key={a} value={a}>Se paga en {a}</option>)}
          </select>
        </div>
      </div>
      <Aviso error={error} ok={ok} />
      {!datos ? <div className="card"><div className="empty">Cargando…</div></div> : (
        <div className="card" style={{ padding: 0 }}>
          <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--line)", fontSize: 13, color: "var(--ink-soft)" }}>
            Período del {fecha(datos.desde)} al {fecha(datos.hasta)} · se paga hasta el {fecha(datos.vence)}
            {tipo === "cuarto" && ` · ${datos.region === "costa" ? "Costa y Galápagos" : "Sierra y Amazonía"} (se cambia en Ajustes)`}
          </div>
          {datos.filas.length === 0 ? (
            <div className="empty">Nadie lo tiene acumulado en este período (o todos lo cobran cada mes).</div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table>
                <thead><tr><th>Persona</th><th>Meses en roles</th><th style={{ textAlign: "right" }}>Acumulado</th><th>Estado</th><th /></tr></thead>
                <tbody>
                  {datos.filas.map((f) => (
                    <tr key={f.empleado}>
                      <td>{f.nombre}</td>
                      <td className="tabular">{f.meses}</td>
                      <td className="tabular" style={{ textAlign: "right", fontWeight: 600 }}>{dinero(f.monto)}</td>
                      <td>{f.pagado ? <span className="badge badge-ok">Pagado el {fecha(f.fecha_pago)}</span>
                        : <span className="badge badge-warn">Pendiente</span>}</td>
                      <td>{!f.pagado && <button type="button" className="btn btn-ghost" style={botonFila}
                                                onClick={() => setPagando(f.empleado)}>Pagar</button>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {Number(datos.pendiente) > 0 && (
            <div style={{ padding: "12px 16px", borderTop: "1px solid var(--line)" }}>
              {pagando ? (
                <Pago texto={pagando === "todos" ? `Pagar a todos: ${dinero(datos.pendiente)}`
                  : `Pagar a ${datos.filas.find((f) => f.empleado === pagando)?.nombre}`}
                      alPagar={pagar} alCancelar={() => setPagando(null)} />
              ) : (
                <button type="button" className="btn btn-primary" onClick={() => setPagando("todos")}>
                  Pagar a todos ({dinero(datos.pendiente)})
                </button>
              )}
            </div>
          )}
        </div>
      )}
      <p style={{ fontSize: 12, color: "var(--ink-faint)" }}>
        El acumulado suma lo provisionado en los roles generados en Clinube. Si alguien entró antes de usar Clinube, añade lo que falte como egreso aparte.
      </p>
    </div>
  );
}
