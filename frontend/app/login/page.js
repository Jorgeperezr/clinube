"use client";

import { useCallback, useState } from "react";
import { currentUser, login, loginConGoogle, RUTA_CAMBIO, RUTA_CONDICIONES } from "../../lib/api";
import BotonGoogle from "../../lib/BotonGoogle";
import PantallaAcceso from "../../lib/PantallaAcceso";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const sesion = await login(email, password);
      // Entrar con una contraseña temporal funciona —si no, no habría
      // forma de cambiarla—, pero el panel entero está bloqueado hasta
      // que se elija la propia, así que se va derecho allí en vez de a
      // un escritorio donde todo fallaría.
      //
      // Después, la administración de una clínica que no ha aceptado la
      // versión vigente de las condiciones pasa antes por ellas.
      window.location.href = sesion?.must_change_password ? RUTA_CAMBIO
        : currentUser()?.condiciones_pendientes ? RUTA_CONDICIONES : "/panel/";
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const conGoogle = useCallback(async (credential) => {
    setError(""); setLoading(true);
    try {
      await loginConGoogle(credential);
      window.location.href = currentUser()?.condiciones_pendientes ? RUTA_CONDICIONES : "/panel/";
    } catch (err) { setError(err.message); setLoading(false); }
  }, []);

  return (
    <PantallaAcceso>
      <form onSubmit={handleSubmit}>
        <h2 style={{ marginBottom: 6 }}>Iniciar sesión</h2>
        <p style={{ color: "var(--ink-soft)", marginBottom: 22, fontSize: 14 }}>
          Acceso para el personal de la clínica
        </p>

        {error && <div className="error-box">{error}</div>}

        <div className="field">
          <label htmlFor="email">Correo electrónico</label>
          <input
            id="email" type="email" required autoComplete="username"
            value={email} onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="password">Contraseña</label>
          <input
            id="password" type="password" required autoComplete="current-password"
            value={password} onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        <button className="btn btn-primary" style={{ width: "100%", justifyContent: "center" }} disabled={loading}>
          {loading ? "Entrando…" : "Entrar"}
        </button>
        <BotonGoogle alEntrar={conGoogle} />
        <p style={{ textAlign: "center", marginTop: 16, fontSize: 13.5 }}>
          <a href="/recuperar/">¿Olvidaste tu contraseña?</a>
        </p>
      </form>
    </PantallaAcceso>
  );
}
