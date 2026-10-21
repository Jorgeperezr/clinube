"""
Filtrar por días sin perder los índices.

`scheduled_start__date__gte=d` es cómodo, pero PostgreSQL lo traduce a
`(scheduled_start AT TIME ZONE '…')::date >= d`: convierte cada fila antes
de comparar y no puede usar el índice (tenant_id, scheduled_start). Con
9.000 citas, la agenda de un día recorría las 9.000 para quedarse con 87.

`rango_dias` pide lo mismo como un intervalo de instantes —desde las 00:00
del primer día hasta las 00:00 del siguiente al último, en la zona horaria
de la clínica—, que el índice resuelve directamente. El resultado es
idéntico a `__date` en la zona horaria activa.
"""

from datetime import datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone


def inicio_del_dia(dia):
    """Las 00:00 de `dia` en la zona horaria activa, como instante."""
    return timezone.make_aware(datetime.combine(dia, time.min), timezone.get_current_timezone())


def rango_dias(campo, desde=None, hasta=None):
    """Q para `campo` (un DateTimeField) entre los días `desde` y `hasta`, ambos incluidos."""
    q = Q()
    if desde:
        q &= Q(**{f"{campo}__gte": inicio_del_dia(desde)})
    if hasta:
        q &= Q(**{f"{campo}__lt": inicio_del_dia(hasta + timedelta(days=1))})
    return q
