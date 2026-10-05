"use client";

/**
 * La barra flotante de la próxima cita: el «reproductor» del panel.
 *
 * Como la barra de Música, está siempre a mano y dice qué viene ahora:
 * la próxima cita de hoy —de quien tiene la sesión si es doctor; de toda
 * la clínica para administración y recepción—, cuánto falta, y atajos a
 * la ficha y a la agenda. Se refresca cada minuto y se puede cerrar;
 * vuelve sola cuando cambia la cita.
 *
 * Si no queda ninguna cita hoy, no ocupa sitio.
 */

import { useEffect, useState } from "react";

import { api, readList } from "./api";

const FINALES = ["cancelled", "completed", "no_show"];

function hoyISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function cuanto(inicio, ahora) {
  const min = Math.round((new Date(inicio) - ahora) / 60000);
  if (min <= 0) return "ahora";
  if (min < 60) return `en ${min} min`;
  const h = Math.floor(min / 60);
  return `en ${h} h${min % 60 ? ` ${min % 60} min` : ""}`;
}

export default function ProximaCita() {
  const [cita, setCita] = useState(null);
  const [ahora, setAhora] = useState(() => new Date());
  const [cerrada, setCerrada] = useState(null);

  useEffect(() => {
    try { setCerrada(sessionStorage.getItem("proximaCitaCerrada")); } catch { /* sin storage */ }
    let vivo = true;
    const pedir = () => api(`/agenda/view/?mode=daily&date=${hoyISO()}`)
      .then(readList)
      .then((lista) => {
        if (!vivo) return;
        const t = new Date();
        setAhora(t);
        // La que está en curso (empezó hace menos de 15 min) o la siguiente.
        setCita(lista.find((c) => !FINALES.includes(c.status)
          && new Date(c.scheduled_start) > new Date(t - 15 * 60000)) || null);
      })
      .catch(() => {});
    pedir();
    const cada = setInterval(pedir, 60000);
    return () => { vivo = false; clearInterval(cada); };
  }, []);

  useEffect(() => {
    document.body.classList.toggle("con-proxima-cita", Boolean(cita && cerrada !== cita.id));
    return () => document.body.classList.remove("con-proxima-cita");
  }, [cita, cerrada]);

  if (!cita || cerrada === cita.id) return null;

  const hora = new Date(cita.scheduled_start).toLocaleTimeString("es-EC", { hour: "2-digit", minute: "2-digit" });
  return (
    <div className="proxima-cita" role="status" aria-label="Próxima cita">
      <div className="proxima-hora">
        <strong>{hora}</strong>
        <span>{cuanto(cita.scheduled_start, ahora)}</span>
      </div>
      <div className="proxima-quien">
        <strong>{cita.patient_name}</strong>
        <span>{[cita.doctor_name, cita.status_display].filter(Boolean).join(" · ")}</span>
      </div>
      <div className="proxima-acciones">
        <a href={`/panel/paciente/?id=${cita.patient}`} className="proxima-boton">Ficha</a>
        <a href="/panel/agenda/" className="proxima-boton proxima-boton--suave">Agenda</a>
        <button type="button" className="proxima-cerrar" aria-label="Ocultar hasta la siguiente cita"
                title="Ocultar hasta la siguiente cita"
                onClick={() => {
                  setCerrada(cita.id);
                  try { sessionStorage.setItem("proximaCitaCerrada", cita.id); } catch { /* sin storage */ }
                }}>
          ×
        </button>
      </div>
    </div>
  );
}
