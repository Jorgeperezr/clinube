/**
 * Teléfonos con su código de país, para el selector de lib/CampoTelefono.js.
 * Puro (sin React) para poder probarlo con `node --test`.
 */

export const PAISES = [
  ["EC", "Ecuador", "+593", "🇪🇨"],
  ["CO", "Colombia", "+57", "🇨🇴"],
  ["PE", "Perú", "+51", "🇵🇪"],
  ["VE", "Venezuela", "+58", "🇻🇪"],
  ["CL", "Chile", "+56", "🇨🇱"],
  ["AR", "Argentina", "+54", "🇦🇷"],
  ["BO", "Bolivia", "+591", "🇧🇴"],
  ["BR", "Brasil", "+55", "🇧🇷"],
  ["PY", "Paraguay", "+595", "🇵🇾"],
  ["UY", "Uruguay", "+598", "🇺🇾"],
  ["PA", "Panamá", "+507", "🇵🇦"],
  ["CR", "Costa Rica", "+506", "🇨🇷"],
  ["GT", "Guatemala", "+502", "🇬🇹"],
  ["CU", "Cuba", "+53", "🇨🇺"],
  ["MX", "México", "+52", "🇲🇽"],
  ["US", "Estados Unidos / Canadá", "+1", "🇺🇸"],
  ["ES", "España", "+34", "🇪🇸"],
  ["IT", "Italia", "+39", "🇮🇹"],
  ["FR", "Francia", "+33", "🇫🇷"],
  ["DE", "Alemania", "+49", "🇩🇪"],
  ["GB", "Reino Unido", "+44", "🇬🇧"],
];

const PREDETERMINADO = "+593";

/** «+593 99 123 4567» → ["+593", "991234567"]; «0991234567» → ["+593", "0991234567"]. */
export function separar(valor) {
  const texto = (valor || "").trim();
  if (texto.startsWith("+")) {
    const cifras = texto.replace(/\D/g, "");
    const codigo = PAISES.map((p) => p[2]).sort((a, b) => b.length - a.length)
      .find((c) => cifras.startsWith(c.slice(1)));
    if (codigo) return [codigo, cifras.slice(codigo.length - 1)];
  }
  return [PREDETERMINADO, texto];
}

/** El número completo, sin el 0 nacional (salvo Italia, que lo marca siempre). */
export function unir(codigo, numero) {
  let n = (numero || "").replace(/[^\d ]/g, "").trim();
  if (!n) return "";
  if (codigo !== "+39") n = n.replace(/^0+/, "");
  return `${codigo} ${n}`;
}
