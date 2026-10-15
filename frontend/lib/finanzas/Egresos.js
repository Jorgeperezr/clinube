"use client";

/**
 * Egresos: lo que sale de la clínica. Cada uno con su categoría, y si
 * hay factura del proveedor, su RUC y número (es lo que pide el contador
 * para declarar). Lo que aún no se paga queda como cuenta por pagar.
 *
 * Nada se borra: un egreso equivocado se anula con su motivo, y se ve
 * tachado si se piden los anulados.
 */

import { useCallback, useEffect, useState } from "react";

import { api, apiErrorMessage, readList } from "../api";
import { useConfirm } from "../ConfirmDialog";
import { hoyISO } from "../fechas.mjs";
import { abrirPdf, Aviso, botonFila, dinero, enviar, fecha, FORMAS_PAGO, rejillaFormulario } from "./comunes";

const VACIO = {
  fecha: "", categoria: "", concepto: "", monto: "", forma_pago: "efectivo", estado: "pagado", vence: "",
  proveedor: "", proveedor_ruc: "", numero_factura: "", profesional: "", descontar_al_profesional: false,
};

const ORIGEN = {
  liquidacion: "Liquidación", rol: "Rol de pagos", inventario: "Compra de inventario",
  iess: "Planilla del IESS", sri: "Retenciones al SRI", decimo_tercero: "Décimo tercero", decimo_cuarto: "Décimo cuarto",
};
// Los crea Clinube al registrar un pago: no se corrigen a mano.
const CALCULADOS = ["liquidacion", "rol", "iess", "sri", "decimo_tercero", "decimo_cuarto"];

