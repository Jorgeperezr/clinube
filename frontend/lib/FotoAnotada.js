"use client";

/**
 * Foto marcada en los documentos del paciente.
 * ────────────────────────────────────────────────────────────────────
 * Tres pasos: conseguir la foto (cámara del teléfono, cámara del equipo
 * o un archivo), marcarla con AnotadorFoto y guardarla en la historia.
 *
 * Se guarda como un documento NUEVO y la foto sin marcas se conserva:
 * si se parte de una foto que ya estaba en la ficha, esa queda intacta;
 * si es una foto nueva, por omisión se guardan las dos. Una historia
 * clínica no debe perder el original por haberle pintado encima.
 *
 * Al terminar avisa con el evento `documentos-paciente` para que la
 * lista de documentos se recargue.
 */

import { useEffect, useRef, useState } from "react";

import AnotadorFoto from "./AnotadorFoto";
import Capa from "./Capa";
import { api, readObject } from "./api";

// Los tipos de PatientDocument.DocType (apps/patients/models.py).
const TIPOS = [
  ["photo", "Foto clínica"], ["radiograph", "Radiografía"], ["exam", "Examen / laboratorio"],
  ["report", "Informe"], ["identification", "Identificación"], ["medical_order", "Orden médica"],
  ["referral", "Referencia"], ["other", "Otro"],
];

export const EVENTO_DOCUMENTOS = "documentos-paciente";

async function subir(patientId, archivo, nombre, tipo, descripcion) {
  const fd = new FormData();
  fd.append("doc_type", tipo);
  fd.append("description", descripcion);
  fd.append("file", archivo, nombre);
  return readObject(await api(`/patients/${patientId}/documents/`, { method: "POST", body: fd }));
}

/** La cámara del equipo, en vivo: para ordenadores sin cámara «de sistema». */
function CamaraEnVivo({ onFoto, onCancelar }) {
  const videoRef = useRef(null);
  const [error, setError] = useState("");
  const [lista, setLista] = useState(false);

  useEffect(() => {
    let stream;
    let vivo = true;
    navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: "environment" }, width: { ideal: 3840 }, height: { ideal: 2160 } }, audio: false,
    }).then(async (s) => {
      stream = s;
      if (!vivo) { s.getTracks().forEach((t) => t.stop()); return; }
      videoRef.current.srcObject = s;
      await videoRef.current.play();
      setLista(true);
    }).catch(() => setError("No se pudo abrir la cámara. Revisa el permiso en el candado de la barra de direcciones."));
    return () => { vivo = false; stream?.getTracks().forEach((t) => t.stop()); };
  }, []);

  function capturar() {
    const v = videoRef.current;
    const c = document.createElement("canvas");
    c.width = v.videoWidth;
    c.height = v.videoHeight;
    c.getContext("2d").drawImage(v, 0, 0);
    c.toBlob((b) => b && onFoto(new File([b], `foto_${Date.now()}.jpg`, { type: "image/jpeg" })), "image/jpeg", 0.92);
  }

  return (
    <div className="foto-camara">
      {error ? <p className="foto-error">{error}</p> : <video ref={videoRef} playsInline muted />}
      <div className="foto-acciones">
        <button type="button" className="anotador-boton" onClick={onCancelar}>Volver</button>
        <button type="button" className="anotador-boton anotador-boton--principal" disabled={!lista} onClick={capturar}>
          ◉ Tomar foto
        </button>
      </div>
    </div>
  );
}

/**
 * @param patientId          paciente al que se adjunta
 * @param srcInicial         foto de la que partir (una ya guardada), o nada para elegir una
 * @param tipoInicial        tipo de documento propuesto
 * @param descripcionInicial descripción propuesta
 */
