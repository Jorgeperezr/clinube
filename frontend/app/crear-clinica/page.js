"use client";

/**
 * Solicitar una cuenta desde la página pública: odontología, medicina o
 * psicología, como consultorio de una persona o clínica con equipo.
 *
 * Desde aquí no se crea nada. La solicitud llega a Plataforma →
 * Solicitudes y, si se aprueba, la persona recibe en su correo un enlace
 * para elegir su contraseña. Odontología se responde a la brevedad;
 * medicina y psicología, en un plazo de hasta 12 horas (lo dice la API).
 */

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { apiBase } from "../../lib/api";
import CampoTelefono from "../../lib/CampoTelefono";
import { LogoClinube, MARCA } from "../../lib/marca";
import { useUrlApp } from "../../lib/sitio";
import { initColorMode } from "../../lib/theme";

const TIPOS = [
  ["odontologia", "Odontología"],
  ["medicina", "Medicina"],
  ["psicologia", "Psicología"],
];
// Lo mismo que SolicitudClinica.PLAZO_HORAS; la respuesta de la API manda.
const PLAZO_HORAS = { medicina: 12, psicologia: 12 };
const MODALIDADES = [
  ["consultorio", "Solo yo", "Atiendo a mis pacientes y llevo todo con mi cuenta."],
  ["clinica", "Clínica con equipo", "Hay recepción u otros profesionales."],
];
const VACIO = { modalidad: "consultorio", clinica: "", ciudad: "", ruc: "", nombre: "", correo: "", telefono: "", mensaje: "", sitio_web: "" };

function textoPlazo(horas) {
  return horas ? `Respuesta en un plazo de hasta ${horas} horas` : "Respuesta a la brevedad";
}

async function enviarSolicitud(cuerpo) {
  let resp;
  try {
    resp = await fetch(`${apiBase()}/api/v1/publico/solicitudes/`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo),
    });
  } catch {
    throw new Error("Sin conexión. Revisa el internet y vuelve a intentarlo.");
  }
  const datos = await resp.json().catch(() => ({}));
  if (resp.status === 429) throw new Error("Demasiados intentos seguidos. Espera un momento y vuelve a intentarlo.");
  if (!resp.ok) {
    const det = datos?.error?.details;
    const primero = det && typeof det === "object" ? Object.values(det).flat()[0] : null;
    throw new Error(primero || datos?.detail || datos?.error?.message || "No se pudo enviar. Inténtalo de nuevo.");
  }
  return datos;
}

export default function CrearClinicaPage() {
  return <Suspense fallback={null}><CrearClinica /></Suspense>;
}

