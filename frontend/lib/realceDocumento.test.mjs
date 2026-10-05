// node --test frontend/lib/*.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  bytesDeDataUrl, medidaDestino, niveles, orientacion, realzar, tamanoLegible,
} from "./realceDocumento.mjs";

/** Una «foto» RGBA con los grises dados, un píxel por valor. */
function foto(grises) {
  const d = new Uint8ClampedArray(grises.length * 4);
  grises.forEach((g, i) => { d.set([g, g, g, 255], i * 4); });
  return d;
}

/** Papel gris oscuro (110) con tinta (40): una foto con poca luz. */
function fotoOscura() {
  return foto(Array.from({ length: 4000 }, (_, i) => (i % 10 === 0 ? 40 : 110)));
}

test("los niveles salen del histograma de la propia foto", () => {
  const { negro, blanco } = niveles(fotoOscura(), { paso: 1 });
  assert.equal(negro, 40);
  assert.equal(blanco, 110);
});

test("modo documento: con poca luz, el papel queda blanco y la tinta negra", () => {
  const d = fotoOscura();
  realzar(d, "documento");
  assert.equal(d[4], 255);          // un píxel de papel
  assert.equal(d[0], 0);            // un píxel de tinta
  assert.equal(d[3], 255);          // la opacidad no se toca
});

test("modo documento convierte a grises", () => {
  const d = new Uint8ClampedArray(4000 * 4);
  for (let i = 0; i < d.length; i += 4) d.set(i % 40 ? [200, 60, 60, 255] : [20, 20, 200, 255], i);
  realzar(d, "documento");
  assert.equal(d[4], d[5]);
  assert.equal(d[5], d[6]);
});

test("modo color conserva el color (una firma en azul sigue azul)", () => {
  const d = new Uint8ClampedArray(4000 * 4);
  for (let i = 0; i < d.length; i += 4) d.set(i % 40 ? [150, 150, 150, 255] : [30, 30, 140, 255], i);
  realzar(d, "color");
  assert.ok(d[2] > d[0] + 50, `azul ${d[2]} frente a rojo ${d[0]}`);
});

test("una página casi uniforme no se estira hasta ser ruido", () => {
  const d = foto(Array.from({ length: 1000 }, (_, i) => 120 + (i % 5)));
  assert.deepEqual(niveles(d), { negro: 0, blanco: 255 });
  realzar(d, "color");
  assert.ok(d[0] >= 118 && d[0] <= 126);
});

test("original no toca nada", () => {
  const d = fotoOscura();
  const antes = Uint8ClampedArray.from(d);
  assert.equal(realzar(d, "original"), null);
  assert.deepEqual(d, antes);
});

test("medidas: se reduce lo grande y no se agranda lo pequeño", () => {
  assert.deepEqual(medidaDestino(4032, 3024), { ancho: 2200, alto: 1650 });
  assert.deepEqual(medidaDestino(3024, 4032), { ancho: 1650, alto: 2200 });
  assert.deepEqual(medidaDestino(1280, 720), { ancho: 1280, alto: 720 });
});

test("la página del PDF se gira con la foto", () => {
  assert.equal(orientacion(1920, 1080), "landscape");
  assert.equal(orientacion(1080, 1920), "portrait");
});

test("peso de una data URL y cómo se dice", () => {
  // «hola» en base64 es aGFsYQ== (4 bytes).
  assert.equal(bytesDeDataUrl("data:image/jpeg;base64,aGFsYQ=="), 4);
  assert.equal(tamanoLegible(1536 * 1024), "1,5 MB");
  assert.equal(tamanoLegible(300), "1 KB");
});
