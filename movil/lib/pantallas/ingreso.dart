/// Entrada del paciente: teléfono o correo, y el código que le llega.
///
/// Por dónde llega el código lo decide la plataforma (WhatsApp o correo)
/// y se pregunta al abrir la pantalla: con WhatsApp se pide el teléfono,
/// con correo, el correo.
///
/// No hay contraseña a propósito. Un paciente entra en su app dos veces
/// al año, y una contraseña que se usa dos veces al año es una
/// contraseña olvidada o apuntada en un papel.
///
/// Si el correo aún no tiene cuenta, se ofrece crearla aquí mismo: el
/// paciente escribe su nombre y le llega el código. Su clínica la enlaza
/// después con su ficha (mientras tanto, ve la pantalla de espera).
///
/// En el iPhone el teclado numérico no tiene tecla «Intro»: el código
/// se envía solo al completar los 6 dígitos, y tocar fuera de los campos
/// cierra el teclado, que si no tapaba el botón de entrar.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api/cliente.dart';
import '../api/modelos.dart';
import '../logo.dart';
import 'aviso_privacidad.dart';

class PantallaIngreso extends StatefulWidget {
  const PantallaIngreso({
    super.key,
    required this.api,
    required this.alEntrar,
    this.marca = Marca.neutra,
  });

  final ClienteApi api;
  final VoidCallback alEntrar;

  /// La de la última clínica con la que se ingresó, si la hay. En el
  /// primer arranque del teléfono no se sabe de qué clínica se trata
  /// —no hay sesión— y se usa la neutra.
  final Marca marca;

  @override
  State<PantallaIngreso> createState() => _PantallaIngresoState();
}

class _PantallaIngresoState extends State<PantallaIngreso> {
  final _telefono = TextEditingController();
  final _codigo = TextEditingController();
  final _nombre = TextEditingController();
  bool _codigoPedido = false;

  /// El correo no tiene cuenta y el paciente va a crearla.
  bool _creando = false;
  bool _ocupado = false;
  String? _error;

  /// `'correo'` o `'whatsapp'`; correo mientras no se sepa.
  String _canal = 'correo';

  /// Lo que contestó el servidor al pedir el código (adónde lo mandó).
  String? _enviado;

  bool get _porCorreo => _canal == 'correo';

  @override
  void initState() {
    super.initState();
    widget.api.canalDelCodigo().then((canal) {
      if (mounted && !_codigoPedido) setState(() => _canal = canal);
    });
  }

  @override
  void dispose() {
    _telefono.dispose();
    _codigo.dispose();
    _nombre.dispose();
    super.dispose();
  }

