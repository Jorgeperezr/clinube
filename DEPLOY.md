# Guía de despliegue a producción

## Decisión de hosting (pendiente del usuario)

> **Actualización (septiembre de 2026):** la opción que cuesta solo el
> dominio es la **Opción C — Oracle Cloud Always Free**, más abajo. Las A
> y B se mantienen como alternativa.

| Criterio | Opción A: VM en GCP | Opción B: PC en la clínica + Cloudflare Tunnel |
|---|---|---|
| Costo mensual | ~US$35-45 (e2-medium + disco + IP) | ~US$0 (electricidad + internet ya pagados) |
| Disponibilidad | Alta (99.9%; SLA del proveedor) | Depende de la luz/internet de la clínica |
| Acceso remoto | Nativo (IP pública) | Vía túnel (sin abrir puertos del router) |
| Backups | Snapshots automáticos del disco | Hay que armarlos (script pg_dump + copia externa) |
| Mantenimiento | Actualizaciones del SO a cargo tuyo | Ídem + hardware físico a tu cargo |
| Riesgo principal | Costo recurrente | Robo/daño del equipo = pérdida del servidor |
| Recomendado si… | La clínica depende del sistema a diario | Presupuesto cero y tolerancia a caídas |

**Recomendación:** empezar con la Opción B (costo cero) durante la marcha
blanca, con backups externos diarios; migrar a la Opción A cuando el
sistema sea crítico para la operación. El código es idéntico en ambas.

---

## Pasos comunes (ambas opciones)

1. **Servidor con Docker:** Ubuntu 22.04+ con Docker Engine y el plugin
   `docker compose`.
2. **Clonar el repo:**
   ```bash
   git clone https://github.com/Jorgeperezr/clinube.git
   cd clinube
   ```
3. **Configurar el entorno.** Lo más sencillo, con el dominio comprado:
   ```bash
   bash scripts/configurar-produccion.sh clinube.com
   ```
   Crea el `.env` con claves nuevas generadas en el propio servidor y el
   panel en `app.clinube.com`, y enseña UNA vez la clave de las copias de
   seguridad para guardarla fuera. A mano, sería:
   ```bash
   cp .env.production.example .env
   nano .env   # completar TODOS los CAMBIAR- y el dominio real
   python3 -c "import secrets; print(secrets.token_urlsafe(64))"  # para la SECRET_KEY
   ```
   **El servidor no arranca si queda algo de ejemplo.** Con
   `docker-compose.prod.yml` (que fija `DJANGO_ENTORNO=produccion`),
   `config/produccion.py` exige `DJANGO_DEBUG=False`, una
   `DJANGO_SECRET_KEY` propia de 50+ caracteres, un
   `INTERNAL_SERVICE_TOKEN` de 32+ y una `POSTGRES_PASSWORD` de 12+, y
   rechaza cualquier valor con «CAMBIAR» o «change-me». El contenedor
   `django-api` se detiene con la lista de lo que falta:
   `docker compose -f docker-compose.prod.yml logs django-api`.
   Con la clave de ejemplo, cualquiera podría firmar tokens de acceso
   válidos y entrar sin contraseña.
4. **Levantar:**
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```
5. **Crear la cuenta del dueño de la plataforma** (Super Administrador,
   sin clínica; desde su panel se dan de alta las clínicas):
   ```bash
   docker compose -f docker-compose.prod.yml exec django-api python manage.py createsuperadmin --email tu@correo.com --password 'una-clave-larga'
   ```
   No `createsuperuser`: ese crea un usuario de Django sin el rol de
   la plataforma, que no ve el panel de Plataforma.
6. **Verificar:** `curl -I http://localhost` debe devolver 200 (panel) y
   `curl http://localhost/api/v1/ready/` también. La documentación de la
   API (`/api/v1/schema/swagger-ui/`) en producción pide sesión: publicarla
   le daría a cualquiera el mapa completo de la API.

## Opción A — VM en GCP

1. Crear VM e2-medium (2 vCPU, 4 GB) en `southamerica-west1`, Ubuntu 22.04,
   disco 30 GB. Reservar IP estática.
2. Firewall: permitir 80 y 443, y en el `.env` `NGINX_PUERTO=80`
   (por omisión Nginx solo escucha en `127.0.0.1`, pensado para el túnel).
3. Apuntar el dominio (registro A) a la IP.
4. TLS con certbot en el host + Nginx del host como proxy, o Cloudflare
   proxied DNS (más simple: activar el proxy naranja de Cloudflare y usar
   modo Full).
5. En `.env`: `SECURE_SSL_REDIRECT=True` si el TLS es propio (certbot).
6. Backups: activar snapshots diarios del disco en GCP.

## Opción B — PC en la clínica + Cloudflare Tunnel

1. PC dedicada (8+ GB RAM recomendado) con Ubuntu Server y Docker, UPS si
   es posible.
2. Dominio en Cloudflare (el DNS del dominio debe estar en Cloudflare).
3. Instalar el túnel:
   ```bash
   # En el host (fuera de Docker):
   curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
   sudo dpkg -i cloudflared.deb
   cloudflared tunnel login
   cloudflared tunnel create clinube
   cloudflared tunnel route dns clinube app.clinube.com
   ```
4. Configurar `/etc/cloudflared/config.yml`:
   ```yaml
   tunnel: clinube
   credentials-file: /root/.cloudflared/<ID>.json
   ingress:
     - hostname: app.clinube.com
       service: http://localhost:80
     - service: http_status:404
   ```
5. `sudo cloudflared service install && sudo systemctl start cloudflared`
6. En `.env`: `SECURE_SSL_REDIRECT=False` (Cloudflare ya fuerza HTTPS).

## Opción C — Oracle Cloud «Always Free» (recomendada: solo se paga el dominio)

Comparativa hecha en septiembre de 2026:

