# Encargo: Clinube en Kotlin (repositorio `clinube_java`)

> Copia todo lo que está debajo de la línea en el primer mensaje del proyecto
> nuevo de Claude Code, abierto sobre el repositorio
> `https://github.com/Jorgeperezr/clinube_java` en tu Mac.

---

Vas a reimplementar en **Kotlin con Spring Boot** el sistema Clinube, que hoy
funciona en producción con Django (Python). El repositorio original es
`https://github.com/Jorgeperezr/clinube` y este repositorio,
`https://github.com/Jorgeperezr/clinube_java`, es donde trabajas.
El desarrollo es **local, en mi Mac**: nada se despliega a ningún servidor.

## 1. Qué es Clinube

Un sistema de gestión clínica multi-clínica, en castellano y para Ecuador:
- agenda;
- pacientes;
- historia clínica odontológica: odontograma (MSP, anatómico y 3D),
  periodontograma, formulario MSP HCU-033/2021, evoluciones, diagnósticos
  CIE-10 y recetas;
- documentos en PDF con la marca de cada clínica;
- cobros y presupuestos;
- finanzas con normativa ecuatoriana (IESS, décimos, rol de pagos, honorarios
  con retención);
- inventario y reportes;
- app del paciente (hoy en Flutter);
- cuentas con correo y Google, e invitaciones;
- panel de plataforma (superadministrador) y alta pública de clínicas;
- consultorio de una sola persona o clínica con equipo;
- copias de seguridad cifradas;
- WhatsApp opcional.

## 2. Objetivo

**Las mismas funcionalidades y la misma apariencia.** Para conseguirlo:

- **El panel web (`frontend/`, Next.js) se copia de `clinube` tal cual.** Lo
  que reescribes es el **servidor**: tiene que responder exactamente como el
  de Django, para que el panel no note el cambio. Si para que algo funcione
  tienes que tocar el panel, es que el servidor no respeta el contrato:
  corrígelo en el servidor.
- **La app del paciente se reescribe en Kotlin** (Kotlin Multiplatform con
  Compose Multiplatform: un solo código para Android e iOS), pero **al
  final**, cuando el servidor ya responda igual que Django. Hasta entonces la
  app Flutter (`movil/`) se copia sin tocarla y sirve de testigo: si funciona
  contra el servidor de Kotlin, el contrato se cumple. Si se reescribieran los
  dos lados a la vez, no se sabría de qué lado está cada fallo.
- Al terminar, todo el proyecto es Kotlin salvo el panel web (ver «Por qué el
  panel sigue en Next.js», en el punto 3).
- **Base de datos compatible con la actual:** mismas tablas, columnas, tipos y
  restricciones (ver `docs/contrato/MODELO_DE_DATOS.md`). Así se podrá usar
  una copia de la base de producción y, llegado el día, cambiar un servidor
  por el otro sin migrar datos.
- **Mismo comportamiento verificable:** cada módulo se da por terminado
  cuando sus rutas responden igual que Django (comparándolas) y sus reglas de
  negocio pasan las pruebas portadas.

## 3. Decisiones ya tomadas

