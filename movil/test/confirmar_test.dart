/// Confirmar asistencia desde la pestaña Citas, con las respuestas
/// capturadas de la API real (antes y después de confirmar).
library;

import 'dart:convert';
import 'dart:io';

import 'package:clinube/api/cliente.dart';
import 'package:clinube/api/modelos.dart';
import 'package:clinube/pantallas/principal.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'sesion_falsa.dart';

String _fixture(String n) => File('test/fixtures/$n.json').readAsStringSync();

void main() {
  setUpAll(() async => initializeDateFormatting('es'));

  test('la API dice qué citas se pueden confirmar', () {
    final antes = Agenda.desdeJson(
        jsonDecode(_fixture('citas-por-confirmar')) as Map<String, dynamic>);
    expect(antes.proximas.single.sePuedeConfirmar, isTrue);
    expect(antes.anteriores.single.sePuedeConfirmar, isFalse);

    final despues = Cita.desdeJson(
        jsonDecode(_fixture('cita-confirmada')) as Map<String, dynamic>);
    expect(despues.estado, 'Confirmada');
    expect(despues.sePuedeConfirmar, isFalse);
  });

  testWidgets('se confirma desde la pestaña Citas y el botón desaparece',
      (tester) async {
    final pedidas = <String>[];
    final sesion = SesionFalsa();
    await sesion.guardar('a', 'r');
    final api = ClienteApi(
      urlBase: 'http://x',
      sesion: sesion,
      http_: MockClient((req) async {
        pedidas.add('${req.method} ${req.url.path}');
        final ruta = req.url.path;
        final cuerpo = ruta.endsWith('/confirmar/')
            ? _fixture('cita-confirmada')
            : ruta.endsWith('/app/citas/')
                ? _fixture('citas-por-confirmar')
                : ruta.endsWith('/app/me/')
                    ? _fixture('me')
                    : '[]';
        return http.Response.bytes(utf8.encode(cuerpo), 200,
            headers: {'content-type': 'application/json'});
      }),
    );

    await tester.pumpWidget(
        MaterialApp(home: PantallaPrincipal(api: api, alSalir: () {})));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Citas'));
    await tester.pumpAndSettle();

    expect(find.textContaining('Pendiente'), findsOneWidget);
    await tester.tap(find.text('Confirmar asistencia'));
    await tester.pumpAndSettle();

    expect(pedidas.where((p) => p.startsWith('POST')).single,
        endsWith('/confirmar/'));
    expect(find.text('Confirmar asistencia'), findsNothing);
    expect(find.textContaining('Confirmada'), findsOneWidget);
    expect(find.text('Listo, la clínica ya sabe que irás.'), findsOneWidget);
  });
}
