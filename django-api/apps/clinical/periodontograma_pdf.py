"""
El periodontograma dibujado en el PDF de la historia clínica.

Es la misma lectura que el diagrama del panel
(frontend/lib/periodontal/DiagramaPeriodontal.js): las piezas vistas de
frente con su corona y sus raíces, la pauta de milímetros y, encima,

  · línea roja  → margen gingival
  · línea azul  → fondo de la bolsa (margen + profundidad de sondaje)
  · sombreado   → la bolsa, entre las dos
  · punto rojo  → sangrado al sondaje
  · aro ámbar   → supuración

Todo en milímetros reales desde la unión amelocementaria de cada pieza,
con las medidas y los perfiles de frontend/lib/odontogram/AnatomiaDental.js
traídos tal cual: si el panel y el papel dibujaran distinto, el papel
diría otra cosa que la pantalla. Si cambian allí, cambian aquí.

Las líneas salen de lo que registró el profesional en la exploración: se
mueven con cada medición, igual que en la pantalla.
"""

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Flowable

MEDIDAS = {
    "permanente": {
        "superior": {1: (8.5, 10.5, 13), 2: (6.5, 9, 13), 3: (7.5, 10, 17), 4: (7, 8.5, 14),
                     5: (6.5, 8.5, 14), 6: (10, 7.5, 13), 7: (9, 7, 12), 8: (8.5, 6.5, 11)},
        "inferior": {1: (5, 9, 12.5), 2: (5.5, 9.5, 14), 3: (7, 11, 16), 4: (7, 8.5, 14),
                     5: (7, 8, 14.5), 6: (11, 7.5, 14), 7: (10.5, 7, 13), 8: (10, 7, 11)},
    },
    "temporal": {
        "superior": {1: (6.5, 6, 10), 2: (5.1, 5.6, 11.4), 3: (7, 6.5, 13.5), 4: (7.3, 5.1, 10),
                     5: (8.2, 5.7, 11.7)},
        "inferior": {1: (4, 5, 9), 2: (4.5, 5.2, 10), 3: (5, 6, 11.5), 4: (7.7, 6, 9.8),
                     5: (9.9, 5.5, 11)},
    },
}
ALTO = {"permanente": 28.2, "temporal": 21}
MARGEN = 0.6
PROFUNDIDAD_ALERTA = 4          # > 4 mm: bolsa patológica

ROJO = colors.HexColor("#d64545")
AMBAR = colors.HexColor("#d99a00")
AZUL = colors.HexColor("#2f6fd6")
CONTORNO = colors.HexColor("#3f8f8a")
CORONA = colors.HexColor("#fbf8f1")
RAIZ = colors.HexColor("#f1e7d3")
PAUTA = colors.HexColor("#d9dee5")
TINTA = colors.HexColor("#14212e")
SUAVE = colors.HexColor("#5b6b7c")

SUPERIOR = ["18", "17", "16", "15", "14", "13", "12", "11", "21", "22", "23", "24", "25", "26", "27", "28"]
INFERIOR = ["48", "47", "46", "45", "44", "43", "42", "41", "31", "32", "33", "34", "35", "36", "37", "38"]


def _superior(code):
    return code[0] in "1256"


def _temporal(code):
    return code[0] in "5678"


def _reflejada(code):
    return code[0] in "2367"


def _medidas(code):
    tabla = MEDIDAS["temporal" if _temporal(code) else "permanente"]
    return tabla["superior" if _superior(code) else "inferior"][int(code[-1])]


def _alto(code):
    return ALTO["temporal" if _temporal(code) else "permanente"]


def _tipo(code):
    n, sup = int(code[-1]), _superior(code)
    if _temporal(code):
        if n <= 2:
            return "incisivo"
        if n == 3:
            return "canino"
        return "molarSup" if sup else ("molarInf" if n == 5 else "molarInf2")
    if n <= 2:
        return "incisivo"
    if n == 3:
        return "canino"
    if n <= 5:
        return "premolar"
    if sup:
        return "molarSup"
    return "molarInf" if n == 6 else "molarInf2"


