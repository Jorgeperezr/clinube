"""
Las consultas que más tiempo de base de datos gastan, según
pg_stat_statements.

    docker compose -f docker-compose.prod.yml exec django-api python manage.py consultas_lentas
    … consultas_lentas --por media --top 20
    … consultas_lentas --reiniciar      (empieza a medir de cero)

Sirve para decidir qué optimizar con datos reales: la consulta que más
pesa no suele ser la que uno cree.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

ORDEN = {"total": "total_exec_time", "media": "mean_exec_time", "llamadas": "calls"}


class Command(BaseCommand):
    help = "Las consultas que más tiempo gastan en PostgreSQL (pg_stat_statements)."

    def add_arguments(self, parser):
        parser.add_argument("--top", type=int, default=15)
        parser.add_argument("--por", choices=ORDEN, default="total",
                            help="total (tiempo acumulado), media (por llamada) o llamadas")
        parser.add_argument("--reiniciar", action="store_true", help="Borra lo medido hasta ahora.")

    def handle(self, top, por, reiniciar, **_):
        if connection.vendor != "postgresql":
            raise CommandError("Solo funciona con PostgreSQL.")
        with connection.cursor() as c:
            try:
                if reiniciar:
                    c.execute("SELECT pg_stat_statements_reset()")
                    self.stdout.write("Medición reiniciada.")
                    return
                c.execute(f"""
                    SELECT calls, round(total_exec_time::numeric, 1), round(mean_exec_time::numeric, 2),
                           rows, regexp_replace(query, '\\s+', ' ', 'g')
                    FROM pg_stat_statements
                    WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
                    ORDER BY {ORDEN[por]} DESC LIMIT %s""", [top])
                filas = c.fetchall()
            except Exception as e:
                raise CommandError(
                    "pg_stat_statements no está activo. En producción lo carga docker-compose.prod.yml "
                    f"(shared_preload_libraries); hay que reiniciar el contenedor de postgres. ({e})") from e
        self.stdout.write(f"{'llamadas':>9} {'total ms':>10} {'media ms':>9} {'filas':>8}  consulta")
        for llamadas, total, media, n, q in filas:
            self.stdout.write(f"{llamadas:>9} {total:>10} {media:>9} {n:>8}  {q[:140]}")
