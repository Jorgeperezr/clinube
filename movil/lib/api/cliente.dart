/// Cliente de la API del paciente.
///
/// Dos cosas que este archivo se toma en serio, porque de ellas depende
/// que la app sea usable y que no filtre nada:
///
///   1. **Los tokens no se guardan en claro.** Dan acceso a datos
///      clínicos, así que van al Keychain (iOS) y al Keystore
///      (Android) a través de `flutter_secure_storage`, no a
///      `shared_preferences`, que es un XML legible en un teléfono con
///      root.
///
///   2. **El refresco es de un solo intento y serializado.** Al abrir la
///      app se piden cuatro pantallas a la vez; si el `access` ha
///      caducado, las cuatro fallarían con 401 y cada una pediría su
///      propio refresco. Como el backend rota el `refresh` en cada uso
///      (`ROTATE_REFRESH_TOKENS`), la primera invalidaría el token de las
///      otras tres y la sesión se caería sola. Por eso hay un único
///      `Future` de refresco compartido.
///
/// Y tres que se aprendieron con la app instalada en un teléfono:
///
///   3. **Las respuestas se leen como UTF-8.** La API dice
///      `Content-Type: application/json` sin `charset`, y en ese caso
///      `http` decodifica en latin1: «Pérez» salía «PÃ©rez». Las pruebas
///      no lo veían porque sus respuestas falsas sí traían el charset.
///
///   4. **Ninguna petición espera para siempre.** En un ascensor o con
///      una wifi que no da salida, la petición se quedaba colgada y la
///      pantalla girando sin fin. Tras [tiempoMaximo] se rinde con un
///      mensaje y un «Reintentar».
///
///   5. **Los fallos de red se dicen en castellano.** Un
///      `SocketException: Failed host lookup` no le dice nada a un
///      paciente.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io' show HandshakeException, SocketException;

import 'package:flutter/services.dart' show PlatformException;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import 'modelos.dart';

/// Fallo con un mensaje que se le puede enseñar a una persona.
class ErrorDeApi implements Exception {
  ErrorDeApi(this.mensaje, {this.codigo, this.puedeCrear = false});

  final String mensaje;
  final int? codigo;

  /// El correo no tiene cuenta y el servidor ofrece crearla.
  final bool puedeCrear;

  /// La sesión ya no vale y hay que volver a entrar.
  bool get sesionCaducada => codigo == 401;

  @override
  String toString() => mensaje;
}

/// Cuánto se espera a la API antes de dar la petición por perdida.
const tiempoMaximo = Duration(seconds: 20);

const _sinConexion =
    'No se pudo contactar con la clínica. Revisa tu conexión e inténtalo otra vez.';

/// El almacén seguro, configurado para que no dé guerra al instalar:
///
///   · Android: `encryptedSharedPreferences`, con su clave en el
///     Keystore. El modo antiguo fallaba al restaurar una copia de otro
///     teléfono (la clave del Keystore no viaja) y la app no arrancaba.
///     Además, AndroidManifest.xml excluye estos datos de las copias.
///   · iOS: `first_unlock_this_device`. Se puede leer tras el primer
///     desbloqueo (la app no falla si se abre desde una notificación con
///     el teléfono bloqueado) y no viaja a otro iPhone en una copia: la
///     sesión de un paciente no debe aparecer en el teléfono nuevo de
///     otra persona.
const almacenSeguro = FlutterSecureStorage(
  aOptions: AndroidOptions(encryptedSharedPreferences: true),
  iOptions:
      IOSOptions(accessibility: KeychainAccessibility.first_unlock_this_device),
);

/// Guarda y recupera los tokens del almacén seguro del sistema.
class Sesion {
  Sesion({FlutterSecureStorage? almacen}) : _almacen = almacen ?? almacenSeguro;

  final FlutterSecureStorage _almacen;

  /// Lee una clave sin dejar que un almacén estropeado tumbe la app.
  ///
  /// Si el sistema no puede descifrar lo guardado (clave del Keystore
  /// perdida, Keychain de una instalación anterior), lo único sensato es
  /// empezar de cero: el paciente vuelve a entrar con su código. Antes
  /// la excepción salía en el arranque y la app se quedaba en blanco.
  Future<String?> _leer(String clave) async {
    try {
      return await _almacen.read(key: clave);
    } on PlatformException {
      try {
        await _almacen.deleteAll();
      } on PlatformException {
        // Ni borrar se puede: se sigue sin sesión.
      }
      return null;
    }
  }