| Pieza | Elección | Por qué |
|---|---|---|
| Lenguaje | **Kotlin 2.x** sobre **Java 21 LTS** | Usa todo el ecosistema Java con menos código, nulos seguros y data classes. Un programador Java lo lee sin esfuerzo. |
| Marco | **Spring Boot 3.x** (Web, Security, Data JPA, Validation, Mail, Cache, Scheduling) | El equivalente maduro de Django/DRF. |
| Construcción | Gradle con Kotlin DSL y el wrapper (`./gradlew`) | — |
| Base de datos | PostgreSQL 16, Hibernate 6 en modo `validate`, migraciones con **Flyway** | Los `JSONField` de Django son `jsonb`: mapéalos con `@JdbcTypeCode(SqlTypes.JSON)`. |
| Caché, límites y colas | Redis 7: Spring Data Redis; límites de intentos con Bucket4j + Redis o contadores propios | — |
| JWT | Mismo formato que SimpleJWT: HS256 con `DJANGO_SECRET_KEY`, claims `token_type`, `exp`, `iat`, `jti`, `user_id`, `role`, `tenant_id`; refresh rotatorio con las mismas tablas `token_blacklist_*` | Los tokens sirven en los dos servidores, y eso permite pasar de uno a otro por partes. |
| PDF | **OpenPDF** (LGPL/MPL) | **No uses iText 7: es AGPL.** |
| Excel | Apache POI | Para la plantilla oficial MSP del 033 se reutiliza el mismo .xlsx de `clinube`. |
| Correo | Spring Mail con el SMTP guardado en la base, mismas plantillas HTML | — |
| Tareas programadas | `@Scheduled` con `zone = "America/Guayaquil"`; las asíncronas con `@Async` sobre hilos virtuales; ShedLock solo si algún día corre más de una instancia | Sustituyen a Celery y Celery Beat sin un proceso aparte. |
| Concurrencia | Hilos virtuales (`spring.threads.virtual.enabled=true`) y HikariCP | — |
| Pruebas | JUnit 5, Spring Boot Test, **Testcontainers** (PostgreSQL 16 y Redis 7), MockMvc o RestAssured | — |
| JSON | Jackson con `SNAKE_CASE`, decimales como texto, fechas ISO con zona, UUID en texto | Igual que DRF. |
| WhatsApp | Un módulo más del servidor | El gateway de clinube (FastAPI) es pequeño; así no queda Python en el proyecto. |
| Estructura | Un solo proyecto Gradle con tres módulos: `backend`, `compartido` y `app` | El servidor y la app comparten código Kotlin. |
| Modelos de la API | Módulo `compartido` (Kotlin Multiplatform) con las clases de las respuestas que usa la app, con kotlinx.serialization | Los usan la app y las pruebas del servidor, que leen sus propias respuestas con esas clases. Si se renombra un campo, el fallo sale al compilar o en las pruebas, no en el teléfono del paciente. |
| App del paciente | Compose Multiplatform (Android e iOS), Ktor Client, kotlinx.serialization y kotlinx-datetime; los tokens en el Keychain (iOS) y en el Keystore (Android), nunca en almacenamiento en claro | Cubre lo mismo que hoy `http`, `flutter_secure_storage` e `intl` en la app Flutter. |

### Por qué el panel sigue en Next.js

Las alternativas del mundo Java (Vaadin, Thymeleaf con HTMX, Compose para web)
obligarían a rehacer el panel entero, y lo más delicado no se puede portar:
el odontograma 3D (three.js) y el periodontograma interactivo son JavaScript
que corre en el navegador. Además, Spring Boot con un frontend React es la
combinación habitual en los equipos Java. Si en algún momento crees que
conviene cambiarlo, dímelo antes de tocar nada.

## 4. De dónde sacar la verdad

Clona el original al lado, solo para leerlo:

```sh
git clone https://github.com/Jorgeperezr/clinube.git ../clinube
```

**No hagas commits ni push en `clinube`.** Léelo en este orden:

1. `../clinube/README.md` y `../clinube/CLAUDE.md`: qué es y cómo se trabaja.
2. `../clinube/docs/contrato/LEEME.md`: reglas transversales (formato,
   errores, autenticación, clínicas y roles, fechas, límites, PDF, tareas).
3. `../clinube/docs/contrato/RUTAS.md`: las ~200 rutas con la vista, el
   archivo y la línea que las implementan.
4. `../clinube/docs/contrato/MODELO_DE_DATOS.md`: todas las tablas.
5. Por cada ruta, **su vista y las pruebas de su app** (`apps/*/tests*.py`).
   Las pruebas dicen las reglas de negocio mejor que cualquier documento.

Si Clinube cambia mientras trabajas, actualiza `../clinube` con `git pull`,
regenera con `bash ../clinube/scripts/exportar-contrato.sh` y mira el diff de
`docs/contrato/`: ahí está lo que hay que portar.

## 5. Reglas de paridad que no se negocian

- **Rutas idénticas:** `/api/v1/...` con barra final, mismos métodos, mismos
  códigos HTTP, mismas claves JSON y en el mismo formato. Paginación
  `{count, next, previous, results}` con 20 por página y `?page=N` donde
  Django pagina, y arreglo plano donde no.
- **Errores en las dos formas que usa Django:** `{"error": {"code", "message",
  "details"}}` y `{"detail": "..."}`, según la vista. **Los mensajes, en el
  mismo castellano, copiados.**
- **Clínica por usuario:** la clínica de la petición es la del usuario en la
  base, no la del token, y toda consulta se filtra por ella. Escribe pruebas
  de aislamiento: un usuario nunca ve datos de otra clínica.
