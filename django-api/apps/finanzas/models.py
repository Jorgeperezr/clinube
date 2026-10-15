"""
Finanzas de la clínica: lo que sale (egresos), la caja del día y lo que
se paga a cada persona del equipo.

Lo que entra ya existía —los cobros de `apps.billing`—; aquí se cruza con
lo que sale para que la clínica sepa cuánto ganó en el mes, y no solo
cuánto cobró.

Nada se borra: un egreso equivocado se ANULA, con su motivo, y deja de
contar. Es lo que pide cualquier contador, y lo que permite reconstruir
un mes cerrado meses después.

Los valores que fija la ley y cambian cada año (salario básico, aportes
al IESS, retención en la fuente) están en `ConfiguracionFinanzas`, por
clínica y editables: no hay que esperar a una actualización de Clinube
cuando el Gobierno los cambia.
"""

from decimal import Decimal

from django.db import models

from apps.accounts.models import User
from apps.common.models import TenantAwareModel

CERO = Decimal("0.00")


class FormaPago(models.TextChoices):
    EFECTIVO = "efectivo", "Efectivo"
    TRANSFERENCIA = "transferencia", "Transferencia"
    TARJETA = "tarjeta", "Tarjeta"
    CHEQUE = "cheque", "Cheque"


class Region(models.TextChoices):
    SIERRA = "sierra", "Sierra y Amazonía (décimo cuarto hasta el 15 de agosto)"
    COSTA = "costa", "Costa y Galápagos (décimo cuarto hasta el 15 de marzo)"


class ConfiguracionFinanzas(TenantAwareModel):
    """Valores de ley y de la clínica. Uno por clínica; se crea al primer uso."""

    salario_basico = models.DecimalField(
        "Salario básico unificado", max_digits=8, decimal_places=2, default=Decimal("482.00"),
        help_text="SBU vigente. 482 US$ en 2026. Sirve para el décimo cuarto.")
    aporte_personal_iess = models.DecimalField(
        "Aporte personal al IESS (%)", max_digits=5, decimal_places=2, default=Decimal("9.45"))
    aporte_patronal_iess = models.DecimalField(
        "Aporte patronal al IESS (%)", max_digits=5, decimal_places=2, default=Decimal("11.15"))
    aporte_iece_secap = models.DecimalField(
        "IECE y SECAP (%)", max_digits=5, decimal_places=2, default=Decimal("1.00"),
        help_text="0,5 % + 0,5 % que paga el empleador junto al aporte patronal.")
    fondos_reserva = models.DecimalField(
        "Fondos de reserva (%)", max_digits=5, decimal_places=2, default=Decimal("8.33"),
        help_text="Desde el segundo año de trabajo.")
    retencion_honorarios = models.DecimalField(
        "Retención en la fuente a honorarios (%)", max_digits=5, decimal_places=2,
        default=Decimal("10.00"),
        help_text="Impuesto a la Renta que se retiene al profesional que factura a la clínica.")
    siguiente_comprobante = models.PositiveIntegerField(
        "Siguiente número de comprobante de cobro", default=1)
    # El décimo cuarto no se paga igual en todo el país.
    region = models.CharField(
        "Región para el décimo cuarto", max_length=6, choices=Region.choices, default=Region.SIERRA)
    recargo_suplementarias = models.DecimalField(
        "Recargo de horas suplementarias (%)", max_digits=5, decimal_places=2, default=Decimal("50.00"),
        help_text="Hasta las 24:00 y en días laborables. 50 % según el Código del Trabajo.")
    recargo_extraordinarias = models.DecimalField(
        "Recargo de horas extraordinarias (%)", max_digits=5, decimal_places=2, default=Decimal("100.00"),
        help_text="Fines de semana, feriados y de 24:00 a 06:00. 100 %.")

    class Meta:
        verbose_name = "Configuración de finanzas"
        verbose_name_plural = "Configuración de finanzas"
        constraints = [models.UniqueConstraint(fields=["tenant"], name="finanzas_config_unica")]

    @classmethod
    def de(cls, tenant):
        config, _ = cls.objects.get_or_create(tenant=tenant)
        return config


