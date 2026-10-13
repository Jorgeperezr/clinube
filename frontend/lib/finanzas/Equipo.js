"use client";

/**
 * Cómo se le paga a cada persona del equipo. Es lo que usan después la
 * liquidación de honorarios y el rol de pagos, así que se ajusta aquí y
 * no en cada cálculo.
 *
 *  · Por honorarios: emite su factura a la clínica y cobra un porcentaje
 *    de lo que pagan sus pacientes, o un monto fijo.
 *  · En relación de dependencia: sueldo con IESS, décimos y fondos de
 *    reserva, en un rol de pagos mensual.
 */

import { useState } from "react";

import { Aviso, botonFila, dinero, enviar, rejillaFormulario } from "./comunes";

const MODALIDADES = {
  ninguna: "No se le paga desde la clínica",
  honorarios: "Por honorarios (factura a la clínica)",
  dependencia: "En relación de dependencia (rol de pagos)",
};

function condicion(p) {
  if (p.modalidad === "honorarios") {
    const base = p.base_honorarios === "fijo" ? `${dinero(p.monto_fijo)} fijos` : `${Number(p.porcentaje)} % de lo cobrado`;
    return `${base}${p.emite_factura ? " · con retención" : ""}`;
  }
  if (p.modalidad === "dependencia") return `Sueldo ${dinero(p.sueldo)}`;
  return "—";
}

export default function Equipo({ equipo, alCambiar }) {
  const [editando, setEditando] = useState(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  async function guardar(ev) {
    ev.preventDefault();
    setError(""); setOk("");
    const { id, nombre, rol, ...perfil } = editando;
    if (!perfil.fecha_ingreso) perfil.fecha_ingreso = null;
    try {
      const r = await enviar(`/finanzas/equipo/${id}/`, perfil, "PATCH");
      alCambiar(r);
      setEditando(null);
      setOk(`Guardado: ${nombre}.`);
    } catch (e) { setError(e.message); }
  }

  const cambia = (campo) => (ev) => setEditando({ ...editando, [campo]: ev.target.type === "checkbox" ? ev.target.checked : ev.target.value });

  return (
    <div>
      <Aviso error={error} ok={ok} />

      {editando && (
        <form className="card" onSubmit={guardar}>
          <h3 style={{ marginBottom: 12 }}>{editando.nombre}</h3>
          <div style={rejillaFormulario}>
            <div className="field" style={{ gridColumn: "span 2" }}>
              <label>Cómo se le paga</label>
              <select value={editando.modalidad} onChange={cambia("modalidad")}>
                {Object.entries(MODALIDADES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <div className="field">
              <label>Cédula o RUC</label>
              <input inputMode="numeric" maxLength={13} value={editando.cedula} onChange={cambia("cedula")} />
            </div>
            <div className="field">
              <label>Cargo</label>
              <input maxLength={80} value={editando.cargo} onChange={cambia("cargo")} placeholder="Ej.: Odontóloga general" />
            </div>
          </div>

          {editando.modalidad === "honorarios" && (
            <div style={rejillaFormulario}>
              <div className="field">
                <label>Se calcula como</label>
                <select value={editando.base_honorarios} onChange={cambia("base_honorarios")}>
                  <option value="cobrado">Porcentaje de lo cobrado a sus pacientes</option>
                  <option value="fijo">Monto fijo por período</option>
                </select>
              </div>
              {editando.base_honorarios === "fijo" ? (
                <div className="field">
                  <label>Monto fijo (USD)</label>
                  <input type="number" step="0.01" min="0" value={editando.monto_fijo} onChange={cambia("monto_fijo")} />
                </div>
              ) : (
                <div className="field">
                  <label>Porcentaje para el profesional</label>
                  <input type="number" step="0.01" min="0" max="100" value={editando.porcentaje} onChange={cambia("porcentaje")} />
                </div>
              )}
              <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 14, marginBottom: 16 }}>
                <input type="checkbox" checked={editando.emite_factura} onChange={cambia("emite_factura")} />
                Emite factura y se le retiene Impuesto a la Renta
              </label>
            </div>
          )}

          {editando.modalidad === "dependencia" && (
            <>
              <div style={rejillaFormulario}>
                <div className="field">
                  <label>Sueldo mensual (USD)</label>
                  <input type="number" step="0.01" min="0" value={editando.sueldo} onChange={cambia("sueldo")} />
                </div>
                <div className="field">
                  <label>Fecha de ingreso</label>
                  <input type="date" value={editando.fecha_ingreso || ""} onChange={cambia("fecha_ingreso")} />
                </div>
              </div>
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink-soft)", marginBottom: 6 }}>Cobra mensualmente en el rol</div>
              <div style={{ display: "flex", gap: 18, flexWrap: "wrap", fontSize: 14, marginBottom: 6 }}>
                <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <input type="checkbox" checked={editando.decimo_tercero_mensual} onChange={cambia("decimo_tercero_mensual")} />
                  Décimo tercero
                </label>
                <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <input type="checkbox" checked={editando.decimo_cuarto_mensual} onChange={cambia("decimo_cuarto_mensual")} />
                  Décimo cuarto
                </label>
                <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <input type="checkbox" checked={editando.fondos_reserva_mensual} onChange={cambia("fondos_reserva_mensual")} />
                  Fondos de reserva
                </label>
              </div>
              <p style={{ fontSize: 12, color: "var(--ink-soft)", marginBottom: 14 }}>
                Lo que no se marque se acumula para pagarlo en su fecha (décimo tercero en diciembre, décimo cuarto en agosto en la Sierra
                y en marzo en la Costa) o, los fondos de reserva, para depositarlos en el IESS. Los fondos se pagan desde el segundo año.
                La mensualización la pide la propia persona por escrito.
              </p>
            </>
          )}

          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-primary">Guardar</button>
            <button type="button" className="btn btn-ghost" onClick={() => setEditando(null)}>Cancelar</button>
          </div>
        </form>
      )}

      <div className="card" style={{ padding: 0 }}>
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead><tr><th>Persona</th><th>Cómo se le paga</th><th>Condición</th><th /></tr></thead>
            <tbody>
              {equipo.map((p) => (
                <tr key={p.id}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{p.nombre}</div>
                    <div style={{ fontSize: 12, color: "var(--ink-soft)" }}>{p.cargo || p.rol}</div>
                  </td>
                  <td>{p.modalidad === "ninguna" ? <span style={{ color: "var(--ink-soft)" }}>Sin definir</span>
                    : p.modalidad === "honorarios" ? "Honorarios" : "Rol de pagos"}</td>
                  <td className="tabular">{condicion(p)}</td>
                  <td><button type="button" className="btn btn-ghost" style={botonFila}
                              onClick={() => { setOk(""); setEditando({ ...p }); }}>Ajustar</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