| Proveedor | Qué da gratis | ¿Sirve para este sistema? |
|---|---|---|
| **Oracle Cloud Always Free** | VM Arm Ampere A1 de **2 OCPU y 12 GB** (recortada en junio de 2026 desde 4/24), 200 GB de disco, 10 TB/mes de salida, 20 GB de Object Storage. Sin fecha de fin. | **Sí.** Sobra para Django, PostgreSQL, Redis, Celery, Nginx y la pasarela de WhatsApp juntos. |
| AWS | Desde julio de 2025, las cuentas nuevas reciben 100–200 US$ en créditos que caducan a los 6 meses. | No para siempre: a los 6 meses hay que pagar. |
| Google Cloud | Una e2-micro (2 vCPU compartidas, **1 GB**) en regiones de EE. UU., sin fecha de fin. | No: 1 GB no alcanza para la base de datos y el resto. |
| Azure | 12 meses de una B1s (1 GB) y créditos de 30 días. | No: temporal y escasa. |

**Lo que hay que saber de Oracle antes de empezar:**

- Pide **tarjeta** al registrarse (verificación; no cobra si no se sale
  de lo gratuito).
- **Recupera las VM «ociosas»** de las cuentas gratuitas: si durante 7
  días la CPU (percentil 95), la red y la memoria quedan por debajo del
  20 %, puede apagarla. Una clínica pequeña puede quedar por debajo.
  Remedio recomendado: **pasar la cuenta a «Pay As You Go»** (sigue
  costando 0 US$ mientras no se salga de lo gratuito y la regla de VM
  ociosas no se aplica) y **crear una alerta de presupuesto de 1 US$**
  para enterarse si algo empieza a cobrar.
- Lo gratuito de A1 es **el mismo con Pay As You Go**: «todas las
  cuentas» reciben 1.500 horas de OCPU y 9.000 GB-hora al mes, es
  decir, 2 OCPU y 12 GB encendidos el mes entero, y lo que pase de ahí
  se cobra. Algunas respuestas del soporte decían que la cuenta de pago
  conservaba el cupo anterior de 4 OCPU / 24 GB; la documentación
  (*Always Free Resources*, octubre de 2026) no lo recoge.
- La VM Arm a veces da «Out of capacity» al crearla: se reintenta más
  tarde o en otro dominio de disponibilidad. En Santiago hay un solo
  dominio y casi nunca hay capacidad: ver «Crear la máquina desde tu
  ordenador», justo debajo.

### Crear la máquina desde tu ordenador

`scripts/oracle-local.sh` intenta crearla desde el Mac mientras está
encendido, cada 2 minutos, hasta que Oracle tenga sitio; entonces avisa
con una notificación y da la IP. No gasta minutos de GitHub. Quien habla
con Oracle es `scripts/crear-instancia-oracle.sh`, el mismo que usaba el
flujo de Actions.

Todo desde la carpeta del repositorio, con los cambios al día:

```sh
git pull
```

Una sola vez:

1. La CLI de Oracle, con el instalador oficial (no con Homebrew: en los
   Mac con Intel compila LLVM y Rust, horas). Acepta todo lo que pregunta
   y después abre una ventana nueva de la Terminal:

   ```sh
   bash -c "$(curl -fsSL https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)" -s --accept-all-defaults
   ```

2. La clave de API en el Mac. El guion crea una nueva —la privada no
   sale del Mac—, copia la pública al portapapeles y dice dónde pegarla
   en Oracle; después pide la «vista previa del archivo de
   configuración» que enseña Oracle al agregarla:

   ```sh
   bash scripts/oracle-local.sh --configurar
   ```

   Si había otra clave de API que se descargó o se compartió fuera del
   Mac, bórrala en **Mi perfil → Claves de API** cuando la nueva
   funcione.

3. Comprobar que no falta nada (la clave, la subred pública y la clave
   SSH `~/.ssh/clinube` con la que se entrará en la máquina):

   ```sh
   bash scripts/oracle-local.sh --comprobar
   ```

Y a intentar, de una de estas dos formas:

- En una ventana de la Terminal, que se deja abierta (Ctrl+C lo para):

  ```sh
  bash scripts/oracle-local.sh
  ```

- En segundo plano: sigue aunque se cierre la Terminal y vuelve a
  empezar cada vez que se enciende el Mac y se inicia sesión, hasta
  crearla. Al conseguirlo deja de arrancar solo.

  ```sh
  bash scripts/oracle-local.sh --al-encender
  ```

  Para ver cómo va y para pararlo:

  ```sh
  bash scripts/oracle-local.sh --estado
  bash scripts/oracle-local.sh --parar
  ```

Mientras intenta, el Mac no se duerme solo; cerrar la tapa de un
portátil sí lo duerme, y dormido no intenta. Si se corta internet,
espera y sigue. Nunca crea una segunda máquina: antes de cada intento
mira si ya existe `clinube`, y si no puede mirarlo, no lanza.

### Crear la máquina desde GitHub Actions (desactivado)

Desactivado en octubre de 2026: agotó los minutos de Actions del mes, y
con ellos el CI. Queda como referencia; lo que se usa ahora es «Crear
la máquina desde tu ordenador», arriba.

El flujo `.github/workflows/oracle-instancia.yml` intenta crearla cada
hora durante unos 55 minutos, una vez cada 5 minutos, y al acabar se
relanza solo (GitHub descarta muchas ejecuciones programadas) (`scripts/crear-instancia-oracle.sh`), sin tener Cloud Shell
abierto ni el computador encendido. Cuando lo consigue, abre una
incidencia en el repositorio con la IP —llega por correo— y se apaga.

Necesita una **clave de API** de Oracle, distinta de la clave SSH:

1. En la consola de Oracle: icono de perfil (arriba a la derecha) →
   **Mi perfil** → **Claves de API** → **Agregar clave de API** →
   **Generar par de claves de API** → **Descargar clave privada** →
   **Agregar**.
2. Oracle enseña una «vista previa del archivo de configuración» con
   `user`, `fingerprint` y `tenancy`.
3. En GitHub: el repositorio → **Settings** → **Secrets and variables**
   → **Actions** → **New repository secret**, cuatro veces:

   | Secreto | Valor |
   |---|---|
   | `OCI_USER_OCID` | el `user=` de la vista previa (`ocid1.user…`) |
   | `OCI_TENANCY_OCID` | el `tenancy=` (`ocid1.tenancy…`) |
   | `OCI_FINGERPRINT` | el `fingerprint=` (`aa:bb:…`) |
   | `OCI_PRIVATE_KEY` | el contenido entero del `.pem` descargado, con las líneas `BEGIN` y `END` |

   La clave privada va **solo** ahí: no se pega en ningún chat, correo
   ni archivo del repositorio. Después se puede borrar del Mac.
