"""
Qué módulos tiene contratada cada clínica.

El catálogo vive aquí y no repartido por el código porque es la lista
que el Super Administrador ve al dar de alta una clínica, la que el
panel usa para esconder lo que no toca y la que la API usa para
rechazar lo que no corresponde. Tres sitios, una sola fuente.

**Lo básico no se apaga.** Pacientes, agenda, historia clínica y pagos
no están en esta lista: una clínica odontológica sin ficha de paciente
no es una versión reducida del producto, es un producto que no sirve.
Lo que se puede apagar es lo que una clínica pequeña puede no querer
—o no pagar— sin dejar de trabajar.

**Apagar algo NO borra sus datos.** Si una clínica desactiva inventario
y lo vuelve a activar el mes que viene, su stock sigue ahí. Apagar es
dejar de ver y de poder tocar, no destruir.

**Dos tipos de función** (`tipo`):

  · «incluida»: forma parte del producto y viene encendida en toda
    clínica nueva (salvo que `por_defecto` diga lo contrario, como
    WhatsApp, que no funciona hasta conectar la cuenta de la clínica).
  · «adicional»: se agrega a pedido, clínica por clínica, desde
    Plataforma. Una clínica nueva NO la trae.

**Funciones a pedido de un cliente.** Cuando una clínica pide algo que
no existe, se desarrolla como función «adicional» con su `origen` (quién
la pidió y cuándo) y queda en este catálogo: se activa para esa clínica
y, desde ese momento, Plataforma la ofrece a cualquier otra. Pasos:

  1. Añadirla aquí, con tipo «adicional», `por_defecto` False y su
     `origen`. Plataforma la muestra sola (lee GET /platform/funcionalidades/).
  2. En la API, cerrar sus vistas con
     `RequiereFuncionalidad.para("clave")` (apps/common/permisos_funcionalidad.py).
  3. En el panel, esconderla si `user.funcionalidades.clave === false`
     (es cortesía; el candado de verdad es el paso 2).
  4. Si se ve en la app del paciente, que /app/clinica/ diga si está
     activa (`funciones`) y la app la esconda si no.
  5. Pruebas: que sin activarla la API responda 403 y que una clínica
     nueva no la tenga.

**Funciones en prueba** (`fase`). Lo nuevo nace con `"fase": "prueba"`:
mientras tanto solo existe en las clínicas de prueba (`Tenant.es_prueba`;
la primera clínica de la instalación lo es). En las demás no aparece ni
en el menú, ni en la API, ni en Configuración → Módulos, aunque esté
marcada. Cuando se ha probado lo suficiente, el Super Administrador la
publica en Plataforma → Funciones y desde ese momento se comporta según
su tipo: una «incluida» llega encendida a todas, una «adicional» queda
lista para agregarla a quien la pida. Publicar se puede deshacer: vuelve
a quedar solo en las de prueba, sin borrar nada.

Cuando ya no haga falta la marcha atrás, se le quita `fase` aquí.
"""

CATALOGO = {
    "inventario": {
        "nombre": "Inventario",
        "descripcion": "Control de stock e insumos por tratamiento.",
        "tipo": "incluida", "por_defecto": True,
    },
    "whatsapp": {
        "nombre": "Recordatorios por WhatsApp",
        "descripcion": "Recordatorios, recetas y confirmaciones por WhatsApp. Se contrata aparte: la "
                       "clínica paga su cuenta de Meta y entrega su número a la plataforma.",
        # A pedido: solo la tienen las clínicas que la pagan y conectan SU
        # cuenta de Meta. Sin ella todo va por correo y por la app.
        "tipo": "adicional", "por_defecto": False,
    },
    "convenios": {
        "nombre": "Convenios y tarifarios",
        "descripcion": "Precios pactados con aseguradoras y empresas.",
        "tipo": "incluida", "por_defecto": True,
    },
    "app_paciente": {
        "nombre": "App del paciente",
        "descripcion": "Sus citas, su saldo y sus indicaciones en el teléfono.",
        "tipo": "incluida", "por_defecto": True,
    },
    "formulario_033": {
        "nombre": "Formulario MSP 033",
        "descripcion": "Historia clínica única del Ministerio de Salud (HCU-033).",
        "tipo": "incluida", "por_defecto": True,
    },
    "reportes": {
        "nombre": "Reportes",
        "descripcion": "Informes financieros y de producción.",
        "tipo": "incluida", "por_defecto": True,
    },
    # En prueba: solo en las clínicas de prueba hasta que se publique.
    "temas_personales": {
        "nombre": "Tema de cada persona",
        "descripcion": "Cada profesional elige el tema de su panel entre los de su clínica y "
                       "los de Clinube. Los documentos y la app del paciente siguen con el "
                       "tema de la clínica.",
        "tipo": "incluida", "por_defecto": True, "fase": "prueba",
    },
    "finanzas": {
        "nombre": "Finanzas",
        "descripcion": "Lo que entra y lo que sale: egresos, caja diaria, utilidad del mes, "
                       "liquidaciones de honorarios, rol de pagos, comprobantes de cobro y el "
                       "Excel para el contador.",
        "tipo": "incluida", "por_defecto": True, "fase": "prueba",
    },
    # ── Adicionales: se agregan a pedido ─────────────────────────────
    "odontograma_3d": {
        "nombre": "Odontograma 3D",
        "descripcion": "Modelo tridimensional de las piezas en la ficha, junto al odontograma "
                       "clásico, que sigue siendo el del formulario oficial.",
        "tipo": "adicional", "por_defecto": False,
        "origen": "Pedida por una clínica odontológica cliente (2026)",
    },
    "logros": {
        "nombre": "Rachas y logros",
        "descripcion": "Programa de fidelización: el paciente gana logros y rachas por acudir a "
                       "sus controles y estar al día, y los ve en su app. No envía mensajes: "
                       "los recordatorios son otra función.",
        "tipo": "adicional", "por_defecto": False,
        "origen": "Pedida por una clínica odontológica cliente (2026)",
    },
}

