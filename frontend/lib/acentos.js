/**
 * Colores de acento que cada persona puede elegir para SU panel
 * (Mis preferencias o el menú de su perfil), como el color de resalte de
 * macOS. "" = el del tema (el de la clínica, o el que haya elegido esa
 * persona), que es lo normal.
 *
 * Cambia el acento —botones, la píldora del menú, enlaces—, no la
 * identidad de la clínica: el logotipo, los documentos y lo que ven los
 * pacientes siguen con sus colores. «Sin color» manda sobre esto.
 *
 * El servidor solo comprueba la forma de la clave
 * (apps/accounts/preferencias.py): una que no esté aquí se ignora y se
 * pinta con el color de la clínica.
 */

export const ACENTOS = [
  { clave: "", nombre: "Del tema", color: null },
  { clave: "default", nombre: "Clinube", color: "#0e7490" },
  { clave: "oceano", nombre: "Océano", color: "#0f4c81" },
  { clave: "violeta", nombre: "Violeta", color: "#6d28d9" },
  { clave: "rosa", nombre: "Rosa", color: "#be185d" },
  { clave: "rojo", nombre: "Rojo", color: "#d70f3a" },
  { clave: "naranja", nombre: "Naranja", color: "#c2410c" },
  { clave: "arena", nombre: "Arena", color: "#8a5a2b" },
  { clave: "bosque", nombre: "Bosque", color: "#1d6b3c" },
  { clave: "grafito", nombre: "Grafito", color: "#374151" },
];

const CLAVE_LOCAL = "acentoPersonal";

/** El color del acento guardado en este navegador, o null (el de la clínica). */
export function leerAcento() {
  try {
    const clave = localStorage.getItem(CLAVE_LOCAL) || "";
    return ACENTOS.find((a) => a.clave === clave)?.color || null;
  } catch {
    return null;
  }
}

/** Guarda la clave en este navegador (la copia buena está en la cuenta). */
export function recordarAcento(clave) {
  try {
    if (clave) localStorage.setItem(CLAVE_LOCAL, clave);
    else localStorage.removeItem(CLAVE_LOCAL);
  } catch { /* modo privado: vale para esta visita */ }
}
