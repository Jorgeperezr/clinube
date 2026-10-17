import assert from "node:assert/strict";
import test from "node:test";

import { separar, unir } from "./telefono.mjs";

test("Ecuador de serie y sin el 0 nacional", () => {
  assert.deepEqual(separar(""), ["+593", ""]);
  assert.deepEqual(separar("0991234567"), ["+593", "0991234567"]);
  assert.equal(unir("+593", "099 123 4567"), "+593 99 123 4567");
  assert.equal(unir("+593", ""), "");
});

test("lo que ya trae prefijo elige su país", () => {
  assert.deepEqual(separar("+593 991234567"), ["+593", "991234567"]);
  assert.deepEqual(separar("+57 300 123 4567"), ["+57", "3001234567"]);
  assert.deepEqual(separar("+1 305 555 1234"), ["+1", "3055551234"]);
  assert.equal(unir("+39", "06 1234 5678"), "+39 06 1234 5678");   // Italia marca el 0
});
