"use client";

/**
 * Plataforma → Solicitudes: lo que llega desde clinube.com.
 *
 * Nada se crea solo. Cada solicitud espera aquí hasta que alguien de la
 * plataforma la aprueba (se crea la clínica y su administrador recibe el
 * enlace para elegir la contraseña) o la descarta, con o sin aviso.
 * Odontología se responde a la brevedad; medicina y psicología tienen un
 * plazo de 12 horas, y la tarjeta dice cuánto queda.
 */

import { useEffect, useState } from "react";

import { api, apiErrorMessage, readList } from "./api";

const COLOR = { pendiente: "badge-warn", creada: "badge-ok", atendida: "badge-ok", descartada: "" };
const FILTROS = [["pendiente", "Pendientes"], ["creada", "Clínicas creadas"], ["descartada", "Descartadas"], ["todas", "Todas"]];
const MODALIDADES = [["consultorio", "Consultorio (una persona)"], ["clinica", "Clínica con equipo"]];
const RECUADRO = {
  marginTop: 12, display: "grid", gap: 10, padding: 14,
  border: "1px solid var(--line)", borderRadius: "var(--radius-sm)",
};

function fecha(iso) {
  return new Date(iso).toLocaleString("es-EC", { dateStyle: "medium", timeStyle: "short" });
}

function hace(iso) {
  const min = Math.max(0, Math.round((Date.now() - new Date(iso)) / 60000));
  if (min < 1) return "hace un momento";
  if (min < 60) return `hace ${min} min`;
  const h = Math.round(min / 60);
  return h < 48 ? `hace ${h} h` : `hace ${Math.round(h / 24)} días`;
}

/** Lo que queda del plazo de una pendiente, o la espera si no tiene plazo. */
function Plazo({ s }) {
  if (!s.responder_antes) return <span style={{ color: "var(--ink-soft)" }}>A la brevedad · llegó {hace(s.created_at)}</span>;
  const restan = Math.round((new Date(s.responder_antes) - Date.now()) / 60000);
  const hora = new Date(s.responder_antes).toLocaleTimeString("es-EC", { hour: "2-digit", minute: "2-digit" });
  if (restan <= 0) return <span className="badge badge-danger">Fuera de plazo desde las {hora}</span>;
  const texto = restan < 60 ? `${restan} min` : `${Math.floor(restan / 60)} h ${restan % 60} min`;
  return <span style={{ color: restan < 120 ? "var(--amber)" : "var(--ink-soft)" }}>Responder antes de las {hora} · quedan {texto}</span>;
}

export default function SolicitudesPlataforma() {
  const [filas, setFilas] = useState(null);
  const [ver, setVer] = useState("pendiente");
  const [error, setError] = useState("");
  // Va arriba y no en la tarjeta: al aprobarla, la tarjeta deja de estar entre las pendientes.
  const [aviso, setAviso] = useState("");
  const [, setReloj] = useState(0);

  useEffect(() => {
    api("/platform/solicitudes/").then(readList).then(setFilas).catch((e) => setError(e.message));
    // Los plazos se recalculan solos mientras la pantalla está abierta.
    const t = setInterval(() => setReloj((n) => n + 1), 60000);
    return () => clearInterval(t);
  }, []);

  const reemplazar = (nueva) => setFilas((fs) => fs.map((f) => (f.id === nueva.id ? { ...f, ...nueva } : f)));
  const visibles = (filas || []).filter((f) => ver === "todas" || f.estado === ver);
  const pendientes = (filas || []).filter((f) => f.estado === "pendiente").length;

  return (
    <div>
      <p style={{ color: "var(--ink-soft)", margin: "0 0 14px", maxWidth: 680 }}>
        Las solicitudes de la página pública esperan aquí. Al aprobar una se crea la clínica y su administrador
        recibe un enlace para elegir su contraseña. Odontología se responde a la brevedad; medicina y psicología,
        dentro de 12 horas.
      </p>
      <div className="barra-herramientas" style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <div className="segmentado" role="group" aria-label="Qué solicitudes ver">
          {FILTROS.map(([k, t]) => (
            <button key={k} type="button" aria-pressed={ver === k} onClick={() => setVer(k)}>
              {t}{k === "pendiente" && pendientes ? ` (${pendientes})` : ""}
            </button>
          ))}
        </div>
      </div>
      {error && <div className="error-box">{error}</div>}
      {aviso && <div className="success-box">{aviso}</div>}
      {!filas ? <div className="card"><div className="empty">Cargando…</div></div> : visibles.length === 0 ? (
        <div className="card"><div className="empty">{ver === "pendiente" ? "No hay solicitudes por revisar." : "Nada por aquí."}</div></div>
      ) : visibles.map((s) => <Tarjeta key={s.id} s={s} onCambio={reemplazar} onAviso={setAviso} />)}
    </div>
  );
}

