/**
 * /download/ es la misma página que /descargar/: así funciona también la
 * dirección en inglés que la gente prueba por costumbre. En producción
 * Nginx la redirige; esto cubre el servidor de desarrollo.
 */
export { default } from "../descargar/page";
