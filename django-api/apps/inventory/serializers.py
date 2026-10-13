from rest_framework import serializers

from apps.inventory.models import Batch, InventoryMovement, Product


class BatchSerializer(serializers.ModelSerializer):
    # Opcionales: con el costo, la compra queda también como egreso en
    # Finanzas (si la clínica la tiene), sin apuntarla dos veces.
    costo_total = serializers.DecimalField(max_digits=12, decimal_places=2, required=False,
                                           write_only=True, min_value=0)
    proveedor = serializers.CharField(required=False, write_only=True, allow_blank=True, max_length=150)
    proveedor_ruc = serializers.CharField(required=False, write_only=True, allow_blank=True, max_length=13)
    numero_factura = serializers.CharField(required=False, write_only=True, allow_blank=True, max_length=20)
    forma_pago = serializers.CharField(required=False, write_only=True, allow_blank=True, max_length=15)

    class Meta:
        model = Batch
        fields = ["id", "product", "batch_number", "quantity", "expiration_date", "received_at",
                  "costo_total", "proveedor", "proveedor_ruc", "numero_factura", "forma_pago"]
        read_only_fields = ["id", "received_at"]


class ProductSerializer(serializers.ModelSerializer):
    current_stock = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "name", "unit", "min_stock",
            "current_stock", "is_low_stock", "is_active",
        ]
        read_only_fields = ["id", "current_stock", "is_low_stock"]


class InventoryMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    movement_type_display = serializers.CharField(source="get_movement_type_display", read_only=True)
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)

    class Meta:
        model = InventoryMovement
        fields = [
            "id", "product", "product_name", "batch", "movement_type",
            "movement_type_display", "quantity", "reason", "reason_display", "date",
        ]
        read_only_fields = ["id", "date"]
