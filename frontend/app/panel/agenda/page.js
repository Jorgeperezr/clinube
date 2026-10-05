"use client";

import { useCallback, useEffect, useState } from "react";
import { api, readList } from "../../../lib/api";
import { fechaISO, hoyISO } from "../../../lib/fechas.mjs";

const STATUS_STYLE = {
  pending:     { label: "Pendiente",   cls: "badge-warn" },
  confirmed:   { label: "Confirmada",  cls: "badge-ok" },
  completed:   { label: "Completada",  cls: "badge-ok" },
  cancelled:   { label: "Cancelada",   cls: "badge-danger" },
  rescheduled: { label: "Reagendada",  cls: "badge-warn" },
  no_show:     { label: "No asistió",  cls: "badge-danger" },
};

function todayISO() { return hoyISO(); }

function fmtTime(iso) {
  return new Date(iso).toLocaleTimeString("es-EC", { hour: "2-digit", minute: "2-digit" });
}

export default function AgendaPage() {
  const [mode, setMode] = useState("daily");
  const [date, setDate] = useState(todayISO());
  const [doctors, setDoctors] = useState([]);

  // Color identificativo por profesional. El backend ya guarda
  // `calendar_color`; si algún doctor no lo tiene, se deriva uno estable
  // de su nombre para que nunca queden dos citas sin distinguir.
  function doctorColor(name) {
    const d = doctors.find((x) => (x.full_name || x.email) === name);
    if (d?.calendar_color) return d.calendar_color;
    let h = 0;
    for (const ch of String(name || "")) h = (h * 31 + ch.charCodeAt(0)) % 360;
    return `hsl(${h} 45% 48%)`;
  }
  const [doctorId, setDoctorId] = useState("");
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");
  const [calNotice, setCalNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ mode, date });
      if (doctorId) params.set("doctor_id", doctorId);
      const resp = await api(`/agenda/view/?${params}`);
      setAppointments(await readList(resp));
    } catch (err) {
      setError(`No se pudo cargar la agenda. ${err?.message || ""}`.trim());
      setAppointments(null);
    } finally {
      setLoading(false);
    }
  }, [mode, date, doctorId]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    api("/doctors/").then(async (r) => {
      setDoctors(await readList(r));
    }).catch(() => {});
  }, []);

  function shiftDate(days) {
    const d = new Date(date + "T12:00:00");
    d.setDate(d.getDate() + days);
    setDate(fechaISO(d));
  }

  async function doAction(appt, action) {
    try {
      const resp = await api(`/appointments/${appt.id}/${action}/`, { method: "POST" });
      if (!resp.ok) {
        const data = await resp.json();
        throw new Error(data?.error?.message || data?.detail || "No se pudo completar la acción.");
      }
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  const shiftDays = mode === "monthly" ? 30 : mode === "weekly" ? 7 : 1;
  const periodo = describirPeriodo(mode, date);
  const citasActivas = (appointments || []).filter((a) => !["cancelled", "no_show"].includes(a.status)).length;

  return (
    <div>
      <div className="encabezado-pagina">
        <div>
          <h1>Agenda</h1>
          <p>{periodo}{!loading && appointments ? ` · ${citasActivas === 1 ? "1 cita" : `${citasActivas} citas`}` : ""}</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cerrar" : "+ Nueva cita"}
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}
      {calNotice && (
        <div className="success-box">
          ✓ URL del calendario copiada al portapapeles. {calNotice}
        </div>
      )}

      {showForm && (
        <AppointmentForm
          doctors={doctors}
          defaultDate={date}
          onSaved={() => { setShowForm(false); load(); }}
        />
      )}

      {/* Controles: día/semana, fecha, doctor */}
      <div className="barra-herramientas">
        <div className="segmentado" role="group" aria-label="Vista">
          {["daily", "weekly", "monthly"].map((m) => (
            <button key={m} type="button" aria-pressed={mode === m} onClick={() => setMode(m)}>
              {m === "daily" ? "Día" : m === "weekly" ? "Semana" : "Mes"}
            </button>
          ))}
        </div>

        <div className="navegador-fecha">
          <button type="button" onClick={() => shiftDate(-shiftDays)} aria-label="Anterior">‹</button>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} aria-label="Fecha" />
          <button type="button" onClick={() => shiftDate(shiftDays)} aria-label="Siguiente">›</button>
        </div>
        <button className="btn btn-ghost" onClick={() => setDate(todayISO())}>Hoy</button>

        {doctorId && (
          <button className="btn btn-ghost" style={{ fontSize: 13 }}
                  onClick={async () => {
                    try {
                      const r = await api(`/doctors/${doctorId}/calendar-url/`);
                      const d = await r.json();
                      if (!r.ok) throw new Error(d?.detail || "Sin permiso.");
                      await navigator.clipboard.writeText(d.url);
                      setError("");
                      setCalNotice(d.instructions);
                      setTimeout(() => setCalNotice(""), 9000);
                    } catch (err) { setError(err.message); }
                  }}>
            🗓 Calendario del doctor
          </button>
        )}
        <select value={doctorId} onChange={(e) => setDoctorId(e.target.value)}
                className="selector-suave" style={{ marginLeft: "auto" }} aria-label="Profesional">
          <option value="">Todos los doctores</option>
          {doctors.map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}
        </select>
      </div>

      {mode === "monthly" ? (
        <MonthGrid date={date} appointments={appointments || []}
                   onDayClick={(d) => { setDate(d); setMode("daily"); }} />
      ) : (
      <div className="card" style={{ padding: 0 }}>
        {loading ? (
          <div className="empty">Cargando…</div>
        ) : appointments === null ? (
          // Si la carga falló no se sabe si hay citas: decir «no hay
          // ninguna» haría que recepción diera huecos por libres.
          <div className="empty">No se pudieron cargar las citas.</div>
        ) : appointments.length === 0 ? (
          <div className="empty">No hay citas en este período. Agenda la primera con “+ Nueva cita”.</div>
        ) : (
          <>
          {doctors.length > 1 && (
            <div style={{ display: "flex", gap: 14, flexWrap: "wrap", padding: "10px 14px",
                          borderBottom: "1px solid var(--line)", fontSize: 12.5 }}
                 aria-label="Leyenda de profesionales">
              {doctors.map((d) => (
                <span key={d.id} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <span aria-hidden="true"
                        style={{ width: 9, height: 9, borderRadius: "50%",
                                 background: doctorColor(d.full_name || d.email) }} />
                  <span style={{ color: "var(--ink-soft)" }}>{d.full_name || d.email}</span>
                </span>
              ))}
            </div>
          )}
          {/* Una fila por cita, con la hora destacada a la izquierda y el
              color del profesional en el borde; en la semana, agrupadas por día. */}
          {agruparPorDia(appointments, mode === "weekly").map(([dia, citas]) => (
            <div key={dia || "dia"}>
              {dia && <div className="lista-citas-dia">{dia}</div>}
              <ol className="lista-citas">
                {citas.map((a) => {
                  const st = STATUS_STYLE[a.status] || { label: a.status, cls: "badge-warn" };
                  return (
                    <li key={a.id} className="cita-fila" style={{ "--color-doctor": doctorColor(a.doctor_name) }}>
                      <span className="cita-fila-hora tabular">
                        {fmtTime(a.scheduled_start)}
                        <small>{fmtTime(a.scheduled_end)}</small>
                      </span>
                      <a href={`/panel/paciente/?id=${a.patient}`} className="cita-fila-paciente">
                        <strong>{a.patient_name}</strong>
                        <span className="cita-fila-doctor">{a.doctor_name}</span>
                      </a>
                      <span className="cita-fila-estado">
                        <span className={`badge ${st.cls}`}>{st.label}</span>
                        {a.reminder_sent_at && (
                          <span title="Recordatorio WhatsApp enviado" style={{ marginLeft: 6, fontSize: 12 }}>📨</span>
                        )}
                      </span>
                      <span className="cita-fila-acciones"><RowActions appt={a} onAction={doAction} /></span>
                    </li>
                  );
                })}
              </ol>
            </div>
          ))}
          </>
        )}
      </div>
      )}
    </div>
  );
}