4. **Actions** → «Crear la máquina en Oracle» → **Run workflow**, para
   comprobar que las credenciales funcionan: debe terminar en verde con
   «Sin capacidad…» o con la máquina creada. Si termina en rojo, el
   mensaje dice qué falta.

Mientras corre, hay que **parar el bucle de Cloud Shell** (Ctrl+C): los
dos a la vez gastan el cupo de peticiones de Oracle. El guion no crea
una segunda máquina si ya existe una llamada `clinube`.

Cada ejecución gasta unos 57 minutos de Actions, así que los 3000 al mes
de la cuenta Pro de estudiante se acaban en pocos días. Entonces Actions
—también el CI— se detiene hasta el mes siguiente, sin cobrar nada
mientras el límite de gasto siga en 0 $. Se eligió así para tener la
máquina cuanto antes: GitHub descarta la mayoría de las ejecuciones
programadas frecuentes, y un intento suelto cada 10 minutos se quedaba
en dos al día. Si en una o dos semanas no sale, lo efectivo es pasar
la cuenta a Pay As You Go (ver arriba): con la cuenta de pago suele haber
capacidad al primer o segundo intento.
- Todo lo del proyecto funciona en Arm: las imágenes de Python,
  PostgreSQL, Redis y Nginx son multiarquitectura.

**Lo que dicen las condiciones de Oracle y cómo se cumple aquí:**

| Condición | Cómo se cumple |
|---|---|
| La seguridad del sistema operativo, de los datos y de las copias es del cliente | Parches automáticos (`preparar-servidor.sh`), copias cifradas y una copia fuera de Oracle |
| Al terminar o suspenderse el servicio, los datos se pueden borrar sin más | La copia fuera de Oracle (ver «Copia fuera del servidor») |
| Prohibido escanear o probar la infraestructura de Oracle | No se pasan escáneres de vulnerabilidades contra la IP pública, la red ni los servicios de Oracle. Lo que se pruebe, contra el propio sistema en local |
| Las cuentas gratuitas pueden suspenderse o cambiar de condiciones | Pay As You Go con alerta de presupuesto, y la copia fuera |
| Los datos personales de terceros (los pacientes) son responsabilidad del cliente | Aviso de privacidad público (`/privacidad`), registro de su entrega en la ficha y condiciones aceptadas por cada clínica |

**Pasos:**

1. Cuenta en <https://www.oracle.com/cloud/free/>. Región de inicio:
   **Chile Central (Santiago)**, la más cercana a Ecuador (si no hay
   capacidad, *Brazil East (São Paulo)*). La región de inicio no se
   puede cambiar después.
2. **Antes de crear nada**, en *Billing & Cost Management*:
   - *Upgrade and Manage Payment* → **Pay As You Go**. Sigue costando 0
     US$ mientras todo sea «Always Free», y evita que Oracle recupere la
     VM por ociosa. Tipo de cuenta **Individual** (la *Corporate* no
     tiene vuelta atrás). Al pedirlo, Oracle retiene **100 US$** en la
     tarjeta y la anula enseguida, aunque el banco tarda lo suyo en
     liberarlos; y el cambio puede tardar **uno o dos días**: llega un
     correo y la página pasa a llamarse *Manage Payment*.
   - *Budgets* → *Create Budget*: importe **1 US$** al mes, alerta al
     **1 %** del presupuesto *real* (no el previsto), con tu correo. Si
     algo empieza a cobrar, llega un aviso en el día.
   - Al crear recursos, fijarse en que lleven la etiqueta
     **«Always Free-eligible»**.

   Si la cuenta todavía está en la **prueba de 30 días** o «en
   aprovisionamiento» (la página de cambio de versión no deja hacer
   nada), Pay As You Go se puede dejar para después y crear ya la VM,
   con dos condiciones: que sea **una sola A1 de 2 OCPU y 12 GB** —si al
   terminar la prueba hay más Ampere A1 que las gratuitas, Oracle
   desactiva **todas** y las borra a los 30 días— y pasar a Pay As You
   Go **antes de cargar pacientes reales**, que es cuando importa que no
   la recupere por ociosa. Durante la prueba lo que no es gratuito se
   paga con los créditos, no con la tarjeta.
3. Crear instancia: *Ubuntu 24.04*, forma **VM.Standard.A1.Flex** con
   2 OCPU y 12 GB, disco de arranque de 100 GB. Guardar la clave SSH.
   **No añadir reglas de entrada** en la *Security List* ni en un
   *Network Security Group*: la que trae (SSH, puerto 22) es la única
   que hace falta. Los puertos 80 y 443 se quedan cerrados.
4. En la VM, preparar el sistema (parches, actualizaciones de seguridad
   automáticas, Docker y rclone):
   ```bash
   git clone https://github.com/Jorgeperezr/clinube.git
   cd clinube
   sudo bash scripts/preparar-servidor.sh
   ```
   Salir y volver a entrar por SSH, y seguir los **Pasos comunes** de
   arriba desde el 3.
5. Publicarla con **Cloudflare Tunnel** (igual que la Opción B, pasos
   2 a 6): el túnel sale desde la VM hacia Cloudflare, así que no hace
   falta abrir puertos, y el certificado HTTPS lo pone Cloudflare gratis.
   El binario para esta VM es el de Arm: `cloudflared-linux-arm64.deb`.
6. Comprobar que no quedó nada abierto hacia fuera:
   ```bash
   sudo bash scripts/preparar-servidor.sh --comprobar
   ```
7. Copias: `scripts/backup.sh` a diario con cron y la copia **fuera de
   Oracle**, en Cloudflare R2 (ver «Copia fuera del servidor»). No en el
   Object Storage de Oracle: si la cuenta se suspende, la copia se va
   con el servidor.

**Lo único que se compra: el dominio, `clinube.com`.** Cómo se reparte:

| Dirección | Qué hay |
|---|---|
| `app.clinube.com` | El panel y la API (Nginx sirve los dos en el mismo nombre) |
| `clinube.com` | Libre para la web comercial; mientras no exista, puede redirigir a `app.` |
| `nombreclinica.clinube.com` | Reservado para la dirección propia de cada clínica (siguiente paso) |