  static const _claveAcceso = 'acceso';
  static const _claveRefresco = 'refresco';
  static const _claveMarca = 'marca';
  static const _claveSinColor = 'sin_color';

  Future<String?> get acceso => _leer(_claveAcceso);
  Future<String?> get refresco => _leer(_claveRefresco);

  Future<void> guardar(String acceso, String? refresco) async {
    await _almacen.write(key: _claveAcceso, value: acceso);
    if (refresco != null) {
      await _almacen.write(key: _claveRefresco, value: refresco);
    }
  }

  Future<void> borrar() async {
    await _almacen.delete(key: _claveAcceso);
    await _almacen.delete(key: _claveRefresco);
    // La marca NO se borra al salir: es la identidad de la clínica, no
    // un dato del paciente, y conservarla hace que la pantalla de
    // ingreso siga siendo la de su clínica cuando vuelva a entrar. Se
    // reemplaza sola si ingresa con una cuenta de otra clínica. Tampoco
    // «Sin color»: es un ajuste de quien usa el teléfono, no de la cuenta.
  }

  Future<bool> get hayTokens async => (await acceso) != null;

  /// La marca guardada, si se llegó a pedir alguna vez.
  ///
  /// Sin esto, cada arranque en frío pinta medio segundo con los
  /// colores neutros y luego salta a los de la clínica. El parpadeo se
  /// ve, y se ve mal.
  Future<Marca?> get marca async {
    final crudo = await _leer(_claveMarca);
    if (crudo == null) return null;
    try {
      return Marca.desdeJson(jsonDecode(crudo) as Map<String, dynamic>);
    } catch (_) {
      // Guardado por una versión anterior con otra forma: se descarta y
      // se vuelve a pedir. Mejor los colores neutros un momento que una
      // excepción al arrancar.
      return null;
    }
  }

  Future<void> guardarMarca(Marca marca) =>
      _almacen.write(key: _claveMarca, value: jsonEncode(marca.aJson()));

  /// «Sin color»: la app en grises, elegido en el perfil.
  Future<bool> get sinColor async => (await _leer(_claveSinColor)) == '1';

  Future<void> guardarSinColor(bool activo) => activo
      ? _almacen.write(key: _claveSinColor, value: '1')
      : _almacen.delete(key: _claveSinColor);
}

/// Mensaje legible de una respuesta de error.
///
/// La API envuelve sus errores en `{"error": {"message", "details"}}` y
/// DRF usa `{"detail": ...}`; se miran los dos antes de rendirse a un
/// «error 500» que no le dice nada a nadie.
String mensajeDeError(int codigo, String cuerpo) {
  if (codigo == 429) {
    return 'Demasiados intentos seguidos. Espera un momento y vuelve a probar.';
  }
  try {
    final Object? datos = jsonDecode(cuerpo);
    if (datos is Map<String, dynamic>) {
      final Object? sobre = datos['error'];
      if (sobre is Map<String, dynamic>) {
        final Object? detalles = sobre['details'];
        if (detalles is Map<String, dynamic> && detalles.isNotEmpty) {
          final Object? primero = detalles.values.first;
          if (primero is List && primero.isNotEmpty) return '${primero.first}';
          if (primero is String && primero.isNotEmpty) return primero;
        }
        final Object? mensaje = sobre['message'];
        if (mensaje is String && mensaje.isNotEmpty) return mensaje;
      }
      final Object? detalle = datos['detail'];
      if (detalle is String && detalle.isNotEmpty) return detalle;
    }
  } on FormatException {
    // Un cuerpo que no es JSON (una página de error de nginx, por
    // ejemplo) no debe tumbar la app: se cae al mensaje genérico.
  }
  return 'No se pudo completar la operación (error $codigo).';
}

class ClienteApi {
  ClienteApi({
    required this.urlBase,
    Sesion? sesion,
    http.Client? http_,
    this.espera = tiempoMaximo,
  })  : sesion = sesion ?? Sesion(),
        _http = http_ ?? http.Client();

  final String urlBase;
  final Sesion sesion;

  /// Lo que se espera a cada petición (ver [tiempoMaximo]).
  final Duration espera;
  final http.Client _http;

  /// El refresco en vuelo, si lo hay. Ver la nota de arriba.
  Future<bool>? _refrescoEnVuelo;

  /// Se llama cuando la sesión deja de valer (el refresco caducó o se
  /// revocó). La app vuelve a la pantalla de ingreso: antes el paciente
  /// se quedaba en un «Reintentar» que nunca iba a funcionar.
  void Function()? alCaducarSesion;