TIPOS = {"incluida": "Incluidas", "adicional": "Adicionales"}

# Lo que lleva una clínica recién creada si nadie dice otra cosa.
POR_DEFECTO = {clave: d["por_defecto"] for clave, d in CATALOGO.items()}

# Las que nacieron en prueba (se pueden publicar y volver a retirar).
NACIDAS_EN_PRUEBA = frozenset(c for c, d in CATALOGO.items() if d.get("fase") == "prueba")


def publicadas():
    """Las nacidas en prueba que el Super Administrador ya dio a todas."""
    from apps.common.models import PlatformConfiguration

    guardadas = PlatformConfiguration.objects.values_list("funciones_publicadas", flat=True).first()
    return {c for c in (guardadas or []) if c in NACIDAS_EN_PRUEBA}


def en_prueba():
    """Las que todavía solo existen en las clínicas de prueba."""
    if not NACIDAS_EN_PRUEBA:
        return set()  # lo normal: ni se consulta la base
    return set(NACIDAS_EN_PRUEBA) - publicadas()


def publicar(clave, publicada):
    """Da una función nacida en prueba a todas las clínicas, o la retira."""
    from apps.common.models import PlatformConfiguration

    if clave not in NACIDAS_EN_PRUEBA:
        raise ValueError("Esa función no está en prueba: ya la tienen todas las clínicas.")
    config = PlatformConfiguration.get_solo()
    lista = set(config.funciones_publicadas or []) & NACIDAS_EN_PRUEBA
    if publicada:
        lista.add(clave)
    else:
        lista.discard(clave)
    config.funciones_publicadas = sorted(lista)
    config.save(update_fields=["funciones_publicadas", "updated_at"])


def catalogo_publico():
    """El catálogo como lo pinta Plataforma: en orden, con su tipo, fase y origen."""
    beta = en_prueba()
    return [
        {"clave": clave, "nombre": d["nombre"], "descripcion": d["descripcion"],
         "tipo": d["tipo"], "por_defecto": d["por_defecto"], "origen": d.get("origen", ""),
         "fase": "prueba" if clave in beta else "estable",
         "nacio_en_prueba": clave in NACIDAS_EN_PRUEBA}
        for clave, d in CATALOGO.items()
    ]


def normalizar(valor):
    """
    Deja el diccionario con exactamente las claves del catálogo.

    Las que no se conozcan se tiran —serán de una versión anterior— y
    las que falten se rellenan con el valor por defecto. Así, añadir una
    funcionalidad nueva no obliga a migrar los datos de nadie: una
    «incluida» llega encendida a todas en cuanto se despliega, y una
    «adicional» llega apagada hasta que Plataforma la active.
    """
    entrante = valor if isinstance(valor, dict) else {}
    return {
        clave: bool(entrante.get(clave, POR_DEFECTO[clave]))
        for clave in CATALOGO
    }


def contratadas(tenant):
    """
    Lo que la plataforma le ha dado de alta a la clínica.

    Una función en prueba solo cuenta en una clínica de prueba: en las
    demás no existe todavía, la tengan marcada o no. Lo marcado se
    conserva y vale en cuanto se publique.
    """
    datos = normalizar(getattr(tenant, "funcionalidades", None))
    if not getattr(tenant, "es_prueba", False):
        for clave in en_prueba():
            datos[clave] = False
    return datos


def efectivas(tenant):
    """
    Lo que la clínica usa de verdad: contratado por la plataforma Y no
    apagado por la propia clínica. Dos llaves, cada una de quien le toca:
    la plataforma decide qué se puede usar y la clínica, qué quiere usar.
    """
    if tenant is None:
        return {clave: False for clave in CATALOGO}
    propias = getattr(tenant, "modulos_clinica", None) or {}
    return {clave: activo and propias.get(clave, True) is not False
            for clave, activo in contratadas(tenant).items()}


def activa(tenant, clave):
    """¿Esta clínica tiene y usa esta funcionalidad?"""
    return efectivas(tenant).get(clave, False)
