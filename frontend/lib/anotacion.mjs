/**
 * Geometría y dibujo de las marcas sobre una foto (lib/AnotadorFoto.js).
 * ────────────────────────────────────────────────────────────────────
 * Sin dependencias y sin DOM: el dibujo recibe un contexto 2D, así que
 * se prueba con `node --test` usando uno falso que anota las llamadas.
 *
 * Todas las marcas se guardan en COORDENADAS DE LA IMAGEN (píxeles de la
 * foto), no de la pantalla. Así no se mueven al ampliar o desplazar, y al
 * exportar se dibujan tal cual sobre la foto a su resolución completa.
 * La vista —cuánto se amplía y dónde— es solo una transformación:
 *
 *     pantalla = imagen × escala + desplazamiento
 */

export const HERRAMIENTAS = [
  { clave: "lapiz", titulo: "Lápiz", tecla: "p" },
  { clave: "flecha", titulo: "Flecha", tecla: "f" },
  { clave: "linea", titulo: "Línea", tecla: "l" },
  { clave: "rect", titulo: "Rectángulo", tecla: "r" },
  { clave: "elipse", titulo: "Círculo", tecla: "c" },
  { clave: "texto", titulo: "Texto", tecla: "t" },
  { clave: "borrador", titulo: "Borrador", tecla: "e" },
  { clave: "mover", titulo: "Mover", tecla: "v" },
];

/** Colores fijos: vivos, para que se distingan sobre encía, diente y radiografía. */
export const COLORES = ["#ef4444", "#f59e0b", "#facc15", "#22c55e", "#06b6d4", "#3b82f6", "#a855f7", "#ffffff", "#111827"];

export const ESCALA_MIN = 0.05;
export const ESCALA_MAX = 16;

/**
 * La unidad de grosor: una milésima del lado mayor de la foto. Un grosor
 * «6» se ve igual en una foto del teléfono (4000 px) que en una
 * radiografía pequeña (800 px).
 */
export function unidad(ancho, alto) {
  return Math.max(ancho, alto) / 1000;
}

// ── Vista ───────────────────────────────────────────────────────────

/** La vista que encaja la imagen entera en el lienzo, centrada. */
export function encuadrar(imgAncho, imgAlto, lienzoAncho, lienzoAlto, margen = 16) {
  const escala = Math.min((lienzoAncho - 2 * margen) / imgAncho, (lienzoAlto - 2 * margen) / imgAlto);
  const e = Math.max(ESCALA_MIN, Math.min(ESCALA_MAX, escala));
  return { escala: e, dx: (lienzoAncho - imgAncho * e) / 2, dy: (lienzoAlto - imgAlto * e) / 2 };
}

export function aImagen([x, y], { escala, dx, dy }) {
  return [(x - dx) / escala, (y - dy) / escala];
}

export function aPantalla([x, y], { escala, dx, dy }) {
  return [x * escala + dx, y * escala + dy];
}

/** Amplía o reduce dejando quieto el punto de la pantalla `[px, py]`. */
export function zoomEn(vista, factor, [px, py]) {
  const escala = Math.max(ESCALA_MIN, Math.min(ESCALA_MAX, vista.escala * factor));
  const real = escala / vista.escala;
  return { escala, dx: px - (px - vista.dx) * real, dy: py - (py - vista.dy) * real };
}

// ── Entrada ─────────────────────────────────────────────────────────

/**
 * Ancho de un tramo según la presión del lápiz. Sin lápiz el navegador
 * da 0,5 fijo (ratón) o 0 (algunos táctiles): ahí no se varía.
 */
export function anchoConPresion(base, presion) {
  if (!(presion > 0) || presion === 0.5) return base;
  return base * (0.35 + 1.3 * Math.min(1, presion));
}

/**
 * Añade un punto al trazo descartando los que están a menos de `minimo`
 * del anterior: el ratón y el lápiz mandan cientos por segundo y los
 * casi repetidos solo dejan el trazo dentado.
 */
export function agregarPunto(puntos, punto, minimo) {
  const u = puntos[puntos.length - 1];
  if (u && Math.hypot(punto[0] - u[0], punto[1] - u[1]) < minimo) return puntos;
  return [...puntos, punto];
}

/** Con Mayús, la línea va en múltiplos de 15° (horizontal, vertical, 45°…). */
export function restringirAngulo([x0, y0], [x1, y1]) {
  const ang = Math.atan2(y1 - y0, x1 - x0);
  const paso = Math.PI / 12;
  const a = Math.round(ang / paso) * paso;
  const largo = Math.hypot(x1 - x0, y1 - y0);
  return [x0 + Math.cos(a) * largo, y0 + Math.sin(a) * largo];
}

