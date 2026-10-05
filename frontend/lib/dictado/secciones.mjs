/**
 * Ordenar un dictado en las secciones de la nota clínica, SIN IA.
 * ────────────────────────────────────────────────────────────────────
 * El doctor dice la palabra clave de la sección y luego su contenido:
 *
 *     «Motivo… dolor al masticar en el lado derecho»
 *     «Hallazgos… caries oclusal en la 46»
 *     «Diagnóstico… caries de dentina»
 *     «Procedimiento… resina compuesta»
 *     «Indicaciones… no masticar por ese lado durante dos horas»
 *
 * Regla que evita falsos cambios de sección: la palabra clave solo
 * cuenta si ABRE una frase, es decir, si va justo después de una pausa
 * (el reconocedor entrega el dictado por frases). «El motivo de la
 * molestia es…» a mitad de frase se queda donde estaba.
 *
 * Sin dependencias y sin tocar el DOM: se prueba con `node --test`.
 */

export const SECCIONES = [
  { clave: "motivo", titulo: "Motivo", disparadores: ["motivo de consulta", "motivo de la consulta", "motivo"] },
  { clave: "hallazgos", titulo: "Hallazgos", disparadores: ["hallazgos", "hallazgo", "examen clínico", "exploración"] },
  { clave: "diagnostico", titulo: "Diagnóstico", disparadores: ["diagnósticos", "diagnóstico"] },
  { clave: "procedimiento", titulo: "Procedimiento", disparadores: ["procedimientos", "procedimiento", "tratamiento realizado"] },
  { clave: "indicaciones", titulo: "Indicaciones", disparadores: ["indicaciones", "indicación", "recomendaciones"] },
];

/** Minúsculas y sin tildes, para comparar lo que dice el reconocedor. */
export function normalizar(texto) {
  return (texto || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").trim();
}

/*
 * Puntuación dictada. Solo las fórmulas explícitas: «punto» a secas no,
 * porque en odontología es una palabra corriente («punto de contacto»).
 * El orden importa: «punto y coma» antes que «coma».
 */
const PUNTUACION = [
  [/\s*\bpunto y aparte\b\s*/gi, ".\n"],
  [/\s*\bnueva l[ií]nea\b\s*/gi, "\n"],
  [/\s*\bpunto y coma\b\s*/gi, "; "],
  [/\s*\bpunto y seguido\b\s*/gi, ". "],
  [/\s*\bpunto final\b\s*/gi, ". "],
  [/\s*\bdos puntos\b\s*/gi, ": "],
  [/\s*\bcoma\b\s*/gi, ", "],
  [/\s*\babr(?:e|ir) par[eé]ntesis\b\s*/gi, " ("],
  [/\s*\bcierr(?:a|e|ar) par[eé]ntesis\b/gi, ")"],
];

export function aplicarPuntuacion(texto) {
  let t = texto;
  for (const [patron, signo] of PUNTUACION) t = t.replace(patron, signo);
  return t.replace(/[ \t]+/g, " ").replace(/ +\n/g, "\n").replace(/ ([,;:.)])/g, "$1").trim()
    // Mayúscula tras un punto dictado, como se escribiría a mano. Solo
    // con espacio o salto detrás: «www.clinube.com» se queda como está.
    .replace(/(\.\s+|\n\s*)(\p{Ll})/gu, (_, antes, letra) => antes + letra.toUpperCase());
}

/*
 * Piezas dentales. El reconocedor suele entregar «pieza 4 6» o «pieza
 * cuatro seis» en vez de «pieza 46», y la nota tiene que decir la pieza
 * en notación FDI. Solo se juntan dos cifras de 1 a 8 cuando van detrás
 * de una palabra que nombra un diente (o de otra pieza en una lista:
 * «piezas 4 6 y 4 7»), para no tocar «2 3 veces al día».
 */
