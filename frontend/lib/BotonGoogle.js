"use client";

/**
 * «Continuar con Google». Solo aparece si la plataforma configuró su ID
 * de cliente (Plataforma → Configuración). El botón lo dibuja Google con
 * su script oficial: no hay librería que instalar.
 */

import { useEffect, useRef, useState } from "react";

import { apiBase } from "./api";

const SCRIPT = "https://accounts.google.com/gsi/client";

function cargarScript() {
  if (typeof window === "undefined") return Promise.reject();
  if (window.google?.accounts?.id) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = SCRIPT; s.async = true; s.onload = resolve; s.onerror = reject;
    document.head.appendChild(s);
  });
}

export default function BotonGoogle({ alEntrar, texto = "continue_with" }) {
  const caja = useRef(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    let vivo = true;
    fetch(`${apiBase()}/api/v1/auth/google/config/`).then((r) => (r.ok ? r.json() : {}))
      .then(async ({ client_id: clientId }) => {
        if (!clientId || !vivo) return;
        await cargarScript();
        if (!vivo || !caja.current) return;
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: (r) => alEntrar(r.credential),
          ux_mode: "popup",
        });
        window.google.accounts.id.renderButton(caja.current, {
          theme: "outline", size: "large", text: texto, shape: "pill", locale: "es",
          width: Math.min(caja.current.offsetWidth || 320, 400),
        });
        setVisible(true);
      }).catch(() => {});
    return () => { vivo = false; };
  }, [alEntrar, texto]);

  return (
    <div style={{ display: visible ? "block" : "none" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "18px 0 14px", color: "var(--ink-faint)", fontSize: 13 }}>
        <span style={{ flex: 1, height: 1, background: "var(--line)" }} />o<span style={{ flex: 1, height: 1, background: "var(--line)" }} />
      </div>
      <div ref={caja} style={{ display: "flex", justifyContent: "center", minHeight: 44 }} />
    </div>
  );
}
