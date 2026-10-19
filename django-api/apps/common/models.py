import uuid

from django.db import models


class Tenant(models.Model):
    """
    Representa una sede/clínica. En la Fase 1 solo existe un Tenant activo,
    pero el campo tenant_id ya se propaga a todas las tablas del dominio
    desde el día uno (Arquitectura v1.2, sección "Escalabilidad").
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    ruc = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    funcionalidades = models.JSONField(
        default=dict, blank=True,
        verbose_name="Funcionalidades contratadas",
        help_text=(
            "Qué módulos tiene esta clínica. El catálogo está en "
            "apps/common/funcionalidades.py. Apagar uno NO borra sus "
            "datos: deja de verse y de poder tocarse."
        ),
    )
    # Lo que la PROPIA clínica decide no usar de lo que tiene contratado
    # (p. ej. el odontograma 3D o las rachas y logros). Lo contratado lo
    # decide la plataforma en `funcionalidades`; esto lo decide la
    # administración de la clínica y solo puede apagar, nunca dar de alta
    # algo que no está contratado. {clave: False} = apagado por la clínica.
    modulos_clinica = models.JSONField(
        default=dict, blank=True,
        verbose_name="Módulos que la clínica decide usar",
    )
    # Donde se prueban las funciones nuevas antes de dárselas a las demás
    # (`fase` en apps/common/funcionalidades.py). La primera clínica de
    # una instalación —la que crea `bootstrap`— nace de pruebas; las que
    # se dan de alta desde Plataforma, no, salvo que se marque.
    es_prueba = models.BooleanField(
        default=False, verbose_name="Clínica de pruebas",
        help_text=(
            "Recibe las funciones nuevas antes que las demás. Lo que se "
            "prueba aquí no llega a otras clínicas hasta publicarlo desde "
            "Plataforma."
        ),
    )
    # Un consultorio es la cuenta de un profesional que trabaja solo: la
    # misma persona administra y atiende. Cambia lo que se ofrece al
    # darla de alta y algunos textos, no lo que el sistema permite: una
    # clínica también puede tener administradores que atienden.
    MODALIDADES = [("clinica", "Clínica con equipo"), ("consultorio", "Consultorio (profesional independiente)")]
    modalidad = models.CharField(max_length=12, choices=MODALIDADES, default="clinica",
                                 verbose_name="Modalidad")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tenant (clínica)"
        verbose_name_plural = "Tenants (clínicas)"

    def __str__(self):
        return self.name


class TenantAwareModel(models.Model):
    """
    Clase base abstracta para cualquier modelo del dominio que deba
    filtrarse por sede. Todas las apps de negocio (patients, agenda,
    clinical, billing, inventory, etc.) heredan de esta clase en vez
    de repetir el campo tenant_id manualmente.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    """
    Borrado lógico obligatorio para tablas clínicas y financieras
    (SRS, sección 0 "Convenciones generales" del Modelo de datos):
    nunca se hace DELETE físico sobre datos de salud o de pagos.
    """

    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def soft_delete(self):
        from django.utils import timezone

        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_active", "deleted_at"])



