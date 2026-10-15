"""
API de finanzas (/api/v1/finanzas/…). Todo exige la función «Finanzas»
de la persona y que la clínica la tenga activa.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Max
from django.http import FileResponse, HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import generics
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.funciones import TieneFuncion
from apps.accounts.models import AuditLog, User
from apps.common.permisos_funcionalidad import RequiereFuncionalidad
from apps.finanzas import calculos, documentos
from apps.finanzas.models import (
    ORIGENES_CALCULADOS,
    ORIGENES_OBLIGACION,
    CategoriaEgreso,
    CierreCaja,
    ConfiguracionFinanzas,
    Egreso,
    FormaPago,
    Liquidacion,
    PerfilLaboral,
    RolPagos,
    categoria,
    categorias_de,
)
from apps.finanzas.serializers import (
    CategoriaSerializer,
    CierreCajaSerializer,
    ConfiguracionSerializer,
    EgresoSerializer,
    LiquidacionSerializer,
    PerfilLaboralSerializer,
    RolSerializer,
)

PERMISO = [TieneFuncion.para("finanzas")]


def _auditar(request, accion, objeto, **datos):
    AuditLog.objects.create(tenant=request.tenant, user=request.user, action=accion,
                            entity_type=type(objeto).__name__, entity_id=str(objeto.pk), metadata=datos)


def _decimal(valor, defecto="0"):
    try:
        return Decimal(str(valor if valor not in (None, "") else defecto))
    except InvalidOperation:
        return None


def _fecha(valor, defecto=None):
    return parse_date(str(valor)) if valor else defecto


def _pdf(contenido, nombre):
    r = HttpResponse(contenido, content_type="application/pdf")
    r["Content-Disposition"] = f'inline; filename="{nombre}"'
    return r


def _equipo(tenant):
    return User.objects.filter(tenant=tenant, is_active=True).exclude(
        role__in=("patient", "superadmin")).order_by("full_name")


# ── Resumen ──────────────────────────────────────────────────────────

class ResumenView(APIView):
    """GET /finanzas/resumen/?mes=2026-10"""

    permission_classes = PERMISO

    def get(self, request):
        try:
            desde, hasta = calculos.mes_de(request.query_params.get("mes"))
        except (ValueError, TypeError):
            return Response({"detail": "El mes va como 2026-10."}, status=400)
        anterior_hasta = desde - timezone.timedelta(days=1)
        anterior = calculos.resumen(request.tenant, anterior_hasta.replace(day=1), anterior_hasta)
        return Response({
            **calculos.resumen(request.tenant, desde, hasta),
            "mes_anterior": {k: anterior[k] for k in ("ingresos", "egresos", "utilidad")},
            "serie": calculos.serie(request.tenant, hasta),
        })


# ── Configuración y categorías ───────────────────────────────────────

class ConfiguracionView(APIView):
    """GET/PATCH /finanzas/configuracion/ — los valores de ley, editables."""

    permission_classes = PERMISO

    def get(self, request):
        return Response(ConfiguracionSerializer(ConfiguracionFinanzas.de(request.tenant)).data)

    def patch(self, request):
        config = ConfiguracionFinanzas.de(request.tenant)
        s = ConfiguracionSerializer(config, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        _auditar(request, "update_finance_settings", config, campos=sorted(request.data.keys()))
        return Response(s.data)


class CategoriasView(generics.ListCreateAPIView):
    permission_classes = PERMISO
    serializer_class = CategoriaSerializer
    pagination_class = None

    def get_queryset(self):
        return categorias_de(self.request.tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)


class CategoriaView(generics.UpdateAPIView):
    permission_classes = PERMISO
    serializer_class = CategoriaSerializer

    def get_queryset(self):
        return CategoriaEgreso.objects.filter(tenant=self.request.tenant)


# ── Egresos ──────────────────────────────────────────────────────────

class EgresosView(generics.ListCreateAPIView):
    """GET/POST /finanzas/egresos/?mes=&categoria=&estado=&anulados=1"""

    permission_classes = PERMISO
    serializer_class = EgresoSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    pagination_class = None

    def get_queryset(self):
        qs = Egreso.objects.filter(tenant=self.request.tenant).select_related("categoria", "profesional")
        p = self.request.query_params
        if p.get("mes"):
            desde, hasta = calculos.mes_de(p["mes"])
            qs = qs.filter(fecha__gte=desde, fecha__lte=hasta)
        if p.get("estado") == "por_pagar":
            # Las cuentas por pagar se ven todas, sean del mes que sean.
            qs = Egreso.objects.filter(tenant=self.request.tenant, estado=Egreso.Estado.POR_PAGAR) \
                .select_related("categoria", "profesional")
        if p.get("categoria"):
            qs = qs.filter(categoria_id=p["categoria"])
        if p.get("anulados") != "1":
            qs = qs.filter(anulado=False)
        return qs[:500]

    def perform_create(self, serializer):
        _rol_ya_pagado(self.request.tenant, serializer.validated_data)
        egreso = serializer.save(tenant=self.request.tenant, registrado_por=self.request.user)
        _auditar(self.request, "create_expense", egreso, monto=str(egreso.monto))


def _rol_ya_pagado(tenant, datos, egreso=None):
    """Un anticipo para descontar en un rol que ya se pagó no se descontaría nunca."""
    def valor(campo):
        return datos.get(campo, getattr(egreso, campo, None))

    if not (valor("descontar_al_profesional") and valor("profesional") and valor("fecha")):
        return
    pagado = RolPagos.objects.filter(tenant=tenant, empleado=valor("profesional"),
                                     mes=valor("fecha").replace(day=1), estado=RolPagos.Estado.PAGADO).first()
    if pagado:
        raise _error(f"El rol de {pagado.empleado.full_name} de ese mes ya está pagado: no se le podría "
                     "descontar. Anula el rol para rehacerlo o registra el anticipo en el mes siguiente.")


def _ya_descontado(egreso):
    """La liquidación o el rol pagado en que entró este egreso, si alguno."""
    if not (egreso.descontar_al_profesional and egreso.profesional_id):
        return None
    _, descontados, rangos, _ = calculos.ya_liquidado(egreso.tenant, egreso.profesional)
    if str(egreso.id) in descontados or any(a <= egreso.fecha <= b for a, b in rangos):
        # Se busca en Python: `__contains` sobre JSON no existe en SQLite (CI).
        for liq in Liquidacion.objects.filter(tenant=egreso.tenant, profesional_id=egreso.profesional_id) \
                .exclude(estado=Liquidacion.Estado.ANULADA):
            if str(egreso.id) in (liq.detalle or {}).get("descuentos_ids", []) \
                    or ("descuentos_ids" not in (liq.detalle or {}) and liq.desde <= egreso.fecha <= liq.hasta):
                return f"la liquidación N.º {liq.numero:05d}"
        return "una liquidación"
    if RolPagos.objects.filter(tenant=egreso.tenant, empleado_id=egreso.profesional_id,
                               mes=egreso.fecha.replace(day=1), estado=RolPagos.Estado.PAGADO).exists():
        return "un rol de pagos ya pagado"
    return None


class EgresoView(generics.RetrieveUpdateAPIView):
    permission_classes = PERMISO
    serializer_class = EgresoSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        return Egreso.objects.filter(tenant=self.request.tenant)

    def perform_update(self, serializer):
        egreso = self.get_object()
        if egreso.anulado:
            raise _error("Un egreso anulado no se modifica.")
        if egreso.origen in ORIGENES_CALCULADOS:
            raise _error("Este egreso lo creó Clinube al registrar un pago: se cambia desde allí.")
        donde = _ya_descontado(egreso)
        if donde:
            raise _error(f"Ya se descontó en {donde}. Anúlala antes de cambiarlo.")
        _rol_ya_pagado(self.request.tenant, serializer.validated_data, egreso)
        serializer.save()
        _auditar(self.request, "update_expense", egreso, campos=sorted(self.request.data.keys()))


def _error(texto):
    from rest_framework.exceptions import ValidationError

    return ValidationError({"detail": texto})


class AnularEgresoView(APIView):
    """POST /finanzas/egresos/{id}/anular/ {"motivo": "…"}"""

    permission_classes = PERMISO

    def post(self, request, pk):
        egreso = generics.get_object_or_404(Egreso, pk=pk, tenant=request.tenant)
        motivo = (request.data.get("motivo") or "").strip()
        if not motivo:
            return Response({"detail": "Escribe por qué se anula."}, status=400)
        if egreso.origen in ORIGENES_CALCULADOS and egreso.origen not in ORIGENES_OBLIGACION:
            return Response({"detail": "Se anula desde la liquidación o el rol que lo creó."}, status=400)
        donde = _ya_descontado(egreso)
        if donde:
            return Response({"detail": f"Ya se descontó en {donde}. Anúlala antes."}, status=400)
        egreso.anulado = True
        egreso.motivo_anulacion = motivo[:200]
        egreso.save(update_fields=["anulado", "motivo_anulacion", "updated_at"])
        _auditar(request, "void_expense", egreso, motivo=motivo)
        return Response(EgresoSerializer(egreso, context={"request": request}).data)


class PagarEgresoView(APIView):
    """POST /finanzas/egresos/{id}/pagar/ {"fecha", "forma_pago"} — una cuenta por pagar, saldada."""

    permission_classes = PERMISO

    def post(self, request, pk):
        egreso = generics.get_object_or_404(Egreso, pk=pk, tenant=request.tenant, anulado=False)
        if egreso.estado == Egreso.Estado.PAGADO:
            return Response({"detail": "Ya estaba pagado."}, status=400)
        forma = request.data.get("forma_pago") or egreso.forma_pago
        if forma not in FormaPago.values:
            return Response({"detail": "Forma de pago desconocida."}, status=400)
        egreso.estado = Egreso.Estado.PAGADO
        egreso.fecha = _fecha(request.data.get("fecha"), timezone.localdate())
        egreso.forma_pago = forma
        egreso.save(update_fields=["estado", "fecha", "forma_pago", "updated_at"])
        _auditar(request, "pay_expense", egreso)
        return Response(EgresoSerializer(egreso, context={"request": request}).data)


class ComprobanteEgresoView(APIView):
    """GET /finanzas/egresos/{id}/comprobante/ — la factura del proveedor (no es pública)."""

    permission_classes = PERMISO

    def get(self, request, pk):
        egreso = generics.get_object_or_404(Egreso, pk=pk, tenant=request.tenant)
        if not egreso.comprobante:
            return Response({"detail": "Este egreso no tiene comprobante."}, status=404)
        return FileResponse(egreso.comprobante.open("rb"), filename=egreso.comprobante.name.split("/")[-1])


# ── Caja ─────────────────────────────────────────────────────────────

class CajaView(APIView):
    """
    GET  /finanzas/caja/?fecha=     lo esperado del día y su cierre, si lo hay.
    POST /finanzas/caja/            cierra (o corrige el cierre de) un día.
    """

    permission_classes = PERMISO

    def get(self, request):
        dia = _fecha(request.query_params.get("fecha"), timezone.localdate())
        if dia is None:
            return Response({"detail": "Fecha no válida."}, status=400)
        cierre = CierreCaja.objects.filter(tenant=request.tenant, fecha=dia).first()
        c = calculos.caja(request.tenant, dia)
        # Un cobro o un pago en efectivo apuntado después de cerrar cambia lo
        # esperado: se avisa para volver a cerrar con la cifra buena.
        desactualizado = bool(cierre) and Decimal(c["esperado"]) != cierre.esperado
        return Response({**c, "desactualizado": desactualizado,
                         "cierre": CierreCajaSerializer(cierre).data if cierre else None,
                         "ultimos": CierreCajaSerializer(
                             CierreCaja.objects.filter(tenant=request.tenant)[:10], many=True).data})

    def post(self, request):
        dia = _fecha(request.data.get("fecha"), timezone.localdate())
        contado = _decimal(request.data.get("contado"), None)
        retirado = _decimal(request.data.get("retirado"), "0")
        if dia is None or contado is None or retirado is None or contado < 0 or retirado < 0:
            return Response({"detail": "Indica el efectivo contado (y lo retirado, si hubo)."}, status=400)
        if retirado > contado:
            return Response({"detail": "No se puede retirar más de lo que hay en caja."}, status=400)
        if dia > timezone.localdate():
            return Response({"detail": "No se cierra un día que aún no llega."}, status=400)
        c = calculos.caja(request.tenant, dia)
        esperado = Decimal(c["esperado"])
        cierre, _ = CierreCaja.objects.update_or_create(tenant=request.tenant, fecha=dia, defaults={
            "saldo_inicial": c["saldo_inicial"], "cobros_efectivo": c["cobros_efectivo"],
            "egresos_efectivo": c["egresos_efectivo"], "esperado": esperado, "contado": contado,
            "diferencia": contado - esperado, "retirado": retirado,
            "observaciones": (request.data.get("observaciones") or "")[:300], "cerrado_por": request.user,
        })
        _auditar(request, "close_cash", cierre, fecha=dia.isoformat(), diferencia=str(cierre.diferencia))
        return Response(CierreCajaSerializer(cierre).data, status=201)


# ── Equipo: cómo se le paga a cada uno ───────────────────────────────

class EquipoView(APIView):
    """GET /finanzas/equipo/ — las personas de la clínica con su forma de pago."""

    permission_classes = PERMISO

    def get(self, request):
        perfiles = {p.usuario_id: p for p in PerfilLaboral.objects.filter(tenant=request.tenant)}
        filas = []
        for u in _equipo(request.tenant):
            perfil = perfiles.get(u.id) or PerfilLaboral(usuario=u)
            filas.append({"id": str(u.id), "nombre": u.full_name or u.email, "rol": u.get_role_display(),
                          **PerfilLaboralSerializer(perfil).data})
        return Response(filas)


class PerfilView(APIView):
    """PATCH /finanzas/equipo/{user_id}/ — su modalidad, porcentaje, sueldo…"""

    permission_classes = PERMISO

    def patch(self, request, pk):
        usuario = generics.get_object_or_404(_equipo(request.tenant), pk=pk)
        perfil = PerfilLaboral.objects.filter(usuario=usuario).first() or PerfilLaboral(
            usuario=usuario, tenant=request.tenant)
        s = PerfilLaboralSerializer(perfil, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save(usuario=usuario, tenant=request.tenant)
        _auditar(request, "update_work_profile", perfil, usuario=str(usuario.id),
                 campos=sorted(request.data.keys()))
        return Response({"id": str(usuario.id), "nombre": usuario.full_name,
                         "rol": usuario.get_role_display(), **s.data})


# ── Liquidaciones de honorarios ──────────────────────────────────────

def _datos_liquidacion(request, fuente):
    profesional = generics.get_object_or_404(_equipo(request.tenant), pk=fuente.get("profesional"))
    desde, hasta = _fecha(fuente.get("desde")), _fecha(fuente.get("hasta"))
    ajustes = _decimal(fuente.get("ajustes"))
    if not desde or not hasta or desde > hasta or ajustes is None:
        raise _error("Indica el período (desde y hasta) y, si hay, un ajuste en dólares.")
    return profesional, desde, hasta, ajustes


class LiquidacionPreviaView(APIView):
    """GET /finanzas/liquidaciones/previa/?profesional=&desde=&hasta=&ajustes= — el cálculo, sin guardar."""

    permission_classes = PERMISO

    def get(self, request):
        profesional, desde, hasta, ajustes = _datos_liquidacion(request, request.query_params)
        r = calculos.liquidacion(request.tenant, profesional, desde, hasta, ajustes)
        return Response({k: (str(v) if isinstance(v, Decimal) else v) for k, v in r.items()})


class LiquidacionesView(APIView):
    """GET (lista) y POST (crea) /finanzas/liquidaciones/"""

    permission_classes = PERMISO

    def get(self, request):
        qs = Liquidacion.objects.filter(tenant=request.tenant).select_related("profesional")
        if request.query_params.get("profesional"):
            qs = qs.filter(profesional_id=request.query_params["profesional"])
        return Response(LiquidacionSerializer(qs[:200], many=True).data)

    @transaction.atomic
    def post(self, request):
        profesional, desde, hasta, ajustes = _datos_liquidacion(request, request.data)
        solapa = Liquidacion.objects.filter(
            tenant=request.tenant, profesional=profesional, desde__lte=hasta, hasta__gte=desde
        ).exclude(estado=Liquidacion.Estado.ANULADA).first()
        if solapa:
            return Response({"detail": f"Ya hay una liquidación de {profesional.full_name} que cubre parte de "
                                       f"ese período (N.º {solapa.numero:05d}). Anúlala antes si hay que rehacerla."},
                            status=400)
        r = calculos.liquidacion(request.tenant, profesional, desde, hasta, ajustes)
        numero = (Liquidacion.objects.select_for_update().filter(tenant=request.tenant)
                  .aggregate(m=Max("numero"))["m"] or 0) + 1
        liq = Liquidacion.objects.create(
            tenant=request.tenant, numero=numero, profesional=profesional, desde=desde, hasta=hasta,
            nota=(request.data.get("nota") or "")[:300], creada_por=request.user, **r)
        _auditar(request, "create_settlement", liq, numero=numero, a_pagar=str(liq.a_pagar))
        return Response(LiquidacionSerializer(liq).data, status=201)


class PagarLiquidacionView(APIView):
    """POST /finanzas/liquidaciones/{id}/pagar/ — la paga y la apunta como egreso."""

    permission_classes = PERMISO

    @transaction.atomic
    def post(self, request, pk):
        liq = generics.get_object_or_404(Liquidacion.objects.select_for_update(), pk=pk, tenant=request.tenant)
        if liq.estado != Liquidacion.Estado.BORRADOR:
            return Response({"detail": "Solo se paga una liquidación pendiente."}, status=400)
        forma = request.data.get("forma_pago") or FormaPago.TRANSFERENCIA
        if forma not in FormaPago.values:
            return Response({"detail": "Forma de pago desconocida."}, status=400)
        liq.egreso = Egreso.objects.create(
            tenant=request.tenant, fecha=_fecha(request.data.get("fecha"), timezone.localdate()),
            categoria=categoria(request.tenant, "honorarios"),
            concepto=f"Honorarios {liq.profesional.full_name} — liquidación N.º {liq.numero:05d}",
            monto=liq.a_pagar, forma_pago=forma, profesional=liq.profesional, origen="liquidacion",
            registrado_por=request.user)
        liq.estado = Liquidacion.Estado.PAGADA
        liq.save(update_fields=["egreso", "estado", "updated_at"])
        _auditar(request, "pay_settlement", liq, numero=liq.numero)
        return Response(LiquidacionSerializer(liq).data)


class AnularLiquidacionView(APIView):
    """POST /finanzas/liquidaciones/{id}/anular/ — también anula su egreso, si se pagó."""

    permission_classes = PERMISO

    @transaction.atomic
    def post(self, request, pk):
        liq = generics.get_object_or_404(Liquidacion, pk=pk, tenant=request.tenant)
        if liq.estado == Liquidacion.Estado.ANULADA:
            return Response({"detail": "Ya estaba anulada."}, status=400)
        if liq.egreso_id:
            Egreso.objects.filter(pk=liq.egreso_id).update(
                anulado=True, motivo_anulacion=f"Se anuló la liquidación N.º {liq.numero:05d}")
        liq.estado = Liquidacion.Estado.ANULADA
        liq.save(update_fields=["estado", "updated_at"])
        _auditar(request, "void_settlement", liq, numero=liq.numero)
        return Response(LiquidacionSerializer(liq).data)


class LiquidacionPdfView(APIView):
    permission_classes = PERMISO

    def get(self, request, pk):
        liq = generics.get_object_or_404(Liquidacion.objects.select_related("profesional"),
                                         pk=pk, tenant=request.tenant)
        return _pdf(documentos.liquidacion(request.tenant, liq), f"liquidacion-{liq.numero:05d}.pdf")


# ── Rol de pagos ─────────────────────────────────────────────────────

CAMPOS_ROL = ("dias_trabajados", "horas_suplementarias", "horas_extraordinarias", "horas_extra",
              "otros_ingresos", "anticipos", "prestamos_iess", "otros_descuentos")


def _datos_rol(request, fuente):
    empleado = generics.get_object_or_404(_equipo(request.tenant), pk=fuente.get("empleado"))
    try:
        inicio, _ = calculos.mes_de(fuente.get("mes"))
    except (ValueError, TypeError):
        raise _error("El mes va como 2026-10.")
    valores = {}
    for campo in CAMPOS_ROL:
        v = _decimal(fuente.get(campo), "30" if campo == "dias_trabajados" else "0")
        if v is None or v < 0:
            raise _error("Los valores del rol son números positivos.")
        valores[campo] = int(v) if campo == "dias_trabajados" else v
    if valores["dias_trabajados"] > 30:
        raise _error("El mes del rol se cuenta de 30 días.")
    if valores["horas_suplementarias"] + valores["horas_extraordinarias"] > 200:
        raise _error("Revisa las horas extra: son más de 200 en el mes.")
    return empleado, inicio, valores


class RolPreviaView(APIView):
    """GET /finanzas/roles/previa/?empleado=&mes=&dias_trabajados=&… — el cálculo, sin guardar."""

    permission_classes = PERMISO

    def get(self, request):
        empleado, inicio, valores = _datos_rol(request, request.query_params)
        return Response(calculos.rol(request.tenant, empleado, inicio, **valores))


class RolesView(APIView):
    """GET (lista, ?mes=) y POST (crea o rehace el borrador) /finanzas/roles/"""

    permission_classes = PERMISO

    def get(self, request):
        qs = RolPagos.objects.filter(tenant=request.tenant).exclude(
            estado=RolPagos.Estado.ANULADO).select_related("empleado")
        if request.query_params.get("mes"):
            inicio, _ = calculos.mes_de(request.query_params["mes"])
            qs = qs.filter(mes=inicio)
        return Response(RolSerializer(qs[:300], many=True).data)

    @transaction.atomic
    def post(self, request):
        empleado, inicio, valores = _datos_rol(request, request.data)
        existente = RolPagos.objects.filter(tenant=request.tenant, empleado=empleado, mes=inicio).exclude(
            estado=RolPagos.Estado.ANULADO).first()
        if existente and existente.estado == RolPagos.Estado.PAGADO:
            return Response({"detail": "El rol de ese mes ya está pagado. Anúlalo antes si hay que rehacerlo."},
                            status=400)
        calculo = calculos.rol(request.tenant, empleado, inicio, **valores)
        rol = existente or RolPagos(tenant=request.tenant, empleado=empleado, mes=inicio, creado_por=request.user)
        for campo, valor in valores.items():
            setattr(rol, campo, valor)
        rol.calculo = calculo
        rol.neto = Decimal(calculo["neto"])
        rol.costo_empleador = Decimal(calculo["costo_empleador"])
        rol.save()
        _auditar(request, "save_payroll", rol, mes=inicio.strftime("%Y-%m"), neto=calculo["neto"])
        return Response(RolSerializer(rol).data, status=201 if not existente else 200)


def _recalcular(rol):
    calculo = calculos.rol(rol.tenant, rol.empleado, rol.mes,
                           **{campo: getattr(rol, campo) for campo in CAMPOS_ROL})
    rol.calculo = calculo
    rol.neto = Decimal(calculo["neto"])
    rol.costo_empleador = Decimal(calculo["costo_empleador"])
    rol.save(update_fields=["calculo", "neto", "costo_empleador", "updated_at"])


class GenerarRolesView(APIView):
    """POST /finanzas/roles/generar/ {"mes"} — un borrador para cada persona en relación de dependencia."""

    permission_classes = PERMISO

    @transaction.atomic
    def post(self, request):
        try:
            inicio, _ = calculos.mes_de(request.data.get("mes"))
        except (ValueError, TypeError):
            return Response({"detail": "El mes va como 2026-10."}, status=400)
        creados = 0
        for perfil in PerfilLaboral.objects.filter(tenant=request.tenant, usuario__is_active=True,
                                                   modalidad=PerfilLaboral.Modalidad.DEPENDENCIA):
            ya = RolPagos.objects.filter(tenant=request.tenant, empleado=perfil.usuario, mes=inicio).exclude(
                estado=RolPagos.Estado.ANULADO).exists()
            if ya:
                continue
            calculo = calculos.rol(request.tenant, perfil.usuario, inicio)
            RolPagos.objects.create(tenant=request.tenant, empleado=perfil.usuario, mes=inicio, calculo=calculo,
                                    neto=Decimal(calculo["neto"]),
                                    costo_empleador=Decimal(calculo["costo_empleador"]),
                                    creado_por=request.user)
            creados += 1
        return Response({"creados": creados})


class PagarRolView(APIView):
    permission_classes = PERMISO

    @transaction.atomic
    def post(self, request, pk):
        rol = generics.get_object_or_404(RolPagos.objects.select_for_update(), pk=pk, tenant=request.tenant)
        if rol.estado != RolPagos.Estado.BORRADOR:
            return Response({"detail": "Solo se paga un rol pendiente."}, status=400)
        # Se recalcula al pagar: un anticipo apuntado después de generar el
        # borrador, o un cambio de sueldo, tiene que estar en lo que se paga.
        _recalcular(rol)
        forma = request.data.get("forma_pago") or FormaPago.TRANSFERENCIA
        if forma not in FormaPago.values:
            return Response({"detail": "Forma de pago desconocida."}, status=400)
        rol.egreso = Egreso.objects.create(
            tenant=request.tenant, fecha=_fecha(request.data.get("fecha"), timezone.localdate()),
            categoria=categoria(request.tenant, "sueldos"),
            concepto=f"Sueldo {rol.empleado.full_name} — {documentos.MESES[rol.mes.month - 1]} {rol.mes.year}",
            monto=rol.neto, forma_pago=forma, profesional=rol.empleado, origen="rol",
            registrado_por=request.user)
        rol.estado = RolPagos.Estado.PAGADO
        rol.save(update_fields=["egreso", "estado", "updated_at"])
        _auditar(request, "pay_payroll", rol, mes=rol.mes.strftime("%Y-%m"))
        return Response(RolSerializer(rol).data)


class AnularRolView(APIView):
    permission_classes = PERMISO

    @transaction.atomic
    def post(self, request, pk):
        rol = generics.get_object_or_404(RolPagos, pk=pk, tenant=request.tenant)
        if rol.estado == RolPagos.Estado.ANULADO:
            return Response({"detail": "Ya estaba anulado."}, status=400)
        if rol.egreso_id:
            Egreso.objects.filter(pk=rol.egreso_id).update(anulado=True, motivo_anulacion="Se anuló el rol de pagos")
        rol.estado = RolPagos.Estado.ANULADO
        rol.save(update_fields=["estado", "updated_at"])
        _auditar(request, "void_payroll", rol, mes=rol.mes.strftime("%Y-%m"))
        return Response(RolSerializer(rol).data)


class RolPdfView(APIView):
    permission_classes = PERMISO

    def get(self, request, pk):
        rol = generics.get_object_or_404(RolPagos.objects.select_related("empleado"), pk=pk, tenant=request.tenant)
        nombre = f"rol-{rol.mes.strftime('%Y-%m')}-{(rol.empleado.full_name or 'empleado').split(' ')[0].lower()}.pdf"
        return _pdf(documentos.rol_pagos(request.tenant, rol), nombre)


# ── Obligaciones con el IESS y el SRI, y décimos ─────────────────────

CATEGORIA_DE = {"iess": "sueldos", "sri": "impuestos", "decimo_tercero": "sueldos", "decimo_cuarto": "sueldos"}


def _forma_y_fecha(request):
    forma = request.data.get("forma_pago") or FormaPago.TRANSFERENCIA
    if forma not in FormaPago.values:
        raise _error("Forma de pago desconocida.")
    return forma, _fecha(request.data.get("fecha"), timezone.localdate())


class ObligacionesView(APIView):
    """
    GET  /finanzas/obligaciones/?mes=2026-10   planilla del IESS y retenciones del mes.
    POST /finanzas/obligaciones/ {"tipo": "iess"|"sri", "mes", "fecha", "forma_pago"} — registra su pago.
    """

    permission_classes = PERMISO

    def get(self, request):
        try:
            inicio, _ = calculos.mes_de(request.query_params.get("mes"))
        except (ValueError, TypeError):
            return Response({"detail": "El mes va como 2026-10."}, status=400)
        return Response({"mes": inicio.strftime("%Y-%m"), "obligaciones": calculos.obligaciones(request.tenant, inicio)})

    @transaction.atomic
    def post(self, request):
        try:
            inicio, _ = calculos.mes_de(request.data.get("mes"))
        except (ValueError, TypeError):
            return Response({"detail": "El mes va como 2026-10."}, status=400)
        tipo = request.data.get("tipo")
        o = next((x for x in calculos.obligaciones(request.tenant, inicio) if x["tipo"] == tipo), None)
        if o is None:
            return Response({"detail": "No hay nada que pagar de eso en ese mes."}, status=400)
        if o["pagado"]:
            return Response({"detail": "Ya está registrado. Si hay que corregirlo, anula ese egreso."}, status=400)
        forma, fecha = _forma_y_fecha(request)
        mes_txt = f"{documentos.MESES[inicio.month - 1]} {inicio.year}"
        egreso = Egreso.objects.create(
            tenant=request.tenant, fecha=fecha, categoria=categoria(request.tenant, CATEGORIA_DE[tipo]),
            concepto=f"{o['nombre']} — {mes_txt}", monto=Decimal(o["monto"]), forma_pago=forma,
            proveedor="IESS" if tipo == "iess" else "SRI", origen=tipo, periodo=inicio,
            registrado_por=request.user)
        _auditar(request, "pay_obligation", egreso, tipo=tipo, mes=inicio.strftime("%Y-%m"))
        return Response(EgresoSerializer(egreso, context={"request": request}).data, status=201)


class DecimosView(APIView):
    """
    GET  /finanzas/decimos/?tipo=tercero|cuarto&anio=2026   lo acumulado por persona.
    POST /finanzas/decimos/ {"tipo", "anio", "empleado"?, "fecha", "forma_pago"} — paga a uno o a todos.
    """

    permission_classes = PERMISO

    def _datos(self, fuente):
        tipo = fuente.get("tipo")
        try:
            anio = int(fuente.get("anio") or timezone.localdate().year)
        except ValueError:
            anio = None
        if tipo not in ("tercero", "cuarto") or not anio or not 2000 <= anio <= 2100:
            raise _error("Indica el décimo (tercero o cuarto) y el año.")
        return tipo, anio

    def get(self, request):
        tipo, anio = self._datos(request.query_params)
        return Response(calculos.decimos(request.tenant, tipo, anio))

    @transaction.atomic
    def post(self, request):
        tipo, anio = self._datos(request.data)
        forma, fecha = _forma_y_fecha(request)
        d = calculos.decimos(request.tenant, tipo, anio)
        filas = [f for f in d["filas"] if not f["pagado"]
                 and (not request.data.get("empleado") or f["empleado"] == str(request.data["empleado"]))]
        if not filas:
            return Response({"detail": "No queda nada pendiente de ese décimo."}, status=400)
        equipo = {str(u.id): u for u in _equipo(request.tenant)}
        for f in filas:
            Egreso.objects.create(
                tenant=request.tenant, fecha=fecha, categoria=categoria(request.tenant, "sueldos"),
                concepto=f"{d['nombre']} {anio} — {f['nombre']}", monto=Decimal(f["monto"]), forma_pago=forma,
                profesional=equipo.get(f["empleado"]), origen=f"decimo_{tipo}", periodo=date(anio, 1, 1),
                registrado_por=request.user)
        _auditar(request, "pay_bonus", ConfiguracionFinanzas.de(request.tenant), tipo=tipo, anio=anio,
                 personas=len(filas))
        return Response(calculos.decimos(request.tenant, tipo, anio), status=201)


# ── Comprobante de cobro ─────────────────────────────────────────────

class ComprobanteCobroView(APIView):
    """
    GET /finanzas/cobros/{id}/comprobante/ — el PDF del comprobante. El
    número se asigna la primera vez y ya no cambia: reimprimir da el mismo.
    Lo puede sacar quien registra cobros, no solo quien ve las finanzas.
    """

    permission_classes = [TieneFuncion.para("cobros"), RequiereFuncionalidad.para("finanzas")]

    def get(self, request, pk):
        from apps.billing.models import Payment

        with transaction.atomic():
            pago = generics.get_object_or_404(
                Payment.objects.select_for_update().select_related("patient", "profesional", "installment"),
                pk=pk, tenant=request.tenant)
            if not pago.numero_comprobante:
                config = ConfiguracionFinanzas.objects.select_for_update().get(
                    pk=ConfiguracionFinanzas.de(request.tenant).pk)
                pago.numero_comprobante = config.siguiente_comprobante
                config.siguiente_comprobante += 1
                config.save(update_fields=["siguiente_comprobante", "updated_at"])
                pago.save(update_fields=["numero_comprobante"])
        return _pdf(documentos.comprobante_cobro(request.tenant, pago, pago.numero_comprobante),
                    f"comprobante-{pago.numero_comprobante:06d}.pdf")


class CobrosView(APIView):
    """
    GET   /finanzas/cobros/?mes=        los cobros del mes, con su profesional.
    PATCH /finanzas/cobros/{id}/        corrige a qué profesional corresponde.
    Sin esto, un cobro mal atribuido pagaría honorarios a quien no era.
    """

    permission_classes = PERMISO

    def get(self, request):
        desde, hasta = calculos.mes_de(request.query_params.get("mes"))
        pagos = calculos.cobros(request.tenant, desde, hasta).select_related("patient", "profesional") \
            .order_by("-date", "-created_at")
        return Response([{
            "id": str(p.id), "fecha": p.date.isoformat(), "paciente": p.patient.full_name,
            "monto": str(p.amount), "forma": calculos.FORMAS_COBRO.get(p.method, p.method),
            "profesional": str(p.profesional_id) if p.profesional_id else None,
            "profesional_nombre": p.profesional.full_name if p.profesional_id else "",
            "numero_comprobante": p.numero_comprobante,
        } for p in pagos[:500]])

    def patch(self, request, pk):
        from apps.billing.models import Payment

        pago = generics.get_object_or_404(Payment, pk=pk, tenant=request.tenant)
        valor = request.data.get("profesional")
        profesional = generics.get_object_or_404(_equipo(request.tenant), pk=valor) if valor else None
        # Solo importa si ya se le liquidó a quien lo tenía. Si el nuevo
        # profesional ya tiene liquidado ese período, el cobro le entra en
        # la próxima liquidación como atrasado.
        enlazada = next((liq for liq in Liquidacion.objects.filter(
            tenant=request.tenant, profesional_id=pago.profesional_id).exclude(estado=Liquidacion.Estado.ANULADA)
            if str(pago.id) in (liq.detalle or {}).get("cobros_ids", [])
            or ("cobros_ids" not in (liq.detalle or {}) and liq.desde <= pago.date <= liq.hasta)),
            None) if pago.profesional_id else None
        if enlazada:
            return Response({"detail": f"Ese cobro ya entró en la liquidación N.º {enlazada.numero:05d}. "
                                       "Anúlala antes de cambiarlo."}, status=400)
        pago.profesional = profesional
        pago.save(update_fields=["profesional"])
        _auditar(request, "reassign_payment", pago, profesional=str(getattr(profesional, "id", "")))
        return Response({"id": str(pago.id), "profesional": str(profesional.id) if profesional else None,
                         "profesional_nombre": profesional.full_name if profesional else ""})


# ── Para el contador ─────────────────────────────────────────────────

class ExportarView(APIView):
    """GET /finanzas/exportar/?mes=2026-10 — Excel con cobros, egresos, honorarios y roles."""

    permission_classes = PERMISO

    def get(self, request):
        from apps.finanzas.exportar import libro_del_mes

        try:
            desde, hasta = calculos.mes_de(request.query_params.get("mes"))
        except (ValueError, TypeError):
            return Response({"detail": "El mes va como 2026-10."}, status=400)
        contenido = libro_del_mes(request.tenant, desde, hasta)
        r = HttpResponse(contenido,
                         content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        r["Content-Disposition"] = f'attachment; filename="finanzas-{desde.strftime("%Y-%m")}.xlsx"'
        return r

