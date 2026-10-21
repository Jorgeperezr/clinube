"""
Exporta el contrato del sistema a docs/contrato/: lo que otra
implementación del servidor (la de Java/Kotlin, clinube_java) tiene que
respetar para que el panel y la app funcionen sin cambios.

    bash scripts/exportar-contrato.sh

  · RUTAS.md            cada ruta de la API: métodos, vista, archivo y
                        línea, permisos, serializador y paginación.
  · MODELO_DE_DATOS.md  cada tabla: campos, tipos, nulos, valores por
                        omisión, opciones, relaciones, unicidad e índices.
  · openapi.yaml        el esquema de drf-spectacular. Exacto en rutas y
                        en los serializadores; las vistas APIView no
                        describen su respuesta (para eso, RUTAS.md lleva
                        al código).

Se genera del código, no se escribe a mano: si Clinube cambia, se vuelve
a exportar y la diferencia en git dice qué hay que portar.
"""

import inspect
from pathlib import Path

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import models
from django.urls import URLPattern, URLResolver, get_resolver

PROPIAS = "apps."


def _rutas(patrones, prefijo=""):
    for p in patrones:
        if isinstance(p, URLResolver):
            yield from _rutas(p.url_patterns, prefijo + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefijo + str(p.pattern), p


def _nombre(obj):
    if obj is None:
        return ""
    if isinstance(obj, (list, tuple)):
        return ", ".join(_nombre(o) for o in obj)
    return getattr(obj, "__name__", None) or obj.__class__.__name__


def _ubicacion(clase, raiz):
    try:
        archivo = Path(inspect.getsourcefile(clase)).resolve()
        linea = inspect.getsourcelines(clase)[1]
        if not archivo.is_relative_to(raiz / "django-api" / "apps"):
            return clase.__module__          # una librería: su módulo, no la ruta del entorno
        return f"{archivo.relative_to(raiz)}:{linea}"
    except (TypeError, OSError, ValueError):
        return clase.__module__


def _permiso(p):
    """Texto de una clase de permiso, también de las compuestas con | y &."""
    if hasattr(p, "op1_class"):                     # OperandHolder de DRF
        operador = {"OR": " o ", "AND": " y "}.get(p.operator_class.__name__, " ? ")
        partes = [_permiso(p.op1_class)] + ([_permiso(p.op2_class)] if hasattr(p, "op2_class") else [])
        return "(" + operador.join(partes) + ")"
    roles = getattr(p, "allowed_roles", None)
    clave = getattr(p, "clave", None)
    if roles:
        return "rol: " + "/".join(roles)
    if clave:
        return f"{p.__mro__[1].__name__}({clave})"
    return _nombre(p)


def _permisos(vista):
    salida = [_permiso(p) for p in (getattr(vista, "permission_classes", []) or [])]
    # Una lista vacía es «sin comprobar nada», no «autenticado».
    texto = ", ".join(salida) or "público"
    if "get_permissions" in vista.__dict__:
        texto += " · varía por método (get_permissions)"
    return texto


def _metodos(vista):
    return [m.upper() for m in ("get", "post", "put", "patch", "delete") if hasattr(vista, m)]


class Command(BaseCommand):
    help = "Exporta rutas, modelo de datos y OpenAPI a docs/contrato/."

    def add_arguments(self, parser):
        parser.add_argument("--destino", default=None, help="Carpeta (por omisión, docs/contrato/ del repositorio).")
        parser.add_argument("--sin-openapi", action="store_true")

    def handle(self, destino, sin_openapi, **_):
        raiz = Path(__file__).resolve().parents[5]
        carpeta = Path(destino) if destino else raiz / "docs" / "contrato"
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / "RUTAS.md").write_text(self._rutas(raiz), encoding="utf-8")
        (carpeta / "MODELO_DE_DATOS.md").write_text(self._modelo(), encoding="utf-8")
        if not sin_openapi:
            call_command("spectacular", file=str(carpeta / "openapi.yaml"), verbosity=0)
        self.stdout.write(f"Contrato exportado en {carpeta}")

    # ── Rutas ────────────────────────────────────────────────────────
    def _rutas(self, raiz):
        filas = []
        for ruta, patron in _rutas(get_resolver().url_patterns):
            vista = getattr(patron.callback, "view_class", None) or getattr(patron.callback, "cls", None)
            if vista is None or not ruta.startswith("api/"):
                continue
            serializador = getattr(vista, "serializer_class", None)
            paginada = bool(getattr(vista, "pagination_class", "x")) and hasattr(vista, "list")
            filas.append((
                "/" + ruta.replace("^", "").replace("$", ""),
                " ".join(_metodos(vista)), vista.__name__, _ubicacion(vista, raiz),
                _permisos(vista), _nombre(serializador), "sí" if paginada else "",
            ))
        filas.sort()
        lineas = [
            "# Rutas de la API",
            "",
            "Generado con `bash scripts/exportar-contrato.sh` desde el código; no editar a mano.",
            "",
            "Convenciones que valen para todas (ver `docs/contrato/LEEME.md`): prefijo `/api/v1/`, barra final,",
            "JSON en snake_case, autenticación `Authorization: Bearer <access>`, listas paginadas como",
            "`{count, next, previous, results}` con 20 por página.",
            "",
            f"{len(filas)} rutas.",
            "",
            "| Ruta | Métodos | Vista | Código | Permisos | Serializador | Paginada |",
            "|---|---|---|---|---|---|---|",
        ]
        lineas += [f"| `{r}` | {m} | {v} | `{u}` | {p} | {s} | {pg} |" for r, m, v, u, p, s, pg in filas]
        return "\n".join(lineas) + "\n"

    # ── Modelo de datos ──────────────────────────────────────────────
    def _modelo(self):
        lineas = [
            "# Modelo de datos",
            "",
            "Generado con `bash scripts/exportar-contrato.sh` desde los modelos de Django; no editar a mano.",
            "Todas las tablas con `tenant` pertenecen a una clínica y toda consulta se filtra por ella.",
            "",
        ]
        for config in sorted(apps.get_app_configs(), key=lambda c: c.label):
            if not config.name.startswith(PROPIAS):
                continue
            modelos = list(config.get_models())
            if not modelos:
                continue
            lineas += [f"## {config.label}", ""]
            for m in modelos:
                lineas += self._tabla(m)
        return "\n".join(lineas) + "\n"

    def _tabla(self, m):
        meta = m._meta
        salida = [f"### {m.__name__} — `{meta.db_table}`", ""]
        if meta.verbose_name:
            salida.append(f"_{meta.verbose_name}_")
            salida.append("")
        salida += ["| Campo | Tipo | Nulo | Por omisión | Detalle |", "|---|---|---|---|---|"]
        for f in meta.concrete_fields:
            tipo = f.get_internal_type()
            detalle = []
            if f.primary_key:
                detalle.append("clave primaria")
            if isinstance(f, models.ForeignKey):
                destino = f.related_model._meta
                detalle.append(f"→ {destino.app_label}.{destino.object_name} ({f.remote_field.on_delete.__name__})")
            if f.unique and not f.primary_key:
                detalle.append("único")
            if getattr(f, "max_length", None) and not isinstance(f, models.UUIDField):
                detalle.append(f"máx. {f.max_length}")
            if getattr(f, "max_digits", None):
                detalle.append(f"{f.max_digits},{f.decimal_places}")
            if f.choices:
                detalle.append("opciones: " + ", ".join(f"`{v}`" for v, _ in f.choices if v != ""))
            if getattr(f, "auto_now_add", False):
                detalle.append("se fija al crear")
            if getattr(f, "auto_now", False):
                detalle.append("se actualiza al guardar")
            if f.help_text:
                detalle.append(str(f.help_text).replace("|", "/"))
            defecto = ""
            if f.has_default():
                d = f.default
                defecto = _nombre(d) + "()" if callable(d) else repr(getattr(d, "value", d))
            nombre = f.attname if isinstance(f, models.ForeignKey) else f.name
            salida.append(f"| `{nombre}` | {tipo} | {'sí' if f.null else ''} | {defecto} | {'; '.join(detalle)} |")
        for f in meta.local_many_to_many:
            destino = f.related_model._meta
            salida.append(f"| `{f.name}` | ManyToMany | | | → {destino.app_label}.{destino.object_name} |")
        extra = []
        for u in meta.unique_together:
            extra.append(f"- Único: ({', '.join(u)})")
        for c in meta.constraints:
            campos = getattr(c, "fields", ())
            condicion = f" si {c.condition}" if getattr(c, "condition", None) else ""
            extra.append(f"- Restricción `{c.name}`: ({', '.join(campos)}){condicion}")
        for i in meta.indexes:
            extra.append(f"- Índice: ({', '.join(i.fields)})")
        if meta.ordering:
            extra.append(f"- Orden por omisión: {', '.join(meta.ordering)}")
        if extra:
            salida += [""] + extra
        return salida + [""]