function MonthGrid({ date, appointments, onDayClick }) {
  const base = new Date(date + "T12:00:00");
  const year = base.getFullYear(), month = base.getMonth();
  const firstDay = new Date(year, month, 1);
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  // Lunes=0 … Domingo=6
  const startOffset = (firstDay.getDay() + 6) % 7;

  const byDay = {};
  for (const a of appointments) {
    const d = a.scheduled_start.slice(0, 10);
    (byDay[d] = byDay[d] || []).push(a);
  }

  const cells = [];
  for (let i = 0; i < startOffset; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push(`${year}-${String(month + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`);
  }

  const todayStr = hoyISO();
  const monthName = base.toLocaleDateString("es-EC", { month: "long", year: "numeric" });

  return (
    <div className="card">
      <h3 style={{ marginBottom: 12, textTransform: "capitalize" }}>{monthName}</h3>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 6 }}>
        {["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"].map((d) => (
          <div key={d} style={{ fontSize: 11, fontWeight: 700, color: "var(--ink-soft)",
                                textTransform: "uppercase", textAlign: "center", padding: 4 }}>{d}</div>
        ))}
        {cells.map((day, i) => {
          if (!day) return <div key={`e${i}`} />;
          const appts = byDay[day] || [];
          const active = appts.filter((a) => !["cancelled", "no_show"].includes(a.status)).length;
          const isToday = day === todayStr;
          return (
            <button key={day} onClick={() => onDayClick(day)}
              style={{
                minHeight: 74, padding: 6, borderRadius: 8, cursor: "pointer",
                border: isToday ? "2px solid var(--petrol)" : "1px solid var(--line)",
                background: active > 0 ? "var(--petrol-soft)" : "var(--elev)",
                display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 4,
                textAlign: "left",
              }}
              aria-label={`Día ${day}: ${active} citas`}>
              <span className="tabular" style={{ fontSize: 12, fontWeight: isToday ? 700 : 500 }}>
                {Number(day.slice(8, 10))}
              </span>
              {active > 0 && (
                <span className="badge badge-ok" style={{ fontSize: 11 }}>
                  {active} cita{active > 1 ? "s" : ""}
                </span>
              )}
            </button>
          );
        })}
      </div>
      <p style={{ fontSize: 12, color: "var(--ink-soft)", marginTop: 10 }}>
        Haz clic en un día para ver su agenda en detalle.
      </p>
    </div>
  );
}

