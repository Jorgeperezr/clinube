// node --test frontend/lib/*.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  aImagen, aPantalla, agregarPunto, aletasFlecha, anchoConPresion, confirmar, desplazar, deshacer,
  dibujarMarca, encuadrar, esClaro, historialVacio, marcaEn, rehacer, restringirAngulo,
  restringirCuadrado, toca, unidad, zoomEn,
} from "./anotacion.mjs";

const cerca = (a, b, eps = 1e-6) => assert.ok(Math.abs(a - b) < eps, `${a} ≉ ${b}`);

test("la foto entra entera y centrada en el lienzo", () => {
  const v = encuadrar(4000, 3000, 1032, 800, 16);
  cerca(v.escala, 0.25);
  cerca(v.dx, 16);
  cerca(v.dy, 25);
});

test("pantalla e imagen son inversas: las marcas no se mueven al ampliar", () => {
  const v = { escala: 2.5, dx: -120, dy: 40 };
  const [x, y] = aPantalla(aImagen([333, 444], v), v);
  cerca(x, 333);
  cerca(y, 444);
});

test("el zoom deja quieto el punto bajo el cursor", () => {
  const v = { escala: 1, dx: 10, dy: 20 };
  const bajoCursor = aImagen([300, 200], v);
  const z = zoomEn(v, 3, [300, 200]);
  const [x, y] = aPantalla(bajoCursor, z);
  cerca(x, 300);
  cerca(y, 200);
  assert.equal(zoomEn(v, 1000, [0, 0]).escala, 16);   // con tope
});

test("el grosor se mide en milésimas de la foto", () => {
  assert.equal(unidad(4000, 3000), 4);
  assert.equal(unidad(600, 800), 0.8);
});

test("la presión del lápiz cambia el ancho; el ratón no", () => {
  assert.equal(anchoConPresion(10, 0.5), 10);   // ratón
  assert.equal(anchoConPresion(10, 0), 10);     // táctil sin presión
  assert.ok(anchoConPresion(10, 0.1) < 10);
  assert.ok(anchoConPresion(10, 1) > 10);
});

test("los puntos casi repetidos no se guardan", () => {
  let p = agregarPunto([], [0, 0, 0.5], 1);
  p = agregarPunto(p, [0.3, 0.2, 0.5], 1);
  p = agregarPunto(p, [2, 0, 0.5], 1);
  assert.equal(p.length, 2);
});

test("con Mayús, líneas a 15° y cuadrados", () => {
  const [x, y] = restringirAngulo([0, 0], [100, 4]);
  cerca(y, 0);
  cerca(x, Math.hypot(100, 4));
  const [a, b] = restringirAngulo([0, 0], [50, 52]);
  cerca(a, b, 1e-9);
  assert.deepEqual(restringirCuadrado([10, 10], [40, -5]), [40, -20]);
});

test("el borrador acierta la marca de más arriba", () => {
  const marcas = [
    { tipo: "linea", a: [0, 0], b: [100, 0], ancho: 4 },
    { tipo: "rect", a: [40, -20], b: [60, 20], ancho: 2 },
    { tipo: "trazo", puntos: [[0, 50], [100, 50]], ancho: 6 },
  ];
  assert.equal(marcaEn(marcas, [50, 1], 2), 0);       // la línea, dentro del rect (que es hueco)
  assert.equal(marcaEn(marcas, [40, 10], 2), 1);      // borde del rect
  assert.equal(marcaEn(marcas, [70, 52], 1), 2);      // el trazo, por su grosor
  assert.equal(marcaEn(marcas, [70, 30], 1), -1);
});

test("elipse y texto también se tocan", () => {
  const elipse = { tipo: "elipse", a: [0, 0], b: [100, 50], ancho: 2 };
  assert.ok(toca(elipse, [100, 25], 2));
  assert.ok(!toca(elipse, [50, 25], 2));               // el centro, no
  const texto = { tipo: "texto", x: 10, y: 10, texto: "caries\nmesial", tamano: 20 };
  assert.ok(toca(texto, [20, 40], 0));
  assert.ok(!toca(texto, [200, 40], 0));
});

test("mover una marca la desplaza entera y conserva la presión", () => {
  const t = desplazar({ tipo: "trazo", puntos: [[1, 1, 0.8]] }, [10, 5]);
  assert.deepEqual(t.puntos, [[11, 6, 0.8]]);
  assert.deepEqual(desplazar({ tipo: "texto", x: 1, y: 2 }, [1, 1]), { tipo: "texto", x: 2, y: 3 });
  assert.deepEqual(desplazar({ tipo: "linea", a: [0, 0], b: [1, 1] }, [2, 2]).b, [3, 3]);
});

test("deshacer y rehacer", () => {
  let h = confirmar(historialVacio, ["a"]);
  h = confirmar(h, ["a", "b"]);
  h = deshacer(h);
  assert.deepEqual(h.presente, ["a"]);
  h = rehacer(h);
  assert.deepEqual(h.presente, ["a", "b"]);
  h = deshacer(deshacer(h));
  assert.deepEqual(h.presente, []);
  assert.equal(deshacer(h), h);
  h = confirmar(h, ["c"]);
  assert.equal(h.futuro.length, 0);                   // una marca nueva borra lo rehacible
});

test("la punta de la flecha apunta al extremo", () => {
  const [i, d] = aletasFlecha([0, 0], [100, 0], 4);
  assert.ok(i[0] < 100 && d[0] < 100);
  cerca(i[1], -d[1]);
});

test("se dibuja cada tipo con su color y grosor", () => {
  const llamadas = [];
  const ctx = new Proxy({}, {
    get: (obj, k) => (k in obj ? obj[k] : (k === "measureText" ? () => ({ width: 50 }) : (...a) => llamadas.push([k, ...a]))),
    set: (obj, k, v) => { obj[k] = v; llamadas.push([`=${String(k)}`, v]); return true; },
  });
  dibujarMarca(ctx, { tipo: "flecha", a: [0, 0], b: [50, 0], color: "#ef4444", ancho: 3 });
  assert.ok(llamadas.some(([k, v]) => k === "=strokeStyle" && v === "#ef4444"));
  assert.ok(llamadas.some(([k]) => k === "fill"));     // la punta
  llamadas.length = 0;
  dibujarMarca(ctx, { tipo: "texto", x: 5, y: 5, texto: "46", tamano: 30, color: "#ffffff", fondo: true });
  assert.ok(llamadas.some(([k, t]) => k === "fillText" && t === "46"));
  assert.ok(llamadas.some(([k]) => k === "fillRect"));
});

test("claro u oscuro", () => {
  assert.ok(esClaro("#ffffff"));
  assert.ok(esClaro("#facc15"));
  assert.ok(!esClaro("#111827"));
  assert.ok(!esClaro("#3b82f6"));
});