export default function FotoAnotada({ patientId, srcInicial = null, tipoInicial = "photo", descripcionInicial = "", onListo, onCerrar }) {
  const [archivo, setArchivo] = useState(null);       // la foto nueva, si no se partió de una guardada
  const [src, setSrc] = useState(srcInicial);
  const [enVivo, setEnVivo] = useState(false);
  const [tipo, setTipo] = useState(tipoInicial);
  const [descripcion, setDescripcion] = useState(descripcionInicial);
  const [conservar, setConservar] = useState(true);
  const camaraRef = useRef(null);
  const archivoRef = useRef(null);
  // Si falla la subida de la marcada y se reintenta, el original no se
  // vuelve a subir.
  const originalSubido = useRef(false);

  // URL de la foto elegida; se libera al cambiarla o al cerrar.
  useEffect(() => {
    if (!archivo) return undefined;
    const url = URL.createObjectURL(archivo);
    setSrc(url);
    return () => URL.revokeObjectURL(url);
  }, [archivo]);

  useEffect(() => {
    if (src) return undefined;
    const tecla = (e) => { if (e.key === "Escape") onCerrar?.(); };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [src, onCerrar]);

  function elegido(e) {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (f) { setArchivo(f); setEnVivo(false); }
  }

  async function guardar({ blob }) {
    const desc = descripcion.trim() || "Foto marcada";
    const marca = Date.now();
    if (archivo && conservar && !originalSubido.current) {
      const ext = (archivo.name.match(/\.[a-z0-9]+$/i)?.[0] || ".jpg").toLowerCase();
      await subir(patientId, archivo, `foto_${marca}${ext}`, tipo, `${desc} · original`);
      originalSubido.current = true;
    }
    await subir(patientId, blob, `foto_marcada_${marca}.jpg`, tipo, desc);
    window.dispatchEvent(new CustomEvent(EVENTO_DOCUMENTOS, { detail: { patientId } }));
    onListo?.();
  }

  if (src) {
    return (
      <AnotadorFoto
        src={src}
        titulo="Marcar foto"
        textoGuardar="Guardar en la ficha"
        onCerrar={onCerrar}
        onGuardar={guardar}
        pie={(
          <div className="foto-pie">
            <select value={tipo} onChange={(e) => setTipo(e.target.value)} aria-label="Tipo de documento">
              {TIPOS.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <input value={descripcion} onChange={(e) => setDescripcion(e.target.value)} maxLength={200}
                   placeholder="Descripción: p. ej. Fisura en 46, vista oclusal" aria-label="Descripción" />
            {archivo && (
              <label className="anotador-casilla">
                <input type="checkbox" checked={conservar} onChange={(e) => setConservar(e.target.checked)} />
                Guardar también la foto sin marcas
              </label>
            )}
          </div>
        )}
      />
    );
  }

  const hayCamaraEnVivo = typeof navigator !== "undefined" && Boolean(navigator.mediaDevices?.getUserMedia);
  return (
    <Capa>
    <div className="anotador" role="dialog" aria-modal="true" aria-label="Foto para marcar">
      <div className="anotador-barra">
        <strong className="anotador-titulo">Foto para marcar</strong>
        <button type="button" className="anotador-boton" onClick={onCerrar}>✕ Cerrar</button>
      </div>
      {enVivo ? (
        <CamaraEnVivo onFoto={setArchivo} onCancelar={() => setEnVivo(false)} />
      ) : (
        <div className="foto-origen">
          <p>Toma una foto o elige una que ya tengas. Después podrás señalar con flechas, círculos y
            texto, y se guardará en los documentos del paciente.</p>
          <div className="foto-opciones">
            <button type="button" onClick={() => camaraRef.current?.click()}>
              <strong>Tomar foto</strong><span>Con la cámara del teléfono o la tableta</span>
            </button>
            {hayCamaraEnVivo && (
              <button type="button" onClick={() => setEnVivo(true)}>
                <strong>Cámara del equipo</strong><span>La webcam o la cámara del portátil</span>
              </button>
            )}
            <button type="button" onClick={() => archivoRef.current?.click()}>
              <strong>Subir foto</strong><span>Una imagen guardada (JPG, PNG…)</span>
            </button>
          </div>
          <input ref={camaraRef} type="file" accept="image/*" capture="environment" hidden onChange={elegido} />
          <input ref={archivoRef} type="file" accept="image/*" hidden onChange={elegido} />
        </div>
      )}
    </div>
    </Capa>
  );
}
