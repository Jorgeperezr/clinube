"use client";

/**
 * Campo de contraseña con el botón del ojo para verla mientras se
 * escribe. Recibe las mismas props que un <input>; el tipo lo decide él.
 *
 * Vuelve a ocultarse al enviar el formulario: si alguien deja la
 * contraseña a la vista y se levanta, no queda así en la pantalla
 * siguiente.
 */

import { useEffect, useRef, useState } from "react";

export default function CampoClave(props) {
  const [visible, setVisible] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const form = ref.current?.form;
    if (!form) return undefined;
    const ocultar = () => setVisible(false);
    form.addEventListener("submit", ocultar);
    return () => form.removeEventListener("submit", ocultar);
  }, []);

  return (
    <span className="campo-clave">
      <input {...props} ref={ref} type={visible ? "text" : "password"}
             autoCapitalize="off" autoCorrect="off" spellCheck={false} />
      <button type="button" aria-label={visible ? "Ocultar contraseña" : "Mostrar contraseña"}
              aria-pressed={visible} title={visible ? "Ocultar contraseña" : "Mostrar contraseña"}
              onClick={() => { setVisible((v) => !v); ref.current?.focus(); }}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
             strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" />
          <circle cx="12" cy="12" r="3" />
          {visible && <path d="M4 4l16 16" />}
        </svg>
      </button>
    </span>
  );
}
