"use client";

/**
 * Aviso de privacidad, público: lo enlazan la pantalla de entrada del
 * panel y la de la app, y la clínica puede mostrarlo o imprimirlo para
 * entregárselo al paciente (la entrega se registra en su ficha).
 */

import TextoLegal, { PaginaLegal, useTextoLegal } from "../../lib/TextoLegal";

export default function PrivacidadPage() {
  const { datos, error } = useTextoLegal("privacidad");
  return (
    <PaginaLegal>
      <TextoLegal datos={datos} error={error} />
      {datos && (
        <p className="legal-pie">
          <button type="button" className="btn" onClick={() => window.print()}>Imprimir</button>
        </p>
      )}
    </PaginaLegal>
  );
}
