/// La cuenta ya existe, pero su clínica todavía no le dio acceso a su
/// ficha. Pasa con quien creó la cuenta él mismo desde la app: hasta que
/// la recepción la enlace no hay citas, recetas ni saldo que enseñar, y
/// decirlo con claridad es mejor que una pantalla de error.
library;

import 'package:flutter/material.dart';

import '../api/cliente.dart';
import '../api/modelos.dart';

class PantallaEspera extends StatefulWidget {
  const PantallaEspera({
    super.key,
    required this.api,
    required this.estado,
    required this.alEnlazar,
    required this.alSalir,
  });

  final ClienteApi api;
  final EstadoCuenta estado;

  /// Se llama cuando, al volver a mirar, la cuenta ya está enlazada.
  final VoidCallback alEnlazar;
  final VoidCallback alSalir;

  @override
  State<PantallaEspera> createState() => _PantallaEsperaState();
}

class _PantallaEsperaState extends State<PantallaEspera> {
  bool _mirando = false;
  String? _aviso;

  Future<void> _revisar() async {
    setState(() {
      _mirando = true;
      _aviso = null;
    });
    try {
      final estado = await widget.api.estadoCuenta();
      if (estado.enlazada) {
        // La clínica sale de la cuenta, no del token: con la misma
        // sesión ya se ven sus datos.
        widget.alEnlazar();
        return;
      }
      if (mounted) {
        setState(() => _aviso = 'Todavía no. Pídelo en la recepción y vuelve a '
            'tocar el botón.');
      }
    } catch (_) {
      if (mounted) setState(() => _aviso = 'No se pudo comprobar. Revisa tu conexión.');
    } finally {
      if (mounted) setState(() => _mirando = false);
    }
  }

  Future<void> _salir() async {
    await widget.api.salir();
    widget.alSalir();
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final correo = widget.estado.correo;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Icon(Icons.mark_email_read_outlined,
                      size: 56, color: tema.colorScheme.primary),
                  const SizedBox(height: 18),
                  Text('Tu cuenta está lista',
                      style: tema.textTheme.headlineSmall,
                      textAlign: TextAlign.center),
                  const SizedBox(height: 12),
                  Text(
                    'Para ver tus citas, tus recetas y tus indicaciones, tu clínica '
                    'tiene que darte acceso. Dales este correo en la recepción:',
                    style: tema.textTheme.bodyMedium,
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 10),
                  SelectableText(correo,
                      style: tema.textTheme.titleMedium,
                      textAlign: TextAlign.center),
                  const SizedBox(height: 10),
                  Text(
                    'Tiene que ser el mismo correo que tienen en tu ficha.',
                    style: tema.textTheme.bodySmall,
                    textAlign: TextAlign.center,
                  ),
                  if (_aviso != null) ...[
                    const SizedBox(height: 16),
                    Text(_aviso!, textAlign: TextAlign.center),
                  ],
                  const SizedBox(height: 22),
                  FilledButton(
                    onPressed: _mirando ? null : _revisar,
                    child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      child: Text(_mirando ? 'Un momento…' : 'Ya me dieron acceso'),
                    ),
                  ),
                  TextButton(onPressed: _salir, child: const Text('Salir')),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
