from decimal import Decimal

from rest_framework import serializers

from apps.finanzas.models import (
    CategoriaEgreso,
    CierreCaja,
    ConfiguracionFinanzas,
    Egreso,
    Liquidacion,
    PerfilLaboral,
    RolPagos,
)

MAXIMO_ARCHIVO = 8 * 1024 * 1024
TIPOS_ARCHIVO = (".pdf", ".jpg", ".jpeg", ".png", ".webp", ".heic", ".xml")


class ConfiguracionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracionFinanzas
        fields = ["salario_basico", "aporte_personal_iess", "aporte_patronal_iess", "aporte_iece_secap",
                  "fondos_reserva", "retencion_honorarios", "siguiente_comprobante", "region",
                  "recargo_suplementarias", "recargo_extraordinarias"]

    def validate(self, datos):
        for campo in ("aporte_personal_iess", "aporte_patronal_iess", "aporte_iece_secap",
                      "fondos_reserva", "retencion_honorarios"):
            if campo in datos and not (Decimal("0") <= datos[campo] <= Decimal("100")):
                raise serializers.ValidationError({campo: "Un porcentaje entre 0 y 100."})
        for campo in ("recargo_suplementarias", "recargo_extraordinarias"):
            if campo in datos and not (Decimal("0") <= datos[campo] <= Decimal("300")):
                raise serializers.ValidationError({campo: "Un recargo entre 0 y 300 %."})
        if "salario_basico" in datos and datos["salario_basico"] <= 0:
            raise serializers.ValidationError({"salario_basico": "El salario básico tiene que ser mayor que cero."})
        return datos


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoriaEgreso
        fields = ["id", "nombre", "clave", "activa", "orden"]
        read_only_fields = ["id", "clave"]


class EgresoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source="categoria.nombre", read_only=True)
    profesional_nombre = serializers.SerializerMethodField()
    tiene_comprobante = serializers.SerializerMethodField()
    forma_pago_nombre = serializers.CharField(source="get_forma_pago_display", read_only=True)

    class Meta:
        model = Egreso
        fields = ["id", "fecha", "categoria", "categoria_nombre", "concepto", "monto", "forma_pago",
                  "forma_pago_nombre", "estado", "vence", "proveedor", "proveedor_ruc", "numero_factura",
                  "comprobante", "tiene_comprobante", "profesional", "profesional_nombre",
                  "descontar_al_profesional", "origen", "periodo", "anulado", "motivo_anulacion", "created_at"]
        read_only_fields = ["id", "origen", "periodo", "anulado", "motivo_anulacion", "created_at"]
        extra_kwargs = {"comprobante": {"write_only": True, "required": False}}

    def get_profesional_nombre(self, obj):
        return obj.profesional.full_name if obj.profesional_id else ""

    def get_tiene_comprobante(self, obj):
        return bool(obj.comprobante)

    def validate_monto(self, valor):
        if valor <= 0:
            raise serializers.ValidationError("El monto tiene que ser mayor que cero.")
        return valor

    def validate_categoria(self, valor):
        if valor.tenant_id != self.context["request"].tenant.id:
            raise serializers.ValidationError("Esa categoría no es de esta clínica.")
        return valor

    def validate_profesional(self, valor):
        if valor and (valor.tenant_id != self.context["request"].tenant.id or valor.role == "patient"):
            raise serializers.ValidationError("Ese profesional no es de esta clínica.")
        return valor

    def validate_proveedor_ruc(self, valor):
        valor = (valor or "").strip()
        if valor and (not valor.isdigit() or len(valor) not in (10, 13)):
            raise serializers.ValidationError("La cédula tiene 10 dígitos y el RUC 13.")
        return valor

    def validate_comprobante(self, archivo):
        if archivo is None:
            return archivo
        if archivo.size > MAXIMO_ARCHIVO:
            raise serializers.ValidationError("El archivo pasa de 8 MB.")
        if not archivo.name.lower().endswith(TIPOS_ARCHIVO):
            raise serializers.ValidationError("Sube una foto, un PDF o el XML de la factura.")
        return archivo

    def validate(self, datos):
        estado = datos.get("estado", getattr(self.instance, "estado", Egreso.Estado.PAGADO))
        if estado == Egreso.Estado.POR_PAGAR and not datos.get("vence", getattr(self.instance, "vence", None)):
            datos["vence"] = datos.get("fecha", getattr(self.instance, "fecha", None))
        return datos


class CierreCajaSerializer(serializers.ModelSerializer):
    cerrado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = CierreCaja
        fields = ["id", "fecha", "saldo_inicial", "cobros_efectivo", "egresos_efectivo", "esperado",
                  "contado", "diferencia", "retirado", "observaciones", "cerrado_por_nombre", "updated_at"]

    def get_cerrado_por_nombre(self, obj):
        return obj.cerrado_por.full_name if obj.cerrado_por_id else ""


class PerfilLaboralSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerfilLaboral
        fields = ["modalidad", "cedula", "cargo", "base_honorarios", "porcentaje", "monto_fijo",
                  "emite_factura", "sueldo", "fecha_ingreso", "decimo_tercero_mensual",
                  "decimo_cuarto_mensual", "fondos_reserva_mensual"]

    def validate_porcentaje(self, valor):
        if not (Decimal("0") <= valor <= Decimal("100")):
            raise serializers.ValidationError("Un porcentaje entre 0 y 100.")
        return valor

    def validate_cedula(self, valor):
        valor = (valor or "").strip()
        if valor and (not valor.isdigit() or len(valor) not in (10, 13)):
            raise serializers.ValidationError("La cédula tiene 10 dígitos y el RUC 13.")
        return valor


class LiquidacionSerializer(serializers.ModelSerializer):
    profesional_nombre = serializers.CharField(source="profesional.full_name", read_only=True)
    estado_nombre = serializers.CharField(source="get_estado_display", read_only=True)

    class Meta:
        model = Liquidacion
        fields = ["id", "numero", "profesional", "profesional_nombre", "desde", "hasta", "base",
                  "porcentaje", "honorario", "descuentos", "ajustes", "retencion_porcentaje",
                  "retencion", "a_pagar", "detalle", "nota", "estado", "estado_nombre", "created_at"]


class RolSerializer(serializers.ModelSerializer):
    empleado_nombre = serializers.CharField(source="empleado.full_name", read_only=True)
    estado_nombre = serializers.CharField(source="get_estado_display", read_only=True)

    class Meta:
        model = RolPagos
        fields = ["id", "empleado", "empleado_nombre", "mes", "dias_trabajados", "horas_suplementarias",
                  "horas_extraordinarias", "horas_extra",
                  "otros_ingresos", "anticipos", "prestamos_iess", "otros_descuentos", "calculo",
                  "neto", "costo_empleador", "estado", "estado_nombre", "created_at"]