def _perfil_corona(t, w, c, y0):
    def X(f):
        return f * w

    def Y(f):
        return y0 + f * c

    if t == "incisivo":
        return [(X(0.03), Y(0.24)), (X(0.12), Y(0.07)), (X(0.5), Y(0.02)), (X(0.88), Y(0)), (X(0.985), Y(0.1))]
    if t == "canino":
        return [(X(0.02), Y(0.4)), (X(0.2), Y(0.2)), (X(0.54), Y(0)), (X(0.84), Y(0.16)), (X(0.985), Y(0.3))]
    if t == "premolar":
        return [(X(0.02), Y(0.34)), (X(0.2), Y(0.13)), (X(0.5), Y(0)), (X(0.8), Y(0.12)), (X(0.985), Y(0.28))]
    if t in ("molarSup", "molarInf2"):
        return [(X(0.02), Y(0.3)), (X(0.12), Y(0.1)), (X(0.3), Y(0.02)), (X(0.5), Y(0.17)),
                (X(0.72), Y(0)), (X(0.9), Y(0.08)), (X(0.985), Y(0.26))]
    return [(X(0.02), Y(0.3)), (X(0.1), Y(0.11)), (X(0.2), Y(0.05)), (X(0.34), Y(0.16)),
            (X(0.5), Y(0.03)), (X(0.64), Y(0.15)), (X(0.8), Y(0)), (X(0.93), Y(0.09)), (X(0.99), Y(0.26))]


def _geometria(code):
    """Corona y raíces en el marco canónico (corona arriba, mesial a la derecha), en mm."""
    w, c, r = _medidas(code)
    t = _tipo(code)
    y0 = MARGEN
    yc = y0 + c
    caida = c * 0.12
    molar = t.startswith("molar")
    cw = w * (0.78 if molar else 0.66)
    xl, xr = (w - cw) / 2, w - (w - cw) / 2

    def lerp(a, b, f):
        return a + (b - a) * f

    oclusal = _perfil_corona(t, w, c, y0)
    primero, ultimo = oclusal[0][1], oclusal[-1][1]
    corona = [
        (xl, yc - caida), (lerp(xl, 0, 0.5), y0 + c * 0.78),
        (-0.02 * w, max(primero + c * 0.12, y0 + c * 0.36)),
        *oclusal,
        (w * 1.01, max(ultimo + c * 0.1, y0 + c * 0.3)),
        (lerp(xr, w, 0.5), y0 + c * 0.78), (xr, yc - caida),
        (lerp(xl, xr, 0.72), yc - caida * 0.3), (lerp(xl, xr, 0.5), yc), (lerp(xl, xr, 0.28), yc - caida * 0.3),
    ]
    debajo = yc - caida - 0.4

    def una_raiz(x0, x1, largo, inclinacion=-0.06):
        ancho = x1 - x0
        apx = (x0 + x1) / 2 + inclinacion * w
        return ([(x0 + 0.05, yc - caida), (x0 + ancho * 0.07, yc + largo * 0.38),
                 (apx - ancho * 0.2, yc + largo * 0.86), (apx, yc + largo),
                 (apx + ancho * 0.2, yc + largo * 0.86), (x1 - ancho * 0.09, yc + largo * 0.38),
                 (x1 - 0.05, yc - caida), ((x0 + x1) / 2, debajo)], 1)

    def dos_raices(largo, tronco, abertura):
        xm = (xl + xr) / 2
        d_apx = xl + cw * 0.14 - abertura
        m_apx = xr - cw * 0.16 + abertura * 0.6
        ft = yc + tronco
        return ([(xl + 0.05, yc - caida), (xl - abertura * 0.4, yc + largo * 0.42),
                 (d_apx - 0.8, yc + largo * 0.86), (d_apx, yc + largo * 0.95),
                 (d_apx + 1.0, yc + largo * 0.84), (xm - 0.7, ft + 1.4), (xm, ft),
                 (xm + 0.7, ft + 1.4), (m_apx - 1.0, yc + largo * 0.88), (m_apx, yc + largo),
                 (m_apx + 0.8, yc + largo * 0.9), (xr + abertura * 0.4, yc + largo * 0.42),
                 (xr - 0.05, yc - caida), (xm, debajo)], 0.9)

    temporal = _temporal(code)
    abertura = w * 0.14 if temporal else 0
    raices = []
    if t == "molarSup":
        raices.append(una_raiz(xl + cw * 0.2, xr - cw * 0.2, r, 0.02))
        raices.append(dos_raices(r * 0.86, r * (0.12 if temporal else 0.3), abertura))
    elif t in ("molarInf", "molarInf2"):
        raices.append(dos_raices(r, r * (0.1 if temporal else 0.28), abertura))
    elif t == "premolar" and _superior(code) and code[-1] == "4":
        raices.append(dos_raices(r, r * 0.55, -w * 0.08))
    else:
        raices.append(una_raiz(xl, xr, r))
    implante = (w / 2 - cw * 0.31, yc - caida, cw * 0.62, r * 0.78 + caida)
    return w, corona, raices, implante


