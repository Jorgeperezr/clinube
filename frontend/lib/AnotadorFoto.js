"use client";

/**
 * Marcar una foto: trazos, flechas, formas y texto encima de la imagen.
 * ────────────────────────────────────────────────────────────────────
 * Pensado para señalar con precisión —una fisura, un borde de una
 * restauración— con ratón, con el dedo o con el lápiz de una tableta:
 *
 *   · Pointer Events con los puntos «agrupados» (getCoalescedEvents): el
 *     lápiz manda hasta 240 puntos por segundo y el navegador solo
 *     entrega uno por fotograma; sin ellos, las curvas salen a tramos.
 *   · Presión: con lápiz, el trazo engorda al apretar (se puede apagar).
 *   · Palma: en cuanto se usa un lápiz, el dedo deja de pintar y solo
 *     mueve o amplía la foto, como en las apps de dibujo.
 *   · Zoom hasta 16× (rueda, pellizco o botones) y desplazamiento (dos
 *     dedos, rueda del ratón pulsada o barra espaciadora): para la
 *     precisión fina se amplía, no se afina el pulso.
 *   · El círculo que sigue al puntero muestra el grosor real del trazo.
 *   · Mayús: líneas a múltiplos de 15°, cuadrados y círculos.
 *   · Ctrl/Cmd+Z deshace; Ctrl+Mayús+Z o Ctrl+Y rehace.
 *
 * Las marcas se guardan como figuras, en coordenadas de la foto (ver
 * anotacion.mjs), y solo se «queman» sobre la imagen al guardar, a la
 * resolución completa. La foto original no se modifica.
 *
 * Lo que hace con el resultado lo decide quien lo usa (`onGuardar`):
 * FotoAnotada.js lo sube a los documentos del paciente; el escáner lo
 * pone en lugar de la página.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import Capa from "./Capa";
import {
  COLORES, ESCALA_MAX, ESCALA_MIN, HERRAMIENTAS, aImagen, aPantalla, agregarPunto, confirmar,
  desplazar, deshacer, dibujarMarca, encuadrar, historialVacio, marcaEn, rehacer,
  restringirAngulo, restringirCuadrado, unidad, zoomEn,
} from "./anotacion.mjs";

/** Lado mayor con el que se trabaja: más, y el teléfono se queda sin memoria. */
const LADO_MAXIMO = 3200;

const ICONOS = {
  lapiz: <path d="M4 20l4-1 11-11-3-3L5 16l-1 4zM14 6l3 3" />,
  flecha: <path d="M5 19L19 5M10 5h9v9" />,
  linea: <path d="M5 19L19 5" />,
  rect: <rect x="4" y="6" width="16" height="12" rx="1" />,
  elipse: <ellipse cx="12" cy="12" rx="8" ry="6" />,
  texto: <path d="M5 6V4h14v2M12 4v16M9 20h6" />,
  borrador: <path d="M8 20h12M5 15l8-8 6 6-6 6H9l-4-4zM10 10l6 6" />,
  mover: <path d="M12 3v18M3 12h18M12 3l-3 3M12 3l3 3M12 21l-3-3M12 21l3-3M3 12l3-3M3 12l3 3M21 12l-3-3M21 12l-3 3" />,
};

function Icono({ nombre }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
         strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {ICONOS[nombre]}
    </svg>
  );
}

/** Carga la imagen y, si es enorme, la reduce a LADO_MAXIMO. */
function cargar(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const w = img.naturalWidth, h = img.naturalHeight;
      const f = Math.min(1, LADO_MAXIMO / Math.max(w, h));
      if (f === 1) { resolve({ fuente: img, ancho: w, alto: h }); return; }
      const c = document.createElement("canvas");
      c.width = Math.round(w * f);
      c.height = Math.round(h * f);
      const ctx = c.getContext("2d");
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(img, 0, 0, c.width, c.height);
      resolve({ fuente: c, ancho: c.width, alto: c.height });
    };
    img.onerror = () => reject(new Error("No se pudo abrir la imagen. Usa JPG o PNG (las HEIC del iPhone solo se abren en Safari)."));
    img.src = src;
  });
}

