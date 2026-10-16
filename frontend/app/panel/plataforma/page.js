"use client";

import { useCallback, useEffect, useState } from "react";
import { api, apiErrorMessage, readList, readObject } from "../../../lib/api";
import { useConfirm } from "../../../lib/ConfirmDialog";
import {
  coloresDelLogotipo, EditorPaleta, LOGOS, SelectorLogo, usePrevisualizacion, VistaTemas,
} from "../../../lib/IdentidadClinica";
import { MARCA } from "../../../lib/marca";
import SolicitudesPlataforma from "../../../lib/SolicitudesPlataforma";

/*
 * El catálogo de funciones NO se repite aquí: lo da la API
 * (GET /platform/funcionalidades/, desde apps/common/funcionalidades.py),
 * con su tipo —incluida o adicional—, si viene encendida en una clínica
 * nueva y de qué cliente salió. Una función nueva aparece sola al
 * desplegarla, sin tocar esta pantalla.
 */
function porDefecto(catalogo) {
  return Object.fromEntries((catalogo || []).map((f) => [f.clave, f.por_defecto]));
}

const TABS = [
  ["dashboard", "Dashboard"], ["clinicas", "Clínicas"], ["solicitudes", "Solicitudes"],
  ["admins", "Administradores"], ["funciones", "Funciones"],
  ["auditoria", "Auditoría"], ["config", "Configuración"],
];

export default function PlataformaPage() {
  const [tab, setTab] = useState("dashboard");

  return (
    <div>
      <h1 style={{ fontSize: 24, marginBottom: 4 }}>Plataforma</h1>
      <p style={{ color: "var(--ink-soft)", marginBottom: 16 }}>
        Administración de Clinube. Desde aquí no se accede a los datos de las clínicas.
      </p>

      <div style={{ display: "flex", gap: 4, marginBottom: 20, borderBottom: "1px solid var(--line)", flexWrap: "wrap" }}>
        {TABS.map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)}
            style={{
              padding: "9px 16px", border: "none", background: "transparent",
              fontWeight: 600, fontSize: 14,
              color: tab === k ? "var(--petrol)" : "var(--ink-soft)",
              borderBottom: tab === k ? "3px solid var(--petrol)" : "3px solid transparent",
            }}>
            {label}
          </button>
        ))}
      </div>

      {tab === "dashboard" && <DashboardTab />}
      {tab === "clinicas" && <ClinicsTab />}
      {tab === "solicitudes" && <SolicitudesPlataforma />}
      {tab === "admins" && <AdminsTab />}
      {tab === "funciones" && <FuncionesTab />}
      {tab === "auditoria" && <AuditTab />}
      {tab === "config" && <ConfigTab />}
    </div>
  );
}

/* ───────────── 1. Dashboard ───────────── */

function DashboardTab() {
  const [data, setData] = useState(null);
  // `error` separado de `data` a propósito: sin él, `r.ok && setData(...)`
  // se traga el fallo y la pantalla se queda diciendo «Cargando…» para
  // siempre. Pasa de verdad —entrar aquí con un usuario que administra
  // una clínica da 403, porque esto es del superadministrador— y quien lo
  // ve no tiene forma de saber si está cargando, si se cayó algo o si no
  // le corresponde entrar.
  const [error, setError] = useState("");
  useEffect(() => {
    api("/platform/overview/")
      .then(async (r) => (r.ok ? setData(await r.json()) : setError(await apiErrorMessage(r))))
      .catch(() => setError("No se pudo contactar con el servidor."));
  }, []);
  if (error) return <div className="error-box">{error}</div>;
  if (!data) return <div className="empty">Cargando…</div>;
  return (
    <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
      <Stat label="Clínicas registradas" value={data.clinics_total} />
      <Stat label="Activas" value={data.clinics_active} accent />
      <Stat label="Suspendidas" value={data.clinics_suspended} danger={data.clinics_suspended > 0} />
      <Stat label="Administradores de clínica" value={data.clinic_admins_total} />
    </div>
  );
}

function Stat({ label, value, accent, danger }) {
  return (
    <div className="card" style={{ flex: 1, minWidth: 170,
        ...(danger ? { borderColor: "var(--red)", background: "var(--red-soft)" } : {}) }}>
      <div style={{ fontSize: 12, color: "var(--ink-soft)", textTransform: "uppercase", letterSpacing: ".04em" }}>{label}</div>
      <div className="tabular" style={{ fontSize: 26, fontWeight: 700,
          color: danger ? "var(--red)" : accent ? "var(--petrol)" : "var(--ink)" }}>{value}</div>
    </div>
  );
}

/* ───────────── Entrega de credenciales ───────────── */

/**
 * La contraseña temporal, una sola vez, y lo que hay que hacer con ella.
 *
 * Lo que de verdad resuelve es el paso siguiente: el dueño de la
 * plataforma tiene que HACER LLEGAR esto a la clínica. Copiar la
 * contraseña suelta obliga a redactar el resto a mano cada vez —dónde se
 * entra, con qué correo, que hay que cambiarla— y ahí es donde se pierde
 * la mitad del mensaje. El botón de abajo copia la nota entera, lista
 * para pegar en un correo o en WhatsApp.
 */