function Tarjeta({ s, onCambio, onAviso }) {
  const [abierto, setAbierto] = useState(null);         // aprobar | descartar
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  async function enviar(ruta, opciones, alTerminar) {
    setError(""); onAviso(""); setOcupado(true);
    try {
      const resp = await api(ruta, opciones);
      if (!resp.ok) throw new Error(await apiErrorMessage(resp));
      alTerminar(await resp.json());
    } catch (e) { setError(e.message); }
    finally { setOcupado(false); }
  }

  const cambiarEstado = (estado, extra = {}) => enviar(`/platform/solicitudes/${s.id}/`, {
    method: "PATCH", body: JSON.stringify({ estado, ...extra }),
  }, (nueva) => { onCambio(nueva); setAbierto(null); });

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
        <div style={{ minWidth: 0 }}>
          <strong>{s.clinica}</strong>
          <span style={{ color: "var(--ink-soft)", fontSize: 13 }}>
            {" "}· {s.tipo_nombre} · {s.modalidad_nombre}{s.ciudad ? ` · ${s.ciudad}` : ""}
          </span>
          <div style={{ fontSize: 14, marginTop: 4 }}>
            {s.nombre} · <a href={`mailto:${s.correo}`}>{s.correo}</a>{s.telefono ? ` · ${s.telefono}` : ""}
            {s.ruc ? <span style={{ color: "var(--ink-soft)" }}> · RUC {s.ruc}</span> : null}
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <span className={`badge ${COLOR[s.estado] || ""}`}>{s.estado_nombre}</span>
          <div style={{ fontSize: 12, color: "var(--ink-faint)", marginTop: 4 }}>{fecha(s.created_at)}</div>
        </div>
      </div>
      {s.estado === "pendiente" && <div style={{ fontSize: 13, marginTop: 8 }}><Plazo s={s} /></div>}
      {s.mensaje && <p style={{ fontSize: 14, margin: "10px 0 0", whiteSpace: "pre-line" }}>{s.mensaje}</p>}
      {s.nota && <p style={{ fontSize: 13, margin: "8px 0 0", color: "var(--ink-soft)" }}>Nota: {s.nota}</p>}
      {error && <div className="error-box" style={{ margin: "10px 0 0" }}>{error}</div>}

      {s.estado === "pendiente" && !abierto && (
        <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          <button type="button" className="btn btn-primary" onClick={() => setAbierto("aprobar")}>Aprobar y crear</button>
          <button type="button" className="btn btn-ghost" onClick={() => setAbierto("descartar")}>Descartar</button>
          <button type="button" className="btn btn-ghost" disabled={ocupado} onClick={() => cambiarEstado("atendida")}
                  title="Se resolvió por otra vía: no se crea nada">Marcar atendida</button>
        </div>
      )}
      {abierto === "aprobar" && (
        <Aprobar s={s} ocupado={ocupado} onCancelar={() => setAbierto(null)}
                 onAprobar={(datos) => enviar(`/platform/solicitudes/${s.id}/aprobar/`, {
                   method: "POST", body: JSON.stringify(datos),
                 }, (nueva) => {
                   onCambio(nueva); setAbierto(null);
                   onAviso(nueva.correo_enviado
                     ? `${nueva.clinica}: clínica creada. Enviamos a ${s.correo} el enlace para elegir la contraseña.`
                     : `${nueva.clinica}: la clínica se creó, pero el correo no salió. Revisa el correo saliente en Configuración y usa «Reenviar el enlace» en Clínicas creadas.`);
                 })} />
      )}
      {abierto === "descartar" && (
        <Descartar s={s} ocupado={ocupado} onCancelar={() => setAbierto(null)}
                   onDescartar={(nota, avisar) => cambiarEstado("descartada", { nota, avisar })} />
      )}

      {(s.estado === "descartada" || s.estado === "atendida") && (
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <button type="button" className="btn btn-ghost" disabled={ocupado} onClick={() => cambiarEstado("pendiente")}>Volver a pendiente</button>
        </div>
      )}
      {s.estado === "creada" && (
        <div style={{ display: "flex", gap: 10, marginTop: 12, alignItems: "center", flexWrap: "wrap", fontSize: 13 }}>
          {s.admin_pendiente ? (
            <>
              <span style={{ color: "var(--amber)" }}>Aún no elige su contraseña.</span>
              <button type="button" className="btn btn-ghost" disabled={ocupado}
                      onClick={() => enviar(`/platform/solicitudes/${s.id}/reenviar/`, { method: "POST" },
                        (r) => onAviso(r.detail))}>
                Reenviar el enlace
              </button>
            </>
          ) : <span style={{ color: "var(--ink-soft)" }}>Su administrador ya entró.</span>}
        </div>
      )}
    </div>
  );
}

