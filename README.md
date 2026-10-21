# Clinube — gestión clínica en la nube

Clinube es un sistema para llevar una consulta de salud: agenda, historia
clínica, recetas, cobros, finanzas y una app para los pacientes. Sirve
igual al **profesional que trabaja por su cuenta** que a la **clínica con
equipo**, y varias clínicas conviven en la misma instalación sin ver los
datos de las demás.

La odontología es la primera especialidad (odontograma, periodontograma,
formulario MSP HCU-033/2021). Medicina y psicología se abren por
solicitud; por eso el nombre no dice «dental».

- **Página pública:** [clinube.com](https://clinube.com): servicios, alta
  de clínicas y consultorios, y descargas.
- **Panel:** [app.clinube.com](https://app.clinube.com), en el navegador
  o instalado como app.
- **App del paciente:** Flutter, en `movil/`.

## Qué hace

| Área | Lo que incluye |
|---|---|
| **Pacientes y agenda** | Ficha completa, citas por profesional, sala de espera, recordatorios y confirmación desde la app. |
| **Historia clínica** | Odontograma en cuatro modelos (Esquema MSP, Anatómico, Periodontograma y 3D), evoluciones, diagnósticos, índices CPO-ceo y formulario MSP 033 con su propio diseño y el membrete de la clínica. |
| **Periodontograma** | Por exploración con fecha: sondaje, margen gingival, nivel de inserción calculado, sangrado, supuración, placa, furcas, movilidad, encía queratinizada y pronóstico por pieza. Dibuja el margen y el fondo de bolsa sobre las piezas, calcula los índices y se exporta en PDF o en imagen PNG. Una exploración nueva hereda las ausencias y los implantes. |
| **Documentos** | Historia clínica, formulario 033, periodontograma, recetas, certificados y solicitudes de examen en PDF con el membrete de la clínica. Antes de descargar se ve una vista previa, y donde el documento tiene partes opcionales se eligen ahí. |
| **Cobros** | Presupuestos, planes de pago, convenios y tarifarios, bloqueo por morosidad. |
| **Finanzas** | Ingresos y egresos, caja, honorarios con retención, rol de pagos con IESS, décimos, fondos de reserva, horas extra y anticipos (normativa de Ecuador). |
| **App del paciente** | Sus citas, recetas y documentos, y mensajes con su consulta. El paciente crea su cuenta con su correo o con Google y la clínica le da acceso. |
| **Cuentas** | Entrada con correo o Google (con botón para ver la contraseña al escribirla), invitación al personal con la marca de la clínica, funciones a medida de cada persona. |
| **Consultorio o clínica** | Un consultorio es la cuenta de una sola persona que administra y atiende. En una clínica, cualquier administrador puede marcarse «Atiende pacientes». |
| **Copias de seguridad** | Cifradas, descargables por la administración de la clínica y verificadas restaurándolas. |
| **Plataforma** | Alta de clínicas, solicitudes que llegan de la página pública, funciones contratadas por clínica y una clínica de pruebas para estrenar lo nuevo. |
| **Buscadores e IA** | La portada se indexa en buscadores, pero los rastreadores de IA están excluidos (`robots.txt` y `X-Robots-Tag: noai`). El panel no se indexa en ningún sitio. El bloqueo de bots de Cloudflare se activa según DEPLOY.md. |

Algunas funciones son **adicionales** y se activan por clínica desde
Plataforma: WhatsApp, odontograma 3D, rachas y logros, entre otras (el
catálogo está en `django-api/apps/common/funcionalidades.py`).

## Cómo está hecho

```
django-api/         Django 5.2 + DRF: la fuente de verdad de todo el dominio
frontend/           Next.js 14: panel, página pública y alta de clínicas (export estático)
movil/              Flutter: la app del paciente
whatsapp-gateway/   FastAPI: envío de plantillas y webhook de WhatsApp Business
nginx/              Proxy de producción: dominio raíz → portada, app. → panel
scripts/            Arranque local, servidor, copias de seguridad, Oracle
```

PostgreSQL guarda los datos; Redis es la cola de Celery (recordatorios y
avisos en segundo plano) y la caché compartida, donde se cuentan los
límites de intentos. Django corre en gunicorn con hilos detrás de nginx,
que comprime las respuestas y reutiliza las conexiones. En producción todo corre con
`docker-compose.prod.yml` en una máquina de Oracle Cloud *Always Free*,
publicada con un túnel de Cloudflare: el servidor no abre puertos web a
internet.

## Primeros pasos en una máquina nueva

```bash
git clone https://github.com/Jorgeperezr/clinube.git
cd clinube
bash scripts/comprobar-entorno.sh
```

`comprobar-entorno.sh` no instala ni arranca nada. Mira qué hay en la
máquina (openssl, PostgreSQL, Python, Node y los puertos ocupados) y dice
qué hacer con lo que falte. Pásalo antes que nada. En macOS, por ejemplo,
`openssl` es en realidad LibreSSL, y sin avisarlo las copias hechas en ese
Mac no podrían descifrar las del servidor.

Con la revisión en verde:

```bash
bash scripts/start-local.sh
```

Levanta PostgreSQL, Django en `:8000` y Next.js en `:3000`, en Linux y en
macOS. La primera vez crea `.venv` e instala las dependencias; después se
lo salta. Para parar los servidores sin tocar la base:

```bash
bash scripts/start-local.sh --stop
```

Abre **http://localhost:3000**, con `localhost` y no con `127.0.0.1`:
para CORS son orígenes distintos y desde el segundo el login falla sin
decir por qué.

Para cualquier otro comando de Django, usa el envoltorio, que pone el
entorno y el intérprete de `.venv`:

```bash
bash scripts/manage.sh shell
```

Un `python manage.py …` a secas busca la base en el host `postgres` (el
nombre del servicio en Docker) y falla con «could not translate host
name».

> Los comandos de este README no llevan comentarios al final de la línea.
> En zsh, la consola de macOS, un `#` o un `?` sueltos pueden llegar como
> argumento o abortar la línea.

## Pruebas

Se valida como valida el CI, no como sea más cómodo:

```bash
cd django-api
python manage.py test --settings=config.settings_test
```

`config.settings_test` usa SQLite en memoria y tarda unos 20 segundos. Hoy
son **783 pruebas**. El CI las pasa dos veces: la segunda con
`DJANGO_TIME_ZONE=Pacific/Kiritimati` (UTC+14), para que la fecha del
servidor y la de la clínica no coincidan nunca. También corre con
`DJANGO_DEBUG=True`.

Antes de subir cambios:

```bash
ruff check apps config
```

Y si se tocó el panel, desde `frontend/`:

```bash
node --test lib/*.test.mjs lib/dictado/*.test.mjs
```
```bash
NEXT_EXPORT=1 npx next build
```

La app, desde `movil/` (Flutter 3.47 o posterior):

```bash
flutter analyze && flutter test
```

Las pruebas de `movil/test/fixtures/` usan respuestas capturadas de la API
real. Si cambia un campo de la API, se recapturan (ver `movil/README.md`);
no se arreglan a mano.

El CI (`.github/workflows/ci.yml`) tiene cinco trabajos: `django-tests`,
`frontend-build`, `movil`, `guiones` (revisa los scripts de shell) y
`whatsapp-gateway`.

## Producción

Todo el despliegue está en **[DEPLOY.md](DEPLOY.md)**: la máquina de
Oracle, el túnel de Cloudflare, el `.env` de producción, el correo con
Gmail, la entrada con Google y las copias de seguridad cifradas.

Para actualizar el servidor con lo último de `main`, conectado a él:

```bash
cd ~/clinube
```
```bash
git pull
```
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Las migraciones se aplican solas al arrancar.

PostgreSQL arranca afinado para el servidor y Django reutiliza las
conexiones. Con un servidor más grande se ajusta en el `.env` sin tocar
el código (tabla por memoria en DEPLOY.md, «Base de datos y tamaño del
servidor»). Para ver qué consultas gastan más tiempo con datos reales:

```bash
docker compose -f docker-compose.prod.yml exec django-api python manage.py consultas_lentas
```

## Marca

Toda clínica nueva tiene el aspecto de Clinube, cian sobre tinta, hasta
que sube su logotipo o elige su paleta en Configuración → Personalización.
Con logotipo propio, su marca manda en todo lo que ve el paciente y
Clinube queda discreto al pie. Entre los temas está «Sin color», que cada
persona puede elegir también solo para sí.

El logotipo está en `frontend/lib/marca.js` (y `MARCA` en
`django-api/config/settings.py`). En `scripts/marca/README.md` se explica
cómo está hecho y cómo regenerar los iconos.

## Documentación

| Archivo | Para qué |
|---|---|
| [DEPLOY.md](DEPLOY.md) | Servidor, dominio, correo, Google, copias de seguridad. |
| [CLAUDE.md](CLAUDE.md) | Convenciones del repositorio: autoría de commits, cómo validar y archivos que no se tocan. |
| [movil/README.md](movil/README.md) | La app del paciente: estructura y cómo recapturar las respuestas de prueba. |
| [movil/EN-MI-MAC.md](movil/EN-MI-MAC.md) | Compilar y probar la app en un Mac, paso a paso. |
| [movil/PUBLICAR.md](movil/PUBLICAR.md) | Publicar la app en App Store y Google Play. |
| [QA-CHECKLIST.md](QA-CHECKLIST.md) | Recorrido manual del panel. |
| [docs/contrato/](docs/contrato/LEEME.md) | El contrato del sistema (rutas, modelo de datos, OpenAPI y reglas transversales) para la versión en Java/Kotlin. Se regenera con `bash scripts/exportar-contrato.sh`. |
| [docs/PROMPT_CLINUBE_JAVA.md](docs/PROMPT_CLINUBE_JAVA.md) | El encargo con el que se inició `clinube_java`. |
| [docs/HISTORIAL.md](docs/HISTORIAL.md) | El diario de desarrollo, sprint a sprint, hasta el 91. |

Código, comentarios, commits y textos de la interfaz van en castellano.
