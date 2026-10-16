"use client";

/**
 * Recuperar el acceso del personal.
 *
 * Dos pasos en la misma dirección:
 *   - sin `?token=`: se pide el correo y el servidor manda un enlace;
 *   - con `?token=` (el enlace del correo): se elige la contraseña nueva.
 *
 * La respuesta al pedir el enlace es la misma exista o no el correo: así
 * nadie puede averiguar desde aquí quién trabaja en una clínica.
 */

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";

import { apiBase, apiErrorMessage, sinRed } from "../../lib/api";
import PantallaAcceso from "../../lib/PantallaAcceso";

async function enviar(paso, cuerpo) {
  const resp = await sinRed(() => fetch(`${apiBase()}/api/v1/auth/recovery/${paso}/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cuerpo),
  }));
  if (!resp.ok) throw new Error(await apiErrorMessage(resp));
}

export default function RecuperarPage() {
  return (
    <Suspense fallback={<div className="empty">Cargando…</div>}>
      <Recuperar />
    </Suspense>
  );
}

function Recuperar() {
  const params = useSearchParams();
  const token = params.get("token");
  return (
    <PantallaAcceso>
      {token ? <ElegirContrasena token={token} bienvenida={params.get("bienvenida") === "1"} /> : <PedirEnlace />}
    </PantallaAcceso>
  );
}

const anchoCompleto = { width: "100%", justifyContent: "center" };

function PedirEnlace() {
  const [email, setEmail] = useState("");
  const [enviado, setEnviado] = useState(false);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  async function pedir(e) {
    e.preventDefault();
    setError("");
    setOcupado(true);
    try {
      await enviar("request", { email });
      setEnviado(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setOcupado(false);
    }
  }

  if (enviado) {
    return (
      <div>
        <h2 style={{ marginBottom: 10 }}>Revisa tu correo</h2>
        <p style={{ color: "var(--ink-soft)", fontSize: 14, marginBottom: 20 }}>
          Si <strong>{email}</strong> tiene una cuenta, te llegará un enlace para elegir una
          contraseña nueva. Es válido durante 30 minutos. Si no lo ves, mira en la carpeta de correo no deseado.
        </p>
        <a className="btn" href="/login/" style={anchoCompleto}>Volver a iniciar sesión</a>
      </div>
    );
  }

  return (
    <form onSubmit={pedir}>
      <h2 style={{ marginBottom: 6 }}>Recuperar el acceso</h2>
      <p style={{ color: "var(--ink-soft)", marginBottom: 22, fontSize: 14 }}>
        Escribe el correo con el que entras y te enviaremos un enlace para elegir una contraseña nueva.
      </p>
      {error && <div className="error-box">{error}</div>}
      <div className="field">
        <label htmlFor="email">Correo electrónico</label>
        <input id="email" type="email" required autoComplete="username" autoFocus
               value={email} onChange={(e) => setEmail(e.target.value)} />
      </div>
      <button className="btn btn-primary" style={anchoCompleto} disabled={ocupado}>
        {ocupado ? "Enviando…" : "Enviar enlace"}
      </button>
      <p style={{ textAlign: "center", marginTop: 16, fontSize: 13.5 }}>
        <a href="/login/">Volver a iniciar sesión</a>
      </p>
    </form>
  );
}

function ElegirContrasena({ token, bienvenida }) {
  const [nueva, setNueva] = useState("");
  const [repetida, setRepetida] = useState("");
  const [listo, setListo] = useState(false);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  async function guardar(e) {
    e.preventDefault();
    setError("");
    if (nueva !== repetida) {
      setError("Las dos contraseñas no coinciden.");
      return;
    }
    setOcupado(true);
    try {
      await enviar("confirm", { token, new_password: nueva });
      setListo(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setOcupado(false);
    }
  }

  if (listo) {
    return (
      <div>
        <h2 style={{ marginBottom: 10 }}>{bienvenida ? "Todo listo" : "Contraseña actualizada"}</h2>
        <p style={{ color: "var(--ink-soft)", fontSize: 14, marginBottom: 20 }}>
          {bienvenida ? "Ya puedes entrar con tu correo y tu contraseña." : "Ya puedes entrar con tu contraseña nueva."}
        </p>
        <a className="btn btn-primary" href="/login/" style={anchoCompleto}>Iniciar sesión</a>
      </div>
    );
  }

  return (
    <form onSubmit={guardar}>
      <h2 style={{ marginBottom: 6 }}>{bienvenida ? "Bienvenido: elige tu contraseña" : "Elige una contraseña nueva"}</h2>
      <p style={{ color: "var(--ink-soft)", marginBottom: 20, fontSize: 14 }}>
        Al menos 10 caracteres. Evita contraseñas comunes o el nombre de la clínica.
      </p>
      {error && <div className="error-box">{error}</div>}
      <div className="field">
        <label htmlFor="nueva">Contraseña nueva</label>
        <input id="nueva" type="password" required minLength={10} autoComplete="new-password" autoFocus
               value={nueva} onChange={(e) => setNueva(e.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="repetida">Repítela</label>
        <input id="repetida" type="password" required autoComplete="new-password"
               value={repetida} onChange={(e) => setRepetida(e.target.value)} />
      </div>
      <button className="btn btn-primary" style={anchoCompleto} disabled={ocupado}>
        {ocupado ? "Guardando…" : "Guardar contraseña"}
      </button>
      <p style={{ textAlign: "center", marginTop: 16, fontSize: 13.5 }}>
        {bienvenida ? <a href="/login/">Prefiero entrar con Google</a> : <a href="/recuperar/">Pedir otro enlace</a>}
      </p>
    </form>
  );
}
