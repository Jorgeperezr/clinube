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
"""

CATALOGO = {
    "inventario": {
        "nombre": "Inventario",
        "descripcion": "Control de stock e insumos por tratamiento.",
        "tipo": "incluida", "por_defecto": True,
    },
    "whatsapp": {
        "nombre": "Recordatorios por WhatsApp",
        "descripcion": "Avisos automáticos de cita y de pago. Necesita conectar la cuenta de Meta de la clínica.",
        # Incluida, pero apagada de fábrica: hasta que la clínica conecte
        # SU cuenta de Meta no manda nada, y encendida parecería rota.
        "tipo": "incluida", "por_defecto": False,
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


def catalogo_publico():
    """El catálogo como lo pinta Plataforma: en orden, con su tipo y origen."""
    return [
        {"clave": clave, "nombre": d["nombre"], "descripcion": d["descripcion"],
         "tipo": d["tipo"], "por_defecto": d["por_defecto"], "origen": d.get("origen", "")}
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
    """Lo que la plataforma le ha dado de alta a la clínica."""
    return normalizar(getattr(tenant, "funcionalidades", None))


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
