/// «Eliminar mi cuenta»: lo exige Apple y aquí se tramita con la clínica.
library;

import 'dart:convert';

import 'package:clinube/api/cliente.dart';
import 'package:clinube/pantallas/perfil.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'sesion_falsa.dart';

void main() {
  testWidgets('pedir eliminar la cuenta envía la solicitud a la clínica',
      (tester) async {
    final enviados = <Map<String, dynamic>>[];
    final sesion = SesionFalsa();
    await sesion.guardar('a', 'r');
    final api = ClienteApi(
      urlBase: 'https://x',
      sesion: sesion,
      http_: MockClient((req) async {
        if (req.method == 'POST') {
          enviados.add(jsonDecode(req.body) as Map<String, dynamic>);
        }
        return http.Response('{"id": "m1"}', 201);
      }),
    );
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: Builder(
            builder: (context) => TextButton(
                  onPressed: () => pedirEliminarCuenta(context, api),
                  child: const Text('Eliminar mi cuenta'),
                )),
      ),
    ));

    await tester.tap(find.text('Eliminar mi cuenta'));
    await tester.pumpAndSettle();
    expect(find.textContaining('historia clínica no se borra'), findsOneWidget);

    await tester.tap(find.text('Enviar solicitud'));
    await tester.pumpAndSettle();
    expect(enviados.single['texto'], contains('eliminación de mi cuenta'));
    expect(find.textContaining('Solicitud enviada'), findsOneWidget);
  });

  testWidgets('cancelar no envía nada', (tester) async {
    var peticiones = 0;
    final api = ClienteApi(
      urlBase: 'https://x',
      sesion: SesionFalsa(),
      http_: MockClient((req) async {
        peticiones++;
        return http.Response('{}', 201);
      }),
    );
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: Builder(
            builder: (context) => TextButton(
                  onPressed: () => pedirEliminarCuenta(context, api),
                  child: const Text('Eliminar mi cuenta'),
                )),
      ),
    ));
    await tester.tap(find.text('Eliminar mi cuenta'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cancelar'));
    await tester.pumpAndSettle();
    expect(peticiones, 0);
  });
}
