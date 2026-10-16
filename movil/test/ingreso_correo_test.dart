/// El ingreso cuando la plataforma manda el código por correo.
///
/// Las respuestas de `fixtures/otp-*.json` están capturadas de la API
/// (ver movil/README.md): si cambian los nombres de los campos en
/// apps/accounts/views.py, hay que recapturarlas, no retocarlas.
library;

import 'dart:convert';
import 'dart:io';

import 'package:clinube/api/cliente.dart';
import 'package:clinube/pantallas/ingreso.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'sesion_falsa.dart';

String _fixture(String nombre) =>
    File('test/fixtures/$nombre.json').readAsStringSync();

http.Response _json(String cuerpo, [int estado = 200]) => http.Response(
    cuerpo, estado,
    headers: {'content-type': 'application/json; charset=utf-8'});

void main() {
  group('Canal del código', () {
    test('lo dice la plataforma', () async {
      final api = ClienteApi(
          urlBase: 'http://x',
          sesion: SesionFalsa(),
          http_: MockClient((req) async => _json(_fixture('otp-canal-correo'))));
      expect(await api.canalDelCodigo(), 'correo');
    });

    test('con WhatsApp, WhatsApp', () async {
      final api = ClienteApi(
          urlBase: 'http://x',
          sesion: SesionFalsa(),
          http_:
              MockClient((req) async => _json(_fixture('otp-canal-whatsapp'))));
      expect(await api.canalDelCodigo(), 'whatsapp');
    });

    test('si no se puede preguntar, correo: es el canal de todos', () async {
      final api = ClienteApi(
          urlBase: 'http://x',
          sesion: SesionFalsa(),
          http_: MockClient((req) async => http.Response('no', 404)));
      expect(await api.canalDelCodigo(), 'correo');
    });
  });

  testWidgets('con correo pide el correo y lo manda como email',
      (tester) async {
    final pedidos = <Map<String, dynamic>>[];
    final falso = MockClient((req) async {
      if (req.url.path.endsWith('/auth/otp/canal/')) {
        return _json(_fixture('otp-canal-correo'));
      }
      pedidos.add(jsonDecode(req.body) as Map<String, dynamic>);
      return _json(_fixture('otp-pedido-correo'), 202);
    });
    final api =
        ClienteApi(urlBase: 'http://x', sesion: SesionFalsa(), http_: falso);

    await tester.pumpWidget(
        MaterialApp(home: PantallaIngreso(api: api, alEntrar: () {})));
    await tester.pumpAndSettle();

    expect(find.text('Correo electrónico'), findsOneWidget);
    expect(find.text('Teléfono'), findsNothing);

    await tester.enterText(
        find.byType(TextField).first, 'lucia.andrade@gmail.com');
    await tester.tap(find.text('Enviarme el código'));
    await tester.pumpAndSettle();

    expect(pedidos.single, {'email': 'lucia.andrade@gmail.com'});
    // Lo que contestó el servidor: adónde llegó, sin el correo entero.
    expect(find.textContaining('lu***@gmail.com'), findsOneWidget);
    expect(find.text('Código de 6 dígitos'), findsOneWidget);
    expect(find.text('Usar otro correo'), findsOneWidget);
  });

  testWidgets('con WhatsApp sigue pidiendo el teléfono', (tester) async {
    final falso =
        MockClient((req) async => _json(_fixture('otp-canal-whatsapp')));
    final api =
        ClienteApi(urlBase: 'http://x', sesion: SesionFalsa(), http_: falso);

    await tester.pumpWidget(
        MaterialApp(home: PantallaIngreso(api: api, alEntrar: () {})));
    await tester.pumpAndSettle();

    expect(find.text('Teléfono'), findsOneWidget);
    expect(find.text('Correo electrónico'), findsNothing);
  });
}
