"""
La configuración de despliegue que sostiene el rendimiento y los límites
de intentos no se pierde en un cambio del compose:

  · Todos los servicios con Django usan la caché compartida en Redis. Sin
    ella cada proceso cuenta los intentos por su lado (20/min por IP,
    5/min para pedir códigos) y quien insiste tiene el triple.
  · Gunicorn con hilos, y nginx reutilizando las conexiones con él.
  · Redis guarda la cola en disco y solo descarta caché si se llena.
  · Celery no guarda resultados que nadie lee.
"""

import os
import subprocess
import sys
from pathlib import Path

import yaml
from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parents[3]


class DespliegueTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.compose = yaml.safe_load((RAIZ / "docker-compose.prod.yml").read_text())["services"]
        cls.nginx = (RAIZ / "nginx" / "nginx.conf").read_text()

    def test_los_servicios_de_django_comparten_la_cache(self):
        con_django = [n for n, s in self.compose.items()
                      if (s.get("environment") or {}).get("DJANGO_ENTORNO") == "produccion"]
        self.assertEqual(sorted(con_django), ["celery-beat", "celery-worker", "django-api"])
        for nombre in con_django:
            self.assertTrue(self.compose[nombre]["environment"]["CACHE_URL"].startswith("redis://redis:6379/"),
                            nombre)

    def test_con_cache_url_la_cache_es_redis_y_sin_ella_en_memoria(self):
        """La configuración real, cargada en un proceso aparte con y sin CACHE_URL."""
        codigo = ("import django, os; os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'; "
                  "from django.conf import settings; print(settings.CACHES['default']['BACKEND'])")

        def backend(**env):
            entorno = {k: v for k, v in os.environ.items() if k != "CACHE_URL"} | env
            r = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ / "django-api", env=entorno,
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            return r.stdout.strip()

        self.assertEqual(backend(CACHE_URL="redis://redis:6379/1"), "django.core.cache.backends.redis.RedisCache")
        self.assertEqual(backend(), "django.core.cache.backends.locmem.LocMemCache")

    def test_gunicorn_con_hilos_y_nginx_con_conexiones_reutilizadas(self):
        orden = self.compose["django-api"]["command"]
        self.assertIn("--threads", orden)
        self.assertIn("--keep-alive", orden)
        self.assertIn("keepalive", self.nginx)
        self.assertIn('proxy_set_header Connection "";', self.nginx)

    def test_redis_persistente_y_con_tope(self):
        orden = self.compose["redis"]["command"]
        self.assertIn("--appendonly yes", orden)
        self.assertIn("volatile-lru", orden)
        self.assertIn("redis_data:/data", self.compose["redis"]["volumes"])

    def test_nginx_comprime_menos_las_respuestas_con_tokens(self):
        self.assertIn("gzip on;", self.nginx)
        bloque = self.nginx.split("location /api/v1/auth/ {", 1)[1].split("}", 1)[0]
        self.assertIn("gzip off;", bloque)

    def test_celery_no_guarda_resultados(self):
        self.assertTrue(settings.CELERY_TASK_IGNORE_RESULT)
        self.assertEqual(settings.CELERY_WORKER_PREFETCH_MULTIPLIER, 1)
