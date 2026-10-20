"use client";

/**
 * Fotografía del periodontograma: un PNG con las cuatro caras, sus
 * líneas y los valores, para adjuntar a un informe o enviar a otro
 * profesional.
 *
 * Se compone como un único SVG con las MISMAS piezas (`VistaVestibular`)
 * y los mismos cálculos de margen y bolsa que el diagrama de la pantalla
 * (`DiagramaPeriodontal.js`), y el navegador lo pasa a PNG. Sin
 * dependencias: React lo dibuja en un contenedor fuera de la pantalla,
 * las variables CSS se sustituyen por sus valores del tema claro (una
 * imagen suelta no las conoce) y un <canvas> hace el resto.
 */

import { flushSync } from "react-dom";
import { createRoot } from "react-dom/client";

import { VistaVestibular, marcoVestibular } from "../odontogram/AnatomiaDental";
import { PERM_LOWER_L, PERM_LOWER_R, PERM_UPPER_L, PERM_UPPER_R } from "../odontogram/contract";
import { ESCALA } from "./DiagramaPeriodontal";
import { CELL_W, ordenSitios } from "./cells";

const COL = CELL_W + 8;
const ETIQUETA = 104;
const LINEA_MEDIA = 10;
const FILA = 15;
const ROJO = "#d64545";
const AZUL = "#2f6fd6";
const AMBAR = "#d99a00";

const SUPERIOR = [...PERM_UPPER_R, ...PERM_UPPER_L];
const INFERIOR = [...PERM_LOWER_R, ...PERM_LOWER_L];

const xColumna = (i) => ETIQUETA + i * COL + (i >= 8 ? LINEA_MEDIA : 0);

/** Puntos de margen y fondo de una cara, como `DiagramaCara`. */
function tramos(codes, base, byCode, top) {
  const lista = [];
  let actual = [];
  codes.forEach((code, i) => {
    const t = byCode[code];
    if (!t || !t.is_present) {
      if (actual.length) lista.push(actual);
      actual = [];
      return;
    }
    const m = marcoVestibular(code);
    const izq = xColumna(i) + (COL - m.ancho * ESCALA) / 2;
    const pts = [0, 1, 2].map((k) => {
      const gm = t.gingival_margin?.[base + k] ?? 0;
      const pd = t.probing_depth?.[base + k] ?? 0;
      return {
        x: izq + m.sitios[k] * ESCALA,
        margen: top + (m.cuello + m.apical * gm) * ESCALA,
        fondo: top + (m.cuello + m.apical * (gm + pd)) * ESCALA,
        sangra: Boolean(t.bleeding?.[base + k]),
        supura: Boolean(t.suppuration?.[base + k]),
      };
    }).sort((a, b) => a.x - b.x);
    actual.push(...pts);
  });
  if (actual.length) lista.push(actual);
  return lista;
}