export default function Egresos({ mes, equipo, categorias }) {
  const [confirmar, ConfirmUI] = useConfirm();
  const [vista, setVista] = useState("mes");
  const [verAnulados, setVerAnulados] = useState(false);
  const [filas, setFilas] = useState(null);
  const [form, setForm] = useState(null);       // null: cerrado; {…, id?}
  const [archivo, setArchivo] = useState(null);
  const [anulando, setAnulando] = useState(null); // {id, motivo}
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const cargar = useCallback(() => {
    const q = vista === "por_pagar" ? "estado=por_pagar" : `mes=${mes}`;
    api(`/finanzas/egresos/?${q}${verAnulados ? "&anulados=1" : ""}`).then(readList).then(setFilas)
      .catch((e) => setError(e.message));
  }, [mes, vista, verAnulados]);

  useEffect(() => { setFilas(null); cargar(); }, [cargar]);

  function nuevo() {
    setOk(""); setError(""); setArchivo(null);
    setForm({ ...VACIO, fecha: hoyISO(), categoria: (categorias.find((c) => c.activa && !["honorarios", "sueldos"].includes(c.clave))
      || categorias.find((c) => c.activa))?.id || "" });
  }

  function editar(e) {
    setOk(""); setError(""); setArchivo(null);
    setForm({ ...VACIO, ...e, profesional: e.profesional || "", vence: e.vence || "" });
  }

  async function guardar(ev) {
    ev.preventDefault();
    setError(""); setGuardando(true);
    try {
      const datos = new FormData();
      for (const [k, v] of Object.entries(VACIO)) {
        const valor = form[k];
        if (k === "vence" && (form.estado !== "por_pagar" || !valor)) continue;
        if (k === "descontar_al_profesional") datos.append(k, valor && form.profesional ? "true" : "false");
        else datos.append(k, valor ?? "");
      }
      if (archivo) datos.append("comprobante", archivo);
      const resp = await api(form.id ? `/finanzas/egresos/${form.id}/` : "/finanzas/egresos/", {
        method: form.id ? "PATCH" : "POST", body: datos,
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp));
      setOk(form.id ? "Egreso actualizado." : "Egreso registrado.");
      setForm(null);
      cargar();
    } catch (e) { setError(e.message); }
    finally { setGuardando(false); }
  }

  async function pagar(e) {
    const si = await confirmar({
      title: "Marcar como pagado",
      message: `${e.concepto} — ${dinero(e.monto)}\nSe apunta con fecha de hoy y ${FORMAS_PAGO[e.forma_pago].toLowerCase()}.`,
      confirmLabel: "Pagado",
    });
    if (!si) return;
    setError("");
    try { await enviar(`/finanzas/egresos/${e.id}/pagar/`, { fecha: hoyISO() }); setOk("Pago registrado."); cargar(); }
    catch (err) { setError(err.message); }
  }

  async function anular(ev) {
    ev.preventDefault();
    setError("");
    try {
      await enviar(`/finanzas/egresos/${anulando.id}/anular/`, { motivo: anulando.motivo });
      setAnulando(null); setOk("Egreso anulado."); cargar();
    } catch (err) { setError(err.message); }
  }

  async function verComprobante(e) {
    setError("");
    try { await abrirPdf(`/finanzas/egresos/${e.id}/comprobante/`); } catch (err) { setError(err.message); }
  }

  const cambia = (campo) => (ev) => setForm({ ...form, [campo]: ev.target.type === "checkbox" ? ev.target.checked : ev.target.value });
  const validos = (filas || []).filter((f) => !f.anulado);
  const total = validos.reduce((s, f) => s + Number(f.monto), 0);
  const pendiente = validos.filter((f) => f.estado === "por_pagar").reduce((s, f) => s + Number(f.monto), 0);

  return (
    <div>
      {ConfirmUI}
      <div className="barra-herramientas" style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
        <div className="segmentado" role="group" aria-label="Qué egresos ver">
          <button type="button" aria-pressed={vista === "mes"} onClick={() => setVista("mes")}>Del mes</button>
          <button type="button" aria-pressed={vista === "por_pagar"} onClick={() => setVista("por_pagar")}>Cuentas por pagar</button>
        </div>
        <label style={{ fontSize: 13, color: "var(--ink-soft)", display: "flex", gap: 6, alignItems: "center" }}>
          <input type="checkbox" checked={verAnulados} onChange={(e) => setVerAnulados(e.target.checked)} />
          Ver anulados
        </label>
        {!form && <button type="button" className="btn btn-primary" style={{ marginLeft: "auto" }} onClick={nuevo}>+ Registrar egreso</button>}
      </div>

      <Aviso error={error} ok={ok} />

      {form && (
        <form className="card" onSubmit={guardar}>
          <h3 style={{ marginBottom: 12 }}>{form.id ? "Corregir egreso" : "Nuevo egreso"}</h3>
          <div style={rejillaFormulario}>
            <div className="field">
              <label>Fecha *</label>
              <input type="date" required value={form.fecha} onChange={cambia("fecha")} />
            </div>
            <div className="field">
              <label>Categoría *</label>
              <select required value={form.categoria} onChange={cambia("categoria")}>
                {categorias.filter((c) => c.activa || c.id === form.categoria)
                  .map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
              </select>
            </div>
            <div className="field" style={{ gridColumn: "span 2" }}>
              <label>Concepto *</label>
              <input required maxLength={200} value={form.concepto} onChange={cambia("concepto")}
                     placeholder="Ej.: Arriendo de octubre, coronas de zirconio" />
            </div>
            <div className="field">
              <label>Monto (USD) *</label>
              <input type="number" step="0.01" min="0.01" required value={form.monto} onChange={cambia("monto")} />
            </div>
            <div className="field">
              <label>Forma de pago</label>
              <select value={form.forma_pago} onChange={cambia("forma_pago")}>
                {Object.entries(FORMAS_PAGO).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <div className="field">
              <label>Estado</label>
              <select value={form.estado} onChange={cambia("estado")}>
                <option value="pagado">Pagado</option>
                <option value="por_pagar">Por pagar</option>
              </select>
            </div>
            {form.estado === "por_pagar" && (
              <div className="field">
                <label>Vence</label>
                <input type="date" value={form.vence} onChange={cambia("vence")} />
              </div>
            )}
          </div>

          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink-soft)", margin: "4px 0 8px" }}>
            Factura del proveedor (si la hay)
          </div>
          <div style={rejillaFormulario}>
            <div className="field">
              <label>Proveedor</label>
              <input maxLength={150} value={form.proveedor} onChange={cambia("proveedor")} />
            </div>
            <div className="field">
              <label>RUC o cédula</label>
              <input inputMode="numeric" maxLength={13} value={form.proveedor_ruc} onChange={cambia("proveedor_ruc")} />
            </div>
            <div className="field">
              <label>N.º de factura</label>
              <input maxLength={20} value={form.numero_factura} onChange={cambia("numero_factura")} placeholder="001-001-000001234" />
            </div>
            <div className="field">
              <label>Archivo (foto, PDF o XML)</label>
              <input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp,.heic,.xml"
                     onChange={(e) => setArchivo(e.target.files?.[0] || null)} />
            </div>
          </div>

          <div style={rejillaFormulario}>
            <div className="field">
              <label>Profesional relacionado</label>
              <select value={form.profesional} onChange={cambia("profesional")}>
                <option value="">Ninguno</option>
                {equipo.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
              </select>
            </div>
            {form.profesional && (
              <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 14, marginBottom: 16 }}>
                <input type="checkbox" checked={form.descontar_al_profesional} onChange={cambia("descontar_al_profesional")} />
                Descontarlo de su liquidación de honorarios (laboratorio, materiales, anticipos)
              </label>
            )}
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-primary" disabled={guardando}>{guardando ? "Guardando…" : "Guardar"}</button>
            <button type="button" className="btn btn-ghost" onClick={() => setForm(null)}>Cancelar</button>
          </div>
        </form>
      )}

      {anulando && (
        <form className="card" onSubmit={anular} style={{ display: "flex", gap: 10, alignItems: "end", flexWrap: "wrap" }}>
          <div className="field" style={{ marginBottom: 0, flex: "1 1 260px" }}>
            <label>¿Por qué se anula «{anulando.concepto}»?</label>
            <input autoFocus required maxLength={200} value={anulando.motivo}
                   onChange={(e) => setAnulando({ ...anulando, motivo: e.target.value })}
                   placeholder="Ej.: registrado dos veces" />
          </div>
          <button className="btn btn-danger">Anular</button>
          <button type="button" className="btn btn-ghost" onClick={() => setAnulando(null)}>Cancelar</button>
        </form>
      )}

      <div className="card" style={{ padding: 0 }}>
        <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--line)", display: "flex", justifyContent: "space-between", gap: 8 }}>
          <strong>{vista === "por_pagar" ? "Pendientes de pago" : "Egresos del mes"}</strong>
          <span className="tabular" style={{ fontWeight: 700 }}>
            {vista === "mes" && pendiente > 0 && (
              <span style={{ fontWeight: 400, fontSize: 13, color: "var(--ink-soft)", marginRight: 10 }}>
                pagado {dinero(total - pendiente)} · por pagar {dinero(pendiente)}
              </span>
            )}
            {dinero(total)}
          </span>
        </div>
        {!filas ? <div className="empty">Cargando…</div> : filas.length === 0 ? (
          <div className="empty">{vista === "por_pagar" ? "No hay cuentas por pagar." : "Sin egresos este mes."}</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr><th>Fecha</th><th>Categoría</th><th>Concepto</th><th>Forma</th><th>Estado</th>
                  <th style={{ textAlign: "right" }}>Monto</th><th /></tr>
              </thead>
              <tbody>
                {filas.map((e) => {
                  const vencido = e.estado === "por_pagar" && e.vence && e.vence < hoyISO();
                  return (
                    <tr key={e.id} style={e.anulado ? { opacity: 0.55 } : undefined}>
                      <td className="tabular" style={{ whiteSpace: "nowrap" }}>{fecha(e.fecha)}</td>
                      <td>{e.categoria_nombre}</td>
                      <td>
                        <div style={e.anulado ? { textDecoration: "line-through" } : undefined}>{e.concepto}</div>
                        <div style={{ fontSize: 12, color: "var(--ink-soft)" }}>
                          {[e.proveedor, e.numero_factura && `Fact. ${e.numero_factura}`, ORIGEN[e.origen],
                            e.profesional_nombre && (e.descontar_al_profesional ? `se descuenta a ${e.profesional_nombre}` : e.profesional_nombre)]
                            .filter(Boolean).join(" · ")}
                          {e.anulado && ` · Anulado: ${e.motivo_anulacion}`}
                        </div>
                      </td>
                      <td>{e.forma_pago_nombre}</td>
                      <td>
                        {e.anulado ? <span className="badge">Anulado</span>
                          : e.estado === "pagado" ? <span className="badge badge-ok">Pagado</span>
                          : <span className={`badge ${vencido ? "badge-danger" : "badge-warn"}`}>
                              {vencido ? "Vencido" : "Por pagar"}{e.vence ? ` · ${fecha(e.vence)}` : ""}
                            </span>}
                      </td>
                      <td className="tabular" style={{ textAlign: "right", fontWeight: 600 }}>{dinero(e.monto)}</td>
                      <td style={{ whiteSpace: "nowrap" }}>
                        {e.tiene_comprobante && (
                          <button type="button" className="btn btn-ghost" style={botonFila} onClick={() => verComprobante(e)}>Factura</button>
                        )}
                        {!e.anulado && e.estado === "por_pagar" && (
                          <button type="button" className="btn btn-ghost" style={botonFila} onClick={() => pagar(e)}>Pagar</button>
                        )}
                        {!e.anulado && !["liquidacion", "rol"].includes(e.origen) && (
                          <>
                            {!CALCULADOS.includes(e.origen) && (
                              <button type="button" className="btn btn-ghost" style={botonFila} onClick={() => editar(e)}>Corregir</button>
                            )}
                            <button type="button" className="btn btn-ghost" style={{ ...botonFila, color: "var(--red)" }}
                                    onClick={() => setAnulando({ id: e.id, concepto: e.concepto, motivo: "" })}>Anular</button>
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
