"use client";

/**
 * Marco de las pantallas sin sesión: iniciar sesión, recuperar el acceso
 * y elegir contraseña. Las tres repetían el mismo bloque con la marca;
 * aquí está una sola vez, y en el teléfono la marca pasa a una franja
 * arriba en vez de quedarse con el 42 % del ancho (ver globals.css).
 */

import { useEffect } from "react";

import { LEMA, LogoClinube } from "./marca";
import { initColorMode } from "./theme";

export default function PantallaAcceso({ children }) {
  // Todavía no hay clínica: paleta de Clinube, con el modo y el «Sin
  // color» que la persona tenga elegidos en este navegador.
  useEffect(() => initColorMode(), []);

  return (
    <div className="acceso">
      <div className="acceso-marca">
        <div>
          <h1 style={{ margin: 0 }}>
            <LogoClinube alto={58} tinta="#ffffff" acento="var(--mint)" />
          </h1>
          <p>{LEMA}</p>
        </div>
      </div>
      <div className="acceso-form">
        <div>
          {children}
          <p className="acceso-legal">
            <a href="/descargar/">Descargar las apps</a> · <a href="/privacidad/">Aviso de privacidad</a> ·{" "}
            <a href="/condiciones/">Condiciones de uso</a>
          </p>
        </div>
      </div>
    </div>
  );
}