  Uri _uri(String ruta) => Uri.parse('$urlBase/api/v1$ruta');

  /// Hace la petición con tiempo máximo y traduce los fallos de red.
  Future<http.Response> _red(Future<http.Response> Function() peticion) async {
    try {
      return await peticion().timeout(espera);
    } on TimeoutException {
      throw ErrorDeApi(
          'La clínica tarda demasiado en responder. Revisa tu conexión e inténtalo otra vez.');
    } on HandshakeException {
      // Certificado no válido: NO se acepta nunca. Una app de salud que
      // se salta la verificación es justo lo que un sistema operativo (y
      // una revisión de tienda) marca como peligroso.
      throw ErrorDeApi(
          'No se pudo establecer una conexión segura con la clínica.');
    } on SocketException {
      throw ErrorDeApi(_sinConexion);
    } on http.ClientException {
      throw ErrorDeApi(_sinConexion);
    }
  }

  /// El cuerpo como texto (ver la nota 3 de arriba): con el charset que
  /// diga la respuesta y, si no dice ninguno, UTF-8, que es lo que manda
  /// el estándar de JSON; latin1 solo si los bytes no son UTF-8 válido.
  static String texto(http.Response r) {
    final tipo = (r.headers['content-type'] ?? '').toLowerCase();
    if (tipo.contains('charset=')) return r.body;
    try {
      return utf8.decode(r.bodyBytes);
    } on FormatException {
      return latin1.decode(r.bodyBytes);
    }
  }

  static Object? _json(http.Response r) => jsonDecode(texto(r));

  static ErrorDeApi _error(http.Response r) =>
      ErrorDeApi(mensajeDeError(r.statusCode, texto(r)), codigo: r.statusCode);

  Future<void> _caducar() async {
    await sesion.borrar();
    alCaducarSesion?.call();
  }

  // ── Entrada por OTP ──────────────────────────────────────────────

  /// Por dónde llega el código: `'correo'` o `'whatsapp'`. Lo decide la
  /// plataforma, y la pantalla de ingreso pide el correo o el teléfono
  /// según esto. Si no se puede preguntar (sin red, un servidor viejo),
  /// correo: es el canal de todas las clínicas.
  Future<String> canalDelCodigo() async {
    try {
      final r = await _red(() => _http.get(_uri('/auth/otp/canal/'),
          headers: const {'Content-Type': 'application/json'}));
      if (r.statusCode >= 400) return 'correo';
      final datos = _json(r);
      return datos is Map && datos['canal'] == 'whatsapp' ? 'whatsapp' : 'correo';
    } catch (_) {
      return 'correo';
    }
  }

  /// Pide el código. [dato] es el teléfono o, con [porCorreo], el correo.
  /// Devuelve el mensaje del servidor («Te enviamos el código a
  /// an***@gmail.com…») para enseñarlo tal cual, o null si no trae.
  ///
  /// Con [crear], si el correo aún no tiene cuenta se crea una con [nombre]
  /// (el paciente la crea él mismo; su clínica la enlaza después). Sin
  /// [crear], un correo sin cuenta lanza [ErrorDeApi] con `puedeCrear`.
  Future<String?> pedirCodigo(String dato,
      {bool porCorreo = false, bool crear = false, String nombre = ''}) async {
    final r = await _red(() => _http.post(
          _uri('/auth/otp/request/'),
          headers: const {'Content-Type': 'application/json'},
          body: jsonEncode({
            porCorreo ? 'email' : 'phone': dato,
            if (crear) 'crear': true,
            if (crear) 'nombre': nombre,
          }),
        ));
    if (r.statusCode >= 400) {
      final error = _error(r);
      var puedeCrear = false;
      try {
        final datos = _json(r);
        puedeCrear = datos is Map && datos['puede_crear'] == true;
      } catch (_) {}
      throw ErrorDeApi(error.mensaje, codigo: error.codigo, puedeCrear: puedeCrear);
    }
    try {
      final datos = _json(r);
      final detalle = datos is Map ? datos['detail'] : null;
      return detalle is String && detalle.isNotEmpty ? detalle : null;
    } catch (_) {
      return null;
    }
  }