class PlatformConfiguration(models.Model):
    """
    Configuración global del SaaS (singleton): identidad de la plataforma,
    SMTP para correos, zona horaria y moneda. La edita únicamente el
    Super Administrador desde su panel.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    platform_name = models.CharField(max_length=120, default="Clinube")
    logo_url = models.URLField(blank=True)
    smtp_host = models.CharField(max_length=255, blank=True)
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_user = models.CharField(max_length=255, blank=True)
    # Cifrada (apps/common/secretos.py) y nunca se expone en la API. La usa
    # apps/common/correo.py, que da preferencia a este servidor sobre el
    # EMAIL_HOST del entorno.
    smtp_password = models.CharField(max_length=255, blank=True)
    timezone = models.CharField(max_length=64, default="America/Guayaquil")
    currency = models.CharField(max_length=8, default="USD")
    # Quién opera la plataforma, para el aviso de privacidad y las
    # condiciones (apps/common/legal.py). Sin ellos los textos legales
    # salen con un marcador de «pendiente».
    titular_nombre = models.CharField("Razón social del titular", max_length=200, blank=True)
    titular_ruc = models.CharField("RUC del titular", max_length=20, blank=True)
    titular_correo = models.EmailField("Correo de contacto para privacidad", blank=True)
    proveedor_correo = models.CharField(
        "Proveedor de correo", max_length=120, blank=True,
        help_text="El servicio que envía los correos (p. ej. «Brevo»). Sale en el aviso de privacidad.",
    )
    # Por dónde le llega al paciente el código para entrar en la app.
    # WhatsApp necesita la cuenta de Meta con la plantilla «otp_login»
    # aprobada; el correo, solo el correo saliente de arriba.
    CANAL_WHATSAPP = "whatsapp"
    CANAL_CORREO = "correo"
    CANALES_CODIGO = [(CANAL_WHATSAPP, "WhatsApp"), (CANAL_CORREO, "Correo electrónico")]
    # El correo es el canal de todos. WhatsApp solo vale para las clínicas
    # que lo tienen contratado y conectado (función «whatsapp», que la
    # plataforma añade a pedido): ver apps/accounts/acceso_paciente.py.
    canal_codigo_paciente = models.CharField(
        "Canal del código de la app del paciente", max_length=10,
        choices=CANALES_CODIGO, default=CANAL_CORREO,
    )
    # «Entrar con Google»: el ID de cliente OAuth (tipo «Aplicación web»)
    # de Google Cloud. Vacío = el botón no aparece.
    google_client_id = models.CharField(
        "ID de cliente de Google", max_length=200, blank=True,
        help_text="De Google Cloud → APIs y servicios → Credenciales. Termina en .apps.googleusercontent.com.",
    )
    # Funciones que nacieron «en prueba» y que ya se publicaron para todas
    # las clínicas (Plataforma → Funciones). Ver apps/common/funcionalidades.py.
    funciones_publicadas = models.JSONField(
        "Funciones publicadas", default=list, blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración de plataforma"
        verbose_name_plural = "Configuración de plataforma"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=cls.objects.values_list("pk", flat=True).first() or None)
        return obj

    def __str__(self):
        return self.platform_name


class AceptacionCondiciones(TenantAwareModel):
    """
    Constancia de que la clínica aceptó una versión concreta de las
    condiciones de uso y del acuerdo de tratamiento de datos
    (apps/common/legal.py). La acepta una persona con rol de
    administración, y queda quién, cuándo y desde qué dirección.

    El nombre y el correo se copian al aceptar: si la cuenta se borra
    algún día, la constancia tiene que seguir diciendo quién fue.
    """

    version = models.CharField(max_length=20)
    aceptada_por = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    nombre = models.CharField(max_length=255)
    correo = models.EmailField()
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "Aceptación de condiciones"
        verbose_name_plural = "Aceptaciones de condiciones"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.version} · {self.correo}"


class SolicitudClinica(models.Model):
    """
    Lo que llega desde la página pública (clinube.com).

    · Odontología: el alta es directa. Se manda un código al correo y,
      al confirmarlo, se crea la clínica con su administrador
      (estado «creada»). Sin el código no se crea nada: así una dirección
      ajena no puede abrir una clínica a nombre de otro.
    · Medicina y psicología: aún no se pueden crear. Queda la solicitud
      («pendiente») para que el Super Administrador la atienda.
    """

    class Tipo(models.TextChoices):
        ODONTOLOGIA = "odontologia", "Odontología"
        MEDICINA = "medicina", "Medicina"
        PSICOLOGIA = "psicologia", "Psicología"

    class Estado(models.TextChoices):
        VERIFICANDO = "verificando", "Esperando el código del correo"
        PENDIENTE = "pendiente", "Pendiente"
        CREADA = "creada", "Clínica creada"
        ATENDIDA = "atendida", "Atendida"
        DESCARTADA = "descartada", "Descartada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    estado = models.CharField(max_length=12, choices=Estado.choices)
    clinica = models.CharField("Nombre de la clínica o consulta", max_length=150)
    ruc = models.CharField(max_length=13, blank=True)
    ciudad = models.CharField(max_length=80, blank=True)
    nombre = models.CharField("Persona de contacto", max_length=150)
    correo = models.EmailField()
    telefono = models.CharField(max_length=20, blank=True)
    mensaje = models.TextField(blank=True)
    # Odontología: un consultorio de una sola persona o una clínica con
    # equipo (Tenant.modalidad).
    modalidad = models.CharField(max_length=12, choices=Tenant.MODALIDADES, default="clinica")
    # Solo el resumen del código, nunca el código.
    codigo_hash = models.CharField(max_length=128, blank=True)
    codigo_vence = models.DateTimeField(null=True, blank=True)
    intentos = models.PositiveSmallIntegerField(default=0)
    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    ip = models.GenericIPAddressField(null=True, blank=True)
    nota = models.CharField("Nota interna", max_length=300, blank=True)

    class Meta:
        verbose_name = "Solicitud de clínica"
        verbose_name_plural = "Solicitudes de clínica"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.clinica}"
