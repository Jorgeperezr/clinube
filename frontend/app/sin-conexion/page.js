"use client";

/**
 * Lo que enseña la app instalada cuando no hay internet y la página
 * pedida no estaba guardada (ver public/sw.js).
 *
 * No hay modo sin conexión con datos a propósito: los datos de los
 * pacientes no se guardan en el dispositivo.
 */

import PantallaAcceso from "../../lib/PantallaAcceso";

export default function SinConexion() {
  return (
    <PantallaAcceso>
      <div>
        <h2 style={{ marginBottom: 10 }}>Sin conexión</h2>
        <p style={{ color: "var(--ink-soft)", fontSize: 14, marginBottom: 20 }}>
          El panel necesita internet para mostrar la agenda y los pacientes: esos datos no se
          guardan en este dispositivo. Revisa el wifi o los datos móviles y vuelve a intentarlo.
        </p>
        <button type="button" className="btn btn-primary"
                style={{ width: "100%", justifyContent: "center" }}
                onClick={() => window.location.reload()}>
          Reintentar
        </button>
      </div>
    </PantallaAcceso>
  );
}
