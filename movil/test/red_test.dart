/// Lo que pasa con la app instalada y una red de verdad: respuestas sin
/// charset, sin cobertura, servidor lento, certificado falso y sesión
/// caducada. Ninguna de estas cosas debe dejar al paciente atascado.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:clinube/api/cliente.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'sesion_falsa.dart';

Future<ClienteApi> _api(MockClientHandler responder,
    {Duration espera = tiempoMaximo}) async {
  final sesion = SesionFalsa();
  await sesion.guardar('acceso', 'refresco');
  return ClienteApi(
      urlBase: 'https://x',
      sesion: sesion,
      http_: MockClient(responder),
      espera: espera);
}

void main() {
  test('sin charset en la respuesta, las tildes llegan bien', () async {
    // Lo que manda Django de verdad: «application/json» a secas y UTF-8.
    final api = await _api((req) async => http.Response.bytes(
        utf8.encode('{"nombre": "Ana Pérez Núñez", "clinica": "Clínica Añil"}'),
        200,
        headers: {'content-type': 'application/json'}));
    final datos = await api.objeto('/app/me/');
    expect(datos['nombre'], 'Ana Pérez Núñez');
    expect(datos['clinica'], 'Clínica Añil');
  });

  test('el mensaje de error del servidor también llega con tildes', () async {
    final api = await _api((req) async => http.Response.bytes(
        utf8.encode('{"detail": "Este teléfono no está registrado."}'), 400,
        headers: {'content-type': 'application/json'}));
    await expectLater(
        api.pedirCodigo('0999'),
        throwsA(isA<ErrorDeApi>().having(
            (e) => e.mensaje, 'mensaje', 'Este teléfono no está registrado.')));
  });

  test('sin cobertura se dice en castellano', () async {
    final api = await _api(
        (req) async => throw const SocketException('Failed host lookup'));
    await expectLater(
        api.objeto('/app/me/'),
        throwsA(isA<ErrorDeApi>().having(
            (e) => e.mensaje, 'mensaje', contains('Revisa tu conexión'))));
  });

  test('un servidor que no contesta no deja la pantalla girando', () async {
    final api = await _api((req) => Completer<http.Response>().future,
        espera: const Duration(milliseconds: 50));
    await expectLater(
        api.objeto('/app/me/'),
        throwsA(isA<ErrorDeApi>()
            .having((e) => e.mensaje, 'mensaje', contains('tarda demasiado'))));
  });

  test('un certificado no válido no se acepta', () async {
    final api = await _api((req) async =>
        throw const HandshakeException('CERTIFICATE_VERIFY_FAILED'));
    await expectLater(
        api.objeto('/app/me/'),
        throwsA(isA<ErrorDeApi>()
            .having((e) => e.mensaje, 'mensaje', contains('conexión segura'))));
  });

  test('si el refresco ya no vale, se avisa para volver al ingreso', () async {
    var avisos = 0;
    final api = await _api(
        (req) async => http.Response('{"detail": "Token inválido"}', 401));
    api.alCaducarSesion = () => avisos++;
    await expectLater(api.objeto('/app/me/'), throwsA(isA<ErrorDeApi>()));
    expect(avisos, 1);
    expect(await api.sesion.hayTokens, isFalse);
  });

  test('un fallo del servidor al refrescar no cierra la sesión', () async {
    final api = await _api((req) async =>
        req.url.path.endsWith('/token/refresh/')
            ? http.Response('<html>502</html>', 502)
            : http.Response('{}', 401));
    var avisos = 0;
    api.alCaducarSesion = () => avisos++;
    await expectLater(api.objeto('/app/me/'), throwsA(isA<ErrorDeApi>()));
    expect(avisos, 0);
    expect(await api.sesion.hayTokens, isTrue);
  });
}