  Future<void> _ejecutar(Future<void> Function() accion) async {
    setState(() {
      _ocupado = true;
      _error = null;
    });
    try {
      await accion();
    } on ErrorDeApi catch (e) {
      if (mounted) setState(() => _error = e.mensaje);
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'No se pudo contactar con la clínica. '
            'Revisa tu conexión e inténtalo otra vez.');
      }
    } finally {
      if (mounted) setState(() => _ocupado = false);
    }
  }

  Future<void> _pedir() => _ejecutar(() async {
        if (_creando && _nombre.text.trim().length < 3) {
          setState(() => _error = 'Escribe tu nombre y apellido.');
          return;
        }
        try {
          final enviado = await widget.api.pedirCodigo(_telefono.text.trim(),
              porCorreo: _porCorreo,
              crear: _creando,
              nombre: _nombre.text.trim());
          if (mounted) {
            setState(() {
              _codigoPedido = true;
              _enviado = enviado;
            });
          }
        } on ErrorDeApi catch (e) {
          if (!e.puedeCrear || !mounted) rethrow;
          setState(() => _creando = true);
        }
      });

  /// Al llegar al sexto dígito se envía solo: es lo que espera quien
  /// copia el código del WhatsApp o del correo y lo pega.
  void _alCambiarCodigo(String valor) {
    if (valor.length == 6 && !_ocupado) {
      FocusScope.of(context).unfocus();
      _verificar();
    }
  }

  Future<void> _verificar() => _ejecutar(() async {
        await widget.api.verificarCodigo(
            _telefono.text.trim(), _codigo.text.trim(),
            porCorreo: _porCorreo);
        widget.alEntrar();
      });

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Scaffold(
      body: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () => FocusScope.of(context).unfocus(),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 420),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _Emblema(marca: widget.marca),
                    const SizedBox(height: 20),
                    Text(widget.marca.nombre,
                        style: tema.textTheme.headlineMedium),
                    const SizedBox(height: 6),
                    Text(_explicacion, style: tema.textTheme.bodyMedium),
                    const SizedBox(height: 22),
                    if (_error != null) ...[
                      _Aviso(texto: _error!),
                      const SizedBox(height: 14),
                    ],
                    TextField(
                      // Otra clave por canal: si cambia mientras se
                      // escribe, el teclado y los filtros se rehacen.
                      key: ValueKey('dato-$_canal'),
                      controller: _telefono,
                      enabled: !_codigoPedido && !_ocupado,
                      keyboardType: _porCorreo
                          ? TextInputType.emailAddress
                          : TextInputType.phone,
                      textInputAction: TextInputAction.send,
                      autocorrect: false,
                      autofillHints: [
                        _porCorreo
                            ? AutofillHints.email
                            : AutofillHints.telephoneNumber
                      ],
                      inputFormatters: _porCorreo
                          ? [
                              FilteringTextInputFormatter.deny(RegExp(r'\s')),
                              LengthLimitingTextInputFormatter(254),
                            ]
                          : [
                              FilteringTextInputFormatter.allow(
                                  RegExp(r'[0-9+ ]')),
                              LengthLimitingTextInputFormatter(20),
                            ],
                      onSubmitted: (_) => _ocupado ? null : _pedir(),
                      decoration: InputDecoration(
                        labelText:
                            _porCorreo ? 'Correo electrónico' : 'Teléfono',
                        hintText: _porCorreo
                            ? 'nombre@gmail.com'
                            : '+593 99 911 1222',
                        border: const OutlineInputBorder(),
                      ),
                    ),
                    if (_creando && !_codigoPedido) ...[
                      const SizedBox(height: 14),
                      TextField(
                        controller: _nombre,
                        enabled: !_ocupado,
                        autofocus: true,
                        textCapitalization: TextCapitalization.words,
                        autofillHints: const [AutofillHints.name],
                        inputFormatters: [LengthLimitingTextInputFormatter(150)],
                        decoration: const InputDecoration(
                          labelText: 'Tu nombre y apellido',
                          border: OutlineInputBorder(),
                        ),
                      ),
                    ],
                    if (_codigoPedido) ...[
                      const SizedBox(height: 14),
                      TextField(
                        controller: _codigo,
                        enabled: !_ocupado,
                        keyboardType: TextInputType.number,
                        autofocus: true,
                        // iOS ofrece el código desde Mensajes si llega por SMS.
                        autofillHints: const [AutofillHints.oneTimeCode],
                        inputFormatters: [
                          FilteringTextInputFormatter.digitsOnly,
                          LengthLimitingTextInputFormatter(6),
                        ],
                        onChanged: _alCambiarCodigo,
                        decoration: const InputDecoration(
                          labelText: 'Código de 6 dígitos',
                          border: OutlineInputBorder(),
                        ),
                        onSubmitted: (_) => _verificar(),
                      ),
                    ],
                    const SizedBox(height: 18),
                    FilledButton(
                      onPressed: _ocupado
                          ? null
                          : (_codigoPedido ? _verificar : _pedir),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        child: Text(_ocupado
                            ? 'Un momento…'
                            : (_codigoPedido
                                ? 'Entrar'
                                : _creando
                                    ? 'Crear mi cuenta'
                                    : 'Enviarme el código')),
                      ),
                    ),
                    if (_codigoPedido)
                      TextButton(
                        onPressed: _ocupado
                            ? null
                            : () => setState(() {
                                  _codigoPedido = false;
                                  _creando = false;
                                  _enviado = null;
                                  _codigo.clear();
                                }),
                        child: Text(
                            _porCorreo ? 'Usar otro correo' : 'Usar otro número'),
                      ),
                    const SizedBox(height: 18),
                    // Antes de dar el número, que se pueda saber qué se
                    // hace con él.
                    TextButton(
                      onPressed: () => Navigator.of(context).push(
                          MaterialPageRoute<void>(
                              builder: (_) =>
                                  PantallaAvisoPrivacidad(api: widget.api))),
                      child: const Text('Aviso de privacidad'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  String get _explicacion {
    if (_codigoPedido) {
      if (_porCorreo && _enviado != null) return _enviado!;
      return _porCorreo
          ? 'Te enviamos un código a tu correo. Si no lo ves, mira en «Spam».'
          : 'Te enviamos un código por WhatsApp al $_telefonoVisible.';
    }
    if (_creando) {
      return 'Aún no tienes cuenta con este correo. Escribe tu nombre y te '
          'enviamos un código para crearla.';
    }
    return _porCorreo
        ? 'Ingresa con tu correo electrónico. Te enviaremos un código.'
        : 'Ingresa con tu número de teléfono. Te enviaremos un código por '
            'WhatsApp.';
  }

  String get _telefonoVisible {
    final t = _telefono.text.trim();
    // No se repite el número entero: si alguien mira por encima del
    // hombro, los últimos dígitos bastan para reconocerlo.
    return t.length > 4 ? '••• ${t.substring(t.length - 4)}' : t;
  }
}

class _Aviso extends StatelessWidget {
  const _Aviso({required this.texto});

  final String texto;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: tema.colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(texto,
          style: TextStyle(color: tema.colorScheme.onErrorContainer)),
    );
  }
}

/// El logotipo de la clínica, o el de Clinube si no tiene.
///
/// `errorBuilder` no es opcional: el logotipo se carga desde la red y un
/// servidor caído, una URL vieja o un archivo borrado dejarían un aspa
/// rota presidiendo la pantalla de ingreso. Se cae al logotipo de
/// Clinube, que está dibujado y nunca falla.
class _Emblema extends StatelessWidget {
  const _Emblema({required this.marca});

  final Marca marca;

  @override
  Widget build(BuildContext context) {
    // Sin logotipo propio, la clínica lleva el de Clinube.
    const deClinube = Align(
      alignment: Alignment.centerLeft,
      child: LogoClinube(alto: 40),
    );
    if (!marca.tieneLogo) return deClinube;
    return Image.network(
      marca.logo!,
      height: 72,
      fit: BoxFit.contain,
      errorBuilder: (context, _, __) => deClinube,
    );
  }
}