def _marco(code):
    """Sitios de sondaje (x) y cuello (y) en la lámina, como `marcoVestibular`."""
    w, c, _ = _medidas(code)
    h = _alto(code)
    canonico = [0.8 * w, 0.5 * w, 0.2 * w]
    sitios = [(w - x if _reflejada(code) else x) + MARGEN for x in canonico]
    y = MARGEN + c
    sup = _superior(code)
    return w + 2 * MARGEN, sitios, (h - y if sup else y), (-1 if sup else 1)


def _curva(canvas, pts, tension, transformar):
    """Catmull-Rom cerrada, como `curvaCerrada` del panel, ya en coordenadas de página."""
    n = len(pts)
    p = canvas.beginPath()
    p.moveTo(*transformar(pts[0]))
    for i in range(n):
        p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6 * tension, p1[1] + (p2[1] - p0[1]) / 6 * tension)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6 * tension, p2[1] - (p3[1] - p1[1]) / 6 * tension)
        p.curveTo(*transformar(c1), *transformar(c2), *transformar(p2))
    p.close()
    return p


def _lista(valor, defecto):
    v = list(valor or [])
    return v + [defecto] * (6 - len(v))


class Periodontograma(Flowable):
    """
    Las cuatro caras (superior vestibular y palatina, inferior lingual y
    vestibular) con sus filas de sondaje y margen debajo de cada una.

    `piezas` es {código FDI: PeriodontalTooth} de una exploración.
    """

    ETIQUETA = 15 * mm
    FILA = 3.4 * mm
    HUECO = 3 * mm

    def __init__(self, piezas, ancho):
        super().__init__()
        self.piezas = piezas
        self.ancho = ancho
        self.col = (ancho - self.ETIQUETA) / 16
        # El molar más ancho (11 mm + aire) llena su columna.
        self.k = self.col / (12.4 * mm) * mm
        self.alto_cara = ALTO["permanente"] * self.k
        self.caras = [
            ("Vestibular", SUPERIOR, 0), ("Palatino", SUPERIOR, 3),
            ("Lingual", INFERIOR, 3), ("Vestibular", INFERIOR, 0),
        ]
        self.alto = (2 * self.FILA                              # códigos arriba y abajo
                     + 4 * (self.alto_cara + 2 * self.FILA)     # cara + sondaje + margen
                     + 2 * self.HUECO + 4 * mm)

    def wrap(self, *_):
        return self.ancho, self.alto

    def draw(self):
        c = self.canv
        y = self.alto
        y = self._codigos(c, y, SUPERIOR)
        for i, (nombre, codigos, base) in enumerate(self.caras):
            if i == 2:
                y -= 2 * self.HUECO + 4 * mm
                c.setStrokeColor(PAUTA)
                c.setLineWidth(0.5)
                c.setDash(2, 2)
                medio = y + self.HUECO + 2 * mm
                c.line(0, medio, self.ancho, medio)
                c.setDash()
            y = self._cara(c, y, nombre, codigos, base)
        self._codigos(c, y, INFERIOR)

    def _codigos(self, c, y, codigos):
        c.setFont("Helvetica-Bold", 6.5)
        c.setFillColor(TINTA)
        for i, code in enumerate(codigos):
            c.drawCentredString(self.ETIQUETA + (i + 0.5) * self.col, y - self.FILA + 1.1 * mm, code)
        return y - self.FILA

    def _cara(self, c, top, nombre, codigos, base):
        k, x0, alto = self.k, self.ETIQUETA, self.alto_cara
        sup = codigos is SUPERIOR

        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(TINTA)
        c.drawString(0, top - alto / 2 + 1 * mm, nombre)
        c.setFont("Helvetica", 5.5)
        c.setFillColor(SUAVE)
        c.drawString(0, top - alto / 2 - 1.8 * mm, "Superior" if sup else "Inferior")

        # Pauta de milímetros, cada 2 mm, como el papel de la ficha.
        c.setStrokeColor(PAUTA)
        c.setLineWidth(0.3)
        paso = 2 * k
        yy = top - paso
        while yy > top - alto:
            c.line(x0, yy, self.ancho, yy)
            yy -= paso
        c.setStrokeColor(colors.HexColor("#b9c2cc"))
        c.setLineWidth(0.6)
        c.line(x0 + 8 * self.col, top, x0 + 8 * self.col, top - alto)    # línea media

        tramos, actual, filas = [], [], []
        for i, code in enumerate(codigos):
            t = self.piezas.get(code)
            ancho_lamina, sitios, cuello, apical = _marco(code)
            izq = x0 + i * self.col + (self.col - ancho_lamina * k) / 2
            presente = t is None or t.is_present
            self._pieza(c, code, izq, top, ausente=not presente,
                        implante=bool(t and t.has_implant))
            if t is None or not t.is_present:
                if actual:
                    tramos.append(actual)
                actual = []
                filas.append(None)
                continue
            gm, pd = _lista(t.gingival_margin, 0), _lista(t.probing_depth, 0)
            sangra, supura = _lista(t.bleeding, False), _lista(getattr(t, "suppuration", None), False)
            puntos = []
            for j in range(3):
                g, p = gm[base + j] or 0, pd[base + j] or 0
                puntos.append({
                    "x": izq + sitios[j] * k,
                    "margen": top - (cuello + apical * g) * k,
                    "fondo": top - (cuello + apical * (g + p)) * k,
                    "pd": p, "gm": g, "sangra": bool(sangra[base + j]), "supura": bool(supura[base + j]),
                })
            puntos.sort(key=lambda q: q["x"])
            actual.extend(puntos)
            filas.append(puntos)
        if actual:
            tramos.append(actual)

        for pts in tramos:
            self._lineas(c, pts)

        y = top - alto
        y = self._fila(c, y, "Sondaje", filas, "pd")
        return self._fila(c, y, "Margen", filas, "gm")

    def _pieza(self, c, code, izq, top, ausente, implante):
        k = self.k
        w, corona, raices, fijacion = _geometria(code)
        h = _alto(code)
        cx, cy = w / 2, h / 2
        sx = -1 if _reflejada(code) else 1
        sy = -1 if _superior(code) else 1

        def T(p):
            x = cx + sx * (p[0] - cx)
            y = cy + sy * (p[1] - cy)
            return izq + (x + MARGEN) * k, top - y * k

        # Ausente: la silueta tenue, como en el panel. La transparencia va
        # DESPUÉS de cada color: setFillColor la devuelve a opaca.
        opacidad = 0.16 if ausente else 1

        def pintar(relleno):
            c.setFillColor(relleno)
            c.setStrokeColor(CONTORNO)
            c.setFillAlpha(opacidad)
            c.setStrokeAlpha(opacidad)

        c.saveState()
        c.setLineWidth(0.35)
        c.setLineJoin(1)
        if implante:
            fx, fy, fw, fh = fijacion
            a, b = T((fx, fy)), T((fx + fw, fy + fh))
            pintar(colors.HexColor("#9aa4ad"))
            c.roundRect(min(a[0], b[0]), min(a[1], b[1]), abs(b[0] - a[0]), abs(b[1] - a[1]),
                        0.8 * mm, stroke=1, fill=1)
        else:
            pintar(RAIZ)
            for pts, tension in raices:
                c.drawPath(_curva(c, pts, tension, T), stroke=1, fill=1)
        pintar(CORONA)
        c.drawPath(_curva(c, corona, 1, T), stroke=1, fill=1)
        c.restoreState()

    def _lineas(self, c, pts):
        c.saveState()
        bolsa = c.beginPath()
        bolsa.moveTo(pts[0]["x"], pts[0]["margen"])
        for p in pts[1:]:
            bolsa.lineTo(p["x"], p["margen"])
        for p in reversed(pts):
            bolsa.lineTo(p["x"], p["fondo"])
        bolsa.close()
        c.setFillColor(AZUL)
        c.setFillAlpha(0.18)
        c.drawPath(bolsa, stroke=0, fill=1)
        c.setFillAlpha(1)
        c.setLineWidth(0.9)
        c.setLineJoin(1)
        for campo, color in (("margen", ROJO), ("fondo", AZUL)):
            linea = c.beginPath()
            linea.moveTo(pts[0]["x"], pts[0][campo])
            for p in pts[1:]:
                linea.lineTo(p["x"], p[campo])
            c.setStrokeColor(color)
            c.drawPath(linea, stroke=1, fill=0)
        for p in pts:
            c.setFillColor(ROJO)
            c.circle(p["x"], p["margen"], 0.45 * mm, stroke=0, fill=1)
            # El fondo que sangra se agranda y se pinta de rojo: es la bolsa activa.
            c.setFillColor(ROJO if p["sangra"] else AZUL)
            c.circle(p["x"], p["fondo"], (0.7 if p["sangra"] else 0.45) * mm, stroke=0, fill=1)
            if p["supura"]:
                c.setStrokeColor(AMBAR)
                c.setLineWidth(0.7)
                c.circle(p["x"], p["fondo"], 1.15 * mm, stroke=1, fill=0)
        c.restoreState()

    def _fila(self, c, top, nombre, filas, campo):
        c.setFont("Helvetica", 5.5)
        c.setFillColor(SUAVE)
        c.drawString(0, top - self.FILA + 1.1 * mm, nombre)
        c.setStrokeColor(PAUTA)
        c.setLineWidth(0.3)
        c.line(self.ETIQUETA, top - self.FILA, self.ancho, top - self.FILA)
        for pts in filas:
            if not pts:
                continue
            for p in pts:
                alerta = campo == "pd" and p["pd"] > PROFUNDIDAD_ALERTA
                c.setFont("Helvetica-Bold" if alerta else "Helvetica", 5.5)
                c.setFillColor(ROJO if alerta else TINTA)
                c.drawCentredString(p["x"], top - self.FILA + 1.1 * mm, str(p[campo]))
        return top - self.FILA


