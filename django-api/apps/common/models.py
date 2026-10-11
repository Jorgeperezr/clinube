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
    canal_codigo_paciente = models.CharField(
        "Canal del código de la app del paciente", max_length=10,
        choices=CANALES_CODIGO, default=CANAL_WHATSAPP,
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
