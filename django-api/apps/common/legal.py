"""
Textos legales de la plataforma: el aviso de privacidad (para pacientes)
y las condiciones de uso con el acuerdo de tratamiento de datos (para
las clínicas).

Viven aquí, en el servidor, y no en el panel ni en la app, por una razón:
lo que se registra es que alguien recibió o aceptó UNA VERSIÓN concreta.
Si el texto estuviera repetido en tres sitios, la versión registrada
podría no corresponder con lo que esa persona leyó. El panel y la app lo
piden a la API y lo pintan tal cual.

CAMBIAR UN TEXTO ES CAMBIAR SU VERSIÓN. Al subir CONDICIONES_VERSION,
cada clínica tiene que volver a aceptarlas al entrar; al subir
AVISO_VERSION, las fichas muestran que el aviso entregado es anterior.
Un cambio de redacción sin cambio de versión deja registros que dicen
que alguien aceptó algo que no leyó.

Los datos de quien opera la plataforma (razón social, RUC, correo de
contacto) salen de PlatformConfiguration: los rellena el Super
Administrador en Plataforma → Configuración. Mientras falten, `pendientes`
lo dice y el panel de plataforma lo avisa.

ESTOS TEXTOS LOS DEBE REVISAR UN ABOGADO antes de tener pacientes reales.
"""

from apps.common.models import PlatformConfiguration

AVISO_VERSION = "2026.10"
CONDICIONES_VERSION = "2026.10"
VIGENTE_DESDE = "4 de octubre de 2026"

# Lo que se muestra mientras el Super Administrador no lo complete.
_SIN_DATO = "[pendiente de completar]"


def _datos_titular():
    c = PlatformConfiguration.get_solo()
    datos = {
        "plataforma": c.platform_name or "Clinube",
        "titular": c.titular_nombre.strip(),
        "ruc": c.titular_ruc.strip(),
        "correo": c.titular_correo.strip(),
        "proveedor_correo": c.proveedor_correo.strip(),
    }
    pendientes = [k for k in ("titular", "ruc", "correo") if not datos[k]]
    for k in pendientes:
        datos[k] = _SIN_DATO
    return datos, pendientes


def _encargados(d):
    from apps.accounts.acceso_paciente import CORREO, canal_codigo

    correo = d["proveedor_correo"] or "El proveedor de correo de la plataforma"
    # Quién envía el código de la app depende del canal elegido en
    # Plataforma: el aviso tiene que decir el que se usa de verdad.
    if canal_codigo() == CORREO:
        meta = "Meta Platforms (WhatsApp): envía, a quien lo autorizó, los recordatorios de citas y pagos."
        envios = (f"{correo}: envía los correos del sistema: los códigos para entrar en la app y "
                  "los de recuperar una contraseña.")
    else:
        meta = ("Meta Platforms (WhatsApp): envía los códigos para entrar en la app y, a quien lo "
                "autorizó, los recordatorios de citas y pagos.")
        envios = f"{correo}: envía los correos del sistema, como los de recuperar una contraseña."
    return [
        "Oracle Cloud Infrastructure: aloja el servidor, en la región de Santiago de Chile.",
        "Cloudflare: por su red pasan, cifradas, las conexiones entre el navegador o la app y "
        "el servidor, y guarda las copias de seguridad, que van cifradas antes de salir y no "
        "puede leer.",
        meta,
        envios,
    ]


