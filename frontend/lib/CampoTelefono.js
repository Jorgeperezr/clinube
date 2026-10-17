"use client";

/**
 * Teléfono con su código de país: un selector (Ecuador, +593, de serie) y
 * el número tal como se marca en el país. Devuelve «+593 991234567»: con
 * el prefijo, que es como la API lo normaliza a E.164
 * (apps/common/telefonos.py) y como lo necesita WhatsApp.
 *
 * El 0 inicial del número nacional se quita al guardar: «0991234567» en
 * Ecuador es +593 991234567. Si lo escrito ya trae «+», se respeta y se
 * elige ese país solo.
 */

import { useEffect, useState } from "react";

import { PAISES, separar, unir } from "./telefono.mjs";

export default function CampoTelefono({ valor, alCambiar, id, required, placeholder = "99 123 4567", etiquetaPais = "Código de país" }) {
  const [codigo, setCodigo] = useState(() => separar(valor)[0]);
  const [numero, setNumero] = useState(() => separar(valor)[1]);

  // Si el valor cambia desde fuera (otra ficha, recargar), se vuelve a separar.
  useEffect(() => {
    if (unir(codigo, numero) !== (valor || "")) {
      const [c, n] = separar(valor);
      setCodigo(c); setNumero(n);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [valor]);

  function cambiar(c, n) {
    setCodigo(c); setNumero(n);
    alCambiar(unir(c, n));
  }

  return (
    <div style={{ display: "flex", gap: 6 }}>
      <select aria-label={etiquetaPais} value={codigo} onChange={(e) => cambiar(e.target.value, numero)}
              style={{ flex: "0 0 auto", width: 112 }}>
        {PAISES.map(([iso, nombre, c, bandera]) => (
          <option key={iso} value={c} title={nombre}>{bandera} {c}</option>
        ))}
      </select>
      <input id={id} type="tel" inputMode="tel" autoComplete="tel-national" required={required}
             value={numero} placeholder={placeholder} maxLength={18}
             onChange={(e) => cambiar(codigo, e.target.value)} style={{ flex: 1, minWidth: 0 }} />
    </div>
  );
}
