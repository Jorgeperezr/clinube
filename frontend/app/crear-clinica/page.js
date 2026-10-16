"use client";

/**
 * Crear una clínica (odontología) o dejar una solicitud (medicina y
 * psicología) desde la página pública.
 *
 * Odontología en dos pasos: los datos, y luego el código que llega al
 * correo junto con la contraseña. Sin el código no se crea nada.
 */

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { apiBase } from "../../lib/api";
import { LogoClinube, MARCA } from "../../lib/marca";
import { useUrlApp } from "../../lib/sitio";
import { initColorMode } from "../../lib/theme";

const TIPOS = [
  ["odontologia", "Odontología"],
  ["medicina", "Medicina"],
  ["psicologia", "Psicología"],
];
const VACIO = { clinica: "", ciudad: "", ruc: "", nombre: "", correo: "", telefono: "", mensaje: "", sitio_web: "" };

async function publico(ruta, cuerpo) {
  let resp;
  try {
    resp = await fetch(`${apiBase()}/api/v1/publico/${ruta}`, {
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
  const [paso, setPaso] = useState("datos");          // datos | codigo | creada | enviada
  const [solicitud, setSolicitud] = useState(null);
  const [codigo, setCodigo] = useState("");
  const [clave, setClave] = useState({ una: "", otra: "" });
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const t = params.get("tipo");
    if (TIPOS.some(([k]) => k === t)) setTipo(t);
  }, [params]);

  const odonto = tipo === "odontologia";
  const cambia = (campo) => (e) => setForm({ ...form, [campo]: e.target.value });

  async function enviarDatos(e) {
    e.preventDefault();
    setError(""); setEnviando(true);
    try {
      const r = await publico("solicitudes/", { ...form, tipo, mensaje: odonto ? "" : form.mensaje });
      setSolicitud(r);
      setPaso(odonto ? "codigo" : "enviada");
    } catch (err) { setError(err.message); }
    finally { setEnviando(false); }
  }

  async function confirmar(e) {
    e.preventDefault();
    setError("");
    if (clave.una !== clave.otra) { setError("Las dos contraseñas no coinciden."); return; }
    setEnviando(true);
    try {
      await publico(`solicitudes/${solicitud.id}/confirmar/`, { codigo: codigo.trim(), password: clave.una });
      setPaso("creada");
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
        {paso === "datos" && (
          <form onSubmit={enviarDatos} className="web-caja">
            <h1>{odonto ? "Crea tu clínica" : "Solicita acceso"}</h1>
            <p className="web-suave">
              {odonto
                ? "Te enviaremos un código al correo para confirmar. Después eliges tu contraseña y entras."
                : "Clinube aún no está abierto para esta especialidad. Déjanos tus datos y te escribimos cuando lo esté."}
            </p>

            <div className="web-segmentado" role="radiogroup" aria-label="Servicio">
              {TIPOS.map(([k, t]) => (
                <button key={k} type="button" role="radio" aria-checked={tipo === k} onClick={() => setTipo(k)}>{t}</button>
              ))}
            </div>

            {error && <div className="error-box">{error}</div>}
            <div className="web-campos">
              <Campo etiqueta={odonto ? "Nombre de la clínica" : "Nombre de la clínica o consulta"} completo>
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
                <input type="tel" maxLength={20} value={form.telefono} onChange={cambia("telefono")} autoComplete="tel" />
              </Campo>
              <Campo etiqueta="Correo" completo>
                <input type="email" required value={form.correo} onChange={cambia("correo")} autoComplete="email" />
              </Campo>
              {!odonto && (
                <Campo etiqueta="¿Algo que debamos saber? (opcional)" completo>
                  <textarea rows={3} maxLength={1000} value={form.mensaje} onChange={cambia("mensaje")} />
                </Campo>
              )}
              {/* Para robots: una persona no lo ve. */}
              <input className="web-trampa" tabIndex={-1} autoComplete="off" aria-hidden="true"
                     value={form.sitio_web} onChange={cambia("sitio_web")} />
            </div>
            <button className="web-boton web-boton--ancho" disabled={enviando}>
              {enviando ? "Enviando…" : odonto ? "Enviar código" : "Enviar solicitud"}
            </button>
            {odonto && (
              <p className="web-nota">Al entrar por primera vez te pediremos aceptar las condiciones de uso y el tratamiento de datos.</p>
            )}
          </form>
        )}

        {paso === "codigo" && (
          <form onSubmit={confirmar} className="web-caja">
            <h1>Revisa tu correo</h1>
            <p className="web-suave">
              Enviamos un código de 6 cifras a <strong>{form.correo}</strong>. Vale {solicitud?.minutos || 30} minutos.
              Si no lo ves, mira en «Spam» o «Promociones».
            </p>
            {error && <div className="error-box">{error}</div>}
            <div className="web-campos">
              <Campo etiqueta="Código" completo>
                <input required inputMode="numeric" autoComplete="one-time-code" pattern="\d{6}" maxLength={6}
                       className="web-codigo" value={codigo} onChange={(e) => setCodigo(e.target.value.replace(/\D/g, ""))} />
              </Campo>
              <Campo etiqueta="Elige tu contraseña">
                <input type="password" required minLength={10} autoComplete="new-password"
                       value={clave.una} onChange={(e) => setClave({ ...clave, una: e.target.value })} />
              </Campo>
              <Campo etiqueta="Repítela">
                <input type="password" required minLength={10} autoComplete="new-password"
                       value={clave.otra} onChange={(e) => setClave({ ...clave, otra: e.target.value })} />
              </Campo>
            </div>
            <button className="web-boton web-boton--ancho" disabled={enviando}>
              {enviando ? "Creando…" : "Crear mi clínica"}
            </button>
            <button type="button" className="web-enlace web-volver" onClick={() => { setPaso("datos"); setError(""); }}>
              ← Corregir los datos
            </button>
          </form>
        )}

        {paso === "creada" && (
          <div className="web-caja web-centro">
            <div className="web-ok" aria-hidden="true">✓</div>
            <h1>{form.clinica} ya está lista</h1>
            <p className="web-suave">Entra con <strong>{form.correo}</strong> y tu contraseña. Te enviamos un correo con los primeros pasos.</p>
            <a className="web-boton web-boton--ancho" href={entrar}>Entrar a Clinube</a>
            <a className="web-enlace" href="/descargar/">Instalar la app en este dispositivo →</a>
          </div>
        )}

        {paso === "enviada" && (
          <div className="web-caja web-centro">
            <div className="web-ok" aria-hidden="true">✓</div>
            <h1>Solicitud recibida</h1>
            <p className="web-suave">Te escribiremos a <strong>{form.correo}</strong> en cuanto podamos abrir tu consulta.</p>
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
