"use client";

/**
 * Monta su contenido directamente en <body>.
 *
 * Las ventanas a pantalla completa (escáner, marcar fotos, vista previa)
 * usan `position: fixed`, pero un `fixed` deja de ser relativo a la
 * pantalla en cuanto algún antecesor tiene `transform`, `filter` o
 * `backdrop-filter` —el panel los usa para el efecto de cristal y para
 * animar la entrada de cada página—: la capa quedaba recortada dentro
 * del contenido, con la barra lateral y la cita flotante encima.
 */

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

export default function Capa({ children }) {
  const [montada, setMontada] = useState(false);
  useEffect(() => setMontada(true), []);
  return montada ? createPortal(children, document.body) : null;
}