def aviso_privacidad():
    d, pendientes = _datos_titular()
    secciones = [
        ("Quién trata tus datos", [
            "Tus datos los trata la clínica o el consultorio que te atiende. Es la responsable "
            "del tratamiento: decide para qué se usan y es a quien primero debes acudir con "
            "cualquier pregunta sobre tu historia clínica, tus citas o tus pagos.",
            f"La clínica lleva esa información en {d['plataforma']}, un sistema que opera "
            f"{d['titular']} (RUC {d['ruc']}). {d['plataforma']} es encargado del tratamiento: "
            "guarda y procesa los datos por cuenta de la clínica y siguiendo sus instrucciones, "
            f"nunca para fines propios. Contacto para temas de privacidad: {d['correo']}.",
        ]),
        ("Qué datos se guardan", [
            "Identificación y contacto: nombre, cédula o pasaporte, fecha de nacimiento, sexo, "
            "teléfono, correo y dirección.",
            "Datos de salud: historia clínica, odontograma, diagnósticos, tratamientos, "
            "radiografías, documentos y consentimientos firmados. La Ley Orgánica de Protección "
            "de Datos Personales (LOPDP) los considera datos sensibles y se protegen como tales.",
            "Citas, presupuestos, pagos y saldos.",
            "Si usas la app: el número de teléfono con el que entras y lo que envías desde ella, "
            "como solicitudes de cita y mensajes.",
        ]),
        ("Para qué se usan", [
            "Para atenderte y llevar tu historia clínica, como exige la normativa sanitaria.",
            "Para organizar tus citas, recordártelas y gestionar cobros y facturación.",
            "Para mandarte recordatorios por WhatsApp, solo si lo autorizaste. Puedes retirar "
            "esa autorización cuando quieras pidiéndolo en la clínica.",
            "No se venden, no se ceden para publicidad y no se usan para tomar decisiones "
            "automáticas sobre ti.",
        ]),
        ("Con qué base legal", [
            "La prestación de asistencia sanitaria, las obligaciones legales de la clínica "
            "(historia clínica, facturación) y tu consentimiento para lo que no es "
            "imprescindible, como los recordatorios por WhatsApp.",
        ]),
        ("Dónde están y quién más interviene", [
            "Los datos se guardan en un servidor de Oracle Cloud en Santiago de Chile. Como es "
            "fuera de Ecuador, se trata de una transferencia internacional de datos.",
            "Además de la clínica y de quien opera la plataforma, intervienen estos proveedores, "
            "cada uno solo en lo necesario para su función:",
            *_encargados(d),
        ]),
        ("Cuánto tiempo se guardan", [
            "La historia clínica se conserva el tiempo que exige la normativa sanitaria del "
            "Ecuador, aunque dejes de ir a la clínica. El resto, mientras dure tu relación con "
            "la clínica y lo que exijan otras leyes, como las tributarias.",
            "Las copias de seguridad se borran solas a los 30 días.",
        ]),
        ("Cómo se protegen", [
            "Conexiones cifradas, una cuenta personal para cada persona de la clínica con "
            "permisos según su función, registro de quién hace qué, y copias de seguridad "
            "diarias cifradas y guardadas fuera del servidor.",
        ]),
        ("Tus derechos", [
            "La LOPDP te reconoce los derechos de acceso, rectificación y actualización, "
            "eliminación, oposición, portabilidad, suspensión del tratamiento y a no ser objeto "
            "de decisiones basadas únicamente en tratamientos automatizados.",
            "Para ejercerlos, pídelo en la clínica que te atiende o escribe a "
            f"{d['correo']}. Tienes respuesta en un plazo máximo de 15 días.",
            "La eliminación tiene un límite: la historia clínica no se puede borrar mientras la "
            "ley obligue a conservarla.",
            "Si crees que no se respetaron tus derechos, puedes presentar un reclamo ante la "
            "Superintendencia de Protección de Datos Personales.",
        ]),
        ("Cambios en este aviso", [
            "Si cambia, la versión nueva se publica en esta misma dirección con su fecha.",
        ]),
    ]
    return _documento("Aviso de privacidad", AVISO_VERSION, secciones, pendientes)


