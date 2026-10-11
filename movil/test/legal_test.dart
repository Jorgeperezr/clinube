/// El aviso de privacidad en la app: se lee el que da el servidor y se
/// puede abrir antes de entrar.
library;

import 'dart:convert';
import 'dart:io';

import 'package:clinube/api/cliente.dart';
import 'package:clinube/api/modelos.dart';
import 'package:clinube/pantallas/aviso_privacidad.dart';
import 'package:clinube/pantallas/ingreso.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'sesion_falsa.dart';

String _fixture(String n) => File('test/fixtures/$n.json').readAsStringSync();

ClienteApi _api({List<String>? pedidas}) => ClienteApi(
      urlBase: 'http://x',
      sesion: SesionFalsa(),
      http_: MockClient((req) async {
        pedidas?.add(req.url.path);
        return http.Response.bytes(utf8.encode(_fixture('legal-privacidad')), 200,
            headers: {'content-type': 'application/json'});
      }),
    );

void main() {
  test('se lee el aviso tal como lo da la API', () {
    final doc = DocumentoLegal.desdeJson(
        jsonDecode(_fixture('legal-privacidad')) as Map<String, dynamic>);
    expect(doc.titulo, 'Aviso de privacidad');
    expect(doc.version, isNotEmpty);
    expect(doc.secciones.map((s) => s.$1), contains('Tus derechos'));
    final todo = doc.secciones.expand((s) => s.$2).join(' ');
    expect(todo, contains('Oracle'));
    expect(todo, contains('Superintendencia de Protección de Datos Personales'));
  });

  testWidgets('se abre desde el ingreso, sin haber entrado', (tester) async {
    final pedidas = <String>[];
    await tester.pumpWidget(MaterialApp(
        home: PantallaIngreso(api: _api(pedidas: pedidas), alEntrar: () {})));

    final enlace = find.text('Aviso de privacidad');
    await tester.scrollUntilVisible(enlace, 100, scrollable: find.byType(Scrollable).first);
    await tester.tap(enlace);
    await tester.pumpAndSettle();

    expect(find.byType(PantallaAvisoPrivacidad), findsOneWidget);
    // La primera la hace el ingreso al abrirse: por dónde llega el código.
    expect(pedidas, ['/api/v1/auth/otp/canal/', '/api/v1/legal/privacidad/']);
    expect(find.text('Quién trata tus datos'), findsOneWidget);
    // Las acentuadas llegan bien aunque la API no diga el juego de caracteres.
    expect(find.textContaining('la clínica o el consultorio'), findsOneWidget);
  });
}