def resumen(piezas):
    """Cifras para leer el periodontograma de un vistazo."""
    sitios = sangran = supuran = placa = bolsas = 0
    suma = suma_nic = 0
    for t in piezas.values():
        if not t.is_present:
            continue
        pd, gm = _lista(t.probing_depth, 0), _lista(t.gingival_margin, 0)
        sg, su, pl = (_lista(t.bleeding, False), _lista(getattr(t, "suppuration", None), False),
                      _lista(t.plaque, False))
        for i in range(6):
            sitios += 1
            suma += pd[i] or 0
            suma_nic += (pd[i] or 0) + (gm[i] or 0)
            sangran += 1 if sg[i] else 0
            supuran += 1 if su[i] else 0
            placa += 1 if pl[i] else 0
            bolsas += 1 if (pd[i] or 0) > PROFUNDIDAD_ALERTA else 0
    if not sitios:
        return None
    return {
        "sondaje_medio": round(suma / sitios, 1),
        "nic_medio": round(suma_nic / sitios, 1),
        "sangrado": round(100 * sangran / sitios),
        "supuracion": round(100 * supuran / sitios),
        "placa": round(100 * placa / sitios),
        "bolsas": bolsas,
        "sitios": sitios,
    }


# Componentes del PDF propio del periodontograma (?incluir=…).
COMPONENTES = ("diagrama", "piezas", "resumen", "notas")