function Cara({ codes, base, byCode, top, nombre, arcada }) {
  const alto = marcoVestibular(codes[0]).alto * ESCALA;
  const ancho = xColumna(16);
  const linea = (pts, c) => pts.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)} ${p[c].toFixed(1)}`).join(" ");
  return (
    <g>
      <text x={8} y={top + alto / 2} fontSize="13" fontWeight="700" fill="#14212e">{nombre}</text>
      <text x={8} y={top + alto / 2 + 15} fontSize="10.5" fill="#5b6b7c">{arcada}</text>
      {Array.from({ length: Math.floor(alto / (ESCALA * 2)) }, (_, k) => (
        <line key={k} x1={ETIQUETA} x2={ancho} y1={top + (k + 1) * ESCALA * 2} y2={top + (k + 1) * ESCALA * 2}
              stroke="#dfe4ea" strokeWidth="0.6" />
      ))}
      <line x1={xColumna(8) - LINEA_MEDIA / 2} x2={xColumna(8) - LINEA_MEDIA / 2} y1={top} y2={top + alto}
            stroke="#b9c2cc" strokeDasharray="3 3" />
      {codes.map((code, i) => {
        const t = byCode[code];
        const m = marcoVestibular(code);
        return (
          <g key={code} transform={`translate(${xColumna(i) + (COL - m.ancho * ESCALA) / 2} ${top})`}>
            <VistaVestibular code={code} escala={ESCALA} implante={Boolean(t?.has_implant)}
                             ausente={t ? !t.is_present : false} />
          </g>
        );
      })}
      {tramos(codes, base, byCode, top).map((pts, i) => (
        <g key={i}>
          <path d={`${linea(pts, "margen")} ${pts.slice().reverse().map((p) => `L${p.x.toFixed(1)} ${p.fondo.toFixed(1)}`).join(" ")} Z`}
                fill={AZUL} opacity="0.18" />
          <path d={linea(pts, "margen")} fill="none" stroke={ROJO} strokeWidth="1.7" strokeLinejoin="round" />
          <path d={linea(pts, "fondo")} fill="none" stroke={AZUL} strokeWidth="1.7" strokeLinejoin="round" />
          {pts.map((p, k) => (
            <g key={k}>
              <circle cx={p.x} cy={p.margen} r="2" fill={ROJO} />
              <circle cx={p.x} cy={p.fondo} r={p.sangra ? 2.8 : 2} fill={p.sangra ? ROJO : AZUL} />
              {p.supura && <circle cx={p.x} cy={p.fondo} r="4.6" fill="none" stroke={AMBAR} strokeWidth="1.4" />}
            </g>
          ))}
        </g>
      ))}
    </g>
  );
}

function Valores({ codes, base, byCode, top, campo, nombre }) {
  return (
    <g>
      <text x={8} y={top + 11} fontSize="10" fill="#5b6b7c">{nombre}</text>
      <line x1={ETIQUETA} x2={xColumna(16)} y1={top + FILA} y2={top + FILA} stroke="#e6eaef" />
      {codes.map((code, i) => {
        const t = byCode[code];
        if (!t || !t.is_present) return null;
        return ordenSitios(code).map((k, j) => {
          const v = campo === "nic"
            ? (t.probing_depth?.[base + k] ?? 0) + (t.gingival_margin?.[base + k] ?? 0)
            : (t[campo]?.[base + k] ?? 0);
          const alerta = campo !== "gingival_margin" && v > 4;
          return (
            <text key={`${code}-${k}`} x={xColumna(i) + COL / 2 + (j - 1) * 14} y={top + 11} fontSize="10"
                  textAnchor="middle" fill={alerta ? ROJO : "#14212e"} fontWeight={alerta ? 700 : 400}>{v}</text>
          );
        });
      })}
    </g>
  );
}

function Numeros({ codes, top }) {
  return codes.map((code, i) => (
    <text key={code} x={xColumna(i) + COL / 2} y={top + 13} fontSize="12" fontWeight="700"
          textAnchor="middle" fill="#14212e">{code}</text>
  ));
}

/** El SVG completo. Devuelve también su tamaño. */
function Lamina({ byCode, titulo, subtitulo, estadisticas }) {
  const altoCara = marcoVestibular("11").alto * ESCALA;
  const ancho = xColumna(16) + 16;
  const filas = [];
  let y = 58;
  const valores = (codes, base) => ["probing_depth", "gingival_margin", "nic"].map((campo) => {
    const nombre = { probing_depth: "Sondaje", gingival_margin: "Margen", nic: "NIC" }[campo];
    const el = <Valores key={`${campo}-${y}`} codes={codes} base={base} byCode={byCode} top={y} campo={campo} nombre={nombre} />;
    y += FILA;
    return el;
  });

  filas.push(...valores(SUPERIOR, 0));
  filas.push(<Cara key="sv" codes={SUPERIOR} base={0} byCode={byCode} top={y} nombre="Vestibular" arcada="Superior" />);
  y += altoCara;
  filas.push(<Numeros key="ns" codes={SUPERIOR} top={y} />);
  y += 18;
  filas.push(<Cara key="sp" codes={SUPERIOR} base={3} byCode={byCode} top={y} nombre="Palatino" arcada="Superior" />);
  y += altoCara;
  filas.push(...valores(SUPERIOR, 3));
  y += 16;
  filas.push(<line key="sep" x1={8} x2={ancho - 8} y1={y - 8} y2={y - 8} stroke="#b9c2cc" strokeDasharray="4 4" />);
  filas.push(...valores(INFERIOR, 3));
  filas.push(<Cara key="il" codes={INFERIOR} base={3} byCode={byCode} top={y} nombre="Lingual" arcada="Inferior" />);
  y += altoCara;
  filas.push(<Numeros key="ni" codes={INFERIOR} top={y} />);
  y += 18;
  filas.push(<Cara key="iv" codes={INFERIOR} base={0} byCode={byCode} top={y} nombre="Vestibular" arcada="Inferior" />);
  y += altoCara;
  filas.push(...valores(INFERIOR, 0));
  y += 22;

  const leyenda = [[ROJO, "Margen gingival"], [AZUL, "Fondo de bolsa"], [AMBAR, "Supuración (aro)"]];
  const alto = y + 44;
  return {
    ancho, alto,
    svg: (
      <svg xmlns="http://www.w3.org/2000/svg" width={ancho} height={alto} viewBox={`0 0 ${ancho} ${alto}`}
           fontFamily="Inter, Helvetica, Arial, sans-serif">
        <rect width={ancho} height={alto} fill="#ffffff" />
        <text x={8} y={26} fontSize="18" fontWeight="700" fill="#14212e">{titulo}</text>
        <text x={8} y={44} fontSize="12" fill="#5b6b7c">{subtitulo}</text>
        {filas}
        {leyenda.map(([c, t], i) => (
          <g key={t} transform={`translate(${8 + i * 150} ${y})`}>
            <line x1={0} x2={18} y1={-4} y2={-4} stroke={c} strokeWidth="2.5" />
            <text x={24} y={0} fontSize="11" fill="#5b6b7c">{t}</text>
          </g>
        ))}
        {estadisticas && (
          <text x={8} y={y + 22} fontSize="11.5" fill="#14212e">{estadisticas}</text>
        )}
      </svg>
    ),
  };
}

/** Las variables CSS de la página, con los valores del tema claro. */
function variablesClaras() {
  const raiz = document.documentElement;
  const antes = raiz.getAttribute("data-theme");
  raiz.setAttribute("data-theme", "light");
  const estilo = getComputedStyle(raiz);
  const leer = (nombre) => estilo.getPropertyValue(nombre).trim();
  return { leer, restaurar: () => (antes == null ? raiz.removeAttribute("data-theme") : raiz.setAttribute("data-theme", antes)) };
}

export async function descargarImagenPeriodontal({ byCode, titulo, subtitulo, estadisticas, nombre }) {
  const { ancho, alto, svg } = Lamina({ byCode, titulo, subtitulo, estadisticas });
  const caja = document.createElement("div");
  caja.style.cssText = "position:fixed;left:-99999px;top:0;";
  document.body.appendChild(caja);
  const raiz = createRoot(caja);
  flushSync(() => raiz.render(svg));
  let marcado = caja.innerHTML;
  raiz.unmount();
  caja.remove();

  const { leer, restaurar } = variablesClaras();
  try {
    marcado = marcado.replace(/var\((--[\w-]+)\)/g, (_, v) => leer(v) || "#000");
  } finally {
    restaurar();
  }

  const imagen = new Image();
  const url = URL.createObjectURL(new Blob([marcado], { type: "image/svg+xml" }));
  try {
    await new Promise((ok, mal) => { imagen.onload = ok; imagen.onerror = () => mal(new Error("No se pudo dibujar la imagen.")); imagen.src = url; });
    const escala = 2;
    const lienzo = document.createElement("canvas");
    lienzo.width = ancho * escala;
    lienzo.height = alto * escala;
    const ctx = lienzo.getContext("2d");
    ctx.scale(escala, escala);
    ctx.drawImage(imagen, 0, 0, ancho, alto);
    const png = await new Promise((ok) => lienzo.toBlob(ok, "image/png"));
    const enlace = URL.createObjectURL(png);
    const a = document.createElement("a");
    a.href = enlace; a.download = nombre || "periodontograma.png"; a.click();
    setTimeout(() => URL.revokeObjectURL(enlace), 10000);
  } finally {
    URL.revokeObjectURL(url);
  }
}
