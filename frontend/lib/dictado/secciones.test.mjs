// Pruebas del orden por palabras clave. Sin dependencias:
//   node --test frontend/lib/dictado/*.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  aTextoNota, agregarFrase, aplicarPuntuacion, detectarSeccion, organizarDictado, pulir, unirPiezas,
} from "./secciones.mjs";

test("cada palabra clave al abrir la frase cambia de sección", () => {
  const s = organizarDictado([
    "Motivo dolor al masticar en el lado derecho",
    "Hallazgos caries oclusal en la 46",
    "procedimiento resina compuesta",
    "Indicaciones no masticar por ese lado durante dos horas",
  ]);
  assert.equal(s.motivo, "Dolor al masticar en el lado derecho");
  assert.equal(s.hallazgos, "Caries oclusal en la 46");
  assert.equal(s.procedimiento, "Resina compuesta");
  assert.equal(s.indicaciones, "No masticar por ese lado durante dos horas");
});

test("la palabra clave a mitad de frase NO cambia de sección", () => {
  const s = organizarDictado(["Hallazgos el motivo de la molestia es una fisura"]);
  assert.equal(s.hallazgos, "El motivo de la molestia es una fisura");
  assert.equal(s.motivo, "");
});

test("sin palabra clave al empezar, va al motivo; las frases sin clave siguen en la sección actual", () => {
  const s = organizarDictado(["dolor desde ayer", "hallazgos gingivitis", "sangrado al sondaje"]);
  assert.equal(s.motivo, "Dolor desde ayer");
  assert.equal(s.hallazgos, "Gingivitis sangrado al sondaje");
});

test("tildes, mayúsculas y variantes del disparador", () => {
  assert.equal(detectarSeccion("INDICACIÓN enjuague con clorhexidina").seccion, "indicaciones");
  assert.equal(detectarSeccion("Motivo de consulta control").resto, "control");
  assert.equal(detectarSeccion("tratamiento realizado profilaxis").seccion, "procedimiento");
  assert.equal(detectarSeccion("hallazgos dos puntos nada relevante").resto, "nada relevante");
  assert.equal(detectarSeccion("el paciente refiere dolor"), null);
});

test("puntuación dictada, pero «punto» a secas se respeta", () => {
  assert.equal(aplicarPuntuacion("caries en la 46 punto y seguido sin dolor"), "caries en la 46. Sin dolor");
  assert.equal(aplicarPuntuacion("ajustar punto de contacto"), "ajustar punto de contacto");
  assert.equal(aplicarPuntuacion("uno punto y aparte dos"), "uno.\nDos");
});

test("la nota solo lleva las secciones con contenido", () => {
  const nota = aTextoNota(organizarDictado(["motivo control", "indicaciones cepillado tres veces al día"]));
  assert.equal(nota, "Motivo: Control\nIndicaciones: Cepillado tres veces al día");
});

test("diagnóstico es una sección propia, entre hallazgos y procedimiento", () => {
  const nota = aTextoNota(organizarDictado([
    "hallazgos caries oclusal", "diagnóstico caries de dentina", "procedimiento resina",
  ]));
  assert.equal(nota, "Hallazgos: Caries oclusal\nDiagnóstico: Caries de dentina\nProcedimiento: Resina");
});

test("coma, punto y coma, punto final y paréntesis", () => {
  assert.equal(aplicarPuntuacion("sin dolor coma sin sangrado punto final"), "sin dolor, sin sangrado.");
  assert.equal(aplicarPuntuacion("resina punto y coma control en una semana"), "resina; control en una semana");
  assert.equal(aplicarPuntuacion("clorhexidina abre paréntesis 0,12 % cierra paréntesis dos veces"),
    "clorhexidina (0,12 %) dos veces");
});

test("tras un punto sin espacio no se pone mayúscula", () => {
  assert.equal(aplicarPuntuacion("ver www.clinube.com"), "ver www.clinube.com");
});

test("las piezas dictadas cifra a cifra se juntan en notación FDI", () => {
  assert.equal(unirPiezas("caries en la pieza 4 6"), "caries en la pieza 46");
  assert.equal(unirPiezas("Pieza cuatro seis"), "Pieza 46");
  assert.equal(unirPiezas("piezas 1 1, 2 1 y 3 1"), "piezas 11, 21 y 31");
  assert.equal(unirPiezas("molar 3 6 con movilidad"), "molar 36 con movilidad");
});

test("fuera de una pieza, los números se respetan", () => {
  assert.equal(unirPiezas("cepillar 2 3 veces al día"), "cepillar 2 3 veces al día");
  assert.equal(unirPiezas("pieza 9 1"), "pieza 9 1");     // no existe en FDI
  assert.equal(pulir("pieza 4 6 punto y seguido sin dolor"), "pieza 46. Sin dolor");
});

test("Chrome en Android repite la frase anterior: no se duplica", () => {
  let l = [];
  l = agregarFrase(l, "caries");
  l = agregarFrase(l, "caries en la 46");
  l = agregarFrase(l, "Caries en la 46");
  l = agregarFrase(l, "hallazgos gingivitis");
  assert.deepEqual(l, ["caries en la 46", "hallazgos gingivitis"]);
  assert.deepEqual(agregarFrase(["uno"], "  "), ["uno"]);
});

test("una frase que empieza con un signo sigue detectando la sección", () => {
  assert.equal(detectarSeccion("- motivo control").resto, "control");
});