function Aprobar({ s, ocupado, onAprobar, onCancelar }) {
  const [clinica, setClinica] = useState(s.clinica);
  const [modalidad, setModalidad] = useState(s.modalidad);
  return (
    <form style={RECUADRO} onSubmit={(e) => { e.preventDefault(); onAprobar({ clinica: clinica.trim(), modalidad }); }}>
      <div style={{ display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
        <label className="field"><span>Nombre de la clínica</span>
          <input required minLength={3} maxLength={150} value={clinica} onChange={(e) => setClinica(e.target.value)} />
        </label>
        <label className="field"><span>Modalidad</span>
          <select value={modalidad} onChange={(e) => setModalidad(e.target.value)}>
            {MODALIDADES.map(([k, t]) => <option key={k} value={k}>{t}</option>)}
          </select>
        </label>
      </div>
      <p style={{ margin: 0, fontSize: 13, color: "var(--ink-soft)" }}>
        Se crea la clínica con <strong>{s.nombre}</strong> como administrador
        {modalidad === "consultorio" ? ", que además atiende pacientes," : ""} y le enviamos a {s.correo} un enlace
        para elegir su contraseña. El enlace vale 72 horas.
        {s.tipo !== "odontologia" && " El formulario MSP 033, que es de odontología, queda apagado."}
      </p>
      <div style={{ display: "flex", gap: 8 }}>
        <button className="btn btn-primary" disabled={ocupado}>{ocupado ? "Creando…" : "Crear la clínica"}</button>
        <button type="button" className="btn btn-ghost" onClick={onCancelar}>Cancelar</button>
      </div>
    </form>
  );
}

function Descartar({ s, ocupado, onDescartar, onCancelar }) {
  const [nota, setNota] = useState(s.nota || "");
  const [avisar, setAvisar] = useState(false);
  return (
    <form style={RECUADRO} onSubmit={(e) => { e.preventDefault(); onDescartar(nota.trim(), avisar); }}>
      <label className="field"><span>Nota interna (opcional)</span>
        <input maxLength={300} value={nota} onChange={(e) => setNota(e.target.value)} placeholder="Por qué no se aprueba" />
      </label>
      <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 14 }}>
        <input type="checkbox" checked={avisar} onChange={(e) => setAvisar(e.target.checked)} />
        Avisar a {s.correo} que no se aprobó
      </label>
      <div style={{ display: "flex", gap: 8 }}>
        <button className="btn btn-danger" disabled={ocupado}>Descartar</button>
        <button type="button" className="btn btn-ghost" onClick={onCancelar}>Cancelar</button>
      </div>
    </form>
  );
}