function PanelDeCredenciales({ cred, clinica, onClose }) {
  const [copiado, setCopiado] = useState("");

  const url = typeof window !== "undefined" ? `${window.location.origin}/login/` : "";
  const nota = [
    `Acceso a ${MARCA}, el sistema de ${clinica || "su clínica"}`,
    "",
    `Dirección: ${url}`,
    `Usuario: ${cred.email}`,
    `Contraseña temporal: ${cred.temporary_password}`,
    "",
    "Al entrar por primera vez el sistema le pedirá elegir su propia",
    "contraseña. Desde ese momento nadie más que usted la conoce, y",
    "podrá registrar a los profesionales de la clínica desde",
    "Configuración → Usuarios.",
  ].join("\n");

  async function copiar(texto, cual) {
    try {
      await navigator.clipboard.writeText(texto);
      setCopiado(cual);
      setTimeout(() => setCopiado(""), 2000);
    } catch {
      // Sin permiso de portapapeles (o sin HTTPS) no se puede copiar; la
      // contraseña está a la vista, que es lo que importa.
      setCopiado("no");
    }
  }

  return (
    <div className="card" style={{ marginBottom: 18, borderColor: "var(--amber)",
                                   background: "var(--amber-soft)" }}>
      <h3 style={{ marginBottom: 4 }}>
        Credenciales de {clinica || "la clínica"}
      </h3>
      <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 12 }}>
        Entrégalas ahora: esta contraseña <strong>no se puede volver a consultar</strong>.
        Solo sirve para el primer ingreso; al entrar, la clínica elige la suya y tú dejas de
        tener acceso a la cuenta.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "8px 14px",
                    alignItems: "center", marginBottom: 12 }}>
        <span style={{ fontSize: 12, color: "var(--ink-soft)", textTransform: "uppercase",
                       letterSpacing: ".04em" }}>Usuario</span>
        <code style={{ fontSize: 15, background: "var(--elev)", padding: "6px 12px",
                       borderRadius: 8, justifySelf: "start" }}>{cred.email}</code>

        <span style={{ fontSize: 12, color: "var(--ink-soft)", textTransform: "uppercase",
                       letterSpacing: ".04em" }}>Contraseña</span>
        <code className="tabular" style={{ fontSize: 18, fontWeight: 700, background: "var(--elev)",
                       padding: "6px 12px", borderRadius: 8, justifySelf: "start",
                       letterSpacing: ".02em" }}>{cred.temporary_password}</code>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <button className="btn btn-primary" style={{ fontSize: 13 }}
                onClick={() => copiar(nota, "nota")}>
          Copiar mensaje de entrega
        </button>
        <button className="btn btn-ghost" style={{ fontSize: 13 }}
                onClick={() => copiar(cred.temporary_password, "clave")}>
          Copiar solo la contraseña
        </button>
        <button className="btn btn-ghost" style={{ fontSize: 13, marginLeft: "auto" }}
                onClick={onClose}>Ya la entregué</button>
      </div>

      {copiado === "nota" && <p style={{ fontSize: 13, marginTop: 8, color: "var(--petrol-deep)" }}>✓ Mensaje copiado.</p>}
      {copiado === "clave" && <p style={{ fontSize: 13, marginTop: 8, color: "var(--petrol-deep)" }}>✓ Contraseña copiada.</p>}
      {copiado === "no" && <p style={{ fontSize: 13, marginTop: 8, color: "var(--red)" }}>
        El navegador no dejó copiar. Selecciónala a mano, arriba.</p>}
    </div>
  );
}

/* ───────────── 2. Gestión de Clínicas ───────────── */

/** La identidad visual sin tocar, como arranca el formulario. */
function identidadVacia(paleta = []) {
  return { paleta, paletaTocada: false, archivos: {}, quitar: {} };
}

function identidadCambiada(id) {
  return id.paletaTocada || Object.keys(id.archivos).length > 0
    || Object.values(id.quitar).some(Boolean);
}

/** Como la espera PATCH /platform/clinics/{id}/identidad/: con archivos, multipart. */
function identidadComoFormulario(id) {
  const fd = new FormData();
  if (id.paletaTocada) fd.append("paleta", JSON.stringify(id.paleta));
  for (const [campo, archivo] of Object.entries(id.archivos)) fd.append(campo, archivo);
  for (const [campo, quitar] of Object.entries(id.quitar)) {
    if (quitar && !id.archivos[campo]) fd.append(`${campo}_clear`, "true");
  }
  return fd;
}

/** Guarda la identidad si se tocó. Devuelve el motivo si falló, o "". */
async function guardarIdentidad(clinicaId, identidad) {
  if (!identidadCambiada(identidad)) return "";
  const resp = await api(`/platform/clinics/${clinicaId}/identidad/`, {
    method: "PATCH", body: identidadComoFormulario(identidad),
  });
  return resp.ok ? "" : apiErrorMessage(resp);
}