Un solo nivel por debajo de `clinube.com` a propósito: el certificado
gratuito de Cloudflare cubre `*.clinube.com`, pero no `*.algo.clinube.com`.

Recomendado registrarlo en
**Cloudflare Registrar**, que lo vende a precio de coste (un `.com`
ronda los 10–11 US$ al año) y deja el DNS y el túnel en el mismo sitio.
Un `.ec` se compra en NIC.ec y cuesta bastante más; si se quiere, se
apunta igualmente a Cloudflare.

**Lo que NO es gratis aunque el servidor lo sea:**
- Los mensajes de WhatsApp (Meta cobra por mensaje de plantilla, también
  los códigos de ingreso de la app).
- Las cuentas de las tiendas: Apple 99 US$/año, Google Play 25 US$ una vez.
- El correo, si se superan los envíos de un plan gratuito (p. ej. Brevo
  da 300 al día, de sobra para recuperar contraseñas).

## Backups CIFRADOS (obligatorio en las opciones B y C, recomendado en la A)

Hay **dos copias distintas** y conviene no confundirlas, porque protegen
cosas diferentes y las hace gente diferente:

| | Copia de la plataforma | Copia de la clínica |
|---|---|---|
| Qué contiene | La base entera de **todas** las clínicas y sus archivos | Los datos de **una** clínica (o los pacientes de un profesional), con sus archivos si se piden |
| Quién la hace | Quien administra el servidor | La administradora de la clínica; cada doctor o auxiliar, la suya |
| Desde dónde | `scripts/backup.sh` en el servidor | Panel → Configuración → Copia de seguridad, o «Mi respaldo» |
| Clave | `BACKUP_PASSPHRASE` del `.env` | La frase que escribe en pantalla |
| Sirve para | Recuperar el servicio ante un desastre | Que la clínica conserve y consulte sus datos |
| Restaura | Sí, con `scripts/restore.sh` | No: solo descifra y muestra el contenido |

La copia de la clínica **no sustituye** a la de la plataforma: no permite
levantar el servicio de nuevo. Puede llevar los archivos adjuntos
(radiografías, documentos, consentimientos firmados) si se marca «Incluir
los archivos», hasta 150 MB por copia; lo que no cabe queda listado en
el manifiesto. Es la exportación completa que la clínica se lleva si
deja la plataforma. La de la plataforma sigue siendo obligatoria.

### Copia de la plataforma (servidor)

El repo incluye `scripts/backup.sh` (exporta toda la base — pacientes,
registros clínicos, pagos — y la cifra con AES-256) y `scripts/restore.sh`
(restaura un backup ante un error, con confirmación explícita).

Configuración (una vez):
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# → pegar el resultado en BACKUP_PASSPHRASE del .env
# → guardar una COPIA de esa clave fuera del servidor (gestor de
#   contraseñas / papel en caja fuerte): sin ella el backup no se
#   puede descifrar.
```

Copia manual: `COMPOSE_FILE=docker-compose.prod.yml ./scripts/backup.sh`

Los guiones funcionan **con Docker y sin él**: si no hay demonio usan el
`pg_dump` / `psql` de la máquina. Eso permite hacer y comprobar copias
desde un portátil sin Docker Desktop.

Cada copia son **dos archivos**: `clinica-….sql.gz.enc` (la base) y
`archivos-….tar.gz.enc` (radiografías, documentos escaneados, firmas,
logotipos). Sin el segundo, una restauración devolvería las fichas con
los adjuntos rotos.

Cron diario (sale con código distinto de 0 si algo falla, también si no
se pudo subir la copia fuera, y entonces avisa por correo):
```bash
# /etc/cron.d/backup-clinica  (07:00 UTC = 02:00 en Ecuador)
0 7 * * * root cd /ruta/al/repo && COMPOSE_FILE=docker-compose.prod.yml ./scripts/backup.sh >> /var/log/backup-clinica.log 2>&1 || mail -s "FALLO: copia de la clinica" tu@correo.ec < /var/log/backup-clinica.log
```
(`mail` viene en el paquete `mailutils`; sin correo configurado en la
VM, al menos queda en el registro.)

Las copias viejas se borran solas: a los `BACKUP_LOCAL_DIAS` (14) en el
servidor y a los `BACKUP_REMOTO_DIAS` (30) fuera.

### Copia fuera del servidor

Una copia que vive en la misma máquina —o en la misma cuenta de nube—
no es una copia: si la VM se pierde o la cuenta se suspende, se va con
ella. `backup.sh` sube las dos piezas con **rclone** al destino de
`BACKUP_REMOTO` y comprueba que llegaron enteras. Sin `BACKUP_REMOTO`
avisa en cada ejecución.

Con **Cloudflare R2** (10 GB gratis, sin coste de salida):

1. Panel de Cloudflare → *R2* → *Create bucket*: `clinube-copias`.
2. *R2* → *Manage API Tokens* → *Create API Token*, permiso
   **Object Read & Write**, limitado a ese bucket. Anotar el *Access Key
   ID*, el *Secret Access Key* y el *endpoint*
   (`https://<id-de-cuenta>.r2.cloudflarestorage.com`).
3. En la VM, como root (el cron corre como root):
   ```bash
   sudo rclone config create r2 s3 provider=Cloudflare access_key_id=EL_ID secret_access_key=EL_SECRETO endpoint=https://ID.r2.cloudflarestorage.com no_check_bucket=true
   ```
4. En el `.env`: `BACKUP_REMOTO=r2:clinube-copias`
5. Probar: `COMPOSE_FILE=docker-compose.prod.yml sudo -E ./scripts/backup.sh`
   debe terminar con «✓ Copias guardadas fuera del servidor», y
   `sudo rclone ls r2:clinube-copias` listar los dos archivos.

Las copias van cifradas antes de salir: Cloudflare guarda bytes que no
puede leer. La clave (`BACKUP_PASSPHRASE`) no se sube nunca con ellas.

### Verificación: una copia sin restaurar no es una copia

`backup.sh` comprueba al terminar que el volcado **está completo** —que
el SQL termina donde `pg_dump` lo cierra—. Eso descarta el fallo más
común y más silencioso: que la exportación se corte a la mitad porque se
llenó el disco o se reinició el contenedor.

