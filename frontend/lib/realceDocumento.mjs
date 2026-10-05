/**
 * El tratamiento de imagen del escáner de documentos (lib/DocumentScanner.js).
 * ────────────────────────────────────────────────────────────────────
 * Sin dependencias y sin tocar el DOM: trabaja sobre los píxeles RGBA de
 * un `ImageData` y se prueba con `node --test`.
 *
 * El realce anterior subía el contraste un 25 % a todas las fotos por
 * igual: una foto oscura seguía oscura y una con buena luz quemaba los
 * blancos. Aquí se miran los niveles de CADA foto (percentiles del
 * histograma) y se estiran para que el papel quede blanco y la tinta
 * negra, que es lo que hace legible un consentimiento fotografiado.
 */

/** Los modos que ofrece el escáner, en el orden del selector. */
export const MODOS = [
  { clave: "documento", titulo: "Documento", ayuda: "Grises, papel blanco y tinta negra. El más legible para texto." },
  { clave: "color", titulo: "Color", ayuda: "Niveles ajustados, conserva los colores (sellos, firmas en azul)." },
  { clave: "original", titulo: "Original", ayuda: "La foto tal cual, sin retoques." },
];

/** Lado mayor de la página guardada: legible y sin PDFs de 50 MB. */
export const LADO_MAXIMO = 2200;

/**
 * Tope del PDF antes de subirlo. Nginx corta en 20 MB (nginx.conf) y el
 * servidor rechaza lo que pase de ahí; con margen para el multipart.
 */
export const TOPE_PDF = 18 * 1024 * 1024;

function luminancia(r, g, b) {
  return (r * 299 + g * 587 + b * 114) / 1000;
}

/**
 * Los niveles de negro y blanco de la imagen: los percentiles `bajo` y
 * `alto` de la luminancia. Se muestrea un píxel de cada `paso` porque
 * una foto de 2200 px tiene millones y el histograma sale igual.
 */
export function niveles(data, { bajo = 0.02, alto = 0.96, paso = 4 } = {}) {
  const hist = new Uint32Array(256);
  let total = 0;
  for (let i = 0; i < data.length; i += 4 * paso) {
    hist[Math.round(luminancia(data[i], data[i + 1], data[i + 2]))]++;
    total++;
  }
  if (!total) return { negro: 0, blanco: 255 };
  const buscar = (fraccion) => {
    const objetivo = total * fraccion;
    let acumulado = 0;
    for (let v = 0; v < 256; v++) {
      acumulado += hist[v];
      if (acumulado >= objetivo) return v;
    }
    return 255;
  };
  let negro = buscar(bajo);
  let blanco = buscar(alto);
  // Una página casi uniforme (en blanco, o una foto movida) no se estira:
  // amplificaría el ruido hasta dejar una mancha.
  if (blanco - negro < 24) return { negro: 0, blanco: 255 };
  return { negro, blanco };
}

/**
 * Realza la imagen EN SITIO según el modo. Devuelve los niveles usados
 * (útil para las pruebas).
 */
export function realzar(data, modo = "documento") {
  if (modo === "original") return null;
  const { negro, blanco } = niveles(data);
  const escala = 255 / (blanco - negro);
  const tabla = new Uint8ClampedArray(256);
  for (let v = 0; v < 256; v++) {
    let x = (v - negro) * escala;
    // En modo documento, una curva suave aclara el gris del papel sin
    // comerse los trazos finos de un bolígrafo.
    if (modo === "documento") x = 255 * Math.pow(Math.max(0, Math.min(255, x)) / 255, 0.85);
    tabla[v] = x;
  }
  for (let i = 0; i < data.length; i += 4) {
    if (modo === "documento") {
      const y = tabla[Math.round(luminancia(data[i], data[i + 1], data[i + 2]))];
      data[i] = data[i + 1] = data[i + 2] = y;
    } else {
      data[i] = tabla[data[i]];
      data[i + 1] = tabla[data[i + 1]];
      data[i + 2] = tabla[data[i + 2]];
    }
  }
  return { negro, blanco };
}

/** Medidas para que el lado mayor no pase de `maximo`, sin agrandar. */
export function medidaDestino(ancho, alto, maximo = LADO_MAXIMO) {
  const factor = Math.min(1, maximo / Math.max(ancho, alto));
  return { ancho: Math.round(ancho * factor), alto: Math.round(alto * factor) };
}

/** Orientación de la página del PDF que desperdicia menos papel. */
export function orientacion(ancho, alto) {
  return ancho > alto ? "landscape" : "portrait";
}

/** Bytes que ocupa una imagen guardada como data URL (base64). */
export function bytesDeDataUrl(url) {
  const coma = url.indexOf(",");
  const b64 = url.length - coma - 1;
  const relleno = url.endsWith("==") ? 2 : url.endsWith("=") ? 1 : 0;
  return Math.floor((b64 * 3) / 4) - relleno;
}

/** «1,4 MB», para decirle al usuario cuánto pesa lo que va a subir. */
export function tamanoLegible(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`;
}