const CIFRA = { uno: "1", dos: "2", tres: "3", cuatro: "4", cinco: "5", seis: "6", siete: "7", ocho: "8" };
const DIGITO = "([1-8]|uno|dos|tres|cuatro|cinco|seis|siete|ocho)";
const PIEZA = new RegExp(
  `\\b(piezas?|dientes?|molar(?:es)?|premolar(?:es)?|caninos?|incisivos?|[1-8]{2}(?:,| y| e))\\s+${DIGITO}\\s+${DIGITO}\\b`,
  "giu");

export function unirPiezas(texto) {
  let anterior;
  let t = texto;
  // Se repite para encadenar listas: cada vuelta une la pieza siguiente.
  do {
    anterior = t;
    t = t.replace(PIEZA, (_, nombre, a, b) =>
      `${nombre} ${CIFRA[a.toLowerCase()] || a}${CIFRA[b.toLowerCase()] || b}`);
  } while (t !== anterior);
  return t;
}

/** Puntuación y piezas: todo lo que se hace al texto dictado. */
export function pulir(texto) {
  return unirPiezas(aplicarPuntuacion(texto));
}

/**
 * Añade una frase final a la lista. Chrome en Android, con dictado
 * continuo, entrega cada frase final REPITIENDO lo anterior («caries»,
 * luego «caries en la 46»): sin esto la nota saldría duplicada. Si la
 * frase nueva empieza por la última, la sustituye; si es idéntica, se
 * ignora.
 */
export function agregarFrase(lista, frase) {
  const nueva = (frase || "").trim();
  if (!nueva) return lista;
  const ultima = lista[lista.length - 1];
  if (ultima) {
    const a = normalizar(ultima), b = normalizar(nueva);
    if (a === b) return lista;
    if (b.startsWith(`${a} `)) return [...lista.slice(0, -1), nueva];
  }
  return [...lista, nueva];
}

/**
 * ¿La frase empieza por la palabra clave de una sección? Devuelve la
 * sección y el resto de la frase, o null.
 */
export function detectarSeccion(frase) {
  const limpia = normalizar(frase).replace(/^[\s,.:;-]+/, "");
  for (const s of SECCIONES) {
    for (const d of s.disparadores) {
      const n = normalizar(d);
      if (limpia === n || limpia.startsWith(`${n} `) || limpia.startsWith(`${n}:`) || limpia.startsWith(`${n},`)) {
        // Se corta sobre la frase ORIGINAL para conservar mayúsculas y
        // tildes del contenido: se cuentan las palabras del disparador.
        const palabras = n.split(" ").length;
        const resto = frase.trim().replace(/^[\s,.:;-]+/, "").split(/\s+/).slice(palabras).join(" ")
          .replace(/^(dos puntos\s*)/i, "").replace(/^[\s,.:;-]+/, "");
        return { seccion: s.clave, resto };
      }
    }
  }
  return null;
}

/**
 * Reparte las frases dictadas entre las secciones.
 *
 * @param frases   frases en el orden dictado (cada una, tras una pausa)
 * @param inicial  sección en la que se empieza si la primera frase no
 *                 dice ninguna (por defecto, «motivo»)
 * @returns { motivo, hallazgos, diagnostico, procedimiento, indicaciones } en texto
 */
export function organizarDictado(frases, inicial = "motivo") {
  const partes = Object.fromEntries(SECCIONES.map((s) => [s.clave, []]));
  let actual = inicial;
  for (const bruta of frases) {
    const frase = (bruta || "").trim();
    if (!frase) continue;
    const d = detectarSeccion(frase);
    if (d) {
      actual = d.seccion;
      if (d.resto) partes[actual].push(d.resto);
    } else {
      partes[actual].push(frase);
    }
  }
  return Object.fromEntries(Object.entries(partes).map(([k, v]) => [k, capitalizar(pulir(v.join(" ")))]));
}

function capitalizar(t) {
  return t ? t[0].toUpperCase() + t.slice(1) : t;
}

/** Las secciones como texto de la nota: solo las que tienen contenido. */
export function aTextoNota(secciones) {
  return SECCIONES
    .filter((s) => secciones[s.clave])
    .map((s) => `${s.titulo}: ${secciones[s.clave]}`)
    .join("\n");
}