function CrearClinica() {
  useEffect(() => initColorMode(), []);
  const params = useSearchParams();
  const entrar = useUrlApp("/login/");
  const [tipo, setTipo] = useState("odontologia");
  const [form, setForm] = useState(VACIO);
  const [enviada, setEnviada] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const t = params.get("tipo");
    if (TIPOS.some(([k]) => k === t)) setTipo(t);
    const m = params.get("modalidad");
    if (MODALIDADES.some(([k]) => k === m)) setForm((f) => ({ ...f, modalidad: m }));
  }, [params]);

  const solo = form.modalidad === "consultorio";
  const servicio = TIPOS.find(([k]) => k === tipo)?.[1].toLowerCase();
  const cambia = (campo) => (e) => setForm({ ...form, [campo]: e.target.value });

  async function enviar(e) {
    e.preventDefault();
    setError(""); setEnviando(true);
    try {
      const r = await enviarSolicitud({ ...form, tipo });
      setEnviada({ plazo: r.plazo_horas ?? PLAZO_HORAS[tipo] ?? null });
    } catch (err) { setError(err.message); }
    finally { setEnviando(false); }
  }

  return (
    <div className="web">
      <header className="web-barra">
        <a href="/" aria-label={MARCA} className="web-marca"><LogoClinube alto={24} /></a>
        <span />
        <a className="web-boton web-boton--chico web-boton--claro" href={entrar}>Entrar</a>
      </header>

      <main className="web-formulario">
        {!enviada && (
          <form onSubmit={enviar} className="web-caja">
            <h1>{solo ? "Solicita tu consultorio" : "Solicita tu clínica"}</h1>
            <p className="web-suave">
              Revisamos cada solicitud antes de abrir la cuenta. Cuando la aprobemos, te llegará un correo con
              el enlace para elegir tu contraseña.
            </p>

            <div className="web-segmentado" role="radiogroup" aria-label="Especialidad">
              {TIPOS.map(([k, t]) => (
                <button key={k} type="button" role="radio" aria-checked={tipo === k} onClick={() => setTipo(k)}>{t}</button>
              ))}
            </div>
            <span className="web-plazo">{textoPlazo(PLAZO_HORAS[tipo])}</span>

            <div className="web-segmentado web-segmentado--dos" role="radiogroup" aria-label="Quién va a usarlo">
              {MODALIDADES.map(([k, t, ayuda]) => (
                <button key={k} type="button" role="radio" aria-checked={form.modalidad === k} title={ayuda}
                        onClick={() => setForm({ ...form, modalidad: k })}>{t}</button>
              ))}
            </div>
            <p className="web-nota" style={{ marginTop: -4 }}>
              {MODALIDADES.find(([k]) => k === form.modalidad)?.[2]}
              {solo && " Si más adelante sumas a alguien, lo das de alta sin cambiar de cuenta."}
            </p>

            {error && <div className="error-box">{error}</div>}
            <div className="web-campos">
              <Campo etiqueta={solo ? "Nombre del consultorio" : "Nombre de la clínica"} completo>
                <input required minLength={3} maxLength={150} value={form.clinica} onChange={cambia("clinica")} autoComplete="organization" />
              </Campo>
              <Campo etiqueta="Ciudad">
                <input required maxLength={80} value={form.ciudad} onChange={cambia("ciudad")} autoComplete="address-level2" />
              </Campo>
              <Campo etiqueta="RUC (opcional)">
                <input inputMode="numeric" maxLength={13} value={form.ruc} onChange={cambia("ruc")} />
              </Campo>
              <Campo etiqueta="Tu nombre">
                <input required maxLength={150} value={form.nombre} onChange={cambia("nombre")} autoComplete="name" />
              </Campo>
              <Campo etiqueta="Teléfono">
                <CampoTelefono valor={form.telefono} alCambiar={(v) => setForm({ ...form, telefono: v })} />
              </Campo>
              <Campo etiqueta="Correo" completo>
                <input type="email" required value={form.correo} onChange={cambia("correo")} autoComplete="email" />
              </Campo>
              <Campo etiqueta="¿Algo que debamos saber? (opcional)" completo>
                <textarea rows={3} maxLength={1000} value={form.mensaje} onChange={cambia("mensaje")}
                          placeholder={tipo === "odontologia" ? "Cuántos profesionales son, si vienen de otro sistema…"
                            : "Qué tipo de consulta llevas y cuántos profesionales son…"} />
              </Campo>
              {/* Para robots: una persona no lo ve. */}
              <input className="web-trampa" tabIndex={-1} autoComplete="off" aria-hidden="true"
                     value={form.sitio_web} onChange={cambia("sitio_web")} />
            </div>
            <button className="web-boton web-boton--ancho" disabled={enviando}>
              {enviando ? "Enviando…" : "Enviar solicitud"}
            </button>
            <p className="web-nota">Al entrar por primera vez te pediremos aceptar las condiciones de uso y el tratamiento de datos.</p>
          </form>
        )}

        {enviada && (
          <div className="web-caja web-centro">
            <div className="web-ok" aria-hidden="true">✓</div>
            <h1>Solicitud recibida</h1>
            <p className="web-suave">
              Anotamos <strong>{form.clinica}</strong> para {servicio}. Te escribiremos a <strong>{form.correo}</strong>.
            </p>
            <span className="web-plazo">{textoPlazo(enviada.plazo)}</span>
            <ol className="web-pasos">
              <li className="web-paso--hecho"><strong>Enviaste la solicitud</strong>Te mandamos una copia al correo.</li>
              <li><strong>La revisamos</strong>Comprobamos los datos de {solo ? "tu consultorio" : "tu clínica"} antes de abrir la cuenta.</li>
              <li><strong>Eliges tu contraseña</strong>Si la aprobamos, te llega un enlace al correo. Con él entras por primera vez.</li>
            </ol>
            <p className="web-nota">Si no ves nuestro correo, mira en «Spam» o «Promociones».</p>
            <a className="web-boton web-boton--claro web-boton--ancho" href="/">Volver al inicio</a>
          </div>
        )}
      </main>
    </div>
  );
}

function Campo({ etiqueta, completo, children }) {
  return (
    <label className={`field web-campo${completo ? " web-campo--completo" : ""}`}>
      <span>{etiqueta}</span>
      {children}
    </label>
  );
}