PRONOSTICOS = {"bueno": "Bueno", "reservado": "Reservado", "malo": "Malo", "imposible": "Imposible"}


def _tabla_piezas(piezas, style, celda):
    """Lo que es de la pieza entera: implante, movilidad, furcas, encía y pronóstico."""
    from reportlab.platypus import Table

    from apps.clinical.pdf_utils import _p

    filas = []
    for code in SUPERIOR + INFERIOR:
        t = piezas.get(code)
        if t is None:
            continue
        if not t.is_present:
            filas.append([code, "Ausente", "—", "—", "—", "—", "—"])
            continue
        filas.append([
            code, "Implante" if t.has_implant else "Natural", str(t.mobility or 0),
            str(t.furcation_buccal or 0), str(t.furcation_lingual or 0),
            f"{t.gum_width} mm" if t.gum_width else "—",
            PRONOSTICOS.get(getattr(t, "prognosis", ""), "—"),
        ])
    cabecera = ["Pieza", "Tipo", "Movilidad", "Furca V", "Furca P/L", "Encía queratinizada", "Pronóstico"]
    anchos = [0.09, 0.14, 0.12, 0.11, 0.12, 0.22, 0.2]
    datos = [cabecera] + [[_p(v, celda) for v in f] for f in filas]
    t = Table(datos, colWidths=[style.content_width * a for a in anchos], repeatRows=1)
    t.setStyle(style.table_style())
    return t


