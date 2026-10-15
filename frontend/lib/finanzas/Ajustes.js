"use client";

/**
 * Los valores que cambian por ley o por decisión de la clínica: salario
 * básico, porcentajes del IESS, retención a honorarios y el número del
 * próximo comprobante. Vienen con los de 2026 y se cambian aquí cuando
 * salga una resolución nueva, sin esperar a una actualización.
 */

import { useEffect, useState } from "react";

import { api, readObject } from "../api";
import { Aviso, enviar, rejillaFormulario } from "./comunes";

const VALORES = [
  ["salario_basico", "Salario básico unificado (USD)", "482 en 2026. Sirve para el décimo cuarto."],
  ["aporte_personal_iess", "Aporte personal IESS (%)", "Se descuenta al trabajador. 9,45 % en el régimen general."],
  ["aporte_patronal_iess", "Aporte patronal IESS (%)", "Lo paga la clínica. 11,15 %."],
  ["aporte_iece_secap", "IECE y SECAP (%)", "También a cargo de la clínica. 1 % (0,5 % cada uno)."],
  ["fondos_reserva", "Fondos de reserva (%)", "8,33 % desde el segundo año de trabajo."],
  ["retencion_honorarios", "Retención IR a honorarios (%)", "Para profesionales que facturan a la clínica. Revisa la tabla vigente del SRI con tu contador."],
];

export default function Ajustes({ categorias, alCambiarCategorias }) {
  const [config, setConfig] = useState(null);
  const [nueva, setNueva] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  useEffect(() => {
    api("/finanzas/configuracion/").then(readObject).then(setConfig).catch((e) => setError(e.message));
  }, []);

  async function guardar(ev) {
    ev.preventDefault();
    setError(""); setOk("");
    try { setConfig(await enviar("/finanzas/configuracion/", config, "PATCH")); setOk("Valores guardados."); }
    catch (e) { setError(e.message); }
  }

  async function agregar(ev) {
    ev.preventDefault();
    if (!nueva.trim()) return;
    setError(""); setOk("");
    try {
      await enviar("/finanzas/categorias/", { nombre: nueva.trim(), orden: 100 });
      setNueva(""); alCambiarCategorias();
    } catch (e) { setError(e.message); }
  }

  async function cambiarCategoria(c, cambios) {
    setError("");
    try { await enviar(`/finanzas/categorias/${c.id}/`, cambios, "PATCH"); alCambiarCategorias(); }
    catch (e) { setError(e.message); }
  }

  return (
    <div>
      <Aviso error={error} ok={ok} />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 18, alignItems: "start" }}>
        <form className="card" onSubmit={guardar}>
          <h3 style={{ marginBottom: 4 }}>Valores de ley</h3>
          <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 14 }}>
            Se usan en el rol de pagos y en las liquidaciones. Cambiarlos no toca lo que ya está guardado.
          </p>
          {!config ? <div className="empty">Cargando…</div> : (
            <>
              {VALORES.map(([k, t, ayuda]) => (
                <div className="field" key={k}>
                  <label>{t}</label>
                  <input type="number" step="0.01" min="0" value={config[k]} onChange={(e) => setConfig({ ...config, [k]: e.target.value })} />
                  <span style={{ fontSize: 12, color: "var(--ink-faint)" }}>{ayuda}</span>
                </div>
              ))}
              <div className="field">
                <label>Región (décimo cuarto)</label>
                <select value={config.region} onChange={(e) => setConfig({ ...config, region: e.target.value })}>
                  <option value="sierra">Sierra y Amazonía: se paga hasta el 15 de agosto</option>
                  <option value="costa">Costa y Galápagos: se paga hasta el 15 de marzo</option>
                </select>
              </div>
              <div style={rejillaFormulario}>
                <div className="field">
                  <label>Recargo horas suplementarias (%)</label>
                  <input type="number" step="0.01" min="0" value={config.recargo_suplementarias}
                         onChange={(e) => setConfig({ ...config, recargo_suplementarias: e.target.value })} />
                </div>
                <div className="field">
                  <label>Recargo horas extraordinarias (%)</label>
                  <input type="number" step="0.01" min="0" value={config.recargo_extraordinarias}
                         onChange={(e) => setConfig({ ...config, recargo_extraordinarias: e.target.value })} />
                </div>
              </div>
              <div className="field">
                <label>Próximo comprobante de cobro</label>
                <input type="number" step="1" min="1" value={config.siguiente_comprobante}
                       onChange={(e) => setConfig({ ...config, siguiente_comprobante: e.target.value })} />
                <span style={{ fontSize: 12, color: "var(--ink-faint)" }}>Si venías de un talonario de papel, empieza donde lo dejaste.</span>
              </div>
              <button className="btn btn-primary">Guardar</button>
            </>
          )}
        </form>

        <div className="card">
          <h3 style={{ marginBottom: 4 }}>Categorías de egreso</h3>
          <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 14 }}>
            Desactivar una categoría la quita del formulario, pero los egresos que ya la usan la conservan.
          </p>
          {categorias.map((c) => (
            <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 0", borderBottom: "1px solid var(--line)" }}>
              <input defaultValue={c.nombre} aria-label="Nombre de la categoría" maxLength={60}
                     style={{ flex: 1, border: "none", background: "transparent", fontSize: 14, color: c.activa ? "var(--ink)" : "var(--ink-faint)" }}
                     onBlur={(e) => e.target.value.trim() && e.target.value !== c.nombre && cambiarCategoria(c, { nombre: e.target.value.trim() })} />
              {c.clave && <span style={{ fontSize: 11, color: "var(--ink-faint)" }} title="La usan las liquidaciones, los roles o el inventario">del sistema</span>}
              <label style={{ fontSize: 12, display: "flex", gap: 4, alignItems: "center" }}>
                <input type="checkbox" checked={c.activa} disabled={["honorarios", "sueldos", "insumos"].includes(c.clave)}
                       onChange={(e) => cambiarCategoria(c, { activa: e.target.checked })} />
                Activa
              </label>
            </div>
          ))}
          <form onSubmit={agregar} style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <div className="field" style={{ marginBottom: 0, flex: 1 }}>
              <input value={nueva} maxLength={60} onChange={(e) => setNueva(e.target.value)} placeholder="Nueva categoría" aria-label="Nueva categoría" />
            </div>
            <button className="btn btn-ghost">Añadir</button>
          </form>
        </div>
      </div>
    </div>
  );
}