/** Con Mayús, el rectángulo es un cuadrado y la elipse un círculo. */
export function restringirCuadrado([x0, y0], [x1, y1]) {
  const lado = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0));
  return [x0 + Math.sign(x1 - x0 || 1) * lado, y0 + Math.sign(y1 - y0 || 1) * lado];
}

// ── Selección y borrado ─────────────────────────────────────────────

export function distanciaASegmento([px, py], [ax, ay], [bx, by]) {
  const vx = bx - ax, vy = by - ay;
  const largo2 = vx * vx + vy * vy;
  const t = largo2 ? Math.max(0, Math.min(1, ((px - ax) * vx + (py - ay) * vy) / largo2)) : 0;
  return Math.hypot(px - (ax + t * vx), py - (ay + t * vy));
}

/** Caja del texto, aproximada sin medir con el navegador. */
export function cajaTexto(o) {
  const lineas = String(o.texto).split("\n");
  const ancho = Math.max(...lineas.map((l) => l.length)) * o.tamano * 0.58;
  return { x: o.x, y: o.y, ancho, alto: lineas.length * o.tamano * 1.25 };
}

/** ¿El punto (en coordenadas de imagen) toca la marca? */
export function toca(o, p, tolerancia) {
  const t = tolerancia + (o.ancho || 0) / 2;
  switch (o.tipo) {
    case "trazo":
      if (o.puntos.length === 1) return Math.hypot(p[0] - o.puntos[0][0], p[1] - o.puntos[0][1]) <= t;
      for (let i = 1; i < o.puntos.length; i++) {
        if (distanciaASegmento(p, o.puntos[i - 1], o.puntos[i]) <= t) return true;
      }
      return false;
    case "linea":
    case "flecha":
      return distanciaASegmento(p, o.a, o.b) <= t;
    case "rect": {
      const [x0, y0] = o.a, [x1, y1] = o.b;
      const esquinas = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
      return esquinas.some((e, i) => distanciaASegmento(p, e, esquinas[(i + 1) % 4]) <= t);
    }
    case "elipse": {
      const cx = (o.a[0] + o.b[0]) / 2, cy = (o.a[1] + o.b[1]) / 2;
      const rx = Math.abs(o.b[0] - o.a[0]) / 2, ry = Math.abs(o.b[1] - o.a[1]) / 2;
      if (rx < 1 || ry < 1) return Math.hypot(p[0] - cx, p[1] - cy) <= t + Math.max(rx, ry);
      // Distancia aproximada al contorno: radio normalizado.
      const r = Math.hypot((p[0] - cx) / rx, (p[1] - cy) / ry);
      return Math.abs(r - 1) * Math.min(rx, ry) <= t;
    }
    case "texto": {
      const c = cajaTexto(o);
      return p[0] >= c.x - t && p[0] <= c.x + c.ancho + t && p[1] >= c.y - t && p[1] <= c.y + c.alto + t;
    }
    default:
      return false;
  }
}

/** Índice de la marca de más arriba que toca el punto, o -1. */
export function marcaEn(objetos, p, tolerancia) {
  for (let i = objetos.length - 1; i >= 0; i--) if (toca(objetos[i], p, tolerancia)) return i;
  return -1;
}

/** La marca desplazada `[dx, dy]`. */
export function desplazar(o, [dx, dy]) {
  const m = ([x, y, ...resto]) => [x + dx, y + dy, ...resto];
  if (o.tipo === "trazo") return { ...o, puntos: o.puntos.map(m) };
  if (o.tipo === "texto") return { ...o, x: o.x + dx, y: o.y + dy };
  return { ...o, a: m(o.a), b: m(o.b) };
}

// ── Historial ───────────────────────────────────────────────────────

/** Deshacer/rehacer guardando la lista entera: las marcas pesan poco. */
export const historialVacio = { pasado: [], presente: [], futuro: [] };

export function confirmar(h, presente) {
  if (presente === h.presente) return h;
  return { pasado: [...h.pasado, h.presente].slice(-100), presente, futuro: [] };
}

export function deshacer(h) {
  if (!h.pasado.length) return h;
  return { pasado: h.pasado.slice(0, -1), presente: h.pasado[h.pasado.length - 1], futuro: [h.presente, ...h.futuro] };
}

export function rehacer(h) {
  if (!h.futuro.length) return h;
  return { pasado: [...h.pasado, h.presente], presente: h.futuro[0], futuro: h.futuro.slice(1) };
}

// ── Dibujo ──────────────────────────────────────────────────────────

/** Punta de flecha: los dos extremos de las aletas. */
export function aletasFlecha([x0, y0], [x1, y1], ancho) {
  const ang = Math.atan2(y1 - y0, x1 - x0);
  const largo = Math.min(Math.max(ancho * 4.5, 10), Math.hypot(x1 - x0, y1 - y0) * 0.6);
  const abre = Math.PI / 7;
  return [
    [x1 - largo * Math.cos(ang - abre), y1 - largo * Math.sin(ang - abre)],
    [x1 - largo * Math.cos(ang + abre), y1 - largo * Math.sin(ang + abre)],
  ];
}

