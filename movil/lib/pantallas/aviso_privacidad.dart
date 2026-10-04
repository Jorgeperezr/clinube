/// El aviso de privacidad, el mismo que publica la plataforma en
/// `/privacidad`. Se abre desde el ingreso —antes de dar el teléfono— y
/// desde el perfil.
library;

import 'package:flutter/material.dart';

import '../api/cliente.dart';
import '../api/modelos.dart';

class PantallaAvisoPrivacidad extends StatefulWidget {
  const PantallaAvisoPrivacidad({super.key, required this.api});

  final ClienteApi api;

  @override
  State<PantallaAvisoPrivacidad> createState() => _PantallaAvisoPrivacidadState();
}

class _PantallaAvisoPrivacidadState extends State<PantallaAvisoPrivacidad> {
  late Future<DocumentoLegal> _futuro;

  @override
  void initState() {
    super.initState();
    _futuro = widget.api.avisoPrivacidad();
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Aviso de privacidad')),
      body: FutureBuilder<DocumentoLegal>(
        future: _futuro,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(28),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text('No se pudo cargar el aviso. Revisa tu conexión.',
                        textAlign: TextAlign.center),
                    const SizedBox(height: 16),
                    FilledButton.tonal(
                      onPressed: () =>
                          setState(() => _futuro = widget.api.avisoPrivacidad()),
                      child: const Text('Reintentar'),
                    ),
                  ],
                ),
              ),
            );
          }
          final doc = snap.data!;
          return ListView(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 40),
            children: [
              Text(doc.titulo, style: tema.textTheme.headlineSmall),
              const SizedBox(height: 4),
              Text('Versión ${doc.version} · vigente desde el ${doc.vigenteDesde}',
                  style: tema.textTheme.bodySmall),
              for (final (titulo, parrafos) in doc.secciones) ...[
                const SizedBox(height: 22),
                Text(titulo, style: tema.textTheme.titleMedium),
                for (final p in parrafos)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(p, style: tema.textTheme.bodyMedium?.copyWith(height: 1.45)),
                  ),
              ],
            ],
          );
        },
      ),
    );
  }
}