class CategoriaEgreso(TenantAwareModel):
    """En qué se gasta. La clínica las renombra, añade o desactiva."""

    nombre = models.CharField(max_length=80)
    # Las que crea Clinube llevan clave: con ella se reconocen las de
    # honorarios, sueldos y compras aunque la clínica les cambie el nombre.
    clave = models.CharField(max_length=30, blank=True)
    activa = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=50)

    class Meta:
        verbose_name = "Categoría de egreso"
        verbose_name_plural = "Categorías de egreso"
        ordering = ["orden", "nombre"]

    def __str__(self):
        return self.nombre


# Las de una clínica dental en Ecuador, en el orden en que se suelen mirar.
CATEGORIAS_INICIALES = [
    ("honorarios", "Honorarios profesionales"),
    ("sueldos", "Sueldos y beneficios de ley"),
    ("laboratorio", "Laboratorio dental"),
    ("insumos", "Insumos y materiales"),
    ("arriendo", "Arriendo del local"),
    ("servicios", "Luz, agua, internet y teléfono"),
    ("equipos", "Equipos y mantenimiento"),
    ("publicidad", "Publicidad"),
    ("contador", "Contador y servicios profesionales"),
    ("impuestos", "Impuestos, permisos y tasas"),
    ("otros", "Otros gastos"),
]


def categorias_de(tenant):
    """Las categorías de la clínica; la primera vez se crean las de serie."""
    existentes = CategoriaEgreso.objects.filter(tenant=tenant)
    if not existentes.exists():
        CategoriaEgreso.objects.bulk_create([
            CategoriaEgreso(tenant=tenant, clave=clave, nombre=nombre, orden=i * 10)
            for i, (clave, nombre) in enumerate(CATEGORIAS_INICIALES)
        ])
    return CategoriaEgreso.objects.filter(tenant=tenant)


def categoria(tenant, clave):
    return categorias_de(tenant).filter(clave=clave).first()


# Egresos que crea un cálculo (una liquidación, un rol o el pago de una
# obligación): no se corrigen a mano ni se descuentan a nadie.
ORIGENES_CALCULADOS = ("liquidacion", "rol", "iess", "sri", "decimo_tercero", "decimo_cuarto")
# De estos, los pagos a terceros sí se anulan desde Egresos: la
# obligación vuelve a quedar pendiente.
ORIGENES_OBLIGACION = ("iess", "sri", "decimo_tercero", "decimo_cuarto")


class Egreso(TenantAwareModel):
    """Un pago que hace la clínica, o una cuenta que tiene pendiente."""

    class Estado(models.TextChoices):
        PAGADO = "pagado", "Pagado"
        POR_PAGAR = "por_pagar", "Por pagar"

    fecha = models.DateField(help_text="Del pago o, si está por pagar, de la factura.")
    categoria = models.ForeignKey(CategoriaEgreso, on_delete=models.PROTECT, related_name="egresos")
    concepto = models.CharField(max_length=200)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    forma_pago = models.CharField(max_length=15, choices=FormaPago.choices, default=FormaPago.EFECTIVO)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PAGADO)
    vence = models.DateField(null=True, blank=True, help_text="Para las cuentas por pagar.")
    proveedor = models.CharField(max_length=150, blank=True)
    proveedor_ruc = models.CharField("RUC o cédula del proveedor", max_length=13, blank=True)
    numero_factura = models.CharField(
        "N.º de la factura del proveedor", max_length=20, blank=True,
        help_text="Como viene en la factura: 001-001-000000123.")
    comprobante = models.FileField(upload_to="finanzas/comprobantes/", null=True, blank=True)
    # La persona del equipo a la que corresponde (honorarios, laboratorio
    # de un caso suyo…): así se descuenta en su liquidación.
    profesional = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    descontar_al_profesional = models.BooleanField(
        default=False,
        help_text="Se resta de lo que se le paga (p. ej. el laboratorio de sus casos).")
    origen = models.CharField(
        max_length=20, blank=True,
        help_text="Quién lo creó si no fue a mano: «liquidacion», «rol», «inventario», «iess», "
                  "«sri», «decimo_tercero» o «decimo_cuarto».")
    # Para los pagos a terceros (IESS, SRI, décimos): el período que salda.
    periodo = models.DateField(null=True, blank=True)
    registrado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="+")
    anulado = models.BooleanField(default=False)
    motivo_anulacion = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "Egreso"
        verbose_name_plural = "Egresos"
        ordering = ["-fecha", "-created_at"]
        indexes = [models.Index(fields=["tenant", "fecha"])]

    def __str__(self):
        return f"{self.concepto} — ${self.monto}"


