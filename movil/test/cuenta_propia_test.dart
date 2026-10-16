/// El paciente crea su propia cuenta y espera a que su clínica le dé
/// acceso a su ficha.
///
/// `otp-sin-cuenta`, `otp-cuenta-creada` y `cuenta-esperando` están
/// capturadas de la API (ver movil/README.md): si cambian los campos en
/// apps/accounts/views.py o apps/app_paciente/views.py, se recapturan.
library;

import 'dart:convert';
import 'dart:io';

import 'package:clinube/api/cliente.dart';
import 'package:clinube/api/modelos.dart';
import 'package:clinube/pantallas/espera.dart';
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
  testWidgets('un correo sin cuenta ofrece crearla y la crea con el nombre',
      (tester) async {
    final pedidos = <Map<String, dynamic>>[];
    final falso = MockClient((req) async {
      if (req.url.path.endsWith('/auth/otp/canal/')) {
        return _json(_fixture('otp-canal-correo'));
      }
      final cuerpo = jsonDecode(req.body) as Map<String, dynamic>;
      pedidos.add(cuerpo);
      return cuerpo['crear'] == true
          ? _json(_fixture('otp-cuenta-creada'), 202)
          : _json(_fixture('otp-sin-cuenta'), 400);
    });
    final api =
        ClienteApi(urlBase: 'http://x', sesion: SesionFalsa(), http_: falso);

    await tester.pumpWidget(
        MaterialApp(home: PantallaIngreso(api: api, alEntrar: () {})));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField).first, 'nueva@gmail.com');
    await tester.tap(find.text('Enviarme el código'));
    await tester.pumpAndSettle();

    // No es un error: se le ofrece crearla.
    expect(find.textContaining('Aún no tienes cuenta'), findsOneWidget);
    expect(find.text('Tu nombre y apellido'), findsOneWidget);

    await tester.enterText(find.byType(TextField).at(1), 'Lucía Paz');
    await tester.tap(find.text('Crear mi cuenta'));
    await tester.pumpAndSettle();

    expect(pedidos.last,
        {'email': 'nueva@gmail.com', 'crear': true, 'nombre': 'Lucía Paz'});
    expect(find.text('Código de 6 dígitos'), findsOneWidget);
  });

  test('el estado de una cuenta que espera a su clínica', () {
    final estado = EstadoCuenta.desdeJson(
        jsonDecode(_fixture('cuenta-esperando')) as Map<String, dynamic>);
    expect(estado.enlazada, isFalse);
    expect(estado.clinica, isNull);
    expect(estado.correo, 'captura.app@ejemplo.ec');
  });

  testWidgets('la pantalla de espera dice qué correo dar en la recepción',
      (tester) async {
    var enlazada = false;
    final api = ClienteApi(
      urlBase: 'http://x',
      sesion: SesionFalsa(),
      http_: MockClient((req) async => _json(jsonEncode({
            ...jsonDecode(_fixture('cuenta-esperando')) as Map<String, dynamic>,
            'enlazada': true,
          }))),
    );
    final estado = EstadoCuenta.desdeJson(
        jsonDecode(_fixture('cuenta-esperando')) as Map<String, dynamic>);
    await tester.pumpWidget(MaterialApp(
        home: PantallaEspera(
            api: api,
            estado: estado,
            alEnlazar: () => enlazada = true,
            alSalir: () {})));

    expect(find.text('captura.app@ejemplo.ec'), findsOneWidget);
    await tester.tap(find.text('Ya me dieron acceso'));
    await tester.pumpAndSettle();
    expect(enlazada, isTrue);
  });
}