/** «Lunes, 5 de octubre», «Semana del 5 al 11 de octubre», «Octubre de 2026». */
function describirPeriodo(mode, date) {
  const d = new Date(date + "T12:00:00");
  const may = (t) => t.charAt(0).toUpperCase() + t.slice(1);
  if (mode === "monthly") return may(d.toLocaleDateString("es-EC", { month: "long", year: "numeric" }));
  if (mode === "weekly") {
    const ini = new Date(d); ini.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    const fin = new Date(ini); fin.setDate(ini.getDate() + 6);
    const mes = (x) => x.toLocaleDateString("es-EC", { month: "long" });
    return mes(ini) === mes(fin)
      ? `Semana del ${ini.getDate()} al ${fin.getDate()} de ${mes(fin)}`
      : `Semana del ${ini.getDate()} de ${mes(ini)} al ${fin.getDate()} de ${mes(fin)}`;
  }
  return may(d.toLocaleDateString("es-EC", { weekday: "long", day: "numeric", month: "long" }));
}

/** [[«Lunes 5», citas], …] en la semana; en el día, un solo grupo sin título. */
function agruparPorDia(citas, porDia) {
  if (!porDia) return [["", citas]];
  const grupos = new Map();
  for (const c of citas) {
    const dia = new Date(c.scheduled_start).toLocaleDateString("es-EC", { weekday: "long", day: "numeric", month: "short" });
    const clave = dia.charAt(0).toUpperCase() + dia.slice(1);
    if (!grupos.has(clave)) grupos.set(clave, []);
    grupos.get(clave).push(c);
  }
  return [...grupos.entries()];
}

function RowActions({ appt, onAction }) {
  const btn = { padding: "5px 10px", fontSize: 12, borderRadius: 7, marginLeft: 6 };
  if (appt.status === "pending") {
    return (
      <>
        <button className="btn btn-ghost" style={btn} onClick={() => onAction(appt, "confirm")}>Confirmar</button>
        <button className="btn btn-ghost" style={btn} onClick={() => onAction(appt, "cancel")}>Cancelar</button>
      </>
    );
  }
  if (appt.status === "confirmed" && !appt.checkin_at) {
    return (
      <>
        <button className="btn btn-primary" style={btn} onClick={() => onAction(appt, "checkin")}>Llegó</button>
        <button className="btn btn-ghost" style={btn} onClick={() => onAction(appt, "cancel")}>Cancelar</button>
      </>
    );
  }
  if (appt.checkin_at && !appt.attention_started_at && !appt.checkout_at) {
    return (
      <>
        <span className="badge badge-warn" style={{ marginRight: 6 }}>En espera</span>
        <button className="btn btn-primary" style={btn} onClick={() => onAction(appt, "start")}>Iniciar atención</button>
      </>
    );
  }
  if (appt.attention_started_at && !appt.checkout_at) {
    return (
      <>
        <span className="badge badge-ok" style={{ marginRight: 6 }}>En atención</span>
        <button className="btn btn-primary" style={btn} onClick={() => onAction(appt, "checkout")}>Finalizar</button>
      </>
    );
  }
  return null;
}