function ClinicsTab() {
  const [confirm, ConfirmUI] = useConfirm();
  const [clinics, setClinics] = useState([]);
  const [catalogo, setCatalogo] = useState([]);
  const VACIO = { name: "", ruc: "", address: "", phone: "", email: "",
                  admin_full_name: "", admin_email: "", es_prueba: false,
                  funcionalidades: porDefecto(catalogo) };
  const [form, setForm] = useState(VACIO);
  const [identidad, setIdentidad] = useState(identidadVacia());
  const [identidadActual, setIdentidadActual] = useState(null);   // la guardada, al editar

  // El catálogo llega de la API; el formulario de alta arranca con lo
  // que trae una clínica nueva (las adicionales, apagadas).
  useEffect(() => {
    api("/platform/funcionalidades/").then(readObject).then((d) => {
      setCatalogo(d.funcionalidades || []);
      setForm((f) => ({ ...f, funcionalidades: porDefecto(d.funcionalidades) }));
    }).catch(() => {});
  }, []);
  const [editing, setEditing] = useState(null);   // clínica en edición
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");
  const [cred, setCred] = useState(null);         // {email, temporary_password, clinica}

  const load = useCallback(async () => {
    try {
      setClinics(await readList(await api("/platform/clinics/")));
    } catch (err) { setError(err?.message ? `No se pudieron cargar las clínicas. ${err.message}` : "No se pudieron cargar las clínicas."); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function createClinic(e) {
    e.preventDefault();
    setError(""); setOkMsg("");
    try {
      const resp = await api("/platform/clinics/", { method: "POST", body: JSON.stringify(form) });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        const detail = data?.error?.details || data;
        const first = typeof detail === "object" ? Object.values(detail)[0] : detail;
        throw new Error(Array.isArray(first) ? first[0] : `Error ${resp.status}`);
      }
      // La identidad visual va después, con sus archivos. Igual que el
      // administrador, si falla no deshace la clínica: se avisa.
      const falloIdentidad = await guardarIdentidad(data.id, identidad);
      const errores = falloIdentidad
        ? [`La clínica "${form.name}" se creó, pero su identidad visual no: ${falloIdentidad} `
           + "Puedes darla desde «Editar»."]
        : [];
      // El alta del administrador va en la misma respuesta, y puede
      // traer su propio error sin que eso deshaga la clínica: un correo
      // repetido no es motivo para cancelar un alta que ya está hecha.
      const alta = data.admin;
      if (alta?.temporary_password) {
        setCred({ ...alta, clinica: form.name });
        setOkMsg(`Clínica "${form.name}" creada con su administrador. Entrégale las credenciales de abajo.`);
      } else if (alta?.error) {
        setOkMsg("");
        errores.unshift(`La clínica "${form.name}" se creó, pero su administrador no: ${alta.error} `
                        + "Créalo desde la pestaña Administradores.");
      } else {
        setOkMsg(`Clínica "${form.name}" creada (activa, con catálogo base). `
                 + "Aún no tiene administrador: créalo en la pestaña Administradores.");
      }
      setError(errores.join(" "));
      setForm(VACIO);
      setIdentidad(identidadVacia());
      load();
    } catch (err) { setError(err.message); }
  }

  async function empezarEdicion(c) {
    setError(""); setOkMsg("");
    setEditing({ id: c.id, name: c.name, ruc: c.ruc, address: c.address, phone: c.phone, email: c.email,
                 es_prueba: Boolean(c.es_prueba),
                 funcionalidades: c.funcionalidades || porDefecto(catalogo) });
    setIdentidadActual(null);
    setIdentidad(identidadVacia());
    window.scrollTo?.({ top: 0, behavior: "smooth" });
    try {
      const actual = await readObject(await api(`/platform/clinics/${c.id}/identidad/`));
      setIdentidadActual(actual);
      setIdentidad(identidadVacia(actual.paleta || []));
    } catch (err) { setError(`No se pudo cargar su identidad visual. ${err.message}`); }
  }

  function dejarDeEditar() {
    setEditing(null);
    setIdentidadActual(null);
    setIdentidad(identidadVacia());
  }

  async function saveEdit(e) {
    e.preventDefault();
    setError("");
    try {
      const resp = await api(`/platform/clinics/${editing.id}/`, {
        method: "PATCH", body: JSON.stringify(editing),
      });
      if (!resp.ok) throw new Error(`No se pudo guardar (error ${resp.status}).`);
      const falloIdentidad = await guardarIdentidad(editing.id, identidad);
      if (falloIdentidad) throw new Error(`Los datos se guardaron, pero la identidad visual no: ${falloIdentidad}`);
      setOkMsg(`Cambios de "${editing.name}" guardados.`);
      dejarDeEditar();
      load();
    } catch (err) { setError(err.message); }
  }

  async function toggleActive(clinic) {
    const action = clinic.is_active ? "Suspender" : "Activar";
    const ok = await confirm({
      title: `${action} ${clinic.name}`,
      message: clinic.is_active
        ? "Los usuarios de esta clínica perderán el acceso de inmediato. Los datos NO se borran."
        : "Los usuarios de esta clínica recuperan el acceso.",
      confirmLabel: action, danger: clinic.is_active,
    });
    if (!ok) return;
    try {
      const resp = await api(`/platform/clinics/${clinic.id}/`, {
        method: "PATCH", body: JSON.stringify({ is_active: !clinic.is_active }),
      });
      if (!resp.ok) throw new Error(`No se pudo actualizar (error ${resp.status}).`);
      load();
    } catch (err) { setError(err.message); }
  }

  const fld = (k, label, type = "text") => (
    <div className="field" style={{ marginBottom: 0 }}>
      <label>{label}</label>
      <input type={type} value={editing ? (editing[k] || "") : form[k]}
             required={k === "name"}
             onChange={(e) => editing
               ? setEditing({ ...editing, [k]: e.target.value })
               : setForm({ ...form, [k]: e.target.value })} />
    </div>
  );

  return (
    <div>
      {ConfirmUI}
      {error && <div className="error-box">{error}</div>}
      {okMsg && <div className="error-box" style={{ background: "var(--mint)", color: "var(--petrol-deep)" }}>✓ {okMsg}</div>}

      {cred && (
        <PanelDeCredenciales cred={cred} clinica={cred.clinica} onClose={() => setCred(null)} />
      )}

      <form onSubmit={editing ? saveEdit : createClinic} className="card"
            style={{ marginBottom: 18, ...(editing ? { borderColor: "var(--petrol)" } : {}) }}>
        <h3 style={{ marginBottom: 2 }}>{editing ? `Editar ${editing.name}` : "Registrar nueva clínica"}</h3>
        {!editing && (
          <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 14 }}>
            La clínica queda activa y con el catálogo base. Si indicas su
            administrador aquí, al guardar se genera su contraseña y se
            muestra una sola vez para que se la entregues.
          </p>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr 1.5fr", gap: "12px 14px" }}>
          {fld("name", "Nombre *")}
          {fld("ruc", "RUC")}
          {fld("address", "Dirección")}
          {fld("phone", "Teléfono")}
          {fld("email", "Correo", "email")}
        </div>
        <label style={{ display: "flex", gap: 8, alignItems: "start", fontSize: 14, marginTop: 14 }}>
          <input type="checkbox" style={{ marginTop: 3 }} checked={Boolean((editing || form).es_prueba)}
                 onChange={(e) => (editing
                   ? setEditing({ ...editing, es_prueba: e.target.checked })
                   : setForm({ ...form, es_prueba: e.target.checked }))} />
          <span>
            Clínica de pruebas <span className="etiqueta-prueba" style={{ marginLeft: 4 }}>Pruebas</span>
            <span style={{ display: "block", fontSize: 12, color: "var(--ink-soft)" }}>
              Recibe las funciones nuevas antes que las demás, para probarlas. Lo que está en prueba no
              llega a otras clínicas hasta publicarlo en la pestaña Funciones.
            </span>
          </span>
        </label>

        {/* Qué módulos tiene esta clínica. Se pueden cambiar después:
            apagar uno NO borra sus datos, solo deja de verse. */}
        <div style={{ borderTop: "1px solid var(--line)", margin: "16px 0 14px" }} />
        <h4 style={{ marginBottom: 2, fontSize: 14 }}>Funcionalidades</h4>
        <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 12 }}>
          Pacientes, agenda, historia clínica y pagos van siempre. Las incluidas vienen marcadas
          en una clínica nueva; las adicionales se agregan a pedido. Se pueden cambiar después:
          apagar una no borra sus datos.
        </p>
        {[
          ["incluida", "Incluidas", (f) => f.fase !== "prueba" && f.tipo === "incluida"],
          ["adicional", "Adicionales · a pedido", (f) => f.fase !== "prueba" && f.tipo === "adicional"],
          ["prueba", "En prueba · solo clínicas de prueba", (f) => f.fase === "prueba"],
        ].map(([grupoClave, titulo, cabe]) => {
          const grupo = catalogo.filter(cabe);
          if (!grupo.length) return null;
          const fuente = editing || form;
          const puesto = fuente.funcionalidades || porDefecto(catalogo);
          // Lo que está en prueba solo se le puede dar a una clínica de pruebas.
          const bloqueado = grupoClave === "prueba" && !fuente.es_prueba;
          return (
            <div key={grupoClave} style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 11.5, fontWeight: 700, letterSpacing: ".05em", textTransform: "uppercase",
                            color: "var(--ink-soft)", margin: "4px 0 8px" }}>
                {titulo}
              </div>
              {bloqueado && (
                <p style={{ fontSize: 12.5, color: "var(--ink-soft)", margin: "0 0 8px" }}>
                  Esta clínica no es de pruebas: las tendrá cuando se publiquen para todas.
                </p>
              )}
              <div className="rejilla-adaptable" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px 18px" }}>
                {grupo.map((f) => (
                  <label key={f.clave} style={{ display: "flex", gap: 8, alignItems: "start", fontSize: 14,
                                                opacity: bloqueado ? 0.6 : 1 }}>
                    <input type="checkbox" style={{ marginTop: 3 }} disabled={bloqueado}
                           checked={!bloqueado && !!puesto[f.clave]}
                           onChange={(e) => {
                             const nuevas = { ...puesto, [f.clave]: e.target.checked };
                             editing
                               ? setEditing({ ...editing, funcionalidades: nuevas })
                               : setForm({ ...form, funcionalidades: nuevas });
                           }} />
                    <span>
                      {f.nombre}
                      <span style={{ display: "block", fontSize: 12, color: "var(--ink-soft)" }}>
                        {f.descripcion}
                      </span>
                      {f.origen && (
                        <span style={{ display: "block", fontSize: 11.5, color: "var(--petrol)", marginTop: 2 }}>
                          {f.origen}
                        </span>
                      )}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          );
        })}

        {/* Paleta y logotipos: con ellos se generan los temas de la clínica. */}
        <div style={{ borderTop: "1px solid var(--line)", margin: "16px 0 14px" }} />
        <IdentidadDeLaClinica valor={identidad} onChange={setIdentidad}
                              actual={editing ? identidadActual : null} />

        {editing && (
          <div style={{ display: "flex", gap: 8, marginTop: 18 }}>
            <button className="btn btn-primary">Guardar cambios</button>
            <button type="button" className="btn btn-ghost" onClick={dejarDeEditar}>Cancelar</button>
          </div>
        )}

        {/* Los datos del administrador solo al crear: al editar una
            clínica ya existente su administrador se gestiona en su
            propia pestaña, donde además se puede desactivar o cambiar. */}
        {!editing && (
          <>
            <div style={{ borderTop: "1px solid var(--line)", margin: "16px 0 14px" }} />
            <h4 style={{ marginBottom: 2, fontSize: 14 }}>Administrador de la clínica</h4>
            <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 12 }}>
              Es quien recibe las credenciales y, ya dentro, da de alta a los
              profesionales. Opcional: puedes crearlo más tarde.
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1.5fr auto",
                          gap: "12px 14px", alignItems: "end" }}>
              {fld("admin_full_name", "Nombre completo")}
              {fld("admin_email", "Correo de acceso", "email")}
              <button className="btn btn-primary">
                {form.admin_email ? "Crear clínica y credenciales" : "Crear clínica"}
              </button>
            </div>
          </>
        )}
      </form>

      <div className="card" style={{ padding: 0 }}>
        {clinics.length === 0 ? <div className="empty">Sin clínicas registradas.</div> : (
          <table>
            <thead>
              <tr><th>Clínica</th><th>RUC</th><th>Contacto</th><th>Estado</th><th>Creada</th><th></th></tr>
            </thead>
            <tbody>
              {clinics.map((c) => (
                <tr key={c.id} style={c.is_active ? {} : { opacity: 0.65 }}>
                  <td style={{ fontWeight: 600 }}>
                    {c.name}
                    {c.es_prueba && <span className="etiqueta-prueba">De pruebas</span>}
                    {/* Las adicionales que tiene, para verlas sin abrir la clínica. */}
                    {catalogo.some((f) => f.tipo === "adicional" && c.funcionalidades?.[f.clave]) && (
                      <span style={{ display: "block", fontSize: 11.5, fontWeight: 500, color: "var(--petrol)" }}>
                        + {catalogo.filter((f) => f.tipo === "adicional" && c.funcionalidades?.[f.clave])
                            .map((f) => f.nombre).join(", ")}
                      </span>
                    )}
                  </td>
                  <td className="tabular">{c.ruc || "—"}</td>
                  <td style={{ fontSize: 13 }}>{c.phone || "—"}{c.email ? ` · ${c.email}` : ""}</td>
                  <td>{c.is_active
                    ? <span className="badge badge-ok">Activa</span>
                    : <span className="badge badge-danger">Suspendida</span>}</td>
                  <td className="tabular">{(c.created_at || "").slice(0, 10)}</td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: 12 }}
                            onClick={() => empezarEdicion(c)}>Editar</button>
                    <button className="btn btn-ghost"
                            style={{ padding: "4px 10px", fontSize: 12, marginLeft: 6,
                                     color: c.is_active ? "var(--red)" : "var(--petrol)" }}
                            onClick={() => toggleActive(c)}>
                      {c.is_active ? "Suspender" : "Activar"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

/**
 * La identidad visual en el alta (o la edición) de una clínica: sus
 * logotipos y la paleta de su marca. Con la paleta se generan sus temas
 * —se ven aquí antes de guardar— y el principal pasa a ser el de la
 * clínica si aún tenía el de fábrica. Todo es opcional: sin nada, empieza
 * con la paleta de Clinube y su administración la cambia cuando quiera.
 */
function IdentidadDeLaClinica({ valor, onChange, actual }) {
  const previa = usePrevisualizacion(valor.paleta);
  const [leyendo, setLeyendo] = useState(false);
  const [aviso, setAviso] = useState("");

  function cambiarPaleta(paleta) {
    onChange({ ...valor, paleta, paletaTocada: true });
  }

  async function sacarDelLogotipo() {
    setLeyendo(true); setAviso("");
    try {
      const colores = await coloresDelLogotipo(valor.archivos.logo);
      if (colores.length) cambiarPaleta(colores);
      else setAviso("El logotipo no tiene colores que sirvan (es blanco y negro): elige la paleta a mano.");
    } catch (e) { setAviso(e.message); }
    finally { setLeyendo(false); }
  }

  function elegirArchivo(campo, archivo) {
    onChange({ ...valor, archivos: { ...valor.archivos, [campo]: archivo },
               quitar: { ...valor.quitar, [campo]: false } });
  }

  function quitar(campo) {
    const archivos = { ...valor.archivos };
    delete archivos[campo];
    onChange({ ...valor, archivos, quitar: { ...valor.quitar, [campo]: true } });
  }

  return (
    <div>
      <h4 style={{ marginBottom: 2, fontSize: 14 }}>Identidad visual</h4>
      <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 12 }}>
        Opcional. Con la paleta de su marca se generan sus temas: el principal será el de la clínica y su
        equipo podrá elegir entre estos y los de Clinube. Se puede cambiar después, aquí o desde su
        Configuración.
      </p>
      <div className="logos-rejilla" style={{ marginBottom: 16 }}>
        {LOGOS.map((d) => (
          <SelectorLogo key={d.campo} definicion={d}
                        url={actual?.[d.url]} version={actual?.updated_at}
                        archivo={valor.archivos[d.campo]} quitado={Boolean(valor.quitar[d.campo])}
                        onArchivo={(f) => elegirArchivo(d.campo, f)} onQuitar={() => quitar(d.campo)} />
        ))}
      </div>
      <div style={{ fontSize: 13.5, fontWeight: 600, marginBottom: 6 }}>Paleta de la marca</div>
      <EditorPaleta colores={valor.paleta} onChange={cambiarPaleta}
                    accionExtra={valor.archivos.logo && (
                      <button type="button" className="btn btn-ghost" style={{ fontSize: 13 }}
                              disabled={leyendo} onClick={sacarDelLogotipo}>
                        {leyendo ? "Leyendo el logotipo…" : "Sacar colores del logotipo"}
                      </button>
                    )} />
      {aviso && <p className="identidad-ayuda" style={{ color: "var(--amber)" }}>{aviso}</p>}
      <div style={{ fontSize: 13.5, fontWeight: 600, margin: "14px 0 8px" }}>Temas que se generan</div>
      {previa.error ? <div className="error-box">{previa.error}</div> : <VistaTemas temas={previa.temas} />}
    </div>
  );
}

/* ───────────── 3. Administradores de Clínicas ───────────── */

function AdminsTab() {
  const [confirm, ConfirmUI] = useConfirm();
  const [clinics, setClinics] = useState([]);
  const [creatingFor, setCreatingFor] = useState(null);
  const [editingEmail, setEditingEmail] = useState(null);   // clinic.id en edición
  const [emailDraft, setEmailDraft] = useState("");
  const [tempCred, setTempCred] = useState(null);  // {email, temporary_password}
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const resp = await api("/platform/clinics/");
      setClinics(await readList(resp));
    } catch (err) { setError(err?.message ? `No se pudieron cargar las clínicas. ${err.message}` : "No se pudieron cargar las clínicas."); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function resetPassword(clinic) {
    const ok = await confirm({
      title: `Restablecer la contraseña de ${clinic.name}`,
      message: `Se generará una contraseña temporal para ${clinic.admin.email}. La actual dejará de funcionar.`,
      confirmLabel: "Restablecer", danger: true,
    });
    if (!ok) return;
    try {
      const resp = await api(`/platform/clinics/${clinic.id}/admin/reset-password/`, { method: "POST" });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data?.detail || `Error ${resp.status}`);
      setTempCred({ ...data, clinica: clinic.name });
      load();   // la cuenta vuelve a quedar pendiente de cambio
    } catch (err) { setError(err.message); }
  }

  async function toggleAdmin(clinic) {
    const active = clinic.admin.is_active;
    const ok = await confirm({
      title: `${active ? "Desactivar" : "Activar"} la cuenta de ${clinic.admin.email}`,
      message: active
        ? "El administrador no podrá iniciar sesión hasta reactivarlo."
        : "El administrador recupera el acceso.",
      confirmLabel: active ? "Desactivar" : "Activar", danger: active,
    });
    if (!ok) return;
    try {
      const resp = await api(`/platform/clinics/${clinic.id}/admin/`, {
        method: "PATCH", body: JSON.stringify({ is_active: !active }),
      });
      if (!resp.ok) throw new Error(`Error ${resp.status}`);
      load();
    } catch (err) { setError(err.message); }
  }

  async function saveEmail(clinic) {
    if (!emailDraft || emailDraft === clinic.admin.email) { setEditingEmail(null); return; }
    try {
      const resp = await api(`/platform/clinics/${clinic.id}/admin/`, {
        method: "PATCH", body: JSON.stringify({ email: emailDraft }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data?.detail || `Error ${resp.status}`);
      setEditingEmail(null);
      load();
    } catch (err) { setError(err.message); }
  }

  return (
    <div>
      {ConfirmUI}
      {error && <div className="error-box">{error}</div>}

      {tempCred && (
        <PanelDeCredenciales cred={tempCred} clinica={tempCred.clinica}
                             onClose={() => setTempCred(null)} />
      )}

      {creatingFor && (
        <CreateAdminForm clinic={creatingFor}
                         onClose={() => setCreatingFor(null)}
                         onSaved={(cred) => {
                           setCreatingFor(null);
                           if (cred?.temporary_password) {
                             setTempCred({ ...cred, clinica: creatingFor.name });
                           }
                           load();
                         }} />
      )}

      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr><th>Clínica</th><th>Administrador</th><th>Correo</th><th>Cuenta</th><th></th></tr>
          </thead>
          <tbody>
            {clinics.map((c) => (
              <tr key={c.id}>
                <td style={{ fontWeight: 600 }}>{c.name}</td>
                <td>{c.admin ? c.admin.full_name : <span style={{ color: "var(--ink-soft)" }}>Sin asignar</span>}</td>
                <td>
                  {editingEmail === c.id ? (
                    <span style={{ display: "inline-flex", gap: 6 }}>
                      <input type="email" value={emailDraft} autoFocus
                             onChange={(e) => setEmailDraft(e.target.value)}
                             onKeyDown={(e) => e.key === "Enter" && saveEmail(c)}
                             style={{ padding: "4px 8px", border: "1px solid var(--petrol)", borderRadius: 6, fontSize: 13 }} />
                      <button className="btn btn-primary" style={{ padding: "3px 10px", fontSize: 12 }}
                              onClick={() => saveEmail(c)}>Guardar</button>
                      <button className="btn btn-ghost" style={{ padding: "3px 8px", fontSize: 12 }}
                              onClick={() => setEditingEmail(null)}>✕</button>
                    </span>
                  ) : (c.admin?.email || "—")}
                </td>
                {/* Tres estados, no dos. «Pendiente» es el que faltaba:
                    dice que las credenciales se generaron pero la clínica
                    todavía no ha entrado a elegir la suya, así que la
                    entrega no ha terminado. Sin él, una clínica que nunca
                    ingresó se ve igual que una que lleva meses trabajando. */}
                <td>{c.admin
                  ? (!c.admin.is_active
                      ? <span className="badge badge-danger">Desactivada</span>
                      : c.admin.must_change_password
                        ? <span className="badge badge-warn"
                                title="Se le generó una contraseña temporal y aún no ha ingresado a cambiarla.">
                            Pendiente de ingreso
                          </span>
                        : <span className="badge badge-ok">Activa</span>)
                  : "—"}
                  {c.admin?.is_active && (
                    <div style={{ fontSize: 11.5, color: "var(--ink-soft)", marginTop: 4 }}
                         title={c.condiciones ? `Aceptadas por ${c.condiciones.por}` : ""}>
                      {c.condiciones
                        ? `Condiciones aceptadas el ${new Date(c.condiciones.fecha).toLocaleDateString("es-EC")}`
                        : "Condiciones sin aceptar"}
                    </div>
                  )}</td>
                <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                  {c.admin ? (
                    <>
                      <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: 12 }}
                              onClick={() => resetPassword(c)}>Restablecer contraseña</button>
                      <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: 12, marginLeft: 6 }}
                              onClick={() => { setEditingEmail(c.id); setEmailDraft(c.admin.email); }}>Correo</button>
                      <button className="btn btn-ghost"
                              style={{ padding: "4px 10px", fontSize: 12, marginLeft: 6,
                                       color: c.admin.is_active ? "var(--red)" : "var(--petrol)" }}
                              onClick={() => toggleAdmin(c)}>
                        {c.admin.is_active ? "Desactivar" : "Activar"}
                      </button>
                    </>
                  ) : (
                    <button className="btn btn-primary" style={{ padding: "4px 12px", fontSize: 12 }}
                            onClick={() => setCreatingFor(c)}>+ Crear administrador</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CreateAdminForm({ clinic, onClose, onSaved }) {
  const [form, setForm] = useState({ full_name: "", email: "" });
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const resp = await api(`/platform/clinics/${clinic.id}/admin/`, {
        method: "POST", body: JSON.stringify(form),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(data?.detail || `Error ${resp.status}`);
      onSaved(data);
    } catch (err) { setError(err.message); }
  }

  return (
    <form onSubmit={submit} className="card" style={{ marginBottom: 18, borderColor: "var(--petrol)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
        <h3>Administrador para {clinic.name}</h3>
        <button type="button" className="btn btn-ghost" style={{ padding: "4px 12px", fontSize: 12 }} onClick={onClose}>✕</button>
      </div>
      {error && <div className="error-box">{error}</div>}
      {/* Ya no se pide contraseña: la genera el servidor y se muestra
          una sola vez al guardar. Pedirle a una persona que invente un
          secreto para otra es como acaban existiendo las «clinica2026». */}
      <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1.5fr auto", gap: "0 12px", alignItems: "end" }}>
        <div className="field" style={{ marginBottom: 0 }}><label>Nombre completo *</label>
          <input required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></div>
        <div className="field" style={{ marginBottom: 0 }}><label>Correo de acceso *</label>
          <input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
        <button className="btn btn-primary">Crear y generar credenciales</button>
      </div>
    </form>
  );
}

/* ───────────── Funciones: en prueba y publicadas ───────────── */

/**
 * Lo nuevo nace «en prueba»: solo lo ven las clínicas de prueba. Cuando
 * se ha probado lo suficiente se publica aquí para todas, y se puede
 * volver a dejar solo en las de prueba. Ni publicar ni retirar borra
 * datos (apps/common/funcionalidades.py).
 */
function FuncionesTab() {
  const [confirm, ConfirmUI] = useConfirm();
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState("");

  const load = useCallback(async () => {
    try { setDatos(await readObject(await api("/platform/funcionalidades/"))); }
    catch (err) { setError(err.message); }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function publicar(f, publicada) {
    const ok = await confirm(publicada ? {
      title: `Publicar «${f.nombre}» para todas las clínicas`,
      message: f.tipo === "adicional"
        ? "Quedará disponible para agregarla a cualquier clínica desde la pestaña Clínicas."
        : "Desde ahora la tendrán todas las clínicas, salvo las que la tengan apagada. Se puede retirar después.",
      confirmLabel: "Publicar",
    } : {
      title: `Volver a dejar «${f.nombre}» en prueba`,
      message: "Dejará de verse en las clínicas que no son de prueba. No se borra nada: al publicarla otra vez, vuelve como estaba.",
      confirmLabel: "Volver a prueba", danger: true,
    });
    if (!ok) return;
    setGuardando(f.clave); setError("");
    try {
      const resp = await api(`/platform/funcionalidades/${f.clave}/`, {
        method: "PATCH", body: JSON.stringify({ publicada }),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp));
      await load();
    } catch (err) { setError(err.message); }
    finally { setGuardando(""); }
  }

  if (!datos) return error ? <div className="error-box">{error}</div> : <div className="empty">Cargando…</div>;
  const catalogo = datos.funcionalidades || [];
  const enPrueba = catalogo.filter((f) => f.fase === "prueba");
  const publicadas = catalogo.filter((f) => f.fase !== "prueba" && f.nacio_en_prueba);
  const pruebas = datos.clinicas_de_prueba || [];

  const fila = (f, accion) => (
    <div key={f.clave} style={{ display: "flex", gap: 14, alignItems: "center", padding: "12px 18px",
                                 borderTop: "1px solid var(--line)" }}>
      <span style={{ flex: 1, minWidth: 0 }}>
        <strong style={{ fontSize: 14 }}>{f.nombre}</strong>
        <span className="etiqueta-adicional"
              style={f.tipo === "adicional" ? undefined : { color: "var(--ink-soft)", background: "var(--line)" }}>
          {f.tipo === "adicional" ? "Adicional" : "Incluida"}
        </span>
        <span style={{ display: "block", fontSize: 12.5, color: "var(--ink-soft)" }}>{f.descripcion}</span>
      </span>
      {accion}
    </div>
  );

  return (
    <div style={{ maxWidth: 860 }}>
      {ConfirmUI}
      {error && <div className="error-box">{error}</div>}
      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginBottom: 4 }}>Clínicas de prueba</h3>
        <p style={{ fontSize: 13, color: "var(--ink-soft)", margin: 0 }}>
          {pruebas.length
            ? <>Ven antes lo que está en prueba: <strong>{pruebas.map((c) => c.name).join(", ")}</strong>.</>
            : "Ninguna clínica es de pruebas: márcala en Clínicas → Editar para probar lo nuevo antes de publicarlo."}
        </p>
      </div>

      <h3 style={{ fontSize: 15, margin: "0 0 4px" }}>En prueba</h3>
      <p style={{ fontSize: 13, color: "var(--ink-soft)", margin: "0 0 10px" }}>
        Solo las tienen las clínicas de prueba. Al publicar una, se comporta como cualquier otra: una incluida
        llega a todas y una adicional se puede agregar a quien la pida.
      </p>
      <div className="card" style={{ padding: 0, marginBottom: 18 }}>
        {enPrueba.length === 0
          ? <div className="empty">No hay nada en prueba ahora mismo.</div>
          : enPrueba.map((f) => fila(f, (
            <button type="button" className="btn btn-primary" style={{ fontSize: 13 }}
                    disabled={guardando === f.clave} onClick={() => publicar(f, true)}>
              {guardando === f.clave ? "Publicando…" : "Publicar para todas"}
            </button>
          )))}
      </div>

      {publicadas.length > 0 && (
        <>
          <h3 style={{ fontSize: 15, margin: "0 0 4px" }}>Publicadas</h3>
          <p style={{ fontSize: 13, color: "var(--ink-soft)", margin: "0 0 10px" }}>
            Nacieron en prueba y ya las tienen todas. Si algo sale mal, se pueden volver a dejar solo en las de prueba.
          </p>
          <div className="card" style={{ padding: 0 }}>
            {publicadas.map((f) => fila(f, (
              <button type="button" className="btn btn-ghost" style={{ fontSize: 13, color: "var(--red)" }}
                      disabled={guardando === f.clave} onClick={() => publicar(f, false)}>
                Volver a prueba
              </button>
            )))}
          </div>
        </>
      )}
    </div>
  );
}

/* ───────────── 4. Auditoría ───────────── */

const ACTION_LABELS = {
  create_clinic: "Creó clínica", update_clinic: "Editó clínica",
  activate_clinic: "Activó clínica", deactivate_clinic: "Suspendió clínica",
  create_clinic_admin: "Creó administrador", update_clinic_admin: "Actualizó administrador",
  reset_clinic_admin_password: "Restableció contraseña", update_platform_config: "Cambió configuración",
  update_clinic_identity: "Cambió identidad visual",
  publish_feature: "Publicó función", unpublish_feature: "Devolvió función a prueba",
};

function AuditTab() {
  const [logs, setLogs] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api("/platform/audit/")
      .then(async (r) => (r.ok ? setLogs(await readList(r)) : setError(await apiErrorMessage(r))))
      .catch(() => setError("No se pudo contactar con el servidor."));
  }, []);

  if (error) return <div className="error-box">{error}</div>;
  if (logs === null) return <div className="empty">Cargando…</div>;

  return (
    <div className="card" style={{ padding: 0 }}>
      {logs.length === 0 ? (
        <div className="empty">Sin acciones registradas todavía.</div>
      ) : (
        <table>
          <thead><tr><th>Fecha y hora</th><th>Usuario</th><th>Acción</th><th>Detalle</th></tr></thead>
          <tbody>
            {logs.map((l) => (
              <tr key={l.id}>
                <td className="tabular" style={{ whiteSpace: "nowrap" }}>
                  {l.created_at.slice(0, 10)} {l.created_at.slice(11, 16)}
                </td>
                <td>{l.user}</td>
                <td><span className="badge badge-ok">{ACTION_LABELS[l.action] || l.action}</span></td>
                <td style={{ fontSize: 13, color: "var(--ink-soft)" }}>
                  {l.metadata?.name || l.metadata?.clinic || l.metadata?.email || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

/* ───────────── 5. Configuración General ───────────── */

function ConfigTab() {
  const [config, setConfig] = useState(null);
  const [smtpPassword, setSmtpPassword] = useState("");
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");
  const [destinoPrueba, setDestinoPrueba] = useState("");
  const [prueba, setPrueba] = useState(null);   // {ok, texto} | "enviando"

  useEffect(() => {
    api("/platform/config/")
      .then(async (r) => (r.ok ? setConfig(await r.json()) : setError(await apiErrorMessage(r))))
      .catch(() => setError("No se pudo contactar con el servidor."));
  }, []);

  if (error) return <div className="error-box">{error}</div>;
  if (!config) return <div className="empty">Cargando…</div>;

  async function save(e) {
    e.preventDefault();
    setError(""); setOkMsg("");
    try {
      const body = { ...config };
      delete body.smtp_password_set;
      delete body.correo_origen;
      delete body.updated_at;
      if (smtpPassword) body.smtp_password = smtpPassword;
      const resp = await api("/platform/config/", { method: "PATCH", body: JSON.stringify(body) });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp));
      const data = await resp.json();
      setConfig(data);
      setSmtpPassword("");
      setOkMsg("Configuración guardada.");
    } catch (err) { setError(err.message); }
  }

  const fld = (k, label, type = "text", placeholder = "") => (
    <div className="field" style={{ marginBottom: 0 }}>
      <label>{label}</label>
      <input type={type} value={config[k] ?? ""} placeholder={placeholder}
             onChange={(e) => setConfig({ ...config, [k]: e.target.value })} />
    </div>
  );

  /** Manda un correo con lo GUARDADO: lo que falte se dice tal cual. */
  async function probarCorreo() {
    setPrueba("enviando");
    try {
      const resp = await api("/platform/config/correo-de-prueba/", {
        method: "POST", body: JSON.stringify(destinoPrueba ? { destino: destinoPrueba } : {}),
      });
      const data = await resp.json().catch(() => null);
      setPrueba({ ok: resp.ok, texto: data?.detail || data?.error?.message
                                      || (resp.ok ? "Enviado." : `No se pudo enviar (error ${resp.status}).`) });
    } catch {
      setPrueba({ ok: false, texto: "No se pudo contactar con el servidor." });
    }
  }

  const origen = {
    plataforma: "Ahora el correo sale por el servidor de este formulario.",
    entorno: "Ahora el correo sale por el servidor del archivo .env del servidor (EMAIL_HOST). Si rellenas este formulario, se usará este.",
  }[config.correo_origen] || "Ahora no sale ningún correo: rellena el servidor y guarda.";

  return (
    <form onSubmit={save}>
      {error && <div className="error-box">{error}</div>}
      {okMsg && <div className="error-box" style={{ background: "var(--mint)", color: "var(--petrol-deep)" }}>✓ {okMsg}</div>}

      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginBottom: 12 }}>Identidad de la plataforma</h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px 14px" }}>
          {fld("platform_name", "Nombre de la plataforma")}
          {fld("logo_url", "URL del logo")}
          {fld("timezone", "Zona horaria")}
          {fld("currency", "Moneda")}
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginBottom: 4 }}>Titular de la plataforma</h3>
        <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 12 }}>
          Quien opera {config.platform_name || "la plataforma"}. Sale en el{" "}
          <a href="/privacidad/" target="_blank" rel="noopener">aviso de privacidad</a> y en las{" "}
          <a href="/condiciones/" target="_blank" rel="noopener">condiciones de uso</a>; mientras
          falte algo, esos textos lo muestran como pendiente.
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px 14px" }}>
          {fld("titular_nombre", "Razón social o nombre")}
          {fld("titular_ruc", "RUC")}
          {fld("titular_correo", "Correo para temas de privacidad", "email")}
          {fld("proveedor_correo", "Proveedor de correo (p. ej. Brevo)")}
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginBottom: 4 }}>Correo saliente (SMTP)</h3>
        <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 6 }}>
          Por aquí salen la recuperación de contraseñas del equipo y, si lo eliges abajo, el código
          para entrar en la app del paciente. {origen}
          {config.smtp_password_set && " Hay una contraseña guardada (no se muestra)."}
        </p>
        <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 12 }}>
          Con Gmail: servidor <code>smtp.gmail.com</code>, puerto <code>587</code>, usuario la
          dirección completa y, como contraseña, una <strong>contraseña de aplicación</strong> de 16
          letras (Cuenta de Google → Seguridad → Verificación en dos pasos → Contraseñas de
          aplicaciones). La contraseña normal de Gmail no sirve.
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "12px 14px" }}>
          {fld("smtp_host", "Servidor SMTP", "text", "smtp.gmail.com")}
          {fld("smtp_port", "Puerto", "number")}
          {fld("smtp_user", "Usuario", "text", "tu.cuenta@gmail.com")}
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Contraseña {config.smtp_password_set ? "(dejar vacío para no cambiar)" : ""}</label>
            <input type="password" value={smtpPassword} autoComplete="new-password"
                   onChange={(e) => setSmtpPassword(e.target.value)} />
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "end", flexWrap: "wrap", marginTop: 14 }}>
          <div className="field" style={{ marginBottom: 0, flex: "1 1 240px" }}>
            <label>Enviar un correo de prueba a</label>
            <input type="email" value={destinoPrueba} placeholder="Tu correo (si lo dejas vacío)"
                   onChange={(e) => setDestinoPrueba(e.target.value)} />
          </div>
          <button type="button" className="btn btn-ghost" disabled={prueba === "enviando"}
                  onClick={probarCorreo}>
            {prueba === "enviando" ? "Enviando…" : "Enviar correo de prueba"}
          </button>
        </div>
        <p style={{ fontSize: 12.5, color: "var(--ink-soft)", margin: "6px 0 0" }}>
          Usa lo guardado: si cambias algo arriba, guarda antes de probar.
        </p>
        {prueba && prueba !== "enviando" && (
          <p style={{ fontSize: 13, margin: "8px 0 0", color: prueba.ok ? "var(--ink)" : "var(--red)" }}>
            {prueba.ok ? "✓ " : ""}{prueba.texto}
          </p>
        )}
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginBottom: 4 }}>Código para entrar en la app del paciente</h3>
        <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 12 }}>
          Cómo le llega al paciente el código de 6 cifras con el que entra en la app. El correo es
          el canal de todas las clínicas. WhatsApp solo se usa con las clínicas que tienen
          contratada la función de WhatsApp (Clínicas → funciones adicionales); las demás siguen
          recibiendo el código por correo.
        </p>
        {[
          { valor: "correo", titulo: "Correo electrónico (recomendado)",
            texto: "Al correo de la ficha. Solo necesita el correo saliente de arriba funcionando: prueba antes con «Enviar correo de prueba»." },
          { valor: "whatsapp", titulo: "WhatsApp para quien lo contrate",
            texto: "Por WhatsApp a las clínicas con la función contratada y su cuenta de Meta conectada (plantilla «otp_login» aprobada). El resto, por correo." },
        ].map((o) => (
          <label key={o.valor} style={{ display: "flex", gap: 10, alignItems: "flex-start",
                                        marginBottom: 10, cursor: "pointer" }}>
            <input type="radio" name="canal_codigo_paciente" value={o.valor}
                   checked={(config.canal_codigo_paciente || "correo") === o.valor}
                   onChange={() => setConfig({ ...config, canal_codigo_paciente: o.valor })}
                   style={{ marginTop: 3 }} />
            <span>
              <strong style={{ fontSize: 14 }}>{o.titulo}</strong>
              <span style={{ display: "block", fontSize: 13, color: "var(--ink-soft)" }}>{o.texto}</span>
            </span>
          </label>
        ))}
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginBottom: 4 }}>Entrar con Google</h3>
        <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 12 }}>
          Con esto aparece «Continuar con Google» en el inicio de sesión del panel. El equipo de una
          clínica entra con el correo que tiene registrado; Google no crea cuentas del equipo.
          Se obtiene gratis en Google Cloud → APIs y servicios → Credenciales → «ID de cliente de
          OAuth» de tipo «Aplicación web», con origen autorizado https://app.clinube.com.
        </p>
        <div className="field" style={{ marginBottom: 0 }}>
          <label>ID de cliente de Google</label>
          <input value={config.google_client_id || ""} placeholder="1234567890-abc.apps.googleusercontent.com"
                 onChange={(e) => setConfig({ ...config, google_client_id: e.target.value.trim() })} />
        </div>
      </div>

      <button className="btn btn-primary">Guardar configuración</button>
    </form>
  );
}