Antes esa comprobación era `gzip -t`, que solo prueba que el archivo se
descomprime. **Un volcado partido por la mitad comprime perfectamente y
pasaba la prueba**: se anunciaba «correcto» una copia irrecuperable.
Verificado cortando un volcado a propósito.

Pero que el archivo esté entero no significa que se pueda restaurar. Eso
solo lo dice restaurarlo:

```bash
./scripts/verificar-backup.sh            # la copia más reciente
./scripts/verificar-backup.sh <archivo>  # una concreta
```

Descifra, **restaura de verdad en una base desechable**, cuenta las filas
de las tablas que importan y la destruye al salir. Nunca toca la base
real: el nombre de la base de prueba se genera con marca de tiempo y el
guion aborta si coincidiera con la de producción.

Devuelve `0` si la copia sirve y distinto de `0` si no, para poder
avisar. Comprobado que **falla** ante los cuatro casos que importan: un
volcado truncado, uno con esquema pero sin datos, la frase de cifrado
equivocada y un archivo inexistente.

Semanal:
```bash
# /etc/cron.d/verificar-backup-clinica  (domingos a las 03:00)
0 3 * * 0 root cd /ruta/al/repo && COMPOSE_FILE=docker-compose.prod.yml ./scripts/verificar-backup.sh >> /var/log/verificar-backup.log 2>&1 || mail -s "FALLO: la copia de la clinica NO es restaurable" tu@correo.ec
```

### En macOS

macOS trae **LibreSSL**, no OpenSSL, y su `enc` no siempre acepta
`-pbkdf2`. Sin esa opción el cifrado caería a una derivación de clave
mucho más débil y —lo grave— no podría descifrar las copias hechas en el
servidor. Los tres guiones lo comprueban antes de escribir nada y
explican qué hacer:

```bash
brew install openssl@3
export PATH="$(brew --prefix openssl@3)/bin:$PATH"
```

### Restauración ante un error real

```bash
COMPOSE_FILE=docker-compose.prod.yml ./scripts/restore.sh backups/clinica-2026-07-09_0200.sql.gz.enc
```

Comprueba que la copia esté completa **antes** de tocar la base: descubrir
que estaba truncada después de haberla borrado es la peor secuencia
posible, y era la que permitía el guion anterior.

Los adjuntos se restauran aparte, con el mismo guion y su propio
archivo:
```bash
COMPOSE_FILE=docker-compose.prod.yml ./scripts/restore.sh backups/archivos-2026-07-09_0200.tar.gz.enc
```

Para restaurar desde fuera, bajar antes las dos piezas:
`rclone copy r2:clinube-copias/clinica-2026-07-09_0200.sql.gz.enc backups/`
(y la de `archivos-` con la misma fecha).

Probar la restauración al menos una vez antes de tener pacientes reales.

### Copia de la clínica (panel)

En **Configuración → Copia de seguridad**, la administradora de la
clínica genera un archivo `.clinicabk` con los datos de su clínica y lo
vuelve a abrir desde la misma pantalla escribiendo su frase de cifrado.

**Cada doctor o auxiliar** puede sacar la suya desde **«Mi respaldo»**:
los pacientes que ha atendido (con cita suya o con algo que escribió en
su historia), la historia clínica completa de esos pacientes y su
agenda. Sin cobros, inventario, auditoría ni pacientes de otros. Es la
función «Respaldo cifrado de sus pacientes» de cada profesional: viene
marcada y la administración la quita en Configuración → Usuarios.
Recepción no la tiene (no ve datos clínicos). Un profesional solo abre
en el panel sus propias copias; la administración, cualquiera de su
clínica.

**Lo que se descarga es un `.zip`** con la copia y lo necesario para
abrirla sin la plataforma:

| Archivo | Para qué |
|---|---|
| `respaldo-….clinicabk` | La copia cifrada |
| `COMO-DESCIFRAR.txt` | Instrucciones con los datos de esa copia y la especificación del formato |
| `descifrar.html` | Abre la copia en cualquier navegador, **sin internet**: tablas, CSV y JSON |
| `descifrar.py` | Lo mismo en la terminal (Python 3.8+ y `cryptography`) |

Las herramientas están en `django-api/apps/common/kit_respaldo/` y no
dependen del proyecto; `tests_paquete_respaldo.py` comprueba que
`descifrar.py` abre las copias que genera el servidor. Desde el panel
se pueden bajar también sueltas, para copias antiguas.

- Cifrado AES-256-GCM con clave derivada por PBKDF2-HMAC-SHA256
  (400 000 iteraciones). El archivo va autenticado: si se altera un solo
  byte, no se abre.
- **La frase no se guarda en ninguna parte**, tampoco en la auditoría.
  Perderla equivale a perder el archivo.
- El Super Administrador de la plataforma no puede emitir ni abrir
  estas copias: administra el servicio, no es titular de los datos de
  ninguna clínica.
- Descifrar no restaura nada. Reponer datos sobre la base sigue siendo
  una operación de servidor (`scripts/restore.sh`), no de panel.
- El JSON descifrado que se descarga va **sin cifrar** y contiene datos
  de salud: hay que borrarlo del equipo al terminar (LOPDP).

## Las dos apps

| | App del paciente | App del personal |
|---|---|---|
| Qué es | Flutter (`movil/`) | El mismo panel web, instalable (PWA) |
| Quién la usa | Pacientes | Administración, recepción, doctores, auxiliares |
| Cómo se instala | App Store y Google Play | Desde el navegador: Android/Chrome → «Instalar app»; iPhone/iPad/Safari → Compartir → «Añadir a pantalla de inicio». Las instrucciones están en el panel, en Mis preferencias |
| Cómo se actualiza | Publicando versión en las tiendas | Sola, con cada despliegue del panel |
| Coste | Cuentas de las tiendas | Ninguno |

**Página de descargas:** `/descargar/` (y `/download/`, que redirige)
presenta las dos apps con la marca de Clinube. Cuando la app del paciente
esté publicada, poner sus enlaces en `URL_APP_STORE` y `URL_GOOGLE_PLAY`
del `.env` y volver a compilar el panel
(`docker compose -f docker-compose.prod.yml up frontend-build`); mientras
estén vacíos, la página dice «Muy pronto». Si `clinube.com` apunta al
mismo servidor, `www.clinube.com/descargar/` funciona sin más.