function trazoSuave(ctx, puntos) {
  // Curvas por los puntos medios: el trazo sale redondo aunque el
  // dispositivo mande los puntos a saltos.
  ctx.beginPath();
  ctx.moveTo(puntos[0][0], puntos[0][1]);
  for (let i = 1; i < puntos.length - 1; i++) {
    const mx = (puntos[i][0] + puntos[i + 1][0]) / 2, my = (puntos[i][1] + puntos[i + 1][1]) / 2;
    ctx.quadraticCurveTo(puntos[i][0], puntos[i][1], mx, my);
  }
  const u = puntos[puntos.length - 1];
  ctx.lineTo(u[0], u[1]);
  ctx.stroke();
}

/** Dibuja una marca en `ctx`, que ya trae la transformación de la vista. */
export function dibujarMarca(ctx, o) {
  ctx.save();
  ctx.strokeStyle = o.color;
  ctx.fillStyle = o.color;
  ctx.lineWidth = o.ancho;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  switch (o.tipo) {
    case "trazo": {
      const p = o.puntos;
      if (p.length === 1) {
        ctx.beginPath();
        ctx.arc(p[0][0], p[0][1], anchoConPresion(o.ancho, p[0][2]) / 2, 0, Math.PI * 2);
        ctx.fill();
      } else if (o.presion) {
        // Con presión, cada tramo lleva su ancho.
        for (let i = 1; i < p.length; i++) {
          ctx.lineWidth = anchoConPresion(o.ancho, (p[i - 1][2] + p[i][2]) / 2);
          ctx.beginPath();
          ctx.moveTo(p[i - 1][0], p[i - 1][1]);
          ctx.lineTo(p[i][0], p[i][1]);
          ctx.stroke();
        }
      } else {
        trazoSuave(ctx, p);
      }
      break;
    }
    case "linea":
    case "flecha": {
      ctx.beginPath();
      ctx.moveTo(o.a[0], o.a[1]);
      ctx.lineTo(o.b[0], o.b[1]);
      ctx.stroke();
      if (o.tipo === "flecha") {
        const [i, d] = aletasFlecha(o.a, o.b, o.ancho);
        ctx.beginPath();
        ctx.moveTo(o.b[0], o.b[1]);
        ctx.lineTo(i[0], i[1]);
        ctx.lineTo(d[0], d[1]);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      }
      break;
    }
    case "rect":
      ctx.strokeRect(Math.min(o.a[0], o.b[0]), Math.min(o.a[1], o.b[1]),
        Math.abs(o.b[0] - o.a[0]), Math.abs(o.b[1] - o.a[1]));
      break;
    case "elipse":
      ctx.beginPath();
      ctx.ellipse((o.a[0] + o.b[0]) / 2, (o.a[1] + o.b[1]) / 2,
        Math.abs(o.b[0] - o.a[0]) / 2, Math.abs(o.b[1] - o.a[1]) / 2, 0, 0, Math.PI * 2);
      ctx.stroke();
      break;
    case "texto": {
      ctx.font = `600 ${o.tamano}px system-ui, -apple-system, "Segoe UI", sans-serif`;
      ctx.textBaseline = "top";
      const lineas = String(o.texto).split("\n");
      const alto = o.tamano * 1.25;
      if (o.fondo) {
        // Recuadro claro u oscuro detrás, según el color del texto, para
        // que se lea sobre cualquier zona de la foto.
        const ancho = Math.max(...lineas.map((l) => ctx.measureText(l).width));
        const pad = o.tamano * 0.25;
        ctx.fillStyle = esClaro(o.color) ? "rgba(17,24,39,.78)" : "rgba(255,255,255,.85)";
        ctx.fillRect(o.x - pad, o.y - pad, ancho + 2 * pad, lineas.length * alto + pad);
        ctx.fillStyle = o.color;
      } else {
        // Sin recuadro, un contorno fino del color contrario.
        ctx.lineWidth = Math.max(1, o.tamano / 9);
        ctx.strokeStyle = esClaro(o.color) ? "rgba(0,0,0,.7)" : "rgba(255,255,255,.85)";
        lineas.forEach((l, i) => ctx.strokeText(l, o.x, o.y + i * alto));
      }
      lineas.forEach((l, i) => ctx.fillText(l, o.x, o.y + i * alto));
      break;
    }
    default:
      break;
  }
  ctx.restore();
}

/** ¿Es un color claro (#rrggbb)? Para elegir el contorno del texto. */
export function esClaro(hex) {
  const n = parseInt(String(hex).replace("#", ""), 16);
  if (Number.isNaN(n)) return false;
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  return r * 0.299 + g * 0.587 + b * 0.114 > 150;
}
