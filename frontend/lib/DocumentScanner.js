"use client";

/**
 * Escanear documentos con la cámara y guardarlos como un PDF en la
 * historia clínica del paciente.
 * ────────────────────────────────────────────────────────────────────
 * Un navegador no puede hablar con un escáner TWAIN/WIA (hace falta
 * software nativo), así que se escanea con la cámara del ordenador o del
 * teléfono:
 *
 *   · en vivo (getUserMedia), pidiendo la mayor resolución que dé la
 *     cámara: la de por omisión, 640×480, no deja leer letra pequeña;
 *   · o con «Añadir fotos», que en el teléfono abre la cámara del sistema
 *     —fotos a plena resolución, con enfoque y flash— y en el ordenador
 *     deja elegir imágenes. También es la salida cuando el navegador no
 *     da acceso a la cámara (permiso denegado, página sin https).
 *
 * Cada página se reduce a LADO_MAXIMO, se realza según sus propios
 * niveles (ver realceDocumento.mjs) y se puede girar, reordenar, marcar
 * (flechas, círculos, texto: lib/AnotadorFoto.js) o quitar.
 * Al guardar se arma un único PDF —cada página con la orientación de su
 * foto— y se sube con `api()`, que renueva la sesión si caducó mientras
 * se escaneaba: antes se mandaba el token tal cual y, si había caducado,
 * se perdían todas las páginas con un «error 401».
 *
 * Recortar bordes y corregir perspectiva automáticamente exigiría visión
 * por computador (OpenCV.js, varios MB): fuera de alcance sin añadir
 * dependencias.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import AnotadorFoto from "./AnotadorFoto";
import Capa from "./Capa";
import { api, readObject } from "./api";
import {
  MODOS, TOPE_PDF, bytesDeDataUrl, medidaDestino, orientacion, realzar, tamanoLegible,
} from "./realceDocumento.mjs";

const CALIDAD_JPEG = 0.82;

/** Dibuja `fuente` reducida y realzada; devuelve la página lista. */
function procesar(fuente, anchoFuente, altoFuente, modo) {
  const { ancho, alto } = medidaDestino(anchoFuente, altoFuente);
  const canvas = document.createElement("canvas");
  canvas.width = ancho;
  canvas.height = alto;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(fuente, 0, 0, ancho, alto);
  if (modo !== "original") {
    const img = ctx.getImageData(0, 0, ancho, alto);
    realzar(img.data, modo);
    ctx.putImageData(img, 0, 0);
  }
  return { url: canvas.toDataURL("image/jpeg", CALIDAD_JPEG), ancho, alto };
}

function cargarImagen(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("imagen ilegible"));
    img.src = src;
  });
}

/** La página girada 90° en el sentido de las agujas del reloj. */
async function girar(pagina) {
  const img = await cargarImagen(pagina.url);
  const canvas = document.createElement("canvas");
  canvas.width = pagina.alto;
  canvas.height = pagina.ancho;
  const ctx = canvas.getContext("2d");
  ctx.translate(canvas.width, 0);
  ctx.rotate(Math.PI / 2);
  ctx.drawImage(img, 0, 0);
  return { ...pagina, url: canvas.toDataURL("image/jpeg", CALIDAD_JPEG), ancho: pagina.alto, alto: pagina.ancho };
}

const plural = (n, una, varias) => `${n} ${n === 1 ? una : varias}`;

let siguienteId = 1;