class CierreCaja(TenantAwareModel):
    """El cierre de caja de un día: lo que debía haber en efectivo y lo que hubo."""

    fecha = models.DateField()
    saldo_inicial = models.DecimalField(max_digits=12, decimal_places=2, default=CERO)
    cobros_efectivo = models.DecimalField(max_digits=12, decimal_places=2, default=CERO)
    egresos_efectivo = models.DecimalField(max_digits=12, decimal_places=2, default=CERO)
    esperado = models.DecimalField(max_digits=12, decimal_places=2, default=CERO)
    contado = models.DecimalField(max_digits=12, decimal_places=2)
    diferencia = models.DecimalField(max_digits=12, decimal_places=2, default=CERO)
    # Lo que no se queda en caja (se deposita o se lleva el dueño).
    retirado = models.DecimalField(max_digits=12, decimal_places=2, default=CERO)
    observaciones = models.CharField(max_length=300, blank=True)
    cerrado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="+")

    class Meta:
        verbose_name = "Cierre de caja"
        verbose_name_plural = "Cierres de caja"
        ordering = ["-fecha"]
        constraints = [models.UniqueConstraint(fields=["tenant", "fecha"], name="un_cierre_por_dia")]

    @property
    def queda_en_caja(self):
        return self.contado - self.retirado


class PerfilLaboral(TenantAwareModel):
    """
    Cómo se le paga a una persona del equipo. Es lo que decide si entra en
    las liquidaciones de honorarios, en el rol de pagos o en ninguno.
    """

    class Modalidad(models.TextChoices):
        HONORARIOS = "honorarios", "Por honorarios (factura a la clínica)"
        DEPENDENCIA = "dependencia", "En relación de dependencia (rol de pagos)"
        NINGUNA = "ninguna", "No se le paga desde la clínica"

    class BaseHonorarios(models.TextChoices):
        COBRADO = "cobrado", "Porcentaje de lo cobrado a sus pacientes"
        FIJO = "fijo", "Monto fijo por período"

    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil_laboral")
    modalidad = models.CharField(max_length=12, choices=Modalidad.choices, default=Modalidad.NINGUNA)
    cedula = models.CharField(max_length=13, blank=True)
    cargo = models.CharField(max_length=80, blank=True)
    # Honorarios
    base_honorarios = models.CharField(max_length=10, choices=BaseHonorarios.choices,
                                       default=BaseHonorarios.COBRADO)
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("40.00"))
    monto_fijo = models.DecimalField(max_digits=10, decimal_places=2, default=CERO)
    emite_factura = models.BooleanField(
        default=True, help_text="Si factura a la clínica, se le retiene el Impuesto a la Renta.")
    # Relación de dependencia
    sueldo = models.DecimalField(max_digits=10, decimal_places=2, default=CERO)
    fecha_ingreso = models.DateField(null=True, blank=True)
    decimo_tercero_mensual = models.BooleanField(
        default=False, help_text="Cobrarlo cada mes en vez de en diciembre.")
    decimo_cuarto_mensual = models.BooleanField(
        default=False, help_text="Cobrarlo cada mes en vez de una vez al año.")
    fondos_reserva_mensual = models.BooleanField(
        default=True, help_text="Cobrarlos cada mes en el rol en vez de que se acumulen en el IESS.")

    class Meta:
        verbose_name = "Perfil laboral"
        verbose_name_plural = "Perfiles laborales"


