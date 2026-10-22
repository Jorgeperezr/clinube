# Contrato del sistema

Lo que una reimplementación del servidor —la de Java/Kotlin en
`clinube_java`— tiene que respetar para que el **panel web** (`frontend/`)
y la **app del paciente** (`movil/`) funcionen sin cambiar una línea.

| Archivo | Qué es | Cómo se obtiene |
|---|---|---|
| [RUTAS.md](RUTAS.md) | Las ~200 rutas: métodos, vista, archivo y línea, permisos, serializador, paginación | Generado |
| [MODELO_DE_DATOS.md](MODELO_DE_DATOS.md) | Cada tabla con campos, tipos, nulos, valores por omisión, opciones, relaciones, unicidad e índices | Generado |
| [openapi.yaml](openapi.yaml) | Esquema de drf-spectacular: exacto en rutas y serializadores; las `APIView` no describen su respuesta | Generado |
| Este archivo | Las reglas que valen para todas las rutas y no se deducen de ellas | A mano |

Los tres primeros se regeneran con `bash scripts/exportar-contrato.sh`. Si
Clinube cambia, se vuelve a exportar y el diff en git dice qué portar.

**La fuente de verdad es el código.** Ante una duda sobre la forma exacta de
una respuesta, la vista citada en RUTAS.md y sus pruebas (`tests*.py` de la
misma app) mandan sobre cualquier documento. Las respuestas reales se
pueden capturar arrancando Django en local (`bash scripts/start-local.sh`).

## Formato

- Prefijo `/api/v1/` y **barra final** en todas las rutas (`/api/v1/patients/`).
- JSON con claves en **snake_case** (`scheduled_start`, `must_change_password`).
- Identificadores: UUID en texto.
- Fechas `YYYY-MM-DD`; fecha y hora en ISO 8601 con zona (`2026-10-21T09:30:00-05:00`).
- Importes (`DecimalField`): **en texto**, `"150.00"`, no como número.
- Listas paginadas: `{"count", "next", "previous", "results"}`, 20 por página,
  `?page=N`. Las que no paginan devuelven un arreglo (columna «Paginada» de RUTAS.md).

## Errores: dos formas, y el panel acepta las dos

1. Las excepciones (validación, permisos, 404) pasan por
   `apps/common/exceptions.py` y salen como
   `{"error": {"code": "...", "message": "...", "details": {campo: [mensajes]}}}`.
2. Muchas vistas responden a mano `{"detail": "..."}` con 400/403/404/409.

Los mensajes están en castellano y el panel los muestra tal cual: se copian,
no se traducen ni se reescriben.

## Autenticación

- **Personal:** `POST /api/v1/auth/login/` `{email, password}` →
  `{access, refresh, role, must_change_password}`. Los pacientes no entran por aquí.
- **JWT** (SimpleJWT): `access` dura 30 min y `refresh` 7 días;
  `POST /api/v1/auth/token/refresh/` `{refresh}` → `{access, refresh}`. El
  refresh **rota** y el anterior queda invalidado. El token lleva `role` y `tenant_id`.
- Cabecera `Authorization: Bearer <access>`.
- **Paciente:** código de 6 cifras por correo (o WhatsApp si la clínica lo
  contrató): `auth/otp/canal/`, `auth/otp/request/`, `auth/otp/verify/`.
- **Google:** `POST /api/v1/auth/google/` con la credencial de Google
  Identity; `auth/google/config/` da el client id.
- **Recuperar contraseña:** `auth/recovery/request/` y `auth/recovery/confirm/`;
  enlaces de un solo uso con caducidad.
- `GET /api/v1/auth/me/` da el perfil con el que el panel arma el menú: rol,
  funciones, funcionalidades de la clínica, preferencias, si atiende, la
  modalidad (clínica o consultorio) y si faltan condiciones por aceptar.

## Clínicas, roles y permisos

- **Multi-clínica:** casi todas las tablas tienen `tenant`. La clínica de una
  petición es la **del usuario en la base** (`request.tenant`), no la del
  token. Toda consulta se filtra por ella: nunca se ve un dato de otra.
- **Roles:** `superadmin` (plataforma, sin clínica), `admin`, `reception`,
  `doctor`, `auxiliary`, `patient`.
- **Funciones por persona** (`apps/accounts/funciones.py`): agenda, cobros,
  inventario, reportes, finanzas… El administrador las tiene todas.
- **Funcionalidades por clínica** (`apps/common/funcionalidades.py`):
  incluidas o adicionales (WhatsApp, odontograma 3D, logros…), con fase de
  prueba. Una ruta de una funcionalidad no contratada responde 403.
- **Atender:** se atiende si hay ficha `Doctor` activa, no solo por rol (un
  administrador de consultorio atiende).

## Altas desde la página pública

Nadie crea una clínica desde la página: `POST /api/v1/publico/solicitudes/`
deja una solicitud «pendiente» y responde `plazo_horas` (12 para medicina y
psicología, `null` para odontología, que se responde a la brevedad). El
Super Administrador la aprueba con `platform/solicitudes/{id}/aprobar/`:
se crea la clínica con un administrador **sin contraseña** y le llega un
enlace de un solo uso (72 horas) para elegirla, el mismo que el de las
invitaciones del personal (`/recuperar/?token=…&bienvenida=1`).

## Fechas y zona horaria

- Se guarda en UTC; «hoy», «este mes» y los filtros por día van en la zona
  de la clínica, `America/Guayaquil` (`DJANGO_TIME_ZONE`).
- Los filtros por día son intervalos de instantes en esa zona
  (`apps/common/fechas.py`), no conversiones por fila.
- El CI pasa todo dos veces, la segunda con `Pacific/Kiritimati` (UTC+14),
  para que la fecha del servidor y la de la clínica nunca coincidan.

## Límites de intentos

En la caché compartida (Redis): 600/min con sesión, **20/min sin sesión por
IP**, **5/min para pedir códigos**, 10/hora para las solicitudes de la
página pública.

## Archivos y documentos

- Los archivos de pacientes **no** se sirven por `/media/`: los da la API
  comprobando clínica, paciente y permisos. Solo los logotipos son públicos
  (`/media/branding/`).
- PDF con reportlab. Todos usan el motor de estilos de la clínica (membrete,
  logotipo, colores, pie con «Página x de N») salvo el **formulario MSP 033**,
  que conserva su diseño oficial y solo añade el membrete.
- Historia clínica, 033 y periodontograma aceptan `?incluir=a,b,c` para
  elegir sus secciones; sin el parámetro, todas.
- Las descargas exponen `Content-Disposition` (y `X-Backup-*` en las copias)
  en CORS.

## Tareas programadas (Celery Beat)

| Tarea | Cuándo |
|---|---|
| `billing.tasks.mark_overdue_installments` | Todos los días a las 00:30 |
| `whatsapp.tasks.send_appointment_reminders` | Cada hora, en punto |
| `whatsapp.tasks.send_payment_reminders` | Todos los días a las 09:00 |

Y una bajo demanda: `notify_doctor_patient_arrived`, cuando se marca la llegada.

## Producción

`config/produccion.py`: el servidor **no arranca** con claves de ejemplo,
`DEBUG` o una clave de base pública. Los correos salen con la marca de cada
clínica (`apps/accounts/correos_*.py`), con el SMTP configurado (y cifrado)
en Plataforma.
