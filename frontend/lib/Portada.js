/**
 * La «portada» de un paciente, como la carátula de un álbum en Música:
 * un cuadrado con un degradado y sus iniciales.
 *
 * Los colores salen del nombre (siempre los mismos para la misma
 * persona), así se la reconoce de un vistazo en la rejilla sin guardar
 * ninguna foto: las fotos de pacientes son datos de salud y no se
 * publican fuera de la API. En «Sin color» se pinta en grises (ver
 * globals.css, .portada).
 */

function semilla(texto) {
  let h = 0;
  for (const c of String(texto || "")) h = (h * 31 + c.codePointAt(0)) >>> 0;
  return h;
}

export function iniciales(nombre) {
  const partes = String(nombre || "?").replace(/^(dra?\.|dr\.)\s*/i, "").split(/\s+/)
    .map((p) => p.replace(/[^\p{L}\p{N}]/gu, "")).filter(Boolean);
  return ((partes[0]?.[0] || "?") + (partes[1]?.[0] || "")).toUpperCase();
}

export default function Portada({ nombre, tam = "100%", redonda = false, texto }) {
  const h = semilla(nombre);
  const tono = h % 360;
  const giro = 25 + (h >> 9) % 70;
  const fondo = `linear-gradient(${135 + (h % 90)}deg, hsl(${tono} 62% 52%), hsl(${(tono + giro) % 360} 68% 38%))`;
  return (
    <div className={`portada${redonda ? " portada--redonda" : ""}`}
         style={{ width: tam, background: fondo }} aria-hidden="true">
      <span>{texto ?? iniciales(nombre)}</span>
    </div>
  );
}