La app del personal **solo funciona con HTTPS** (en `localhost` también,
para probar): con el túnel de Cloudflare ya lo está. Guarda en el
dispositivo el envoltorio del panel —páginas, JS, CSS, iconos— y **nunca**
respuestas de la API ni archivos de pacientes (`frontend/public/sw.js`).
Sin conexión abre lo ya visitado y dice «Sin conexión» al pedir datos.

Nginx sirve `sw.js` sin caché (si no, los teléfonos no se enterarían de
un despliegue) y `/_next/static/` con caché de un año, porque esos
archivos llevan un hash en el nombre.

Si un día hace falta que el personal la descargue de las tiendas, se
puede envolver el mismo panel en una app nativa; supone una dependencia
nueva (un WebView) y Apple suele rechazar las apps que solo envuelven una
web, así que la PWA es la vía recomendada.

## Actualizaciones del sistema

```bash
cd /ruta/al/repo
git pull
docker compose -f docker-compose.prod.yml up -d --build
```
(Las migraciones corren solas en el arranque.)

## Sondas de salud y orden de arranque

Django expone dos rutas **públicas y sin autenticación** (un monitor no
tiene credenciales):

| Ruta | Pregunta | Toca la base de datos |
|---|---|---|
| `GET /api/v1/health/` | ¿Está vivo el proceso? | No |
| `GET /api/v1/ready/` | ¿Puede atender? | Sí (`SELECT 1`) |

Son dos preguntas distintas y conviene no mezclarlas. Si `/ready/`
devuelve 503, el proceso está sano pero le falta la base: hay que sacarlo
del reparto de tráfico, **no reiniciarlo**. Reiniciar procesos sanos
porque la base tiene un mal momento convierte una incidencia en una
caída.

Ninguna de las dos revela versión, motor, nombre de clínica ni cuentas:
el detalle del error va al registro, porque el mensaje de la base lleva
host, puerto y usuario.

**Orden de arranque.** `docker-compose.prod.yml` no tenía sonda en
Postgres —el de desarrollo sí—, así que `depends_on: postgres` solo
esperaba a que el contenedor arrancara. En un arranque en frío o tras
reiniciar el host, `migrate` corría contra una base que aún no aceptaba
conexiones; el contenedor moría, `restart: unless-stopped` lo reintentaba
y acababa levantando, pero con un ciclo de caídas. Ahora:

- `postgres` y `redis` tienen sonda propia.
- `django-api` espera a que ambas estén sanas y publica la suya
  (`/api/v1/ready/`, consultada con `urllib`: la imagen `python:3.12-slim`
  no trae `curl` ni `wget`).
- `celery-worker`, `celery-beat` y `nginx` esperan a que Django **atienda**,
  no a que exista. Antes subían mientras aún corrían `migrate` y
  `collectstatic`, y las primeras peticiones devolvían 502.

Para monitorización externa (uptime, alertas), la ruta a vigilar es
`/api/v1/ready/`.

## Registro y diagnóstico

**El problema que había.** El proyecto no tenía bloque `LOGGING`, y eso no
significaba «el de Django por defecto»: significaba **silencio**.
Comprobado con un 500 real y `DEBUG=False` — el cliente recibe su 500 y la
traza no aparece en ningún sitio, ni en la salida estándar. El único
logger que trae Django es `django`, con el manejador `console` filtrado
por `require_debug_true` (callado en producción) y `mail_admins`, que
necesita `ADMINS` y un backend de correo; `ADMINS` estaba vacío. Cuando el
panel fallaba, nadie llegaba a enterarse de por qué.

**Cómo queda.** Una línea por petición a la salida estándar, que es donde
la recoge Docker:

```
DJANGO_LOG_FORMAT=json   # por defecto con DEBUG=False
DJANGO_LOG_FORMAT=plain  # por defecto en desarrollo
DJANGO_LOG_LEVEL=INFO
```

```json
{"ts":"...","level":"ERROR","logger":"apps.request","msg":"Excepción no controlada",
 "request_id":"34cb3d80bf9f4d4d","method":"GET","path":"/api/v1/patients/",
 "query_keys":["search"],"user_id":"...","tenant_id":"...",
 "exc_type":"RuntimeError","traceback":"..."}
```

**Correlación.** Cada petición lleva un `request_id` que va también en la
cabecera `X-Request-ID` de la respuesta. Si un usuario reporta un fallo y
da ese código, la incidencia se encuentra sin buscar por hora y a ojo.
Si nginx o el gateway mandan ya un `X-Request-ID`, se respeta, de modo que
una petición se sigue de punta a punta.

**Qué NO va al registro.** Esto es un sistema de datos de salud y un
registro se copia a un agregador, se conserva meses y lo lee gente que no
tiene por qué ver la historia de nadie:

| Sí | No |
|---|---|
| método, ruta, estado, duración | nombres, cédulas, teléfonos, correos |
| id de usuario, rol, id de clínica | contraseñas, tokens, cabeceras de auth |
| tipo de excepción y traza | contenido de notas clínicas |
| **nombres** de los parámetros de consulta | **valores** de esos parámetros |

Esa última fila importa más de lo que parece: `/api/v1/patients/?search=Pérez`
lleva un apellido dentro de la URL. Se registra `query_keys: ["search"]` y
nunca su contenido. Por el mismo motivo se descarta el logger
`django.request`, que pasa el objeto de petición en `extra` y cuyo repr
incluye la cadena de consulta entera.

Los UUID sí se registran: son seudónimos, sin la base de datos no dicen
quién es nadie, y sin ellos no se puede reconstruir qué pasó.

**Qué monitorizar.** Alertar sobre líneas con `level: ERROR` del logger
`apps.request`, y sobre `/api/v1/ready/` devolviendo 503. Las sondas de
salud no se registran a propósito: un balanceador las pide cada diez
segundos y ahogarían todo lo demás.

## Google Calendar — estado y Fase 2

**Fase 1 (ya funciona, sin credenciales):** cada doctor tiene un feed
iCalendar con URL secreta (Agenda → filtrar por doctor → "🗓 Calendario
del doctor"). Al suscribirla en Google Calendar (Otros calendarios → + →
Desde URL), las citas de la clínica aparecen en su calendario personal y
se actualizan solas (Google refresca las suscripciones cada varias horas).