  /// Canjea el código por los tokens y los deja guardados.
  Future<void> verificarCodigo(String dato, String codigo,
      {bool porCorreo = false}) async {
    final r = await _red(() => _http.post(
          _uri('/auth/otp/verify/'),
          headers: const {'Content-Type': 'application/json'},
          body: jsonEncode({porCorreo ? 'email' : 'phone': dato, 'code': codigo}),
        ));
    if (r.statusCode >= 400) throw _error(r);
    final datos = _json(r) as Map<String, dynamic>;
    await sesion.guardar(
        datos['access'] as String, datos['refresh'] as String?);
  }

  Future<void> salir() => sesion.borrar();

  /// El aviso de privacidad. Es público: se puede leer antes de entrar.
  Future<DocumentoLegal> avisoPrivacidad() async {
    final r = await _red(() => _http.get(_uri('/legal/privacidad/')));
    if (r.statusCode >= 400) throw _error(r);
    return DocumentoLegal.desdeJson(_json(r) as Map<String, dynamic>);
  }

  /// Si la cuenta ya está enlazada con su ficha o espera a su clínica.
  Future<EstadoCuenta> estadoCuenta() async =>
      EstadoCuenta.desdeJson(await objeto('/app/cuenta/'));

  /// La marca de la clínica del paciente, guardada de paso.
  Future<Marca> marcaDeLaClinica() async {
    final marca = Marca.desdeJson(await objeto('/app/clinica/'));
    await sesion.guardarMarca(marca);
    return marca;
  }

  /// «Sí, asistiré». Devuelve la cita ya confirmada.
  Future<Cita> confirmarCita(String id) async =>
      Cita.desdeJson(await enviar('/app/citas/$id/confirmar/', const {}));

  // ── Peticiones autenticadas ──────────────────────────────────────

  Future<Map<String, dynamic>> objeto(String ruta) async =>
      await _pedir(ruta) as Map<String, dynamic>;

  Future<List<dynamic>> lista(String ruta) async =>
      await _pedir(ruta) as List<dynamic>;

  /// Envía datos (POST) con la misma renovación de sesión que las
  /// lecturas: pedir cita o escribir a la clínica con el token caducado
  /// no debe dar un error, sino renovarlo y reintentar una vez.
  Future<Map<String, dynamic>> enviar(
          String ruta, Map<String, dynamic> cuerpo) async =>
      await _pedir(ruta, cuerpo: cuerpo) as Map<String, dynamic>;

  Future<Object?> _pedir(String ruta, {Map<String, dynamic>? cuerpo}) async {
    Future<http.Response> hacer() =>
        cuerpo == null ? _get(ruta) : _post(ruta, cuerpo);
    var r = await hacer();
    if (r.statusCode == 401 && await _refrescar()) {
      r = await hacer();
    }
    if (r.statusCode >= 400) {
      if (r.statusCode == 401) await _caducar();
      throw _error(r);
    }
    return _json(r);
  }

  Future<http.Response> _get(String ruta) async {
    final token = await sesion.acceso;
    return _red(() => _http.get(_uri(ruta), headers: {
          'Content-Type': 'application/json',
          if (token != null) 'Authorization': 'Bearer $token',
        }));
  }

  Future<http.Response> _post(String ruta, Map<String, dynamic> cuerpo) async {
    final token = await sesion.acceso;
    return _red(() => _http.post(_uri(ruta),
        headers: {
          'Content-Type': 'application/json',
          if (token != null) 'Authorization': 'Bearer $token',
        },
        body: jsonEncode(cuerpo)));
  }

  /// Un solo refresco a la vez, compartido por todas las peticiones que
  /// hayan chocado con el mismo 401.
  Future<bool> _refrescar() {
    return _refrescoEnVuelo ??= _refrescarDeVerdad().whenComplete(() {
      _refrescoEnVuelo = null;
    });
  }

  Future<bool> _refrescarDeVerdad() async {
    final token = await sesion.refresco;
    if (token == null) return false;
    final r = await _red(() => _http.post(
          _uri('/auth/token/refresh/'),
          headers: const {'Content-Type': 'application/json'},
          body: jsonEncode({'refresh': token}),
        ));
    // Solo un «no» del servidor (token caducado o revocado) cierra la
    // sesión. Un fallo de red ya salió arriba como ErrorDeApi, y un error
    // del servidor se dice como tal: sin cobertura, o con el servidor
    // reiniciándose, no se echa a nadie.
    if (r.statusCode == 400 || r.statusCode == 401) return false;
    if (r.statusCode >= 400) throw _error(r);
    final datos = _json(r) as Map<String, dynamic>;
    await sesion.guardar(
        datos['access'] as String, datos['refresh'] as String?);
    return true;
  }
}
