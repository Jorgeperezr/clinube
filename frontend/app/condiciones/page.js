"use client";

/**
 * Condiciones de uso y acuerdo de tratamiento de datos.
 *
 * Cualquiera puede leerlas. Si quien entra es la administración de una
 * clínica que todavía no ha aceptado la versión vigente, el panel la
 * trae aquí y no la deja pasar hasta que las acepte: queda constancia de
 * la versión, la fecha y quién lo hizo.
 */

import { useEffect, useState } from "react";

import { api, apiErrorMessage, currentUser, logout } from "../../lib/api";
import TextoLegal, { PaginaLegal, useTextoLegal } from "../../lib/TextoLegal";

export default function CondicionesPage() {
  const { datos, error } = useTextoLegal("condiciones");
  const [usuario, setUsuario] = useState(null);

  useEffect(() => setUsuario(currentUser()), []);
  const pendiente = usuario?.role === "admin" && usuario?.condiciones_pendientes;

  return (
    <PaginaLegal>
      {pendiente && (
        <div className="aviso-legal">
          Antes de seguir, lee y acepta las condiciones en nombre de la clínica. Hay que hacerlo
          una sola vez por cada versión.
        </div>
      )}
      <TextoLegal datos={datos} error={error} />
      {pendiente && datos && <Aceptar version={datos.version} usuario={usuario} />}
    </PaginaLegal>
  );
}

function Aceptar({ version, usuario }) {
  const [leido, setLeido] = useState(false);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  async function aceptar() {
    setOcupado(true); setError("");
    try {
      const resp = await api("/legal/condiciones/aceptar/", {
        method: "POST", body: JSON.stringify({ version }),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp));
      localStorage.setItem("user", JSON.stringify({ ...usuario, condiciones_pendientes: false }));
      window.location.href = "/panel/";
    } catch (err) {
      setError(err.message);
      setOcupado(false);
    }
  }

  return (
    <div className="card legal-aceptar">
      {error && <div className="error-box">{error}</div>}
      <label style={{ display: "flex", gap: 10, alignItems: "flex-start", fontSize: 14, cursor: "pointer" }}>
        <input type="checkbox" checked={leido} onChange={(e) => setLeido(e.target.checked)}
               style={{ marginTop: 3 }} />
        <span>
          He leído las condiciones de uso y el acuerdo de tratamiento de datos (versión {version}) y
          los acepto en nombre de la clínica.
        </span>
      </label>
      <div style={{ display: "flex", gap: 10, marginTop: 14, flexWrap: "wrap" }}>
        <button type="button" className="btn btn-primary" disabled={!leido || ocupado} onClick={aceptar}>
          {ocupado ? "Guardando…" : "Aceptar y entrar"}
        </button>
        <button type="button" className="btn" onClick={logout}>Salir</button>
      </div>
      <p style={{ fontSize: 12.5, color: "var(--ink-soft)", marginTop: 10 }}>
        Se guarda quién acepta ({usuario.email}), la fecha y la versión.
      </p>
    </div>
  );
}
