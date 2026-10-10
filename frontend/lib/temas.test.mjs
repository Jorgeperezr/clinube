// node --test frontend/lib/*.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";

import { colorHex, leerPaleta, opcionesDeTema, resolverTemaPersonal } from "./temas.mjs";

const PRESETS = [
  { key: "default", label: "Clinube (original)", primary: "#0e7490", secondary: "#67e8f9", nav: "#0b1220" },
  { key: "sin_color", label: "Sin color", primary: "#404040", secondary: "#9ca3af", nav: "#111111" },
  { key: "bosque", label: "Bosque", primary: "#1d6b3c", secondary: "#b6e2c5" },
];
const TEMAS_CLINICA = [
  { clave: "principal", nombre: "Principal", descripcion: "El de la marca.",
    primary: "#7b1e3c", secondary: "#f0c9d4", nav: "#1a0a10" },
  { clave: "alterno", nombre: "Alterno", primary: "#f0c9d4", secondary: "#7b1e3c" },
];
const DATOS = { presets: PRESETS, temasClinica: TEMAS_CLINICA };

test("sin elección, manda el de la clínica", () => {
  assert.equal(resolverTemaPersonal("", DATOS), null);
  assert.equal(resolverTemaPersonal(undefined, DATOS), null);
});

test("uno de la clínica, con sus colores y su navegación", () => {
  assert.deepEqual(resolverTemaPersonal("clinica:principal", DATOS),
    { key: "clinica:principal", primary: "#7b1e3c", secondary: "#f0c9d4", nav: "#1a0a10" });
});

test("uno de Clinube", () => {
  assert.equal(resolverTemaPersonal("clinube:bosque", DATOS).primary, "#1d6b3c");
});

test("si el elegido ya no existe, vuelve al de la clínica en vez de pintar en negro", () => {
  // La clínica cambió su paleta y el «alterno» dejó de salir, o el tema
  // de Clinube se retiró: nada de colores rotos.
  assert.equal(resolverTemaPersonal("clinica:sobrio", DATOS), null);
  assert.equal(resolverTemaPersonal("clinube:inventado", DATOS), null);
  assert.equal(resolverTemaPersonal("otro:bosque", DATOS), null);
});

test("las opciones: primero los de la clínica, luego los de Clinube y sin «Sin color»", () => {
  const grupos = opcionesDeTema(DATOS);
  assert.deepEqual(grupos.map((g) => g.grupo), ["clinica", "clinube"]);
  assert.deepEqual(grupos[0].temas.map((t) => t.clave), ["clinica:principal", "clinica:alterno"]);
  assert.deepEqual(grupos[1].temas.map((t) => t.clave), ["clinube:default", "clinube:bosque"]);
});

test("una clínica sin paleta solo ofrece los de Clinube", () => {
  const grupos = opcionesDeTema({ presets: PRESETS, temasClinica: [] });
  assert.deepEqual(grupos.map((g) => g.grupo), ["clinube"]);
});

test("colores: formas cortas, mayúsculas y almohadilla opcional", () => {
  assert.equal(colorHex("#ABC"), "#aabbcc");
  assert.equal(colorHex(" 0E7490 "), "#0e7490");
  assert.equal(colorHex("azul"), "");
  assert.equal(colorHex("#12345"), "");
});

test("una paleta pegada se lee como la lee el servidor", () => {
  assert.deepEqual(leerPaleta("#0e7490, #67E8F9; 0b1220 #0E7490"),
    { colores: ["#0e7490", "#67e8f9", "#0b1220"], malos: [] });
  assert.deepEqual(leerPaleta("#0e7490 verde").malos, ["verde"]);
});