def condiciones():
    d, pendientes = _datos_titular()
    secciones = [
        ("Partes y objeto", [
            f"{d['titular']} (RUC {d['ruc']}), que opera {d['plataforma']} («la plataforma»), y "
            "la clínica que la usa («la clínica»), representada por quien acepta estas "
            "condiciones como administrador o administradora.",
            "La plataforma presta un sistema de gestión clínica en la nube: agenda, fichas de "
            "pacientes, historia clínica, cobros, app del paciente y copias de seguridad.",
        ]),
        ("Quién responde de los datos", [
            "La clínica es la responsable del tratamiento de los datos de sus pacientes y de su "
            "personal. La plataforma es encargada del tratamiento: los trata solo para prestar "
            "el servicio y según las instrucciones de la clínica, que son estas condiciones y el "
            "uso que la clínica hace del sistema.",
        ]),
        ("Lo que se compromete a hacer la plataforma", [
            "Usar los datos únicamente para prestar el servicio. No venderlos, no cederlos y no "
            "usarlos para fines propios.",
            "Exigir confidencialidad a toda persona que tenga acceso a ellos.",
            "Mantener medidas de seguridad: conexiones cifradas, copias diarias cifradas "
            "guardadas fuera del servidor, parches de seguridad automáticos y acceso "
            "administrativo restringido.",
            "Trabajar solo con estos proveedores (subencargados), y avisar a la clínica antes de "
            "añadir o cambiar alguno:",
            *_encargados(d),
            "Avisar a la clínica sin demora de cualquier violación de seguridad que afecte a sus "
            "datos, con lo que se sepa en ese momento, para que pueda cumplir su propio deber de "
            "notificarla a la Superintendencia de Protección de Datos Personales y a los "
            "afectados.",
            "Ayudar a la clínica a atender las solicitudes de sus pacientes sobre sus derechos.",
            "Al terminar el servicio, dar a la clínica 30 días para descargar su copia completa "
            "(datos y archivos). Después, los datos se borran del servidor, y de las copias de "
            "seguridad cuando estas caducan, a los 30 días.",
        ]),
        ("Lo que se compromete a hacer la clínica", [
            "Tener base legal para los datos que registra y entregar a cada paciente el aviso de "
            "privacidad. El sistema permite dejar constancia de la entrega en la ficha.",
            "Pedir la autorización del paciente antes de activarle los recordatorios por "
            "WhatsApp.",
            "Crear una cuenta personal para cada persona que use el sistema, con el rol que le "
            "corresponde, y desactivarla cuando deje la clínica. Las contraseñas no se "
            "comparten.",
            "Usar el sistema solo para la gestión de la propia clínica. No está permitido subir "
            "contenido ilícito o programas maliciosos, intentar acceder a datos de otras "
            "clínicas, sobrecargar el servicio, escanear o probar la seguridad del sistema o de "
            "la infraestructura donde se aloja sin autorización por escrito, ni hacer nada que "
            "vaya contra las políticas de uso aceptable de los proveedores de alojamiento.",
            "Descargar sus propias copias de seguridad cada cierto tiempo, desde Configuración → "
            "Copia de seguridad.",
        ]),
        ("Disponibilidad y suspensión", [
            "La plataforma procura que el servicio esté siempre disponible, pero no puede "
            "garantizar que funcione sin interrupciones: hay mantenimientos y fallos de "
            "proveedores que no controla.",
            "Puede suspender el acceso de una clínica que incumpla el uso permitido. Avisará "
            "antes, salvo que el riesgo para otros sea inmediato.",
        ]),
        ("Cambios", [
            "Si estas condiciones cambian, la versión nueva se mostrará al entrar en el panel y "
            "habrá que aceptarla para seguir usándolo.",
        ]),
        ("Ley aplicable", [
            "Estas condiciones se rigen por las leyes de la República del Ecuador, en particular "
            "por la Ley Orgánica de Protección de Datos Personales y su reglamento.",
        ]),
    ]
    return _documento(
        "Condiciones de uso y acuerdo de tratamiento de datos",
        CONDICIONES_VERSION, secciones, pendientes,
    )


def _documento(titulo, version, secciones, pendientes):
    return {
        "titulo": titulo,
        "version": version,
        "vigente_desde": VIGENTE_DESDE,
        "secciones": [{"titulo": t, "parrafos": p} for t, p in secciones],
        # Datos del titular sin rellenar. El texto sale igual, con un
        # marcador visible, para que se note y no pase desapercibido.
        "pendientes": pendientes,
    }