export default function DocumentScanner({ patientId, docType = "exam", onDone, onClose }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const archivoRef = useRef(null);
  const [pages, setPages] = useState([]);            // { id, url, ancho, alto }
  const [camara, setCamara] = useState("iniciando"); // iniciando | lista | sin-camara
  const [modo, setModo] = useState("documento");
  const [descripcion, setDescripcion] = useState("");
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");
  const [saving, setSaving] = useState(false);
  const [linterna, setLinterna] = useState(null);    // null: la cámara no tiene
  const [destello, setDestello] = useState(false);
  const [confirmarSalida, setConfirmarSalida] = useState(false);
  const [marcando, setMarcando] = useState(null);    // id de la página que se marca

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!navigator.mediaDevices?.getUserMedia) {
        setCamara("sin-camara");
        setAviso(window.isSecureContext === false
          ? "La cámara en vivo necesita abrir el panel con https. Puedes usar «Añadir fotos»."
          : "Este navegador no da acceso a la cámara en vivo. Puedes usar «Añadir fotos».");
        return;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: "environment" }, width: { ideal: 2560 }, height: { ideal: 1440 } },
          audio: false,
        });
        if (cancelled) { stream.getTracks().forEach((t) => t.stop()); return; }
        streamRef.current = stream;
        const pista = stream.getVideoTracks()[0];
        if (pista?.getCapabilities?.().torch) setLinterna(false);
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
          setCamara("lista");
        }
      } catch (e) {
        if (cancelled) return;
        setCamara("sin-camara");
        setAviso(e?.name === "NotAllowedError"
          ? "El navegador no tiene permiso para usar la cámara (se activa en el candado de la barra de direcciones). Mientras tanto, puedes usar «Añadir fotos»."
          : "No se encontró una cámara disponible. Puedes usar «Añadir fotos».");
      }
    })();
    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  // Cerrar con páginas sin guardar pide confirmación: antes un clic de
  // más en «Cerrar» tiraba todo lo escaneado.
  const pedirCierre = useCallback(() => {
    if (saving) return;
    if (pages.length) setConfirmarSalida(true);
    else onClose?.();
  }, [pages.length, saving, onClose]);

  useEffect(() => {
    if (marcando) return undefined;   // con el editor abierto, Escape es suyo
    const tecla = (e) => {
      if (e.key !== "Escape") return;
      if (confirmarSalida) setConfirmarSalida(false);
      else pedirCierre();
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [confirmarSalida, pedirCierre, marcando]);

  function agregar(pagina) {
    setPages((p) => [...p, { id: siguienteId++, ...pagina }]);
  }

  function capture() {
    const video = videoRef.current;
    if (!video?.videoWidth) return;
    agregar(procesar(video, video.videoWidth, video.videoHeight, modo));
    setDestello(true);
    setTimeout(() => setDestello(false), 160);
  }

  async function desdeArchivos(e) {
    const archivos = [...(e.target.files || [])];
    e.target.value = "";
    let fallidas = 0;
    for (const archivo of archivos) {
      const url = URL.createObjectURL(archivo);
      try {
        // eslint-disable-next-line no-await-in-loop
        const img = await cargarImagen(url);
        agregar(procesar(img, img.naturalWidth, img.naturalHeight, modo));
      } catch {
        fallidas++;
      } finally {
        URL.revokeObjectURL(url);
      }
    }
    setError(fallidas
      ? `No se pudo leer ${fallidas === 1 ? "una imagen" : `${fallidas} imágenes`}. Usa JPG o PNG (las HEIC del iPhone solo se leen en Safari).`
      : "");
  }

  async function alternarLinterna() {
    const pista = streamRef.current?.getVideoTracks()[0];
    if (!pista) return;
    try {
      await pista.applyConstraints({ advanced: [{ torch: !linterna }] });
      setLinterna(!linterna);
    } catch { setLinterna(null); }
  }

  async function girarPagina(id) {
    const pagina = pages.find((p) => p.id === id);
    if (!pagina) return;
    const girada = await girar(pagina);
    setPages((p) => p.map((x) => (x.id === id ? girada : x)));
  }

  function mover(id, delta) {
    setPages((p) => {
      const i = p.findIndex((x) => x.id === id);
      const j = i + delta;
      if (i < 0 || j < 0 || j >= p.length) return p;
      const copia = [...p];
      [copia[i], copia[j]] = [copia[j], copia[i]];
      return copia;
    });
  }

  const peso = pages.reduce((total, p) => total + bytesDeDataUrl(p.url), 0);
  const demasiado = peso > TOPE_PDF;

  async function saveAsPdf() {
    if (pages.length === 0) { setError("Captura al menos una página."); return; }
    if (demasiado) return;
    setSaving(true); setError("");
    try {
      const { jsPDF } = await import("jspdf");
      const primera = pages[0];
      const pdf = new jsPDF({ unit: "pt", format: "a4", orientation: orientacion(primera.ancho, primera.alto) });
      pages.forEach((p, i) => {
        if (i > 0) pdf.addPage("a4", orientacion(p.ancho, p.alto));
        const pw = pdf.internal.pageSize.getWidth();
        const ph = pdf.internal.pageSize.getHeight();
        const ratio = Math.min(pw / p.ancho, ph / p.alto);
        const w = p.ancho * ratio, h = p.alto * ratio;
        // "NONE": el JPEG ya va comprimido; volver a comprimirlo solo
        // gasta tiempo en el teléfono.
        pdf.addImage(p.url, "JPEG", (pw - w) / 2, (ph - h) / 2, w, h, undefined, "NONE");
      });
      const blob = pdf.output("blob");

      const fd = new FormData();
      fd.append("doc_type", docType);
      fd.append("description", descripcion.trim()
        || `Documento escaneado (${plural(pages.length, "página", "páginas")})`);
      fd.append("file", new File([blob], `escaneo_${Date.now()}.pdf`, { type: "application/pdf" }));
      await readObject(await api(`/patients/${patientId}/documents/`, { method: "POST", body: fd }));
      onDone?.();
    } catch (err) {
      setError(`${err.message || "No se pudo generar el PDF."} Las páginas siguen aquí: puedes volver a intentarlo.`);
    } finally {
      setSaving(false);
    }
  }

  const ayudaModo = MODOS.find((m) => m.clave === modo)?.ayuda;
  const paginaMarcada = pages.find((p) => p.id === marcando);

  return (
    <Capa>
    <div className="escaner" role="dialog" aria-modal="true" aria-label="Escanear documento">
      <div className="escaner-barra">
        <span className="escaner-titulo">Escanear documento</span>
        <div className="escaner-modos" role="radiogroup" aria-label="Tratamiento de la imagen">
          {MODOS.map((m) => (
            <button key={m.clave} type="button" role="radio" aria-checked={modo === m.clave}
                    className={modo === m.clave ? "activo" : ""} title={m.ayuda}
                    onClick={() => setModo(m.clave)}>
              {m.titulo}
            </button>
          ))}
        </div>
        <button type="button" className="escaner-boton" onClick={pedirCierre}>✕ Cerrar</button>
      </div>
      <p className="escaner-nota">{ayudaModo} Se aplica a las páginas que captures desde ahora.</p>

      {error && <div className="escaner-error" role="alert">{error}</div>}
      {aviso && <div className="escaner-aviso">{aviso}</div>}

      <div className="escaner-cuerpo">
        <div className="escaner-camara">
          {camara !== "sin-camara" ? (
            <div className="escaner-visor">
              <video ref={videoRef} playsInline muted />
              <div className="escaner-guia" aria-hidden="true" />
              {destello && <div className="escaner-destello" aria-hidden="true" />}
              {camara === "iniciando" && <div className="escaner-cargando">Abriendo la cámara…</div>}
            </div>
          ) : (
            <div className="escaner-sin-camara">
              Toma fotos del documento con la cámara del teléfono o elige imágenes del equipo.
            </div>
          )}
          <div className="escaner-acciones">
            {camara === "lista" && (
              <button type="button" className="escaner-boton escaner-boton--principal" onClick={capture}>
                ◉ Capturar página
              </button>
            )}
            <button type="button" className="escaner-boton" onClick={() => archivoRef.current?.click()}>
              Añadir fotos
            </button>
            {linterna !== null && (
              <button type="button" className="escaner-boton" aria-pressed={linterna} onClick={alternarLinterna}>
                {linterna ? "Apagar luz" : "Encender luz"}
              </button>
            )}
            <input ref={archivoRef} type="file" accept="image/*" capture="environment" multiple hidden
                   onChange={desdeArchivos} />
          </div>
        </div>

        <div className="escaner-paginas">
          <div className="escaner-resumen">
            {pages.length ? `${plural(pages.length, "página", "páginas")} · ${tamanoLegible(peso)}` : "Sin páginas todavía"}
          </div>
          <ol>
            {pages.map((p, i) => (
              <li key={p.id}>
                <img src={p.url} alt={`Página ${i + 1}`} />
                <span className="escaner-numero">{i + 1}</span>
                <div className="escaner-herramientas">
                  <button type="button" onClick={() => mover(p.id, -1)} disabled={i === 0}
                          aria-label={`Subir la página ${i + 1}`} title="Subir">↑</button>
                  <button type="button" onClick={() => mover(p.id, 1)} disabled={i === pages.length - 1}
                          aria-label={`Bajar la página ${i + 1}`} title="Bajar">↓</button>
                  <button type="button" onClick={() => setMarcando(p.id)}
                          aria-label={`Marcar la página ${i + 1}`} title="Marcar">✎</button>
                  <button type="button" onClick={() => girarPagina(p.id)}
                          aria-label={`Girar la página ${i + 1}`} title="Girar">↻</button>
                  <button type="button" onClick={() => setPages((x) => x.filter((y) => y.id !== p.id))}
                          aria-label={`Quitar la página ${i + 1}`} title="Quitar">✕</button>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>

      {paginaMarcada && (
        <AnotadorFoto src={paginaMarcada.url} titulo={`Marcar la página ${pages.indexOf(paginaMarcada) + 1}`}
                      textoGuardar="Aplicar a la página" onCerrar={() => setMarcando(null)}
                      onGuardar={({ dataUrl, ancho, alto }) => {
                        setPages((x) => x.map((y) => (y.id === marcando ? { ...y, url: dataUrl, ancho, alto } : y)));
                        setMarcando(null);
                      }} />
      )}

      <div className="escaner-pie">
        {confirmarSalida ? (
          <>
            <span className="escaner-pregunta">
              ¿Descartar {pages.length === 1 ? "la página capturada" : `las ${pages.length} páginas capturadas`}?
            </span>
            <button type="button" className="escaner-boton" onClick={() => setConfirmarSalida(false)}>Seguir escaneando</button>
            <button type="button" className="escaner-boton escaner-boton--peligro" onClick={onClose}>Descartar</button>
          </>
        ) : (
          <>
            <input className="escaner-descripcion" value={descripcion} maxLength={200}
                   onChange={(e) => setDescripcion(e.target.value)}
                   placeholder="Descripción (opcional): p. ej. Consentimiento de extracción"
                   aria-label="Descripción del documento" />
            {demasiado && (
              <span className="escaner-limite">
                Pasa de {tamanoLegible(TOPE_PDF)}: quita páginas o guárdalo en dos partes.
              </span>
            )}
            <button type="button" className="escaner-boton" onClick={pedirCierre} disabled={saving}>Cancelar</button>
            <button type="button" className="escaner-boton escaner-boton--principal"
                    disabled={saving || pages.length === 0 || demasiado} onClick={saveAsPdf}>
              {saving ? "Guardando…" : `Guardar PDF (${plural(pages.length, "pág.", "págs.")})`}
            </button>
          </>
        )}
      </div>
    </div>
    </Capa>
  );
}