function AppointmentForm({ doctors, defaultDate, onSaved }) {
  const [patientQuery, setPatientQuery] = useState("");
  const [patientResults, setPatientResults] = useState([]);
  const [patient, setPatient] = useState(null);
  const [doctor, setDoctor] = useState("");
  const [date, setDate] = useState(defaultDate);
  const [start, setStart] = useState("09:00");
  const [end, setEnd] = useState("09:30");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [delinquent, setDelinquent] = useState(false);
  const [saving, setSaving] = useState(false);

  async function searchPatients(q) {
    setPatientQuery(q);
    setPatient(null);
    if (q.length < 2) { setPatientResults([]); return; }
    try {
      const resp = await api(`/patients/?search=${encodeURIComponent(q)}`);
      setPatientResults((await readList(resp)).slice(0, 6));
    } catch { /* silencioso */ }
  }

  async function submit(withOverride = false) {
    if (!patient) { setError("Selecciona un paciente de la lista."); return; }
    setError("");
    setSaving(true);
    setDelinquent(false);
    try {
      const body = {
        patient: patient.id,
        doctor,
        scheduled_start: `${date}T${start}:00`,
        scheduled_end: `${date}T${end}:00`,
        notes,
      };
      if (withOverride) body.override = "true";
      const resp = await api("/appointments/", { method: "POST", body: JSON.stringify(body) });
      const data = await resp.json();
      if (resp.status === 409 && data?.error?.code === "patient_delinquent") {
        setDelinquent(true);
        return;
      }
      if (!resp.ok) {
        const detail = data?.error?.details || data?.error?.message || data;
        const first = typeof detail === "object" ? Object.values(detail)[0] : detail;
        throw new Error(Array.isArray(first) ? first[0] : String(first));
      }
      onSaved();
    } catch (err) {
      setError(err.message || "No se pudo agendar la cita.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <h3 style={{ marginBottom: 14 }}>Nueva cita</h3>
      {error && <div className="error-box">{error}</div>}

      {delinquent && (
        <div className="error-box" style={{ background: "var(--amber-soft)", color: "var(--amber)" }}>
          <strong>Paciente con cuotas vencidas.</strong> El sistema bloquea el
          agendamiento por morosidad. ¿Agendar de todas formas (excepción manual)?
          <div style={{ marginTop: 10 }}>
            <button className="btn btn-primary" style={{ fontSize: 13 }} onClick={() => submit(true)} disabled={saving}>
              Sí, agendar con excepción
            </button>
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 16px" }}>
        <div className="field" style={{ position: "relative" }}>
          <label>Paciente *</label>
          <input
            placeholder="Buscar por nombre o cédula…"
            value={patient ? `${patient.full_name} (${patient.national_id})` : patientQuery}
            onChange={(e) => searchPatients(e.target.value)}
          />
          {patientResults.length > 0 && !patient && (
            <div style={{
              position: "absolute", top: "100%", left: 0, right: 0, zIndex: 10,
              background: "var(--elev)", border: "1px solid var(--line)", borderRadius: 8,
              boxShadow: "var(--shadow)",
            }}>
              {patientResults.map((p) => (
                <div key={p.id}
                     onClick={() => { setPatient(p); setPatientResults([]); }}
                     style={{ padding: "9px 12px", cursor: "pointer", fontSize: 14 }}>
                  <strong>{p.full_name}</strong> · <span className="tabular">{p.national_id}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="field">
          <label>Doctor *</label>
          <select required value={doctor} onChange={(e) => setDoctor(e.target.value)}>
            <option value="">Seleccionar…</option>
            {doctors.map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}
          </select>
        </div>

        <div className="field">
          <label>Fecha *</label>
          <input type="date" required value={date} onChange={(e) => setDate(e.target.value)} />
        </div>

        <div className="field" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <div>
            <label>Inicio *</label>
            <input type="time" required value={start} onChange={(e) => setStart(e.target.value)} style={{ width: "100%" }} />
          </div>
          <div>
            <label>Fin *</label>
            <input type="time" required value={end} onChange={(e) => setEnd(e.target.value)} style={{ width: "100%" }} />
          </div>
        </div>
      </div>

      <div className="field">
        <label>Notas</label>
        <textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
      </div>

      <button className="btn btn-primary" disabled={saving || !patient || !doctor} onClick={() => submit(false)}>
        {saving ? "Agendando…" : "Agendar cita"}
      </button>
    </div>
  );
}
