"use client";

/**
 * Finanzas de la clínica: lo que entra, lo que sale, la caja del día y
 * lo que se le paga a cada persona del equipo, con los documentos que se
 * usan en Ecuador (liquidación de honorarios con retención y rol de
 * pagos con IESS y décimos).
 *
 * Es una función de la clínica (Plataforma → Funciones) y, dentro de la
 * clínica, de cada persona: ve sueldos y honorarios de todos, así que no
 * la tiene cualquiera. Quien la cierra de verdad es la API.
 */

import { useCallback, useEffect, useState } from "react";

import { api, readList } from "../../../lib/api";
import Ajustes from "../../../lib/finanzas/Ajustes";
import Caja from "../../../lib/finanzas/Caja";
import Cobros from "../../../lib/finanzas/Cobros";
import { mesActual, SelectorMes } from "../../../lib/finanzas/comunes";
import Egresos from "../../../lib/finanzas/Egresos";
import Equipo from "../../../lib/finanzas/Equipo";
import Honorarios from "../../../lib/finanzas/Honorarios";
import Obligaciones from "../../../lib/finanzas/Obligaciones";
import Resumen from "../../../lib/finanzas/Resumen";
import Roles from "../../../lib/finanzas/Roles";

const PESTANAS = [
  ["resumen", "Resumen"],
  ["cobros", "Cobros"],
  ["egresos", "Egresos"],
  ["caja", "Caja"],
  ["equipo", "Equipo"],
  ["honorarios", "Honorarios"],
  ["roles", "Rol de pagos"],
  ["obligaciones", "IESS, SRI y décimos"],
  ["ajustes", "Ajustes"],
];

// La caja va por día y Equipo y Ajustes no dependen del mes.
const SIN_MES = ["caja", "equipo", "ajustes"];

export default function FinanzasPage() {
  const [pestana, setPestana] = useState("resumen");
  const [mes, setMes] = useState(mesActual());
  const [equipo, setEquipo] = useState([]);
  const [categorias, setCategorias] = useState([]);
  const [error, setError] = useState("");

  const cargarCategorias = useCallback(() => {
    api("/finanzas/categorias/").then(readList).then(setCategorias).catch(() => {});
  }, []);

  useEffect(() => {
    // Se recuerda la pestaña de la dirección (#egresos) para volver a ella.
    const desdeUrl = window.location.hash.slice(1);
    if (PESTANAS.some(([k]) => k === desdeUrl)) setPestana(desdeUrl);
    api("/finanzas/equipo/").then(readList).then(setEquipo).catch((e) => setError(e.message));
    cargarCategorias();
  }, [cargarCategorias]);

  function irA(clave) {
    setPestana(clave);
    window.history.replaceState(null, "", `#${clave}`);
  }

  function alCambiarPerfil(perfil) {
    setEquipo((lista) => lista.map((p) => (p.id === perfil.id ? { ...p, ...perfil } : p)));
  }

  return (
    <div>
      <div className="encabezado-pagina">
        <div>
          <h1>Finanzas</h1>
          <p>Ingresos, egresos, caja y pagos al equipo.</p>
        </div>
        {!SIN_MES.includes(pestana) && <SelectorMes mes={mes} alCambiar={setMes} />}
      </div>

      <div className="tabs" role="tablist" style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 20, borderBottom: "1px solid var(--line)" }}>
        {PESTANAS.map(([k, etiqueta]) => (
          <button key={k} type="button" role="tab" aria-selected={pestana === k} onClick={() => irA(k)}
            style={{
              padding: "9px 14px", border: "none", background: "transparent", fontWeight: 600, fontSize: 14,
              color: pestana === k ? "var(--petrol)" : "var(--ink-soft)",
              borderBottom: pestana === k ? "3px solid var(--petrol)" : "3px solid transparent",
            }}>
            {etiqueta}
          </button>
        ))}
      </div>

      {error && <div className="error-box">{error}</div>}

      {pestana === "resumen" && <Resumen mes={mes} irA={irA} />}
      {pestana === "cobros" && <Cobros mes={mes} equipo={equipo} />}
      {pestana === "egresos" && <Egresos mes={mes} equipo={equipo} categorias={categorias} />}
      {pestana === "caja" && <Caja />}
      {pestana === "equipo" && <Equipo equipo={equipo} alCambiar={alCambiarPerfil} />}
      {pestana === "honorarios" && <Honorarios mes={mes} equipo={equipo} irA={irA} />}
      {pestana === "roles" && <Roles mes={mes} equipo={equipo} irA={irA} />}
      {pestana === "obligaciones" && <Obligaciones mes={mes} />}
      {pestana === "ajustes" && <Ajustes categorias={categorias} alCambiarCategorias={cargarCategorias} />}
    </div>
  );
}
