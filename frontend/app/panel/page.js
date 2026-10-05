"use client";

import { useEffect, useState } from "react";
import { api, currentUser, readList, tieneFuncion } from "../../lib/api";
import DayAlerts from "../../lib/DayAlerts";
import Portada from "../../lib/Portada";
import { hoyISO } from "../../lib/fechas.mjs";

const money = (v) => `$${Number(v || 0).toFixed(2)}`;
const todayISO = () => hoyISO();
const fmtTime = (iso) =>
  new Date(iso).toLocaleTimeString("es-EC", { hour: "2-digit", minute: "2-digit" });

function firstOfMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

export default function Dashboard() {
  const [user, setUser] = useState(null);
  const [appointments, setAppointments] = useState(null);
  const [patientCount, setPatientCount] = useState(null);
  const [income, setIncome] = useState(null);
  const [delinquents, setDelinquents] = useState(null);
  const [lowStock, setLowStock] = useState(null);
  const [followUps, setFollowUps] = useState(null);
  const [recientes, setRecientes] = useState(null);

  useEffect(() => {
    const u = currentUser();
    if (u?.role === "superadmin") {
      window.location.href = "/panel/plataforma/";
      return;
    }
    setUser(u);
    if (!u) return;

    // Cada widget carga según lo que el rol puede ver; los que el
    // backend rechace (403) simplemente no se muestran.
    api(`/agenda/view/?mode=daily&date=${todayISO()}`)
      .then(async (r) => { if (r.ok) { setAppointments(await readList(r)); } })
      .catch(() => {});

    api("/patients/?search=")
      .then(async (r) => { if (r.ok) { const d = await r.json(); setPatientCount(d.count ?? (d.results || d).length); } })
      .catch(() => {});
    api("/patients/?ordering=created_desc")
      .then(readList)
      .then((l) => setRecientes(l.slice(0, 12)))
      .catch(() => setRecientes([]));

    if (tieneFuncion(u, "reportes")) {
      api(`/reports/financial/?date_from=${firstOfMonth()}&date_to=${todayISO()}`)
        .then(async (r) => { if (r.ok) setIncome(await r.json()); })
        .catch(() => {});
    }
    if (tieneFuncion(u, "cobros")) {
      api("/reports/delinquency/")
        .then(async (r) => { if (r.ok) { const d = await r.json(); setDelinquents(d.patients || []); } })
        .catch(() => {});
    }
    if (["admin", "doctor", "auxiliary"].includes(u.role)) {
      api("/clinical/follow-ups/")
        .then(async (r) => { if (r.ok) { const d = await r.json(); setFollowUps(d.results || []); } })
        .catch(() => {});
    }
    if (tieneFuncion(u, "inventario")) {
      api("/inventory/alerts/low-stock/")
        .then(async (r) => { if (r.ok) { const d = await r.json(); setLowStock(d.low_stock_products || []); } })
        .catch(() => {});
    }
  }, []);

  if (!user) return null;

  const today = new Date().toLocaleDateString("es-EC", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });
  const upcoming = (appointments || []).filter((a) =>
    !["cancelled", "completed", "no_show"].includes(a.status));
  const blockingCount = (delinquents || []).filter((p) => p.is_blocking).length;

  return (
    <div>
      <div className="encabezado-pagina">
        <div>
          <h1>Hola, {user.full_name || user.email}</h1>
          {/* Solo la primera letra en mayúscula: «capitalize» escribía
              «30 De Septiembre De 2026», que en castellano es un error. */}
          <p>{today.charAt(0).toUpperCase() + today.slice(1)}</p>
        </div>
      </div>

      {/* Acciones rápidas */}
      <div style={{ display: "flex", gap: 10, marginBottom: 22, flexWrap: "wrap" }}>
        {/* Solo a quien de verdad puede crearla: antes lo veían todos
            los doctores y la API les respondía 403 al guardar. */}
        {tieneFuncion(user, "agenda") && (
          <a className="btn btn-primary" href="/panel/agenda/">+ Nueva cita</a>
        )}
        <a className="btn btn-ghost" href="/panel/pacientes/">+ Nuevo paciente</a>
        {tieneFuncion(user, "cobros") && (
          <a className="btn btn-ghost" href="/panel/pagos/">Registrar cobro</a>
        )}
      </div>

      {/* Avisos del día: llegadas de pacientes y cumpleaños */}
      <DayAlerts role={user.role} />

      {/* Indicadores */}
      <div style={{ display: "flex", gap: 14, marginBottom: 22, flexWrap: "wrap" }}>
        <StatCard label="Citas hoy" value={appointments === null ? "…" : appointments.length}
                  sub={appointments !== null ? `${upcoming.length} activas` : ""} href="/panel/agenda/" />
        <StatCard label="Pacientes" value={patientCount ?? "…"} href="/panel/pacientes/" />
        {income && (
          <StatCard label="Ingresos del mes" value={money(income.total_income)}
                    sub={`${income.payment_count} pagos`} accent href="/panel/reportes/" />
        )}
        {delinquents !== null && (
          <StatCard label="Pacientes morosos" value={delinquents.length}
                    sub={blockingCount ? `${blockingCount} con bloqueo` : ""}
                    danger={delinquents.length > 0} href="/panel/reportes/" />
        )}
        {lowStock !== null && (
          <StatCard label="Stock bajo" value={lowStock.length}
                    danger={lowStock.length > 0} href="/panel/inventario/" />
        )}
        {followUps !== null && (
          <StatCard label="Seguimientos pendientes" value={followUps.length}
                    danger={followUps.length > 0} />
        )}
      </div>

      {/* Estanterías, como el «Inicio» de Música: lo de hoy y lo reciente. */}
      <section className="estante">
        <div className="estante-cabecera">
          <h2>Hoy</h2>
          <a href="/panel/agenda/">Ver agenda completa</a>
        </div>
        {appointments === null ? (
          <div className="estante-vacio">Cargando…</div>
        ) : appointments.length === 0 ? (
          <div className="estante-vacio">No hay citas agendadas para hoy.</div>
        ) : (
          <div className="estante-fila">
            {appointments.map((a) => (
              <a key={a.id} className="album" href={`/panel/paciente/?id=${a.patient}`} title={a.patient_name}>
                <div className="cita-hora">
                  <Portada nombre={a.patient_name} texto={<HoraPortada iso={a.scheduled_start} />} />
                  <span className="cita-estado">{a.status_display}</span>
                </div>
                <span className="album-titulo">{a.patient_name}</span>
                <span className="album-sub">{a.doctor_name}</span>
              </a>
            ))}
          </div>
        )}
      </section>

      {recientes !== null && recientes.length > 0 && (
        <section className="estante">
          <div className="estante-cabecera">
            <h2>Pacientes recientes</h2>
            <a href="/panel/pacientes/">Ver todos</a>
          </div>
          <div className="estante-fila">
            {recientes.map((p) => (
              <a key={p.id} className="album" href={`/panel/paciente/?id=${p.id}`} title={p.full_name}>
                <Portada nombre={p.full_name} />
                <span className="album-titulo">{p.full_name}</span>
                <span className="album-sub">Desde el {new Date(p.created_at).toLocaleDateString("es-EC", { day: "numeric", month: "short" })}</span>
              </a>
            ))}
          </div>
        </section>
      )}

      {/* Alertas de stock (si las hay) */}
      {lowStock !== null && lowStock.length > 0 && (
        <div className="card" style={{ padding: 0, marginTop: 18 }}>
          <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--line)",
                        display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <strong style={{ color: "var(--red)" }}>⚠ Productos con stock bajo</strong>
            <a href="/panel/inventario/" style={{ fontSize: 13 }}>Ir a inventario →</a>
          </div>
          <table>
            <thead><tr><th>Producto</th><th>Stock actual</th><th>Mínimo</th></tr></thead>
            <tbody>
              {lowStock.slice(0, 5).map((p) => (
                <tr key={p.product_id}>
                  <td style={{ fontWeight: 600 }}>{p.name}</td>
                  <td className="tabular" style={{ color: "var(--red)", fontWeight: 600 }}>{p.current_stock}</td>
                  <td className="tabular">{p.min_stock}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {followUps !== null && followUps.length > 0 && (
        <div className="card" style={{ padding: 0, marginTop: 18 }}>
          <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--line)", fontWeight: 600, color: "var(--red)" }}>
            🔔 Seguimientos clínicos pendientes
          </div>
          <table>
            <thead><tr><th>Paciente</th><th>Seguimiento para</th><th>Atraso</th><th>Nota</th></tr></thead>
            <tbody>
              {followUps.slice(0, 5).map((f) => (
                <tr key={f.id} onClick={() => window.location.href = `/panel/paciente/?id=${f.patient_id}`}
                    style={{ cursor: "pointer" }}>
                  <td style={{ fontWeight: 600 }}>{f.patient_name}</td>
                  <td className="tabular">{f.follow_up_date}</td>
                  <td className="tabular" style={{ color: f.days_overdue > 0 ? "var(--red)" : "var(--ink)" }}>
                    {f.days_overdue > 0 ? `${f.days_overdue} día${f.days_overdue > 1 ? "s" : ""}` : "hoy"}
                  </td>
                  <td style={{ color: "var(--ink-soft)", fontSize: 13 }}>{f.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/** «06:10 p. m.» en la portada: la hora grande y el «p. m.» debajo. */
function HoraPortada({ iso }) {
  const [hora, ...resto] = fmtTime(iso).split(" ");
  return (
    <span className="portada-hora">
      <b>{hora}</b>
      {resto.length > 0 && <small>{resto.join(" ")}</small>}
    </span>
  );
}

function StatCard({ label, value, sub, href, accent, danger }) {
  return (
    <a href={href} className="card tarjeta-cifra"
       style={{
         flex: 1, minWidth: 150, textDecoration: "none", color: "inherit", padding: "14px 16px",
         display: "flex", flexDirection: "column", gap: 2,
         ...(danger ? { borderColor: "var(--red)", background: "var(--red-soft)" } : {}),
       }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: "var(--ink-soft)", textTransform: "uppercase",
                    letterSpacing: ".05em", lineHeight: 1.3, minHeight: 28 }}>
        {label}
      </div>
      <div className="tabular"
           style={{ fontSize: 28, fontWeight: 700, letterSpacing: "-.02em", lineHeight: 1.15,
                    color: danger ? "var(--red)" : accent ? "var(--petrol)" : "var(--ink)" }}>
        {value}
      </div>
      {sub ? <div style={{ fontSize: 12, color: "var(--ink-soft)" }}>{sub}</div> : null}
    </a>
  );
}