**Fase 2 (bidireccional real — pendiente de credenciales):** que un evento
creado en el Google Calendar del doctor bloquee su agenda en la clínica.
Requiere: proyecto en Google Cloud Console → habilitar Google Calendar API
→ credenciales OAuth 2.0 (client ID + secret) → pantalla de consentimiento.
El campo `Appointment.google_calendar_event_id` ya existe en el modelo
para ese momento. Cuando tengas las credenciales, se implementa el flujo
OAuth por doctor y la sincronización con webhooks push de Google.

## firmaEC — firma electrónica legal (Fase 2)

Las recetas se generan en PDF profesional con la firma manuscrita del
doctor estampada (dibujada en "Mi firma"). Para la firma electrónica
LEGAL de Ecuador (firmaEC): cada doctor necesita su certificado digital
`.p12` emitido por una entidad acreditada (Registro Civil, Security Data,
UANATACA, ANF). Con esos certificados se integra el firmado PAdES del
PDF (librería endesive) — mismo patrón que Meta y Google: el código
queda listo, faltan las credenciales del trámite.

## Archivos subidos (`/media/`)

Nginx sirve desde disco **únicamente** `/media/branding/` — el logotipo de la
clínica, que es público y va en un `<img>` sin sesión. Cualquier otra ruta
bajo `/media/` devuelve 404 a propósito.

El resto de lo que hay ahí dentro son radiografías, documentos de pacientes,
consentimientos firmados y firmas manuscritas. Nginx no sabe quién pide un
archivo, así que publicarlos por esa vía los dejaría al alcance de cualquiera
que acertara la URL, sin sesión y sin registro de acceso. Se entregan por la
API (`/api/v1/patients/{id}/documents/{doc}/file/`), que valida clínica,
paciente y permisos antes de devolver el binario.

**Si alguna vez hace falta publicar una carpeta nueva**, añádele su propio
`location` con `alias`; no amplíes el de `branding` ni sustituyas el `return
404` por un `alias` general.

Con `USE_CLOUD_STORAGE=True` los archivos van al bucket y esto no aplica:
las URLs son absolutas y el control de acceso lo da el propio bucket, que debe
quedar **privado** por el mismo motivo.

## Seguridad de las dependencias

Revisado con `npm audit` y `pip-audit` (septiembre de 2026). Se
actualizó todo lo que tenía arreglo sin cambiar de versión mayor del
framework: Django 5.2 LTS (la 5.0 ya no recibe parches), DRF, SimpleJWT,
Pillow, cryptography, FastAPI/Starlette, python-multipart, Next.js
14.2.35 y jsPDF 4.

Quedan dos avisos de `npm audit`, **sin efecto en producción**:

- **Next.js 14**: los fallos que siguen abiertos en la rama 14
  (optimizador de imágenes, acciones de servidor, middleware) exigen un
  servidor Next en marcha. En producción no lo hay: el panel se exporta
  a HTML estático y lo sirve Nginx. El servidor de desarrollo
  (`next dev`) sí los tiene: no exponerlo fuera del equipo.
- **postcss**: lo usa Next al compilar, sobre el CSS propio.

Pasar a Next 15/16 los cierra también en desarrollo, pero es una
actualización mayor (React 19) que conviene hacer aparte.

Repetir la revisión antes de cada despliegue:

```bash
cd frontend && npm audit --omit=dev
```

```bash
pip install pip-audit && pip-audit -r django-api/requirements.txt -r whatsapp-gateway/requirements.txt
```

## Correo con Gmail

El correo de la plataforma —recuperar la contraseña del equipo y, si se
elige, el código para entrar en la app del paciente— se configura en
**Plataforma → Configuración → Correo saliente**. Lo de ese formulario
manda sobre `EMAIL_HOST` del `.env`, que queda como respaldo.

1. En la cuenta de Gmail que va a enviar (mejor una solo para esto, p. ej.
   `clinube.notificaciones@gmail.com`): **Cuenta de Google → Seguridad →
   Verificación en dos pasos**, activarla si no lo está.
2. En esa misma página, **Contraseñas de aplicaciones** → nombre «Clinube»
   → **Crear**. Gmail enseña 16 letras una sola vez: es la contraseña que
   va en el formulario. La contraseña normal de Gmail **no** sirve.
3. En Plataforma: servidor `smtp.gmail.com`, puerto `587`, usuario la
   dirección completa, la contraseña de aplicación → **Guardar**.
4. **Enviar correo de prueba**. Si falla, el mensaje dice qué tocar.

La contraseña se guarda cifrada con `DJANGO_SECRET_KEY`: si se cambia esa
clave, hay que volver a escribirla. Gmail permite unos 500 correos al
día; si alguna vez no alcanza, el formulario vale igual para Brevo,
Amazon SES o un Google Workspace con el dominio.

### Código de la app del paciente: WhatsApp o correo

En la misma página, **Código para entrar en la app del paciente**:

- **WhatsApp** (como hasta ahora): necesita la cuenta de Meta con la
  plantilla `otp_login` aprobada.
- **Correo electrónico**: solo necesita el correo de arriba funcionando.
  No deja elegirlo sin correo configurado.

Cambiar de uno a otro no obliga a volver a activar a nadie: la app
pregunta el canal al abrirse y pide el teléfono o el correo, y una app
antigua que aún pide el teléfono recibe el código en el correo de su
ficha. Con correo, la ficha tiene que tener el correo del paciente, y
cada correo da acceso a una sola ficha (igual que cada teléfono).

## Pendientes ANTES de pacientes reales

- [ ] Cambiar TODAS las contraseñas de desarrollo (Jorge2025 no va a producción).
- [ ] **Ingreso a la app del paciente:** elegir el canal en Plataforma →
      Configuración (ver «Correo con Gmail»). Con WhatsApp hace falta la
      cuenta de la PLATAFORMA (`META_ACCESS_TOKEN` y `META_PHONE_NUMBER_ID`
      en el `.env`) y una plantilla aprobada por Meta en la categoría
      «Autenticación»: `otp_login`, con el código como variable `{{1}}`;
      sin eso el envío queda simulado y **nadie puede entrar a la app**.
      Con correo, basta el correo de la plataforma.