class Liquidacion(TenantAwareModel):
    """Lo que se le paga a un profesional por honorarios en un período."""

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Por pagar"
        PAGADA = "pagada", "Pagada"
        ANULADA = "anulada", "Anulada"

    numero = models.PositiveIntegerField()
    profesional = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    desde = models.DateField()
    hasta = models.DateField()
    base = models.DecimalField(max_digits=12, decimal_places=2, default=CERO,
                               help_text="Lo cobrado a sus pacientes en el período.")
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=CERO)
    honorario = models.DecimalField(max_digits=12, decimal_places=2, default=CERO)
    descuentos = models.DecimalField(max_digits=12, decimal_places=2, default=CERO)
    ajustes = models.DecimalField(max_digits=12, decimal_places=2, default=CERO,
                                  help_text="Bonos (+) o anticipos (−) puestos a mano.")
    retencion_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=CERO)
    retencion = models.DecimalField(max_digits=12, decimal_places=2, default=CERO)
    a_pagar = models.DecimalField(max_digits=12, decimal_places=2, default=CERO)
    # El detalle tal como se calculó: cobros, descuentos y ajustes. Se guarda
    # para que el PDF de un mes viejo siga diciendo lo mismo.
    detalle = models.JSONField(default=dict, blank=True)
    nota = models.CharField(max_length=300, blank=True)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.BORRADOR)
    egreso = models.OneToOneField(Egreso, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="liquidacion")
    creada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="+")

    class Meta:
        verbose_name = "Liquidación de honorarios"
        verbose_name_plural = "Liquidaciones de honorarios"
        ordering = ["-hasta", "-numero"]


class RolPagos(TenantAwareModel):
    """El rol de pagos de un mes de una persona en relación de dependencia."""

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Por pagar"
        PAGADO = "pagado", "Pagado"
        ANULADO = "anulado", "Anulado"

    empleado = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    mes = models.DateField(help_text="El día 1 del mes del rol.")
    dias_trabajados = models.PositiveSmallIntegerField(default=30)
    horas_extra = models.DecimalField(max_digits=10, decimal_places=2, default=CERO,
                                      help_text="Otro valor por horas extra, en dólares.")
    horas_suplementarias = models.DecimalField(max_digits=6, decimal_places=2, default=CERO,
                                               help_text="Número de horas con recargo del 50 %.")
    horas_extraordinarias = models.DecimalField(max_digits=6, decimal_places=2, default=CERO,
                                                help_text="Número de horas con recargo del 100 %.")
    otros_ingresos = models.DecimalField(max_digits=10, decimal_places=2, default=CERO,
                                         help_text="Bonos o comisiones.")
    anticipos = models.DecimalField(max_digits=10, decimal_places=2, default=CERO)
    prestamos_iess = models.DecimalField(max_digits=10, decimal_places=2, default=CERO)
    otros_descuentos = models.DecimalField(max_digits=10, decimal_places=2, default=CERO)
    # El cálculo completo, congelado al guardar (ver `calculos.rol`).
    calculo = models.JSONField(default=dict, blank=True)
    neto = models.DecimalField(max_digits=12, decimal_places=2, default=CERO)
    costo_empleador = models.DecimalField(max_digits=12, decimal_places=2, default=CERO)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.BORRADOR)
    egreso = models.OneToOneField(Egreso, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="rol")
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="+")

    class Meta:
        verbose_name = "Rol de pagos"
        verbose_name_plural = "Roles de pagos"
        ordering = ["-mes"]
        constraints = [models.UniqueConstraint(
            fields=["tenant", "empleado", "mes"], condition=~models.Q(estado="anulado"),
            name="un_rol_por_mes")]
