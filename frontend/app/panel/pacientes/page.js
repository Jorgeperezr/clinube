"use client";

import { useEffect, useState, useCallback } from "react";
import { api, readList } from "../../../lib/api";

const ORDER_OPTIONS = [
  ["name_asc", "Nombre (A-Z)"],
  ["name_desc", "Nombre (Z-A)"],
  ["created_desc", "Registro (recientes)"],
  ["created_asc", "Registro (antiguos)"],
  ["attention_desc", "Nº de atenciones (mayor)"],
  ["attention_asc", "Nº de atenciones (menor)"],
  ["next_appt_asc", "Próxima cita"],
];

function fmtDateTime(iso) {
  if (!iso) return "—";
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)}`;
}

export default function PacientesPage() {
  const [patients, setPatients] = useState([]);
  const [search, setSearch] = useState("");
  const [ordering, setOrdering] = useState("name_asc");
  const [view, setView] = useState("list");   // "list" | "cards"
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (q = "", order = "name_asc") => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (q) params.set("search", q);
      params.set("ordering", order);
      const resp = await api(`/patients/?${params.toString()}`);
      setPatients(await readList(resp));
    } catch {
      setError("No se pudo cargar la lista de pacientes.");
    } finally {
      setLoading(false);
    }
  }, []);

  // La búsqueda de la barra lateral llega como ?buscar=: se aplica nada
  // más entrar, y después la página sigue a su aire.
  const [inicial] = useState(() => (typeof window === "undefined" ? ""
    : new URLSearchParams(window.location.search).get("buscar") || ""));
  useEffect(() => { if (inicial) setSearch(inicial); }, [inicial]);
  useEffect(() => { load(search || inicial, ordering); }, [load, ordering]);   // recarga al cambiar orden

  // Recordar la preferencia de vista
  useEffect(() => {
    try {
      const v = localStorage.getItem("patientsView");
      if (v === "cards" || v === "list") setView(v);
    } catch {}
  }, []);

  function setViewPersist(v) {
    setView(v);
    try { localStorage.setItem("patientsView", v); } catch {}
  }

  function handleSearch(e) {
    e.preventDefault();
    load(search, ordering);
  }

  return (
    <div>
      <div className="encabezado-pagina">
        <div>
          <h1>Pacientes</h1>
          {!loading && <p>{patients.length === 1 ? "1 paciente" : `${patients.length} pacientes`}{search ? ` con «${search}»` : ""}</p>}
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cerrar" : "+ Nuevo paciente"}
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}

      {showForm && (
        <PatientForm
          onSaved={() => { setShowForm(false); load(search, ordering); }}
        />
      )}

      {/* Buscar, ordenar y alternar vista, en una sola barra */}
      <div className="barra-herramientas">
        <form onSubmit={handleSearch} className="campo-busqueda" role="search">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9"
               strokeLinecap="round" aria-hidden="true"><circle cx="11" cy="11" r="6.5" /><path d="M16 16l4.5 4.5" /></svg>
          <input placeholder="Buscar por nombre, apellido o cédula" aria-label="Buscar pacientes"
                 value={search} onChange={(e) => setSearch(e.target.value)} />
        </form>
        <select value={ordering} onChange={(e) => setOrdering(e.target.value)}
                className="selector-suave" aria-label="Ordenar por">
          {ORDER_OPTIONS.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
        </select>
        <div className="segmentado" role="group" aria-label="Vista">
          <button type="button" aria-pressed={view === "list"} onClick={() => setViewPersist("list")}>▤ Lista</button>
          <button type="button" aria-pressed={view === "cards"} onClick={() => setViewPersist("cards")}>▦ Tarjetas</button>
        </div>
      </div>

      {loading ? (
        <div className="card"><div className="empty">Cargando…</div></div>
      ) : patients.length === 0 ? (
        <div className="card"><div className="empty">
          No hay pacientes registrados todavía. Registra el primero con “+ Nuevo paciente”.
        </div></div>
      ) : view === "list" ? (
        <div className="card" style={{ padding: 0 }}>
          <table>
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Cédula</th>
                <th>Teléfono</th>
                <th>Atenciones</th>
                <th>Próxima cita</th>
                <th>Registrado</th>
              </tr>
            </thead>
            <tbody>
              {patients.map((p) => (
                <tr key={p.id} onClick={() => window.location.href = `/panel/paciente/?id=${p.id}`}
                    style={{ cursor: "pointer" }}>
                  <td style={{ fontWeight: 600 }}>{p.full_name}</td>
                  <td className="tabular">{p.national_id}</td>
                  <td className="tabular">{p.phone || "—"}</td>
                  <td className="tabular">{p.attention_count ?? 0}</td>
                  <td className="tabular">{p.next_appointment ? fmtDateTime(p.next_appointment) : "—"}</td>
                  <td className="tabular">{(p.created_at || "").slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div style={{ display: "grid", gap: 14,
                      gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))" }}>
          {patients.map((p) => <PatientCard key={p.id} patient={p} />)}
        </div>
      )}
    </div>
  );
}

function PatientCard({ patient: p }) {
  const initials = (p.full_name || "?").split(" ").filter(Boolean).slice(0, 2)
    .map((w) => w[0]).join("").toUpperCase();
  return (
    <div className="card" onClick={() => window.location.href = `/panel/paciente/?id=${p.id}`}
         style={{ cursor: "pointer", display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ width: 46, height: 46, borderRadius: "50%", flexShrink: 0,
                      background: "var(--petrol-soft)", color: "var(--petrol-deep)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontWeight: 700, fontSize: 16 }}>
          {initials}
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {p.full_name}
          </div>
          <div className="tabular" style={{ fontSize: 13, color: "var(--ink-soft)" }}>{p.national_id}</div>
        </div>
      </div>
      <div style={{ fontSize: 13, color: "var(--ink-soft)", display: "flex", flexDirection: "column", gap: 3 }}>
        <span>📞 {p.phone || "—"}</span>
        <span>🗂 {p.attention_count ?? 0} atencion{(p.attention_count ?? 0) === 1 ? "" : "es"}</span>
        <span>📅 {p.next_appointment ? fmtDateTime(p.next_appointment) : "Sin cita próxima"}</span>
      </div>
    </div>
  );
}

function PatientForm({ onSaved }) {
  const [form, setForm] = useState({
    first_name: "", last_name: "", national_id: "",
    phone: "", email: "", birth_date: "", agreement: "",
  });
  const [agreements, setAgreements] = useState([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  // Los convenios se cargan una vez al abrir el formulario. Si la clínica
  // no tiene ninguno, el selector no llega a pintarse: no tiene sentido
  // pedir «particular o convenio» donde solo existe una respuesta.
  useEffect(() => {
    api("/config/agreements/")
      .then(async (r) => setAgreements((await readList(r)).filter((a) => a.is_active)))
      .catch(() => setAgreements([]));
  }, []);

  function set(k, v) { setForm((f) => ({ ...f, [k]: v })); }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const body = { ...form };
      if (!body.birth_date) delete body.birth_date;
      if (!body.email) delete body.email;
      // "" no es un UUID: el paciente particular va sin convenio, no con
      // uno vacío, o el serializador responde 400.
      if (!body.agreement) delete body.agreement;
      const resp = await api("/patients/", { method: "POST", body: JSON.stringify(body) });
      const data = await resp.json();
      if (!resp.ok) {
        const detail = data?.error?.details || data;
        const first = typeof detail === "object" ? Object.values(detail)[0] : detail;
        throw new Error(Array.isArray(first) ? first[0] : String(first));
      }
      onSaved();
    } catch (err) {
      setError(err.message || "No se pudo guardar el paciente.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="card" style={{ marginBottom: 20 }}>
      <h3 style={{ marginBottom: 14 }}>Nuevo paciente</h3>
      {error && <div className="error-box">{error}</div>}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 16px" }}>
        <div className="field">
          <label>Nombres *</label>
          <input required value={form.first_name} onChange={(e) => set("first_name", e.target.value)} />
        </div>
        <div className="field">
          <label>Apellidos *</label>
          <input required value={form.last_name} onChange={(e) => set("last_name", e.target.value)} />
        </div>
        <div className="field">
          <label>Cédula / Identificación *</label>
          <input required value={form.national_id} onChange={(e) => set("national_id", e.target.value)} />
        </div>
        <div className="field">
          <label>Teléfono (WhatsApp)</label>
          <input placeholder="+5939…" value={form.phone} onChange={(e) => set("phone", e.target.value)} />
        </div>
        <div className="field">
          <label>Correo</label>
          <input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} />
        </div>
        <div className="field">
          <label>Fecha de nacimiento</label>
          <input type="date" value={form.birth_date} onChange={(e) => set("birth_date", e.target.value)} />
        </div>
        {agreements.length > 0 && (
          <div className="field">
            <label>Convenio</label>
            <select value={form.agreement} onChange={(e) => set("agreement", e.target.value)}>
              <option value="">Particular (sin convenio)</option>
              {agreements.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </div>
        )}
      </div>
      <button className="btn btn-primary" disabled={saving}>
        {saving ? "Guardando…" : "Guardar paciente"}
      </button>
    </form>
  );
}
