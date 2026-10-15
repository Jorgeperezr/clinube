"use client";

/**
 * Certificado de atención odontológica, desde la ficha del paciente.
 * Al elegir el día se rellena con lo que ya hay: la hora de su cita,
 * quién lo atendió y los diagnósticos de ese día. Todo se puede cambiar
 * antes de generar el PDF.
 */

import { useEffect, useState } from "react";

import { api, apiErrorMessage, readList } from "./api";
import { hoyISO } from "./fechas.mjs";

const VACIO = {
  hora_inicio: "", hora_fin: "", doctor: "", diagnostico: "", procedimiento: "",
  reposo_dias: "0", lugar: "", observaciones: "",
};

export default function CertificadoAtencion({ patientId }) {
  const [abierto, setAbierto] = useState(false);
  const [fecha, setFecha] = useState(hoyISO());
  const [form, setForm] = useState(VACIO);
  const [doctores, setDoctores] = useState([]);
  const [sinCita, setSinCita] = useState(false);
  const [generando, setGenerando] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!abierto) return;
    api("/doctors/").then(readList).then((ds) => setDoctores(ds.filter((d) => d.is_active))).catch(() => {});
  }, [abierto]);

  useEffect(() => {
    if (!abierto || !fecha) return;
    api(`/patients/${patientId}/certificado-atencion/?fecha=${fecha}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d) return;
        setSinCita(!d.hubo_cita);
        setForm((f) => ({
          ...f, hora_inicio: d.hora_inicio, hora_fin: d.hora_fin, doctor: d.doctor || f.doctor,
          diagnostico: d.diagnostico, lugar: f.lugar || d.lugar,
        }));
      }).catch(() => {});
  }, [abierto, fecha, patientId]);

  async function generar(e) {
    e.preventDefault();
    setError("");
    setGenerando(true);
    // La pestaña se abre antes de pedir el PDF: Safari bloquea las que
    // se abren cuando ya terminó la petición.
    const pestana = window.open("", "_blank");
    try {
      const resp = await api(`/patients/${patientId}/certificado-atencion/`, {
        method: "POST", body: JSON.stringify({ ...form, fecha }),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp));
      const url = URL.createObjectURL(await resp.blob());
      if (pestana) pestana.location.href = url; else window.location.href = url;
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      pestana?.close();
      setError(err.message);
    } finally { setGenerando(false); }
  }

  const cambia = (campo) => (e) => setForm({ ...form, [campo]: e.target.value });

  return (
    <div className="card" style={{ marginBottom: 18 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <h3 style={{ margin: 0 }}>Certificado de atención</h3>
          <p style={{ fontSize: 13, color: "var(--ink-soft)", margin: "2px 0 0" }}>
            Para justificar la consulta en el trabajo o en el colegio, con reposo si hace falta.
          </p>
        </div>
        {!abierto && <button type="button" className="btn btn-ghost" onClick={() => setAbierto(true)}>Emitir certificado</button>}
      </div>

      {abierto && (
        <form onSubmit={generar} style={{ marginTop: 14 }}>
          {error && <div className="error-box">{error}</div>}
          <div style={{ display: "grid", gap: "0 12px", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))" }}>
            <div className="field">
              <label>Día de la atención</label>
              <input type="date" required max={hoyISO()} value={fecha} onChange={(e) => setFecha(e.target.value)} />
            </div>
            <div className="field">
              <label>Llegó</label>
              <input type="time" value={form.hora_inicio} onChange={cambia("hora_inicio")} />
            </div>
            <div className="field">
              <label>Salió</label>
              <input type="time" value={form.hora_fin} onChange={cambia("hora_fin")} />
            </div>
            <div className="field">
              <label>Firma</label>
              <select required value={form.doctor} onChange={cambia("doctor")}>
                <option value="">Elige el profesional</option>
                {doctores.map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}
              </select>
            </div>
          </div>
          {sinCita && (
            <p style={{ fontSize: 12, color: "var(--amber)", margin: "-6px 0 10px" }}>
              No hay una cita registrada ese día. Revisa la fecha y escribe las horas a mano.
            </p>
          )}
          <div className="field">
            <label>Diagnóstico (CIE-10, opcional)</label>
            <input maxLength={300} value={form.diagnostico} onChange={cambia("diagnostico")} placeholder="Ej.: K02.1 Caries de la dentina" />
          </div>
          <div className="field">
            <label>Procedimiento realizado (opcional)</label>
            <input maxLength={300} value={form.procedimiento} onChange={cambia("procedimiento")} placeholder="Ej.: Exodoncia de la pieza 48" />
          </div>
          <div style={{ display: "grid", gap: "0 12px", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))" }}>
            <div className="field">
              <label>Días de reposo</label>
              <input type="number" min="0" max="30" value={form.reposo_dias} onChange={cambia("reposo_dias")} />
            </div>
            <div className="field">
              <label>Ciudad</label>
              <input maxLength={60} value={form.lugar} onChange={cambia("lugar")} placeholder="Quito" />
            </div>
          </div>
          <div className="field">
            <label>Observaciones (opcional)</label>
            <input maxLength={400} value={form.observaciones} onChange={cambia("observaciones")} />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-primary" disabled={generando}>{generando ? "Generando…" : "Generar PDF"}</button>
            <button type="button" className="btn btn-ghost" onClick={() => setAbierto(false)}>Cerrar</button>
          </div>
          <p style={{ fontSize: 12, color: "var(--ink-faint)", marginTop: 10 }}>
            Cada certificado lleva un número correlativo y queda registrado quién lo emitió.
          </p>
        </form>
      )}
    </div>
  );
}