- [ ] **Correo** (Plataforma → Configuración, o `EMAIL_HOST` en el `.env`):
      sin él, la recuperación de contraseña del personal no sale. Probar
      con «Enviar correo de prueba».
- [ ] Dominio con HTTPS: la app móvil se compila apuntando a esa dirección
      (`--dart-define=API_URL=https://app.clinube.com`) y no se puede
      cambiar sin publicar otra versión.
- [ ] Plantilla `recordatorio_cita` en Meta con 3 variables (nombre, fecha,
      instrucción de confirmación) — el webhook ya entiende "CONFIRMO"/"sí".
- [ ] Credenciales de Meta en `.env` cuando la verificación esté aprobada
      (sin esto, los recordatorios WhatsApp quedan en modo simulado).
- [ ] Validar catálogo del odontograma y formularios por especialidad con el doctor.
- [ ] **Datos del titular** en Plataforma → Configuración (razón social, RUC,
      correo de privacidad, proveedor de correo): sin ellos el aviso de
      privacidad (`/privacidad`) y las condiciones (`/condiciones`) salen
      con «[pendiente de completar]».
- [ ] Revisión LOPDP con un abogado de los textos de `django-api/apps/common/legal.py`
      (aviso de privacidad y condiciones con el acuerdo de tratamiento de
      datos). Cambiar un texto obliga a subir su versión: las clínicas
      vuelven a aceptar las condiciones y las fichas marcan el aviso como
      pendiente.
- [ ] Probar la restauración de un backup (un backup no probado no existe).

## Entrar con Google

Opcional. Con esto aparece «Continuar con Google» en el inicio de sesión
del panel. El equipo entra con el correo que tiene registrado en su
clínica; Google no crea cuentas del equipo.

1. En https://console.cloud.google.com crea un proyecto (gratis).
2. **APIs y servicios → Pantalla de consentimiento de OAuth**: tipo
   «Externo», nombre «Clinube», correo de soporte y el dominio
   `clinube.com`. Publícala.
3. **APIs y servicios → Credenciales → Crear credenciales → ID de
   cliente de OAuth**, tipo «Aplicación web». En «Orígenes de JavaScript
   autorizados» pon `https://app.clinube.com`.
4. Copia el ID de cliente (termina en `.apps.googleusercontent.com`) en
   **Plataforma → Configuración → Entrar con Google** y guarda.

No hay secreto que guardar: el panel solo usa el ID público, y la API
comprueba la firma de Google con sus claves públicas.

## Rastreadores de IA y buscadores

Nginx ya pide que no se use nada para IA: la portada sirve un
`robots.txt` que excluye a los rastreadores de IA conocidos (GPTBot,
ClaudeBot, Google-Extended, CCBot, PerplexityBot…) y manda
`X-Robots-Tag: noai, noimageai`; `app.clinube.com` sirve
`robots-panel.txt` (`Disallow: /`) y `noindex, nofollow, noarchive`. Es
una petición, y la respetan los rastreadores serios.

El bloqueo de verdad lo hace Cloudflare, antes de que la petición llegue
al servidor:

1. dash.cloudflare.com → el dominio `clinube.com`.
2. **Security** → **Bots** (en algunas cuentas, **AI Crawl Control**).
3. Activar **Block AI bots** (o «Bloquear rastreadores de IA») para
   todas las páginas.

Nada de esto protege los datos de las clínicas: esos ya no son visibles
para ningún rastreador porque están detrás del inicio de sesión.

## Base de datos y tamaño del servidor

`docker-compose.prod.yml` arranca PostgreSQL con una configuración pensada
para un servidor real (los valores de fábrica son para 512 MB) y Django
reutiliza las conexiones (`DB_CONN_MAX_AGE`, 60 s) en vez de abrir una
por petición. Sin tocar nada sirve para la máquina de Oracle de 6 GB.

Con un servidor mayor, se ponen en el `.env` del servidor y se reinicia
(`docker compose -f docker-compose.prod.yml up -d`; los datos no se tocan):

| Servidor | PG_SHARED_BUFFERS | PG_EFFECTIVE_CACHE_SIZE | PG_WORK_MEM | GUNICORN_WORKERS | CELERY_CONCURRENCY |
|---|---|---|---|---|---|
| 4–6 GB, 1–2 núcleos (por omisión) | 1GB | 3GB | 16MB | 3 | 2 |
| 8 GB, 2 núcleos | 2GB | 5GB | 16MB | 3 | 2 |
| 12 GB, 3 núcleos | 3GB | 8GB | 24MB | 4 | 3 |
| 24 GB, 4 núcleos | 6GB | 16GB | 32MB | 5 | 4 |

- `PG_SHARED_BUFFERS` ≈ 25 % de la RAM y `PG_EFFECTIVE_CACHE_SIZE` ≈ 65 %.
- Gunicorn corre con **hilos**: `GUNICORN_WORKERS` ≈ núcleos (+1) y
  `GUNICORN_THREADS` = 2. Medido con 6 descargas de PDF a la vez y alguien
  navegando: 4 procesos × 2 hilos generan los mismos PDF por segundo que
  3 procesos sin hilos, y quien navega pasa de 243 ms de mediana (475 ms
  en el peor caso) a 13 ms (95 ms). Más hilos por proceso no ayuda: los
  PDF compiten por el mismo núcleo.
- Cada hilo tiene su conexión a PostgreSQL: procesos × hilos + Celery
  tiene que quedar por debajo de `PG_MAX_CONNECTIONS` (100).
- Con más de 2 GB de `shared_buffers`, subir también `PG_SHM_SIZE` a `1gb`.
- Redis guarda la cola de Celery y la caché, con un tope de
  `REDIS_MAXMEMORY` (256mb); si se llena, solo se descarta caché.

Para ver qué consultas gastan más tiempo con los datos reales (el
registro de PostgreSQL además deja toda consulta de más de 500 ms):

```bash
docker compose -f docker-compose.prod.yml exec django-api python manage.py consultas_lentas
```
```bash
docker compose -f docker-compose.prod.yml exec django-api python manage.py consultas_lentas --por media
```

`--reiniciar` empieza a medir de cero (útil antes y después de un cambio).