- **Roles, funciones por persona y funcionalidades por clínica**, tal como
  están en `apps/accounts/funciones.py` y `apps/common/funcionalidades.py`.
- **Contraseñas compatibles:** verifica y genera el formato de Django
  `pbkdf2_sha256$<iteraciones>$<sal>$<hash base64>`, con las iteraciones que
  lleve cada hash. Así entran los usuarios que ya existen.
- **Secretos guardados en la base** (la contraseña del SMTP en
  `PlatformConfiguration`): están cifrados con **Fernet** y una clave derivada
  de `DJANGO_SECRET_KEY` (`apps/common/secretos.py`). Implementa Fernet
  compatible para leerlos y escribirlos.
- **Copias cifradas de la clínica** (`apps/common/tenant_backup.py`): AES-GCM
  con la clave derivada por PBKDF2-HMAC-SHA256 y la cabecera como dato
  asociado. Una copia hecha por Django se abre en Kotlin y al revés; escribe
  una prueba con una copia real hecha por Django.
- **Fechas:** se guarda en UTC y «hoy», los meses y los filtros por día van en
  la zona de la clínica (`America/Guayaquil`). Filtra por día con intervalos
  de instantes (inicio del día en la zona de la clínica hasta el inicio del
  siguiente), nunca convirtiendo cada fila. Pasa la suite **dos veces**, la
  segunda con la JVM en `-Duser.timezone=Pacific/Kiritimati` (UTC+14).
- **Límites de intentos** en Redis y compartidos entre hilos e instancias:
  600/min con sesión, 20/min sin sesión por IP, 5/min para pedir códigos,
  10/hora para las solicitudes públicas.
- **Archivos de pacientes** solo por la API con permisos; logotipos públicos
  en `/media/branding/`.
- **PDF:** el motor de estilos de documentos (`apps/common/document_style.py`)
  se porta entero (membrete, logotipo, colores, «Página x de N»). El
  **formulario MSP 033 conserva su propio diseño**. Historia, 033 y
  periodontograma aceptan `?incluir=`. El periodontograma en PDF dibuja las
  piezas con las mismas medidas que el panel. Compara visualmente cada PDF
  con el de Django: misma información en el mismo sitio.
- **Producción segura:** con el perfil de producción, el servidor no arranca
  con claves de ejemplo ni con depuración activa, igual que `config/produccion.py`.

## 6. Estructura del repositorio

```
backend/            Kotlin + Spring Boot: el servidor, con WhatsApp como un módulo más
compartido/         Kotlin Multiplatform: modelos de la API para la app y las pruebas
app/                Kotlin Multiplatform + Compose: la app del paciente (fase 14)
frontend/           copia exacta de clinube/frontend
movil/              copia exacta de clinube/movil (Flutter): testigo hasta que app/ la sustituya
docs/               decisiones, progreso y diferencias encontradas
scripts/            arranque local, comprobación del entorno, comparador de contrato
docker-compose.yml  PostgreSQL 16, Redis 7 y Mailpit (correo de prueba) para desarrollo
settings.gradle.kts los tres módulos de Kotlin
CLAUDE.md           convenciones (ver punto 11)
```

`compartido/` y `app/` se crean cuando les toque; al principio basta con `backend/`.

Haz un guion `scripts/sincronizar-clientes.sh` que copie `frontend/` y
`movil/` desde `../clinube`, para traer los cambios cuando el original avance.

## 7. Entorno local en el Mac

Antes de nada, crea `scripts/comprobar-entorno.sh`: comprueba Java 21,
Docker, Node 20 y Flutter, y dice qué falta y cómo instalarlo.

Para pedirme que instale algo, dame comandos **de uno en uno y sin comentarios
detrás**: en zsh `interactive_comments` puede estar desactivado y un `#` llega
como argumento. Por ejemplo:

```sh
brew install --cask temurin@21
```
```sh
brew install --cask docker
```

Para la app de Kotlin, más adelante:

```sh
brew install --cask android-studio
```

Y para compilarla en iOS, **Xcode completo** desde la App Store: las Command
Line Tools no bastan (`xcodebuild` falla con «requires Xcode»). Android se
prueba con el emulador de Android Studio sin necesidad de Xcode.

- Las dependencias de servicio (PostgreSQL, Redis, Mailpit) corren con
  `docker compose up -d`.
