/**
 * Temas del panel: de cuáles se puede elegir y qué colores son.
 *
 * Al pintar (lib/theme.js) manda, por este orden:
 *   1. «Sin color» de cada persona, sobre todo lo demás;
 *   2. el tema que eligió esa persona (función «temas_personales»): uno
 *      de los de su clínica —«clinica:<clave>», generados con su paleta
 *      en el servidor, apps/configuration/temas_clinica.py— o uno de
 *      Clinube —«clinube:<clave>», los PRESETS de theme.js—;
 *   3. el de la clínica, que eligió su administración.
 * El acento personal (lib/acentos.js) cambia, encima, el color de resalte.
 *
 * Aquí no hay nada del navegador, para poder probarlo con node.
 */

export const PREFIJO_CLINICA = "clinica:";
export const PREFIJO_CLINUBE = "clinube:";
export const MAX_COLORES = 6;

/** El tema de una clave elegida, o null (= el de la clínica). */
export function resolverTemaPersonal(clave, { presets = [], temasClinica = [] } = {}) {
  if (typeof clave !== "string" || !clave) return null;
  if (clave.startsWith(PREFIJO_CLINICA)) {
    const buscada = clave.slice(PREFIJO_CLINICA.length);
    const tema = (temasClinica || []).find((t) => t && t.clave === buscada);
    if (!tema || !colorHex(tema.primary)) return null;
    return { key: clave, primary: tema.primary, secondary: tema.secondary, nav: tema.nav };
  }
  if (clave.startsWith(PREFIJO_CLINUBE)) {
    const buscada = clave.slice(PREFIJO_CLINUBE.length);
    const preset = (presets || []).find((p) => p.key === buscada);
    return preset ? { ...preset } : null;
  }
  return null;
}

/**
 * Lo que se puede elegir, agrupado como lo pinta el selector. «Sin
 * color» no está: tiene su propio interruptor en Apariencia.
 *
 *   [{ grupo, titulo, temas: [{ clave, nombre, descripcion, primary, secondary, nav }] }]
 */
export function opcionesDeTema({ presets = [], temasClinica = [] } = {}) {
  const grupos = [];
  const deLaClinica = (temasClinica || [])
    .filter((t) => t && t.clave && colorHex(t.primary))
    .map((t) => ({
      clave: PREFIJO_CLINICA + t.clave, nombre: t.nombre || t.clave,
      descripcion: t.descripcion || "", primary: t.primary, secondary: t.secondary, nav: t.nav,
    }));
  if (deLaClinica.length) grupos.push({ grupo: "clinica", titulo: "De tu clínica", temas: deLaClinica });
  grupos.push({
    grupo: "clinube",
    titulo: "De Clinube",
    temas: (presets || []).filter((p) => p.key !== "sin_color").map((p) => ({
      clave: PREFIJO_CLINUBE + p.key, nombre: p.label, descripcion: "",
      primary: p.primary, secondary: p.secondary, nav: p.nav,
    })),
  });
  return grupos;
}

/** «#ABC», «aabbcc», « #AaBbCc » → «#aabbcc»; lo que no es un color → "". */
export function colorHex(texto) {
  const limpio = String(texto ?? "").trim().replace(/^#/, "");
  if (/^[0-9a-f]{3}$/i.test(limpio)) {
    return "#" + limpio.split("").map((c) => c + c).join("").toLowerCase();
  }
  return /^[0-9a-f]{6}$/i.test(limpio) ? `#${limpio.toLowerCase()}` : "";
}

/**
 * Una paleta pegada («#0e7490, #67E8F9 0b1220») → { colores, malos }.
 *
 * Igual que la del servidor (normalizar_paleta), para avisar mientras se
 * escribe; la que vale es la del servidor.
 */
export function leerPaleta(texto) {
  const colores = [];
  const malos = [];
  for (const trozo of String(texto ?? "").split(/[\s,;]+/).filter(Boolean)) {
    const color = colorHex(trozo);
    if (!color) malos.push(trozo);
    else if (!colores.includes(color)) colores.push(color);
  }
  return { colores, malos };
}
