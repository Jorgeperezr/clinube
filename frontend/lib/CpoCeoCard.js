"use client";

/**
 * Literal J del formulario MSP 033 — Índices CPO-ceo, calculados
 * automáticamente desde el odontograma, con los botones de export: la
 * historia clínica completa con el membrete y los colores de la clínica,
 * y el formulario 033 en PDF y en la plantilla oficial del MSP.
 */

import { useCallback, useEffect, useState } from "react";
import { api, currentUser } from "./api";
import VistaPreviaPDF from "./VistaPreviaPDF";

/* Partes opcionales de cada documento (las acepta la API en ?incluir=). */
const SECCIONES_HISTORIA = [
  { clave: "datos", etiqueta: "Datos del paciente" },
  { clave: "antecedentes", etiqueta: "Antecedentes médicos" },
  { clave: "diagnosticos", etiqueta: "Diagnósticos" },
  { clave: "periodontograma", etiqueta: "Periodontograma", ayuda: "La última exploración, con sus líneas" },
  { clave: "evoluciones", etiqueta: "Evoluciones, recetas e indicaciones" },
  { clave: "planes", etiqueta: "Planes de tratamiento" },
];
const SECCIONES_033 = [
  { clave: "anamnesis", etiqueta: "Motivo, enfermedad actual y antecedentes", ayuda: "Literales B a G" },
  { clave: "indicadores", etiqueta: "Indicadores de salud bucal" },
  { clave: "cpo", etiqueta: "Índices CPO-ceo" },
  { clave: "diagnosticos", etiqueta: "Diagnósticos (CIE-10)" },
  { clave: "plan", etiqueta: "Plan de tratamiento" },
  { clave: "periodontograma", etiqueta: "Periodontograma" },
  { clave: "examenes", etiqueta: "Exámenes complementarios" },
  { clave: "documentos", etiqueta: "Documentos adjuntos" },
  { clave: "consentimientos", etiqueta: "Consentimientos informados" },
];

export default function CpoCeoCard({ patientId, refreshKey }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [vista, setVista] = useState(null);   // documento en vista previa

  const load = useCallback(async () => {
    try {
      const resp = await api(`/patients/${patientId}/cpo-ceo/`);
      if (resp.ok) setData(await resp.json());
    } catch { /* silencioso */ }
  }, [patientId]);

  useEffect(() => { load(); }, [load, refreshKey]);

  // La historia completa la exporta quien escribe en ella (admin y doctor).
  const puedeHistoria = ["admin", "doctor"].includes(currentUser()?.role);

  const HISTORIA = { titulo: "Historia clínica", ruta: `/patients/${patientId}/clinical-record/export-pdf/`,
                     nombre: "historia_clinica.pdf", clave: "historia", componentes: SECCIONES_HISTORIA };
  const F033 = { titulo: "Formulario 033", ruta: `/patients/${patientId}/form033/export-pdf/`,
                 nombre: "formulario_033.pdf", clave: "form033", componentes: SECCIONES_033 };

  // Formulario OFICIAL del MSP (plantilla xlsx del Ministerio) autocompletado
  async function exportXlsx() {
    setError("");
    try {
      const resp = await api(`/patients/${patientId}/form033/export-xlsx/`);
      if (!resp.ok) throw new Error(`No se pudo generar el formulario (error ${resp.status}).`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "formulario_033.xlsx"; a.click();
      URL.revokeObjectURL(url);
    } catch (err) { setError(err.message); }
  }

  if (!data) return null;
  const { cpo, ceo } = data;

  const base = { border: "1px solid var(--line)", padding: "8px 16px", textAlign: "center",
                 fontVariantNumeric: "tabular-nums" };
  const hdr = { ...base, fontWeight: 700, fontSize: 13, color: "var(--petrol-deep)" };
  const rowLabel = { ...base, fontWeight: 700, background: "var(--mint)",
                     color: "var(--mint-ink)", minWidth: 40 };
  const numCell = { ...base, minWidth: 44 };
  const totalCell = { ...base, fontWeight: 700, background: "var(--amber-soft)",
                      color: "var(--amber)" };

  return (
    <div className="card" style={{ marginBottom: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <h3 style={{ margin: 0 }}>Índices CPO-ceo</h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {puedeHistoria && (
            <button className="btn btn-primary" style={{ fontSize: 13 }}
                    onClick={() => setVista(HISTORIA)}
                    title="Datos, antecedentes, diagnósticos, evoluciones y planes, con el membrete de la clínica">
              Historia clínica (PDF)
            </button>
          )}
          <button className={`btn ${puedeHistoria ? "btn-ghost" : "btn-primary"}`} style={{ fontSize: 13 }}
                  onClick={() => setVista(F033)}>
            Formulario 033 (PDF)
          </button>
          <button className="btn btn-ghost" style={{ fontSize: 13 }} onClick={exportXlsx}
                  title="Plantilla oficial del MSP autocompletada con los datos del paciente">
            Formulario oficial MSP (Excel)
          </button>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}
      {vista && <VistaPreviaPDF {...vista} onCerrar={() => setVista(null)} />}

      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", fontSize: 14 }}>
          <thead>
            <tr style={{ background: "var(--petrol-soft)" }}>
              <th style={hdr}></th>
              <th style={hdr}>C</th><th style={hdr}>P</th><th style={hdr}>O</th>
              <th style={{ ...hdr, minWidth: 120 }}>TOTAL</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style={rowLabel}>D</td>
              <td style={numCell}>{cpo.C}</td>
              <td style={numCell}>{cpo.P}</td>
              <td style={numCell}>{cpo.O}</td>
              <td style={totalCell}>{cpo.total}</td>
            </tr>
            <tr style={{ background: "var(--petrol-soft)" }}>
              <th style={hdr}></th>
              <th style={hdr}>c</th><th style={hdr}>e</th><th style={hdr}>o</th>
              <th style={hdr}>TOTAL</th>
            </tr>
            <tr>
              <td style={rowLabel}>d</td>
              <td style={numCell}>{ceo.c}</td>
              <td style={numCell}>{ceo.e}</td>
              <td style={numCell}>{ceo.o}</td>
              <td style={totalCell}>{ceo.total}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p style={{ fontSize: 12, color: "var(--ink-soft)", marginTop: 8 }}>
        Calculado automáticamente desde el odontograma ({data.teeth_evaluated} piezas con registro).
        C/c = cariados · P/e = perdidos o con extracción indicada · O/o = obturados o con corona.
      </p>
    </div>
  );
}