- **El backend escucha en `http://localhost:8000`**, el mismo puerto que
  usaba Django. Así funcionan sin cambios el panel en modo desarrollo
  (`NEXT_PUBLIC_API_URL=http://localhost:8000`, `npm run dev` en el 3000) y la
  app (en iOS `localhost:8000`; en el emulador de Android `10.0.2.2:8000`).
- Un `scripts/start-local.sh` levanta todo con un comando y otro lo para.
- Los datos de prueba: una copia de la clínica demo de `clinube` (se crea con
  `bootstrap` y los guiones de `clinube`), o un `pg_dump` de una base local
  de Django restaurado en la de Kotlin. **Nunca datos reales de pacientes.**

## 8. Plan por fases

Trabaja **módulo por módulo**, cada uno de punta a punta (entidades,
repositorios, servicios, controladores, pruebas y comparación con Django) y
con un commit propio. Lleva un `docs/PROGRESO.md` generado a partir de
`RUTAS.md`, con el estado de cada ruta: pendiente, hecha o igual a Django.

0. **Cimientos:**
   - proyecto Gradle, `CLAUDE.md`, `docker-compose.yml`, comprobación del
     entorno y la copia del panel y la app;
   - Flyway con una línea base sacada del esquema de una base de Django ya
     migrada (`pg_dump --schema-only`, sin las tablas internas de Django que
     no se usan);
   - Jackson, formato de errores, paginación, zona horaria;
   - clínica por usuario, roles y permisos.
1. **Cuentas:** inicio de sesión del personal, JWT y renovación, `auth/me`,
   cambio y recuperación de contraseña, usuarios y funciones, invitaciones.
   *Al terminar, el panel tiene que dejar entrar con un usuario creado por Django.*
2. Configuración y catálogos (tratamientos, especialidades, parámetros,
   convenios, tarifarios, marca e identidad visual, temas).
3. Pacientes (ficha, búsqueda, antecedentes, documentos y archivos, aviso de privacidad).
4. Agenda (citas, vista diaria, semanal y mensual, sala de espera, flujo de
   atención, doctores, firma).
5. Historia clínica: evoluciones, diagnósticos, odontograma y sus registros,
   periodontograma, formulario 033, exámenes, consentimientos, plantillas de plan.
6. Motor de documentos y todos los PDF (historia, 033, periodontograma,
   receta, certificado, consentimiento, examen, comprobantes) y el Excel del 033.
7. Cobros: presupuestos, planes de pago, cuotas, pagos, estado de cuenta, morosidad.
8. Inventario y reportes (con Excel).
9. Finanzas: ingresos, egresos, caja, honorarios, rol de pagos, IESS/SRI,
   décimos y exportación. **Las pruebas de cálculo de clinube se portan una a una.**
10. Rutas de la app del paciente en el servidor: código por correo, cuenta
    propia, Google, citas, solicitudes, mensajes, saldo, logros. *Al terminar,
    la app Flutter tiene que funcionar entera contra el servidor de Kotlin.*
11. Plataforma: clínicas, solicitudes públicas, funcionalidades, correo SMTP,
    condiciones legales, auditoría.
12. Copias de seguridad cifradas (compatibles con las de Django) y tareas
    programadas.
13. WhatsApp: lo que hoy hace `whatsapp-gateway`, como módulo del servidor,
    y los recordatorios.
14. **App del paciente en Kotlin** (`compartido/` y `app/`):
    - las mismas pantallas, textos, colores y logotipo que la de Flutter
      (`movil/lib/pantallas/`, `movil/lib/tema.dart`, `movil/lib/logo.dart`);
    - el mismo identificador, `com.clinube.paciente`, en Android y en iOS,
      para que llegue a las tiendas como una **actualización** de la actual y
      no como otra app; en Android, firmada con la misma clave de subida (ver
      `movil/PUBLICAR.md`);
    - la app Flutter se retira solo cuando la nueva haga todo lo que hacía.

## 9. Cómo se demuestra la paridad

- **Comparador de contrato** (`scripts/comparar-contrato`):
  - arranca Django de `../clinube` en el **8010** y Kotlin en el **8000**,
    cada uno con su copia de la misma base;
  - lanza la misma lista de peticiones (con el mismo usuario) contra los dos;
  - compara código HTTP, claves y tipos de cada JSON, ignorando lo que cambia
    solo (ids nuevos, fechas de creación, tokens);
  - el informe va en `docs/PROGRESO.md`.
- **Pruebas portadas** de `clinube/django-api/apps/*/tests*.py`, empezando por
  aislamiento entre clínicas, permisos, fechas en los bordes del día,
  cálculos de finanzas y periodontograma, y cifrado de copias.