function esCampo(el) {
  return el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable);
}

export default function AnotadorFoto({ src, titulo = "Marcar foto", textoGuardar = "Guardar", onGuardar, onCerrar, pie = null }) {
  const lienzoRef = useRef(null);
  const marcoRef = useRef(null);
  const textoRef = useRef(null);
  const [img, setImg] = useState(null);
  const [error, setError] = useState("");
  const [vista, setVista] = useState(null);
  const [hist, setHist] = useState(historialVacio);
  const [herramienta, setHerramienta] = useState("lapiz");
  const [color, setColor] = useState(COLORES[0]);
  const [grosor, setGrosor] = useState(6);
  const [tamTexto, setTamTexto] = useState(40);
  const [fondoTexto, setFondoTexto] = useState(true);
  const [conPresion, setConPresion] = useState(true);
  const [texto, setTextoEstado] = useState(null);     // { x, y, valor } en coordenadas de la foto
  const [guardando, setGuardando] = useState(false);
  const [salir, setSalir] = useState(false);
  const [espacio, setEspacio] = useState(false);
  const [lapiz, setLapiz] = useState(false);           // se ha usado un lápiz

  // Lo que leen el pintado y los gestos, sin esperar a un render.
  const r = useRef({});
  r.current = { img, vista, hist, herramienta, color, grosor, conPresion, espacio, lapiz };
  const gesto = useRef(null);
  const enCurso = useRef(null);
  const punteros = useRef(new Map());
  const cursor = useRef(null);                         // [x, y] en pantalla, para el círculo
  const tamano = useRef({ ancho: 0, alto: 0 });
  const raf = useRef(0);
  // El texto en edición también en una referencia: al pulsar fuera, el
  // clic y la pérdida de foco lo confirman los dos en el mismo instante
  // y, leyendo el estado, se añadía dos veces.
  const textoActual = useRef(null);
  const setTexto = (t) => { textoActual.current = t; setTextoEstado(t); };

  // ── Pintado ──────────────────────────────────────────────────────
  const pintar = useCallback(() => {
    const c = lienzoRef.current;
    const { img: im, vista: v, hist: h, herramienta: herr, grosor: g } = r.current;
    if (!c || !im || !v) return;
    const dpr = window.devicePixelRatio || 1;
    const ctx = c.getContext("2d");
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, c.width, c.height);
    ctx.setTransform(dpr * v.escala, 0, 0, dpr * v.escala, dpr * v.dx, dpr * v.dy);
    ctx.imageSmoothingEnabled = v.escala < 3;          // ampliada, se ven los píxeles reales
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(im.fuente, 0, 0, im.ancho, im.alto);

    const ge = gesto.current;
    const lista = ge?.tipo === "borrar" ? ge.lista : h.presente;
    lista.forEach((o, i) => {
      dibujarMarca(ctx, ge?.tipo === "mover" && ge.indice === i ? desplazar(o, ge.delta) : o);
    });
    if (enCurso.current) dibujarMarca(ctx, enCurso.current);

    // El círculo del grosor, del tamaño real con el que se va a pintar.
    if (cursor.current && (herr === "lapiz" || herr === "borrador") && !ge) {
      const [x, y] = aImagen(cursor.current, v);
      const radio = herr === "lapiz" ? (g * unidad(im.ancho, im.alto)) / 2 : 10 / v.escala;
      ctx.lineWidth = 1.5 / v.escala;
      ctx.strokeStyle = "rgba(255,255,255,.9)";
      ctx.beginPath(); ctx.arc(x, y, Math.max(radio, 2 / v.escala), 0, Math.PI * 2); ctx.stroke();
      ctx.lineWidth = 0.75 / v.escala;
      ctx.strokeStyle = "rgba(0,0,0,.8)";
      ctx.stroke();
    }
  }, []);

  const pedirPintado = useCallback(() => {
    if (raf.current) return;
    raf.current = requestAnimationFrame(() => { raf.current = 0; pintar(); });
  }, [pintar]);

  useEffect(() => () => cancelAnimationFrame(raf.current), []);
  useEffect(() => { pedirPintado(); }, [img, vista, hist, herramienta, grosor, pedirPintado]);

  // ── Carga y tamaño ───────────────────────────────────────────────
  useEffect(() => {
    let vivo = true;
    setImg(null); setVista(null); setHist(historialVacio); setError("");
    cargar(src).then((im) => { if (vivo) setImg(im); }).catch((e) => { if (vivo) setError(e.message); });
    return () => { vivo = false; };
  }, [src]);

  // Mientras nadie amplíe ni desplace a mano, la foto se reencuadra
  // sola al girar la tableta o cambiar el tamaño de la ventana.
  const encajada = useRef(true);
  const ajustar = useCallback(() => {
    const { img: im } = r.current;
    const { ancho, alto } = tamano.current;
    encajada.current = true;
    if (im && ancho) setVista(encuadrar(im.ancho, im.alto, ancho, alto));
  }, []);
  const moverVista = (v) => { encajada.current = false; setVista(v); };

  useEffect(() => {
    const marco = marcoRef.current;
    if (!marco) return undefined;
    const medir = () => {
      const c = lienzoRef.current;
      const { width, height } = marco.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      tamano.current = { ancho: width, alto: height };
      c.width = Math.round(width * dpr);
      c.height = Math.round(height * dpr);
      c.style.width = `${width}px`;
      c.style.height = `${height}px`;
      if (!r.current.vista || encajada.current) ajustar();
      pedirPintado();
    };
    medir();
    const obs = new ResizeObserver(medir);
    obs.observe(marco);
    return () => obs.disconnect();
  }, [img, ajustar, pedirPintado]);

  // ── Historial ────────────────────────────────────────────────────
  const agregarMarca = (o) => setHist((h) => confirmar(h, [...h.presente, o]));
  const cambios = hist.pasado.length > 0 || hist.presente.length > 0;

  // ── Texto ────────────────────────────────────────────────────────
  function confirmarTexto() {
    const t = textoActual.current;
    if (!t) return;
    const valor = t.valor.replace(/\s+$/, "");
    if (valor) {
      agregarMarca({
        tipo: "texto", x: t.x, y: t.y, texto: valor, color, fondo: fondoTexto,
        tamano: tamTexto * unidad(img.ancho, img.alto),
      });
    }
    setTexto(null);
  }

  useEffect(() => {
    if (texto) setTimeout(() => textoRef.current?.focus(), 0);
  }, [texto?.x, texto?.y]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Gestos ───────────────────────────────────────────────────────
  function posicion(e) {
    const rect = lienzoRef.current.getBoundingClientRect();
    return [e.clientX - rect.left, e.clientY - rect.top];
  }

  function empezarPan(p) {
    gesto.current = { tipo: "pan", inicio: p, vista: r.current.vista };
  }

  function borrarEn(p) {
    const ge = gesto.current;
    const tolerancia = 10 / r.current.vista.escala;
    const i = marcaEn(ge.lista, p, tolerancia);
    if (i >= 0) {
      ge.lista = ge.lista.filter((_, k) => k !== i);
      pedirPintado();
    }
  }

  function alPulsar(e) {
    const { img: im, vista: v, herramienta: herr } = r.current;
    if (!im || !v || guardando) return;
    if (textoActual.current) { confirmarTexto(); return; }
    e.preventDefault();
    lienzoRef.current.setPointerCapture?.(e.pointerId);
    const pos = posicion(e);
    punteros.current.set(e.pointerId, pos);
    if (e.pointerType === "pen" && !r.current.lapiz) setLapiz(true);

    // Dos dedos: ampliar y desplazar. Lo que se estuviera dibujando con
    // el primero se descarta (era el inicio del pellizco).
    if (punteros.current.size === 2) {
      enCurso.current = null;
      const [a, b] = [...punteros.current.values()];
      gesto.current = {
        tipo: "pellizco", vista: r.current.vista,
        distancia: Math.hypot(a[0] - b[0], a[1] - b[1]) || 1,
        centro: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2],
      };
      pedirPintado();
      return;
    }
    if (punteros.current.size > 2) return;

    const palma = e.pointerType === "touch" && (r.current.lapiz || e.width > 40);
    if (palma || e.button === 1 || r.current.espacio) { empezarPan(pos); return; }
    if (e.button !== 0) return;

    const p = aImagen(pos, v);
    const u = unidad(im.ancho, im.alto);
    const base = { color: r.current.color, ancho: r.current.grosor * u };
    switch (herr) {
      case "lapiz":
        enCurso.current = {
          ...base, tipo: "trazo", puntos: [[p[0], p[1], e.pressure]],
          presion: r.current.conPresion && e.pointerType === "pen",
        };
        gesto.current = { tipo: "dibujo", inicio: p };
        break;
      case "flecha":
      case "linea":
      case "rect":
      case "elipse":
        enCurso.current = { ...base, tipo: herr, a: p, b: p };
        gesto.current = { tipo: "dibujo", inicio: p };
        break;
      case "texto":
        setTexto({ x: p[0], y: p[1], valor: "" });
        break;
      case "borrador":
        gesto.current = { tipo: "borrar", lista: r.current.hist.presente };
        borrarEn(p);
        break;
      case "mover": {
        const i = marcaEn(r.current.hist.presente, p, 8 / v.escala);
        if (i >= 0) gesto.current = { tipo: "mover", indice: i, inicio: p, delta: [0, 0] };
        else empezarPan(pos);
        break;
      }
      default:
        break;
    }
    pedirPintado();
  }

  function alMover(e) {
    const pos = posicion(e);
    if (e.pointerType !== "touch") { cursor.current = pos; }
    if (!punteros.current.has(e.pointerId)) { pedirPintado(); return; }
    punteros.current.set(e.pointerId, pos);
    const ge = gesto.current;
    const v = r.current.vista;
    if (!ge) return;

    if (ge.tipo === "pellizco") {
      const [a, b] = [...punteros.current.values()];
      if (!b) return;
      const distancia = Math.hypot(a[0] - b[0], a[1] - b[1]) || 1;
      const centro = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
      const z = zoomEn(ge.vista, distancia / ge.distancia, ge.centro);
      moverVista({ ...z, dx: z.dx + centro[0] - ge.centro[0], dy: z.dy + centro[1] - ge.centro[1] });
      return;
    }
    if (ge.tipo === "pan") {
      moverVista({ ...ge.vista, dx: ge.vista.dx + pos[0] - ge.inicio[0], dy: ge.vista.dy + pos[1] - ge.inicio[1] });
      return;
    }

    // Los puntos intermedios solo los tiene el evento nativo, no el de React.
    const eventos = e.nativeEvent?.getCoalescedEvents?.() || [];
    const muestras = eventos.length ? eventos : [e];
    if (ge.tipo === "dibujo" && enCurso.current) {
      const o = enCurso.current;
      if (o.tipo === "trazo") {
        let puntos = o.puntos;
        for (const ev of muestras) {
          const [x, y] = aImagen(posicion(ev), v);
          puntos = agregarPunto(puntos, [x, y, ev.pressure], 0.6 / v.escala);
        }
        enCurso.current = { ...o, puntos };
      } else {
        let b = aImagen(pos, v);
        if (e.shiftKey) b = o.tipo === "rect" || o.tipo === "elipse" ? restringirCuadrado(o.a, b) : restringirAngulo(o.a, b);
        enCurso.current = { ...o, b };
      }
    } else if (ge.tipo === "borrar") {
      for (const ev of muestras) borrarEn(aImagen(posicion(ev), v));
    } else if (ge.tipo === "mover") {
      const p = aImagen(pos, v);
      ge.delta = [p[0] - ge.inicio[0], p[1] - ge.inicio[1]];
    }
    pedirPintado();
  }

  function alSoltar(e) {
    if (!punteros.current.has(e.pointerId)) return;
    punteros.current.delete(e.pointerId);
    lienzoRef.current?.releasePointerCapture?.(e.pointerId);
    const ge = gesto.current;
    if (!ge) return;
    // Al levantar un dedo del pellizco no se empieza a pintar con el otro.
    if (ge.tipo === "pellizco") {
      if (punteros.current.size === 0) gesto.current = null;
      else gesto.current = { tipo: "nada" };
      return;
    }
    if (punteros.current.size > 0) return;
    gesto.current = null;
    const cancelado = e.type === "pointercancel";

    if (ge.tipo === "dibujo" && enCurso.current && !cancelado) {
      const o = enCurso.current;
      const v = r.current.vista;
      // Un trazo de un solo punto es un punto, y vale. Una forma de menos
      // de 3 px en pantalla es un clic suelto: dejaría una marca invisible.
      if (o.tipo === "trazo" || Math.hypot(o.b[0] - o.a[0], o.b[1] - o.a[1]) * v.escala >= 3) agregarMarca(o);
    } else if (ge.tipo === "borrar" && ge.lista !== r.current.hist.presente) {
      setHist((h) => confirmar(h, ge.lista));
    } else if (ge.tipo === "mover" && (ge.delta[0] || ge.delta[1])) {
      setHist((h) => confirmar(h, h.presente.map((o, i) => (i === ge.indice ? desplazar(o, ge.delta) : o))));
    }
    enCurso.current = null;
    pedirPintado();
  }

  function alSalirDelLienzo() {
    cursor.current = null;
    pedirPintado();
  }

  // Rueda: con el ratón amplía donde está el cursor; en el trackpad,
  // dos dedos desplazan y el pellizco (que llega con ctrlKey) amplía.
  useEffect(() => {
    const c = lienzoRef.current;
    if (!c) return undefined;
    const rueda = (e) => {
      const v = r.current.vista;
      if (!v) return;
      e.preventDefault();
      const rect = c.getBoundingClientRect();
      const p = [e.clientX - rect.left, e.clientY - rect.top];
      const raton = e.deltaMode === 1 || (e.deltaX === 0 && Math.abs(e.deltaY) >= 50 && Number.isInteger(e.deltaY));
      if (e.ctrlKey || raton) {
        encajada.current = false;
        setVista(zoomEn(v, Math.exp(-e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0025)), p));
      } else {
        encajada.current = false;
        setVista({ ...v, dx: v.dx - e.deltaX, dy: v.dy - e.deltaY });
      }
    };
    c.addEventListener("wheel", rueda, { passive: false });
    return () => c.removeEventListener("wheel", rueda);
  }, [img]);

  // ── Teclado ──────────────────────────────────────────────────────
  useEffect(() => {
    const abajo = (e) => {
      if (esCampo(e.target)) return;
      const mod = e.ctrlKey || e.metaKey;
      const k = e.key.toLowerCase();
      if (mod && k === "z") { e.preventDefault(); setHist((h) => (e.shiftKey ? rehacer(h) : deshacer(h))); return; }
      if (mod && k === "y") { e.preventDefault(); setHist(rehacer); return; }
      if (mod) return;
      if (e.key === " ") { e.preventDefault(); setEspacio(true); return; }
      if (e.key === "Escape") { e.preventDefault(); pedirSalida(); return; }
      if (e.key === "0") { ajustar(); return; }
      if (e.key === "+" || e.key === "=") { zoomCentro(1.25); return; }
      if (e.key === "-") { zoomCentro(0.8); return; }
      const h = HERRAMIENTAS.find((x) => x.tecla === k);
      if (h) setHerramienta(h.clave);
    };
    const arriba = (e) => { if (e.key === " ") setEspacio(false); };
    window.addEventListener("keydown", abajo);
    window.addEventListener("keyup", arriba);
    return () => { window.removeEventListener("keydown", abajo); window.removeEventListener("keyup", arriba); };
  });

  function zoomCentro(factor) {
    const v = r.current.vista;
    if (!v) return;
    const { ancho, alto } = tamano.current;
    moverVista(zoomEn(v, factor, [ancho / 2, alto / 2]));
  }

  function pedirSalida() {
    if (guardando) return;
    if (salir) { setSalir(false); return; }
    if (cambios) setSalir(true);
    else onCerrar?.();
  }

  // ── Guardar ──────────────────────────────────────────────────────
  async function guardar() {
    if (!img || guardando) return;
    setGuardando(true); setError("");
    try {
      const c = document.createElement("canvas");
      c.width = img.ancho;
      c.height = img.alto;
      const ctx = c.getContext("2d");
      ctx.drawImage(img.fuente, 0, 0);
      hist.presente.forEach((o) => dibujarMarca(ctx, o));
      const blob = await new Promise((res, rej) => c.toBlob((b) => (b ? res(b) : rej(new Error("No se pudo generar la imagen."))), "image/jpeg", 0.92));
      await onGuardar?.({ blob, dataUrl: c.toDataURL("image/jpeg", 0.92), ancho: img.ancho, alto: img.alto });
    } catch (e) {
      setError(e.message || "No se pudo guardar.");
      setGuardando(false);
    }
  }

  // Lápiz y borrador llevan su propio círculo (el grosor real); el resto, una cruz.
  const cursorCss = espacio || herramienta === "mover" ? "grab"
    : herramienta === "texto" ? "text"
      : herramienta === "lapiz" || herramienta === "borrador" ? "none" : "crosshair";
  const cajaTexto = texto && vista && img ? (() => {
    const [x, y] = aPantalla([texto.x, texto.y], vista);
    const px = tamTexto * unidad(img.ancho, img.alto) * vista.escala;
    return { left: x, top: y, fontSize: Math.max(10, px), color };
  })() : null;

  return (
    <Capa>
    <div className="anotador" role="dialog" aria-modal="true" aria-label={titulo}>
      <div className="anotador-barra">
        <strong className="anotador-titulo">{titulo}</strong>
        <div className="anotador-grupo">
          <button type="button" className="anotador-boton" onClick={() => setHist(deshacer)}
                  disabled={!hist.pasado.length} title="Deshacer (Ctrl+Z)">↶ Deshacer</button>
          <button type="button" className="anotador-boton" onClick={() => setHist(rehacer)}
                  disabled={!hist.futuro.length} title="Rehacer (Ctrl+Mayús+Z)">↷ Rehacer</button>
        </div>
        <div className="anotador-grupo">
          <button type="button" className="anotador-boton" onClick={() => zoomCentro(0.8)}
                  disabled={!vista || vista.escala <= ESCALA_MIN} aria-label="Reducir">−</button>
          <button type="button" className="anotador-boton anotador-zoom" onClick={ajustar} title="Ajustar a la pantalla (0)">
            {vista ? `${Math.round(vista.escala * 100)} %` : "—"}
          </button>
          <button type="button" className="anotador-boton" onClick={() => zoomCentro(1.25)}
                  disabled={!vista || vista.escala >= ESCALA_MAX} aria-label="Ampliar">+</button>
        </div>
        <button type="button" className="anotador-boton" onClick={pedirSalida}>✕ Cerrar</button>
      </div>

      {error && <div className="anotador-error" role="alert">{error}</div>}

      <div className="anotador-cuerpo">
        <aside className="anotador-panel">
          <div className="anotador-herramientas" role="radiogroup" aria-label="Herramienta">
            {HERRAMIENTAS.map((h) => (
              <button key={h.clave} type="button" role="radio" aria-checked={herramienta === h.clave}
                      className={herramienta === h.clave ? "activa" : ""}
                      title={`${h.titulo} (${h.tecla.toUpperCase()})`}
                      onClick={() => { confirmarTexto(); setHerramienta(h.clave); }}>
                <Icono nombre={h.clave} /><span>{h.titulo}</span>
              </button>
            ))}
          </div>

          <div className="anotador-seccion">
            <span className="anotador-etiqueta">Color</span>
            <div className="anotador-colores">
              {COLORES.map((c) => (
                <button key={c} type="button" aria-label={`Color ${c}`} aria-pressed={color === c}
                        className={color === c ? "activo" : ""} style={{ background: c }}
                        onClick={() => setColor(c)} />
              ))}
              <label className="anotador-color-libre" title="Otro color">
                <input type="color" value={color} onChange={(e) => setColor(e.target.value)} aria-label="Otro color" />
              </label>
            </div>
          </div>

          {herramienta === "texto" ? (
            <div className="anotador-seccion">
              <label className="anotador-etiqueta" htmlFor="anotador-tam">Tamaño del texto · {tamTexto}</label>
              <input id="anotador-tam" type="range" min="10" max="200" value={tamTexto}
                     onChange={(e) => setTamTexto(Number(e.target.value))} />
              <label className="anotador-casilla">
                <input type="checkbox" checked={fondoTexto} onChange={(e) => setFondoTexto(e.target.checked)} />
                Con recuadro detrás
              </label>
            </div>
          ) : (
            <div className="anotador-seccion">
              <label className="anotador-etiqueta" htmlFor="anotador-grosor">Grosor · {grosor}</label>
              <div className="anotador-grosor">
                <input id="anotador-grosor" type="range" min="1" max="40" value={grosor}
                       onChange={(e) => setGrosor(Number(e.target.value))} />
                <span className="anotador-muestra" aria-hidden="true">
                  <span style={{ width: Math.max(2, grosor), height: Math.max(2, grosor), background: color }} />
                </span>
              </div>
              <div className="anotador-rapidos">
                {[2, 4, 8, 16].map((g) => (
                  <button key={g} type="button" className={grosor === g ? "activo" : ""} onClick={() => setGrosor(g)}>
                    {g}
                  </button>
                ))}
              </div>
              {lapiz && (
                <label className="anotador-casilla">
                  <input type="checkbox" checked={conPresion} onChange={(e) => setConPresion(e.target.checked)} />
                  Presión del lápiz
                </label>
              )}
            </div>
          )}

          <button type="button" className="anotador-boton anotador-vaciar" disabled={!hist.presente.length}
                  onClick={() => setHist((h) => confirmar(h, []))}>
            Quitar todas las marcas
          </button>
          <p className="anotador-ayuda">
            {lapiz
              ? "Con el lápiz se dibuja; con el dedo se mueve y se amplía la foto."
              : "Rueda o pellizco: ampliar. Barra espaciadora o dos dedos: mover la foto. Mayús: líneas rectas y círculos."}
          </p>
        </aside>

        <div className="anotador-marco" ref={marcoRef}>
          {!img && !error && <div className="anotador-cargando">Abriendo la foto…</div>}
          <canvas ref={lienzoRef} style={{ cursor: cursorCss, touchAction: "none" }}
                  onPointerDown={alPulsar} onPointerMove={alMover} onPointerUp={alSoltar}
                  onPointerCancel={alSoltar} onPointerLeave={alSalirDelLienzo}
                  onContextMenu={(e) => e.preventDefault()} />
          {cajaTexto && (
            <textarea ref={textoRef} className="anotador-texto" rows={1}
                      style={{ left: cajaTexto.left, top: cajaTexto.top, fontSize: cajaTexto.fontSize, color: cajaTexto.color }}
                      value={texto.valor} placeholder="Escribe…" aria-label="Texto de la marca"
                      onChange={(e) => setTexto({ ...texto, valor: e.target.value })}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); confirmarTexto(); }
                        if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); setTexto(null); }
                      }}
                      onBlur={confirmarTexto} />
          )}
        </div>
      </div>

      <div className="anotador-pie">
        {salir ? (
          <>
            <span className="anotador-pregunta">¿Salir sin guardar las marcas?</span>
            <button type="button" className="anotador-boton" onClick={() => setSalir(false)}>Seguir marcando</button>
            <button type="button" className="anotador-boton anotador-boton--peligro" onClick={onCerrar}>Salir sin guardar</button>
          </>
        ) : (
          <>
            <div className="anotador-extra">{pie}</div>
            <button type="button" className="anotador-boton" onClick={pedirSalida} disabled={guardando}>Cancelar</button>
            <button type="button" className="anotador-boton anotador-boton--principal" onClick={guardar}
                    disabled={!img || guardando}>
              {guardando ? "Guardando…" : textoGuardar}
            </button>
          </>
        )}
      </div>
    </div>
    </Capa>
  );
}
