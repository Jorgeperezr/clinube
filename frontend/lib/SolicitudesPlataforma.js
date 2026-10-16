"use client";

/**
 * Plataforma → Solicitudes: lo que llega desde clinube.com. Las de
 * medicina y psicología esperan a que alguien las atienda; las de
 * odontología ya se crearon solas y quedan aquí como registro.
 */

import { useEffect, useState } from "react";

import { api, apiErrorMessage, readList } from "./api";

const COLOR = { pendiente: "badge-warn", creada: "badge-ok", atendida: "badge-ok", descartada: "" };

export default function SolicitudesPlataforma() {
  const [filas, setFilas] = useState(null);
  const [ver, setVer] = useState("pendiente");
  const [error, setError] = useState("");

  useEffect(() => {
    api("/platform/solicitudes/").then(readList).then(setFilas).catch((e) => setError(e.message));
  }, []);

  async function cambiar(s, estado) {
    setError("");
    const nota = estado === "pendiente" ? s.nota : (window.prompt("Nota (opcional):", s.nota || "") ?? s.nota);
    const resp = await api(`/platform/solicitudes/${s.id}/`, {
      method: "PATCH", body: JSON.stringify({ estado, nota: nota || "" }),
    });
    if (!resp.ok) { setError(await apiErrorMessage(resp)); return; }
    const nueva = await resp.json();
    setFilas((fs) => fs.map((f) => (f.id === s.id ? nueva : f)));
  }

  const visibles = (filas || []).filter((f) => ver === "todas" || f.estado === ver);
  const pendientes = (filas || []).filter((f) => f.estado === "pendiente").length;

  return (
    <div>
      <div className="barra-herramientas" style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <div className="segmentado" role="group" aria-label="Qué solicitudes ver">
          {[["pendiente", `Pendientes${pendientes ? ` (${pendientes})` : ""}`], ["creada", "Clínicas creadas"],
            ["todas", "Todas"]].map(([k, t]) => (
            <button key={k} type="button" aria-pressed={ver === k} onClick={() => setVer(k)}>{t}</button>
          ))}
        </div>
      </div>
      {error && <div className="error-box">{error}</div>}
      {!filas ? <div className="card"><div className="empty">Cargando…</div></div> : visibles.length === 0 ? (
        <div className="card"><div className="empty">Nada por aquí.</div></div>
      ) : visibles.map((s) => (
        <div key={s.id} className="card">
          <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
            <div>
              <strong>{s.clinica}</strong>
              <span style={{ color: "var(--ink-soft)", fontSize: 13 }}> · {s.tipo_nombre}{s.ciudad ? ` · ${s.ciudad}` : ""}</span>
              <div style={{ fontSize: 14, marginTop: 4 }}>
                {s.nombre} · <a href={`mailto:${s.correo}`}>{s.correo}</a>{s.telefono ? ` · ${s.telefono}` : ""}
                {s.ruc ? <span style={{ color: "var(--ink-soft)" }}> · RUC {s.ruc}</span> : null}
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <span className={`badge ${COLOR[s.estado] || ""}`}>{s.estado_nombre}</span>
              <div style={{ fontSize: 12, color: "var(--ink-faint)", marginTop: 4 }}>
                {new Date(s.created_at).toLocaleString("es-EC", { dateStyle: "medium", timeStyle: "short" })}
              </div>
            </div>
          </div>
          {s.mensaje && <p style={{ fontSize: 14, margin: "10px 0 0", whiteSpace: "pre-line" }}>{s.mensaje}</p>}
          {s.nota && <p style={{ fontSize: 13, margin: "8px 0 0", color: "var(--ink-soft)" }}>Nota: {s.nota}</p>}
          {s.estado !== "creada" && (
            <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
              {s.estado !== "atendida" && <button type="button" className="btn btn-ghost" onClick={() => cambiar(s, "atendida")}>Marcar atendida</button>}
              {s.estado !== "descartada" && <button type="button" className="btn btn-ghost" onClick={() => cambiar(s, "descartada")}>Descartar</button>}
              {s.estado !== "pendiente" && <button type="button" className="btn btn-ghost" onClick={() => cambiar(s, "pendiente")}>Volver a pendiente</button>}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