- **La app Flutter:** sus pruebas usan respuestas capturadas de la API real
  (`movil/test/fixtures/`). Recaptúralas contra el servidor de Kotlin y
  comprueba que `flutter test` sigue pasando sin tocar las pruebas.
- **La app de Kotlin:** pasa sus pruebas con esas mismas respuestas
  capturadas, leídas con los modelos de `compartido/`, y se compara pantalla
  por pantalla con capturas de la de Flutter.
- **En el navegador:** abre el panel contra el servidor de Kotlin y recorre el
  módulo terminado, con capturas. Si algo se ve o se comporta distinto que
  con Django, el fallo está en el servidor.

## 10. Lo que ya aprendimos en clinube (no lo repitas)

- **Sin N+1:** usa `@EntityGraph` o `JOIN FETCH` en las listas. La auditoría
  y la lista de pacientes deben hacer las mismas consultas con 3 filas que con 30.
- Atenciones y próxima cita de la lista de pacientes: subconsultas por fila
  después de paginar, no un JOIN con GROUP BY sobre todas las citas.
- Los índices compuestos de `MODELO_DE_DATOS.md` se crean igual.
- Los informes agrupan en la base, no en memoria.
- Conexiones a la base reutilizadas (HikariCP) y PostgreSQL afinado: la
  configuración de `clinube/docker-compose.prod.yml` sirve de referencia.

## 11. Convenciones de trabajo (ponlas en `CLAUDE.md` desde el primer commit)

- **Idioma:** código, comentarios, nombres de dominio, mensajes de commit y
  textos en castellano, como en clinube. Los textos de la interfaz y de los
  errores son los de clinube, copiados.
- **Autoría de los commits:**
  ```sh
  git config user.name "Jorgeperezr"
  ```
  ```sh
  git config user.email "148003448+Jorgeperezr@users.noreply.github.com"
  ```
- **Archivos que no se tocan**, ni en la copia del panel: el odontograma
  (`frontend/lib/odontogram/meshProvider.js`, `contract.js`, `registry.js`,
  `Odontogram3D.js`), `frontend/lib/ClinicalTabs.js`,
  `frontend/lib/Odontogram.js` y `frontend/lib/periodontal/PeriodontalMatrix.js`.
  El panel y la app Flutter (`movil/`) no se modifican: llegan de `clinube`
  con `scripts/sincronizar-clientes.sh`.
- **Sin dependencias que no hagan falta**, y ninguna con licencia AGPL o GPL
  incompatible.
- **Validar antes de cada commit:**
  ```sh
  ./gradlew test
  ```
  La segunda pasada se hace con la zona `Pacific/Kiritimati`, y el
  comparador de contrato se ejecuta para el módulo tocado.
- **Seguridad:**
  - Nunca me pidas ni aceptes en el chat claves privadas, contraseñas ni
    secretos de producción; solo claves públicas.
  - Si necesitas una salida de terminal, dime que quite antes cualquier línea
    con secretos.
  - No te conectes al servidor de producción ni a su base.
- No despliegues nada: este proyecto es local hasta que yo decida otra cosa.
- **Sé honesto con el avance:** si una ruta no está igual que en Django,
  `PROGRESO.md` lo dice, aunque las pruebas propias pasen.

## 12. Primera sesión

1. Clona `clinube` al lado y lee lo del punto 4.
2. Crea los cimientos de la fase 0:
   - el proyecto Gradle con el módulo `backend` (Spring Boot y Kotlin);
   - `CLAUDE.md`;
   - `docker-compose.yml` con PostgreSQL, Redis y Mailpit;
   - `scripts/comprobar-entorno.sh` y `scripts/start-local.sh`;
   - la copia de `frontend/` y `movil/`;
   - la línea base de Flyway desde el esquema de Django;
   - la configuración de Jackson, los errores y la paginación;
   - `docs/PROGRESO.md` con las ~200 rutas pendientes.
3. Deja funcionando de punta a punta `POST /api/v1/auth/login/`,
   `POST /api/v1/auth/token/refresh/` y `GET /api/v1/auth/me/`, con un usuario
   creado por Django, y comprueba que el panel entra con él.
4. Haz commit y push a `main` de `clinube_java`, y cuéntame qué falta
   instalar en mi Mac, si falta algo, con los comandos de uno en uno.