def generar_pdf(exam, style, clinic, incluir=None, _total=None):
    """El periodontograma de una exploración como documento propio."""
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import KeepTogether, Paragraph, Spacer

    from apps.clinical.pdf_utils import _base_styles, _construir, _p
    from apps.common.document_style import fecha_documento

    incluir = set(COMPONENTES) if incluir is None else set(incluir)
    styles = _base_styles(style)
    celda = ParagraphStyle("celda", parent=styles["Normal"], fontSize=style.size - 1,
                           leading=(style.size - 1) * 1.3)
    patient = exam.patient
    piezas = {t.tooth_code: t for t in exam.teeth.all()}
    autor = (exam.created_by.full_name or exam.created_by.email) if exam.created_by else None

    story = list(style.header_flowables(clinic=clinic))
    story += style.title_flowables(
        "Periodontograma", subtitle=patient.full_name,
        meta=[("Identificación", patient.national_id), ("Exploración", fecha_documento(exam.date)),
              ("Registró", autor)],
    )
    numero = 0

    def seccion(titulo):
        nonlocal numero
        numero += 1
        story.append(style.section_flowable(titulo, numero))

    datos = resumen(piezas)
    if "resumen" in incluir and datos:
        seccion("Índices")
        story.append(style.fields_table([
            [("Sondaje medio", f"{datos['sondaje_medio']} mm"), ("Nivel de inserción medio", f"{datos['nic_medio']} mm"),
             ("Sitios de más de 4 mm", str(datos["bolsas"]))],
            [("Sangrado al sondaje", f"{datos['sangrado']} %"), ("Supuración", f"{datos['supuracion']} %"),
             ("Placa", f"{datos['placa']} %")],
        ]))
    if "diagrama" in incluir and piezas:
        seccion("Diagrama")
        leyenda = ('<font color="#d64545"><b>——</b></font> Margen gingival &nbsp;&nbsp; '
                   '<font color="#2f6fd6"><b>——</b></font> Fondo de bolsa &nbsp;&nbsp; '
                   '<font backColor="#d5e2f7">&nbsp;&nbsp;&nbsp;&nbsp;</font> Bolsa &nbsp;&nbsp; '
                   '<font color="#d64545"><b>•</b></font> Sangrado &nbsp;&nbsp; '
                   '<font color="#d99a00"><b>o</b></font> Supuración &nbsp;&nbsp; '
                   'En rojo, sondajes de más de 4 mm.')
        story.append(KeepTogether([Periodontograma(piezas, style.content_width), Spacer(1, 3),
                                   Paragraph(leyenda, styles["Small"])]))
    if "piezas" in incluir and piezas:
        seccion("Datos por pieza")
        story.append(_tabla_piezas(piezas, style, celda))
    if "notas" in incluir and exam.notes:
        seccion("Observaciones")
        story.append(_p(exam.notes, styles["Normal"]))

    pdf, paginas = _construir(style, clinic, "Periodontograma", story, _total)
    if _total is None:
        return generar_pdf(exam, style, clinic, incluir, _total=paginas)
    return pdf
