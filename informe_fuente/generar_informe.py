"""Genera Grupo<N>_AE4_U3.pdf a partir de config.json, los scripts, las salidas reales y las metricas medidas.
Uso:  python informe_fuente/generar_informe.py      (requiere reportlab y Pillow)
Las cifras se leen de resultados/b1_ingesta.json y resultados/metricas.json: si se vuelve a medir, el informe cambia solo.
Los fragmentos de codigo se extraen de los scripts, asi el informe no se desincroniza del repositorio."""
import json, os
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle,
                                Preformatted, KeepTogether, CondPageBreak)
from PIL import Image as PILImage

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
cfg = json.load(open(os.path.join(BASE, "informe_fuente", "config.json"), encoding="utf-8"))
SALIDA = os.path.join(BASE, f"Grupo{cfg['grupo']}_{cfg['actividad']}.pdf")
b1 = json.load(open(os.path.join(BASE, "resultados", "b1_ingesta.json"), encoding="utf-8"))
MET = json.load(open(os.path.join(BASE, "resultados", "metricas.json"), encoding="utf-8"))

F = r"C:\Windows\Fonts"
pdfmetrics.registerFont(TTFont("Body", os.path.join(F, "arial.ttf")))
pdfmetrics.registerFont(TTFont("Body-B", os.path.join(F, "arialbd.ttf")))
pdfmetrics.registerFont(TTFont("Body-I", os.path.join(F, "ariali.ttf")))
pdfmetrics.registerFont(TTFont("Mono", os.path.join(F, "consola.ttf")))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-B", italic="Body-I", boldItalic="Body-B")

AZUL, GRIS = colors.HexColor("#1f4e8c"), colors.HexColor("#f2f4f8")
s_body = ParagraphStyle("b", fontName="Body", fontSize=10, leading=14, spaceAfter=6, alignment=4)
s_h1 = ParagraphStyle("h1", fontName="Body-B", fontSize=16, leading=20, textColor=AZUL, spaceBefore=4, spaceAfter=8)
s_h2 = ParagraphStyle("h2", fontName="Body-B", fontSize=12, leading=16, textColor=AZUL, spaceBefore=8, spaceAfter=4)
s_cap = ParagraphStyle("c", fontName="Body-I", fontSize=8.5, leading=11, textColor=colors.HexColor("#555555"), spaceAfter=8)
s_cell = ParagraphStyle("t", fontName="Body", fontSize=8.5, leading=11)
s_cellb = ParagraphStyle("tb", fontName="Body-B", fontSize=8.5, leading=11, textColor=colors.white)
s_code = ParagraphStyle("code", fontName="Mono", fontSize=7.2, leading=9, backColor=GRIS, borderPadding=5, spaceAfter=8, leftIndent=4)
s_bul = ParagraphStyle("bul", parent=s_body, leftIndent=14, bulletIndent=2, spaceAfter=3, alignment=0)
s_box = ParagraphStyle("box", parent=s_body, backColor=colors.HexColor("#eaf2fb"), borderColor=AZUL, borderWidth=0.6,
                       borderPadding=6, spaceBefore=4, spaceAfter=10, alignment=0)

def P(t, st=s_body): return Paragraph(t, st)
def H1(t): return Paragraph(t, s_h1)
def H2(t): return Paragraph(t, s_h2)
def B(t): return Paragraph(t, s_bul, bulletText="•")
def M(t): return f"<font name='Mono'>{t}</font>"
def leer(*ruta): return open(os.path.join(BASE, *ruta), encoding="utf-8").read()
def num(x, d=0): return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def code(t, max_ancho=118):
    out = []
    for l in t.strip("\n").splitlines():
        while len(l) > max_ancho:
            corte = l.rfind(" ", 0, max_ancho); corte = corte if corte > 40 else max_ancho
            out.append(l[:corte]); l = "      " + l[corte:].lstrip()
        out.append(l)
    return Preformatted("\n".join(out), s_code)

def entre(texto, ini, fin=None):
    i = texto.index(ini); i = texto.rfind("\n", 0, i) + 1
    j = texto.index(fin, i + len(ini)) if fin else len(texto)
    j = texto.rfind("\n", 0, j) + 1 if fin else j
    return texto[i:j].rstrip()

def img(nombre, ancho=17 * cm, tope=19 * cm):
    ruta = os.path.join(BASE, "capturas", nombre); w, h = PILImage.open(ruta).size
    esc = min(ancho / w, tope / h); return Image(ruta, width=w * esc, height=h * esc)

def tabla(filas, anchos, cab=True):
    data = [[Paragraph(str(c), s_cellb if (cab and i == 0) else s_cell) for c in f] for i, f in enumerate(filas)]
    t = Table(data, colWidths=anchos, repeatRows=1 if cab else 0)
    est = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c2d3")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if cab: est += [("BACKGROUND", (0, 0), (-1, 0), AZUL)] + [("BACKGROUND", (0, i), (-1, i), GRIS) for i in range(2, len(filas), 2)]
    t.setStyle(TableStyle(est)); return t

nfig = [0]
def fig(nombre, txt, tope=19 * cm):
    nfig[0] += 1
    return KeepTogether([img(nombre, tope=tope), P(f"Figura {nfig[0]}. {txt}", s_cap)])

def enlace(url, pendiente):
    return f"<link href='{url}' color='#1f4e8c'><u>{url}</u></link>" if url else f"<font color='#b03a2e'>{pendiente}</font>"

def met(prueba, clave):
    return next(f for f in MET if f["prueba"] == prueba and clave in f["motor"])

AUTORES = [i["nombre"] for i in cfg["integrantes"]]
INDIVIDUAL = len(AUTORES) == 1

def pie(c, d):
    c.saveState(); c.setFont("Body", 8); c.setFillColor(colors.HexColor("#666666"))
    c.drawString(2 * cm, 1.2 * cm, f"{' · '.join(AUTORES)} · AE4-U3 · Bases de Datos II · 2026-2")
    c.drawRightString(letter[0] - 2 * cm, 1.2 * cm, f"Página {d.page}"); c.restoreState()

sql = leer("scripts", "01_postgres_esquema.sql")
mjs = leer("scripts", "03_mongo_esquema.js")
ing = leer("scripts", "04_ingesta_telemetria.py")
ana = leer("scripts", "05_analisis_comparativo.py")
carga = leer("scripts", "02_cargar_postgres.py")

# cifras medidas
mg1, pg1 = met("B1", "MongoDB"), met("B1", "PostgreSQL")
BM = {p: (met(p, "MongoDB" if p != "B5" else "Hibrido"), met(p, "PostgreSQL" if p != "B5" else "Solo")) for p in ("B2", "B3", "B4", "B5")}
x_ing = b1["mongo_lect_s"] / b1["pg_lect_s"]
x_disco = b1["pg_mb_disco"] / b1["mongo_mb_disco"]
x_b4 = BM["B4"][1]["mediana_ms"] / BM["B4"][0]["mediana_ms"]
def ms(f): return num(f["mediana_ms"], 1) + " ms"

S = []
# =================================================================== Portada
S += [Spacer(1, 2.4 * cm),
      Paragraph("Tarea. Construyendo y comparando ecosistemas híbridos",
                ParagraphStyle("t", fontName="Body-B", fontSize=22, leading=28, textColor=AZUL)),
      Spacer(1, .4 * cm),
      Paragraph("Historia Clínica Electrónica Básica — Subsistema de Hospitalización<br/>Gobernación de Antioquia · "
                "PostgreSQL (ACID) + MongoDB (BASE) para telemetría clínica", ParagraphStyle("t2", fontName="Body", fontSize=14, leading=19)),
      Spacer(1, 1.0 * cm),
      tabla([["Asignatura", "Bases de Datos II (G101) — Tecnología en Desarrollo de Software"],
             ["Profesora", "Oralia Cortés Grajales"],
             ["Actividad", "AE4 · Unidad 3 · Informe técnico"],
             ["Modalidad", cfg["modalidad"]],
             ["Autor" if INDIVIDUAL else "Integrantes", "<br/>".join(AUTORES)],
             ["SGBD", "PostgreSQL 17.11 (Docker) + MongoDB Community 8.3.7 (colección time series)"],
             ["Bases de datos", "hce_hibrido (esquema hce) y hce_telemetria"],
             ["Repositorio", enlace(cfg.get("repositorio_url"), "Pendiente: agregar enlace en config.json")],
             ["Video", enlace(cfg.get("video_url"), "Pendiente: agregar enlace en config.json")],
             ["Fecha", cfg["fecha"]]], [3.6 * cm, 13.4 * cm], cab=False),
      Spacer(1, .8 * cm),
      P("<b>Contenido:</b> 1. Justificación de la arquitectura híbrida · 2. División ACID vs. BASE · 3. Diagrama de "
        "arquitectura · 4. Implementación · 5. Operaciones y análisis comparativo · 6. Integración de IA · 7. Reflexión "
        "técnica y ética · 8. Repositorio y video · 9. Conclusiones."),
      P("<b>Resumen.</b> Se separó el subsistema de hospitalización de la Unidad 3 en dos capas: PostgreSQL guarda la identidad "
        "del paciente, los profesionales, los catálogos, las camas, las hospitalizaciones y el registro de dispositivos; MongoDB "
        f"recibe {num(b1['lecturas'])} lecturas de {b1['por_tipo'].__len__()} tipos de dispositivo clínico y {b1['teleconsultas']} "
        f"teleconsultas. La misma telemetría se cargó también en PostgreSQL (JSONB) para comparar: MongoDB ingirió {num(x_ing, 1)} "
        f"veces más rápido, ocupó {num(x_disco, 0)} veces menos disco y resolvió el análisis de todo el hospital (B4) {num(x_b4, 1)} "
        "veces más rápido; PostgreSQL fue igual o más rápido en consultas puntuales y fue el único que garantizó que una cama no "
        "se asignara dos veces."),
      P("<b>Nota:</b> todos los datos son <b>ficticios</b>. Las salidas y cifras son copias de la ejecución real de los scripts "
        "(carpeta " + M("resultados/") + "); el PDF las lee de ahí."),
      PageBreak()]

# =================================================================== 1. Justificación
S += [H1("1. Justificación de la arquitectura híbrida"),
      P("En la Unidad 3 la HCE de hospitalización vivía completa en MongoDB: un documento por episodio con diagnósticos, "
        "evolución y signos vitales tomados a mano (unas tres tomas al día). El reto de esta unidad agrega un volumen de otro "
        "orden: <b>monitores, oxímetros portátiles, glucómetros continuos y bombas de infusión</b> que reportan cada 1 a 5 "
        "minutos, más las teleconsultas posteriores al alta. Un solo paciente de Medicina Interna genera en un día "
        "1.440 lecturas de monitor y 720 de oxímetro, frente a 3 tomas manuales."),
      P("Ningún motor resuelve bien las dos cosas a la vez:"),
      B("<b>La identidad y la gestión de camas</b> exigen consistencia fuerte: dos pacientes en la misma cama, un documento "
        "duplicado o un dispositivo asignado al paciente equivocado son errores clínicos. Eso pide claves foráneas, unicidad y "
        "transacciones: un SGBD relacional ACID."),
      B("<b>La telemetría</b> es lo contrario: se escribe sin parar, nunca se modifica, cada tipo de sensor trae campos "
        "distintos, crece sin límite y tolera consistencia eventual (si una lectura llega 2 segundos tarde al tablero no pasa "
        "nada). Eso pide ingesta rápida, esquema flexible y escalado horizontal: un motor NoSQL documental BASE."),
      P("Siguiendo el principio de <b>persistencia políglota</b> del libro del curso <i>Arquitecturas NoSQL e híbridas</i>, cada "
        "dato va al motor que mejor lo trata, y la aplicación los une por una llave puente. El insumo <i>Integración de "
        "PostgreSQL con NoSQL para IoT y big data</i> plantea la otra opción: guardar los sensores en PostgreSQL con " + M("JSONB") +
        " e índice GIN. Este trabajo implementa <b>las dos</b> y las mide con los mismos datos, para decidir con evidencia y "
        "no por preferencia."),
      P("<b>Continuidad con el proyecto.</b> Los datos de PostgreSQL son los de la Unidad 3 (exportados a " + M("datos_origen/") +
        "): 25 pacientes, 9 profesionales, 30 camas y 36 hospitalizaciones, con los mismos identificadores " +
        M("PAC-…") + ", " + M("HOSP-2026-…") + " y " + M("MI-201") + ". La telemetría se generó a partir de los signos vitales "
        "reales de cada episodio, de modo que el oxímetro del paciente con neumonía (HOSP-2026-0029, puntaje NEWS2 de 11 en la U3) "
        "muestra la misma SpO<sub>2</sub> de 87–88 % que su historia.", s_box),
      PageBreak()]

# =================================================================== 2. ACID vs BASE
S += [H1("2. División ACID vs. BASE"),
      P("La tabla de la página 1 del documento de arquitecturas híbridas del curso resume los dos modelos. Se completa con lo que "
        "significó cada propiedad en esta implementación:"),
      tabla([["Propiedad", "ACID (PostgreSQL)", "BASE (MongoDB)", "En este proyecto"],
             ["Consistencia", "Fuerte", "Eventual", "Admisión, alta y asignación de dispositivo deben verse igual para todos al instante. "
              "Una lectura de SpO<sub>2</sub> puede llegar unos segundos tarde."],
             ["Disponibilidad", "Limitada (prioriza consistencia)", "Alta", "Si el registro clínico no puede confirmar una admisión, es "
              "mejor rechazarla. Los sensores no pueden dejar de escribir porque un nodo esté ocupado."],
             ["Aplicación", "Sistema de registro (SoR)", "Sistema de información / análisis (SoI)", "PostgreSQL es la fuente de verdad del "
              "paciente; MongoDB alimenta tableros y analítica."],
             ["Esquema", "Fijo, con CHECK y FK", "Flexible por documento", "Cada sensor trae campos distintos (PI y batería en el "
              "oxímetro, TA en el monitor, tendencia en el CGM, eventos en la bomba)."],
             ["Escalado", "Vertical (y particiones)", "Horizontal (sharding)", "La telemetría crece sin límite; los datos maestros, no."]],
            [2.6 * cm, 3.3 * cm, 3.3 * cm, 7.8 * cm]),
      Spacer(1, 6),
      H2("2.1 Qué dato vive en cada capa y por qué"),
      tabla([["Dato", "Capa", "Justificación"],
             ["Paciente (documento, nombres, nacimiento, EPS), alergias", "ACID", "Identidad única (" + M("UNIQUE(tipo_documento, documento)") +
              "), dato sensible (Ley 1581/2012). Se corrige rara vez y debe ser una sola verdad."],
             ["Profesionales, CIE-10, medicamentos", "ACID", "Datos maestros compartidos, referenciados con FK."],
             ["Camas y hospitalizaciones", "ACID", "Regla de negocio crítica: " + M("ux_cama_activa") + " y " + M("ux_paciente_activo") +
              " (índices únicos parciales) impiden dos episodios activos en la misma cama o para el mismo paciente."],
             ["Dispositivo y asignación a un episodio", "ACID", "Es el <b>puente</b>: dice de quién es cada lectura. " +
              M("ux_dispositivo_vigente") + " impide que un oxímetro quede asignado a dos pacientes."],
             ["Lecturas de monitor, oxímetro, CGM, eventos de bomba", "BASE", "Alto volumen, solo inserción, campos variables, "
              "consulta por tiempo. Colección <b>time series</b> con retención de 2 años."],
             ["Teleconsultas post-alta", "BASE", "Semiestructuradas: adjuntos, signos reportados por el paciente o reconsulta "
              "aparecen solo en algunas. Validador " + M("$jsonSchema") + " para lo mínimo."],
             ["Vista " + M("v_episodio_analitico"), "ACID → app", "Lo único que se cruza con la telemetría: edad, sexo, subregión y "
              "episodio. <b>Sin nombre ni documento</b>."]],
            [5.2 * cm, 1.8 * cm, 10 * cm]),
      Spacer(1, 6),
      P("<b>La llave puente.</b> Cada lectura en MongoDB guarda " + M("meta: {dispositivo_id, tipo, hosp}") + ". El " +
        M("hosp") + " es el " + M("hospitalizacion_id") + " (un seudónimo del episodio): con él la telemetría se puede analizar "
        "sin saber quién es el paciente. Para llegar a la identidad hay que pasar por PostgreSQL, que es donde están los permisos "
        "y la auditoría. No hay clave foránea entre motores: la ingesta solo acepta dispositivos con asignación vigente.", s_box),
      PageBreak()]

# =================================================================== 3. Diagrama
S += [H1("3. Diagrama de arquitectura"),
      fig("00_diagrama_arquitectura.png", "Arquitectura híbrida. Los usuarios clínicos escriben en la capa ACID; los dispositivos "
          "escriben en la capa BASE a través de la ingesta, que consulta en PostgreSQL a qué episodio pertenece cada dispositivo. "
          "La aplicación une las dos capas por " + M("hospitalizacion_id") + ".", tope=12 * cm),
      H2("3.1 Flujos"),
      tabla([["Flujo", "Motor", "Garantía"],
             ["Admisión: reservar cama y crear hospitalización", "PostgreSQL, una transacción", "Todo o nada (probado en T1)"],
             ["Asignar oxímetro a un episodio", "PostgreSQL", M("ux_dispositivo_vigente") + ": un dispositivo, un episodio vigente"],
             ["Lectura de sensor cada 60–300 s", "MongoDB " + M("insert_many") + " por lotes", "Alta disponibilidad; lecturas fuera de rango descartadas"],
             ["Tablero de pacientes activos", "PG (episodios) + Mongo (resumen 6 h)", "Unión en la aplicación (B5)"],
             ["Analítica de todo el hospital", "MongoDB (agregación sobre buckets)", "Consistencia eventual aceptable"]],
            [6 * cm, 5.2 * cm, 5.8 * cm]),
      PageBreak()]

# =================================================================== 4. Implementación
S += [H1("4. Implementación"),
      H2("4.1 Capa ACID: PostgreSQL 17.11"),
      P("El esquema " + M("hce") + " tiene 9 tablas de la arquitectura y una de comparación (" + M("telemetria_jsonb") +
        "). Las restricciones hacen el trabajo que en MongoDB tocaba a la aplicación:"),
      code(entre(sql, "CREATE TABLE hospitalizacion (", "-- ---------- Registro de dispositivos") + "\n" +
           entre(sql, "CREATE TABLE asignacion_dispositivo (", "-- ---------- Vista seudonimizada")),
      code(entre(sql, "CREATE VIEW v_episodio_analitico AS", "-- ---------- Tabla SOLO")),
      fig("01_postgres_esquema.png", "Ejecución de 01_postgres_esquema.sql: 10 tablas y 19 índices.", tope=13 * cm),
      P("La carga (" + M("02_cargar_postgres.py") + ") lee los JSON exportados de la U3 y los inserta en <b>una sola "
        "transacción</b>. Cada episodio recibe los dispositivos que su servicio y diagnóstico justifican: oxímetro para todos, "
        "monitor en Medicina Interna y UCI, glucómetro continuo si tiene diabetes (E11) y bomba de infusión en UCI o dengue grave."),
      code(entre(carga, "    for h in hosp:\n        dxs", "    cur.executemany(\"INSERT INTO dispositivo")),
      H2("4.2 Capa BASE: MongoDB 8.3.7"),
      code(entre(mjs, 't.createCollection("telemetria"', 't.createCollection("teleconsultas"')),
      P("Una colección <b>time series</b> agrupa internamente las lecturas del mismo " + M("meta") + " en <i>buckets</i> por "
        f"ventana de tiempo y las comprime: las {num(b1['lecturas'])} lecturas quedaron en {num(b1['mongo_buckets'])} buckets. "
        "<b>Limitación encontrada:</b> MongoDB no permite validadores " + M("$jsonSchema") + " en este tipo de colección, así que "
        "los rangos fisiológicos se validan en la ingesta."),
      fig("02_carga_y_esquema_mongo.png", "Carga de la capa ACID (conteos por tabla) y creación de la capa BASE.", tope=9 * cm),
      H2("4.3 Ingesta masiva simulada"),
      P("El script " + M("04_ingesta_telemetria.py") + " recorre cada asignación de dispositivo y genera una lectura por "
        "periodo, <b>interpolando entre las tomas reales de signos vitales del episodio</b> con un ruido determinista (semilla "
        "866: se obtienen siempre los mismos datos). Las bombas emiten eventos (cambio de velocidad, bolo, alarma de oclusión) y "
        "el glucómetro sigue a un diabético descompensado que se controla. Se inyectan artefactos de sensor (FC = 400) para "
        "probar la validación."),
      code(entre(ing, "def valida(l):", "lecturas, descartadas = [], 0") + "\n" +
           entre(ing, "# ---------------- B1: ingesta en MongoDB", "# ---------------- B1: misma ingesta en PostgreSQL")),
      fig("03_ingesta_masiva.png", f"Ingesta: {num(b1['lecturas'])} lecturas válidas, {b1['descartadas']} descartadas por fuera "
          "de rango, mismo conteo en los dos motores.", tope=4 * cm),
      tabla([["Tipo de dispositivo", "Periodo", "Lecturas", "Campos propios"],
             ["Monitor multiparámetro", "60 s", num(b1["por_tipo"].get("MONITOR_MULTIPARAMETRO", 0)), "fc, fr, spo2, ta{s,d}, temp"],
             ["Oxímetro portátil", "120 s", num(b1["por_tipo"].get("OXIMETRO_WEARABLE", 0)), "spo2, fc, pi, bateria, movimiento"],
             ["Glucómetro continuo (CGM)", "300 s", num(b1["por_tipo"].get("GLUCOMETRO_CGM", 0)), "glucosa, tendencia"],
             ["Bomba de infusión", "por evento", num(b1["por_tipo"].get("BOMBA_INFUSION", 0)), "evento, ml_h, medicamento_id, resuelta_en_s"]],
            [5 * cm, 2.2 * cm, 2.6 * cm, 7.2 * cm]),
      CondPageBreak(12 * cm)]

# =================================================================== 5. Comparativo
S += [H1("5. Operaciones y análisis comparativo"),
      P("<b>Método.</b> Las dos capas corren en el mismo portátil (Windows 11; PostgreSQL en Docker, MongoDB nativo). Cada "
        "consulta se ejecuta 3 veces para calentar caché y 15 veces medidas; se reporta la <b>mediana</b> y el <b>percentil "
        "95</b>. Antes de comparar tiempos se comprueba que <b>los dos motores devuelven exactamente el mismo resultado</b>. La "
        "telemetría en PostgreSQL usa " + M("JSONB") + " con índice " + M("(dispositivo_id, ts)") + " y GIN " +
        M("jsonb_path_ops") + ", como propone el insumo del curso."),
      tabla([["Prueba", "Operación", "MongoDB", "PostgreSQL", "Más rápido"],
             ["B1", "Ingesta completa, lecturas/s (" + num(b1["lecturas"]) + ")", num(b1["mongo_lect_s"]), num(b1["pg_lect_s"]),
              f"MongoDB ×{num(x_ing, 1)}"],
             ["B1", "Ingesta repetida 50.000 lecturas ×5, lecturas/s", num(mg1["lecturas_s"]), num(pg1["lecturas_s"]),
              f"MongoDB ×{num(mg1['lecturas_s'] / pg1['lecturas_s'], 1)}"],
             ["—", "Disco de la telemetría (datos + índices)", num(b1["mongo_mb_disco"], 1) + " MB", num(b1["pg_mb_disco"], 1) + " MB",
              f"MongoDB ×{num(x_disco, 0)} menos"]] +
            [[p, d, ms(BM[p][0]), ms(BM[p][1]),
              ("MongoDB" if p != "B5" else "Híbrido") + f" ×{num(BM[p][1]['mediana_ms'] / BM[p][0]['mediana_ms'], 1)}"
              if BM[p][0]["mediana_ms"] < BM[p][1]["mediana_ms"] else
              ("PostgreSQL" if p != "B5" else "Solo PostgreSQL") + f" ×{num(BM[p][0]['mediana_ms'] / BM[p][1]['mediana_ms'], 1)}"]
             for p, d in (("B2", "Última lectura de un dispositivo (mediana)"), ("B3", "Promedio horario de un episodio, 24 h"),
                          ("B4", "Desaturación SpO<sub>2</sub> &lt; 90 % en todo el hospital, 7 días"),
                          ("B5", "Tablero de activos: híbrido vs. todo en PostgreSQL"))],
            [1.6 * cm, 6.7 * cm, 2.6 * cm, 2.6 * cm, 3.5 * cm]),
      Spacer(1, 6),
      fig("20_grafica_ingesta_disco.png", "Ingesta completa y espacio en disco de la misma telemetría.", tope=6.5 * cm),
      fig("21_grafica_latencia.png", "Latencia de consulta (escala logarítmica): mediana y p95 de 15 ejecuciones.", tope=7 * cm),
      H2("5.1 B1. Ingesta masiva"),
      P("MongoDB inserta lotes de 5.000 documentos en <i>buckets</i> comprimidos, sin claves primarias secuenciales ni índice "
        "GIN que mantener. PostgreSQL, en cambio, escribe cada fila con su encabezado, repite los nombres de las claves del JSON "
        "en cada fila y actualiza tres índices (llave primaria, " + M("(dispositivo_id, ts)") + " y GIN). Por eso la diferencia "
        "en disco es todavía mayor que la de velocidad."),
      fig("10_prueba_B1.png", "B1 repetida: 5 ingestas de 50.000 lecturas en colecciones/tablas temporales.", tope=3 * cm),
      H2("5.2 B2 y B3. Consultas puntuales sobre un dispositivo o un episodio"),
      code(entre(ana, "r = medir(\"B2\", \"MongoDB\"", "r = medir(\"B2\", \"PostgreSQL\"") + "\n" + entre(ana, "def b2_pg():", "r = medir(\"B2\", \"PostgreSQL\"") +
           "\n" + entre(ana, "P3 = [", "rm = medir(\"B3\"") + "\n" + entre(ana, "SQL3 = ", "def b3_pg()")),
      P("Con índice sobre " + M("(dispositivo, ts)") + " las dos consultas leen pocas filas y los motores quedan cerca: aquí no "
        "hay ventaja clara de ninguno, y PostgreSQL puede ganar porque no tiene que descomprimir un bucket. B3 obliga a "
        "PostgreSQL a hacer un JOIN con " + M("asignacion_dispositivo") + " para llegar del episodio al dispositivo, mientras "
        "MongoDB filtra directamente por " + M("meta.hosp") + "."),
      fig("11_prueba_B2.png", "B2: la misma última lectura del monitor del paciente con neumonía en los dos motores.", tope=3.6 * cm),
      fig("12_prueba_B3.png", "B3: 24 horas con promedios idénticos en los dos motores.", tope=4.5 * cm),
      H2("5.3 B4. Análisis de todo el hospital: la diferencia grande"),
      code(entre(ana, "P4 = [", "rm = medir(\"B4\"") + "\n" + entre(ana, "SQL4 = ", "def b4_pg()")),
      P(f"Esta consulta recorre la semana completa de telemetría. MongoDB fue {num(x_b4, 1)} veces más rápido. El plan de "
        "ejecución de PostgreSQL explica por qué: hace <b>Seq Scan</b> de toda la tabla. El índice GIN " + M("jsonb_path_ops") +
        " del insumo solo acelera búsquedas de contención (" + M("lectura @> '{\"spo2\": 88}'") + "), no rangos como " +
        M("(lectura->>'spo2')::int &lt; 90") + ". Para acelerarlo en PostgreSQL habría que crear un índice de expresión por "
        "cada atributo o convertir los campos en columnas, y se perdería parte de la flexibilidad que justificaba el JSONB."),
      fig("13_prueba_B4.png", "B4: tres episodios con desaturación, mismo resultado y plan de ejecución de PostgreSQL.", tope=5 * cm),
      H2("5.4 B5. Consulta híbrida: tablero de pacientes activos"),
      code(entre(ana, "def b5_hibrido():", "SQL5 = ")),
      P("La versión híbrida hace dos consultas pequeñas y une en memoria: una a la vista seudonimizada de PostgreSQL y una "
        "agregación en MongoDB filtrada por los " + M("hospitalizacion_id") + " activos. La versión solo-PostgreSQL usa un " +
        M("LEFT JOIN LATERAL") + " sobre la tabla JSONB. Los tiempos son del mismo orden: unir dos motores no penaliza la "
        "latencia de un tablero, pero sí suma complejidad (dos conexiones, dos lenguajes de consulta y código de unión)."),
      fig("14_prueba_B5.png", "B5: tablero de los 7 pacientes activos con su telemetría de 6 horas; las dos versiones coinciden.", tope=6 * cm),
      H2("5.5 T1. Atomicidad: lo que solo garantiza la capa ACID"),
      code(entre(ana, "cur.execute(\"SELECT count(*) FROM hospitalizacion\"); antes", "# ------------------------------------------------------------------ salida")),
      P("Se intentó admitir a un paciente en la cama MI-201, ocupada por HOSP-2026-0029, y en la misma transacción asignarle un "
        "dispositivo. PostgreSQL rechazó la admisión por " + M("ux_cama_activa") + " (código 23505) y deshizo <b>toda</b> la "
        "transacción. En MongoDB, un lote de 5 lecturas con una inválida guardó las 4 válidas: escritura parcial. Para "
        "telemetría eso es lo deseable (no se pierden 4 lecturas buenas por una mala); para una admisión sería inaceptable."),
      fig("15_prueba_T1.png", "T1: ROLLBACK completo en PostgreSQL y escritura parcial en MongoDB.", tope=3.4 * cm),
      CondPageBreak(8 * cm),
      H2("5.6 Análisis cualitativo: flexibilidad, complejidad y escalabilidad"),
      tabla([["Criterio", "PostgreSQL (ACID)", "MongoDB (BASE)", "Arquitectura híbrida"],
             ["Flexibilidad: llega un capnógrafo con " + M("etco2"),
              "Con columnas: ALTER TABLE y migración. Con JSONB: se inserta, pero cada consulta necesita cast y un índice de "
              "expresión nuevo.", "Se inserta el documento con el campo nuevo; nada que cambiar en la colección.",
              "Solo se registra el dispositivo en PostgreSQL (una fila)."],
             ["Integridad", "FK, UNIQUE, CHECK y transacciones: el motor protege el dato.",
              "Sin validador en time series: la ingesta debe validar (72 lecturas descartadas).",
              "Reglas críticas en PG; validación de rangos en el código de ingesta."],
             ["Complejidad de consulta", "Un SQL para todo (B5 en una sentencia), pero JSONB requiere casts y LATERAL.",
              "Pipelines legibles para series de tiempo ($dateTrunc, $group).",
              "Dos lenguajes, dos conexiones y una unión en la aplicación."],
             ["Escalabilidad", "Vertical; particionar " + M("telemetria") + " por mes ayudaría, pero el disco crece "
              f"{num(x_disco, 0)} veces más rápido.", "Horizontal: sharding por " + M("meta.dispositivo_id") +
              ", compresión y TTL de 2 años nativos.", "Cada capa escala según su carga: la maestra no crece; la telemetría sí."],
             ["Operación", "Un motor que el equipo ya conoce.", "Otro motor que mantener, respaldar y asegurar.",
              "Más piezas: monitoreo, copias y permisos en dos lugares."]],
            [3.2 * cm, 4.6 * cm, 4.6 * cm, 4.6 * cm]),
      P("<b>Límites de la medición.</b> Es un laboratorio en un portátil con 306 mil lecturas, no una prueba de carga: en "
        "producción el orden de magnitud sería de miles de millones de lecturas, con red de por medio y réplicas. Los resultados "
        "muestran la tendencia, no cifras de capacidad. Las cifras se tomaron con los demás contenedores de Docker en pausa: con otro "
        "clúster corriendo en la misma máquina virtual, PostgreSQL (que corre en Docker) llegó a ser hasta 10 veces más lento, mientras "
        "MongoDB (nativo) casi no cambió; comparar con cargas distintas habría dado conclusiones falsas. El sharding y la réplica "
        "no se probaron en este entorno.", s_box),
      CondPageBreak(14 * cm)]

# =================================================================== 6. IA
S += [H1("6. Integración de herramientas de IA"),
      P("Se usó <b>Claude Code</b> (Anthropic, modelo Claude Opus 5.5) en la terminal, con acceso a los archivos del proyecto y "
        "a los dos motores locales. La regla fue la misma de la Unidad 3: <b>todo lo que la IA propone se ejecuta contra las bases "
        "reales</b> y solo se acepta lo que la ejecución confirma. La traza completa está en " + M("ia_evidencia/EVIDENCIA_IA.md") + "."),
      tabla([["#", "Prompt / situación", "Resultado de la IA", "Cómo mejoró el trabajo"],
             ["1", "«Haz la tarea siguiendo lo que ya hicimos» + enunciado, insumo y libro",
              "Propuso reutilizar los datos de la U3, separar identidad (PG) y telemetría (Mongo) y crear el registro de dispositivos como puente.",
              "Arquitectura con continuidad y una razón para cada tabla y colección."],
             ["2", "«Los datos de sensores deben tener sentido clínico»",
              "Interpoló la telemetría entre los signos vitales reales de cada episodio e inyectó artefactos para probar la validación.",
              "Los resultados de B4 y B5 coinciden con los hallazgos clínicos de la U3."],
             ["3", "Errores: validador en time series, VARCHAR(20), fechas antes de 1970, collStats en 0, CHECKPOINT",
              "Explicó cada causa y aplicó la corrección mínima.", "Limitaciones reales documentadas en scripts e informe."],
             ["4", "B5 decía «mismo resultado: False»",
              "Comparó fila por fila: empate de marcas de tiempo entre oxímetro y monitor; agregó desempate determinista.",
              "Las comparaciones de latencia son entre consultas equivalentes."],
             ["5", "«Sugiere índices y comprueba si se usan»",
              "Mostró con EXPLAIN que el GIN jsonb_path_ops no sirve para rangos.",
              "Explica la diferencia de B4 y corrige una idea común del insumo."],
             ["6", "Mediciones con el equipo ocupado",
              "Detectó con docker stats otro clúster que frenaba solo a PostgreSQL; se midió con él en pausa, mediana y p95 de 15 corridas.", "Métricas reproducibles."]],
            [0.7 * cm, 4.4 * cm, 6.6 * cm, 5.3 * cm]),
      Spacer(1, 6),
      H2("6.1 Prompts reutilizables"),
      B("«Esta consulta da resultados distintos en PostgreSQL y en MongoDB: compárame fila por fila y dime por qué.»"),
      B("«Muéstrame el plan de ejecución de esta consulta y dime si usa el índice; si no, explica por qué.»"),
      B("«¿Qué dato de este modelo debe vivir en una capa ACID y cuál en una BASE? Justifica con consistencia, volumen y cambio.»"),
      B("«Genera un pipeline que resuma la telemetría de las últimas 6 horas por episodio.»"),
      P("<b>Responsabilidad humana:</b> la IA no tuvo acceso a datos reales (todo es sintético). El autor revisó cada script, "
        "puede explicarlo y es responsable de las decisiones de diseño.", s_box),
      PageBreak()]

# =================================================================== 7. Reflexión
S += [H1("7. Reflexión final: implicaciones técnicas y éticas"),
      H2("7.1 Técnicas"),
      B("<b>No hay motor ganador, hay datos con necesidades distintas.</b> MongoDB fue claramente mejor en ingesta, disco y "
        "análisis masivo; PostgreSQL fue igual o mejor en consultas puntuales y el único que impidió un error clínico (T1)."),
      B("<b>El insumo del curso funciona, con un costo.</b> Guardar telemetría en JSONB evita un segundo motor, pero en este "
        f"volumen ocupó {num(x_disco, 0)} veces más disco y el índice GIN no ayudó en consultas por rango. Es razonable para "
        "pocos sensores; no para un departamento entero."),
      B("<b>La consistencia entre motores es responsabilidad de la aplicación.</b> No existe una transacción que abarque "
        "PostgreSQL y MongoDB: si un dispositivo se reasigna, las lecturas en tránsito pueden quedar con el episodio anterior. "
        "Se mitiga con la asignación con fechas " + M("desde/hasta") + " y validando en la ingesta."),
      B("<b>Más piezas, más superficie de fallo.</b> Dos motores son dos políticas de respaldo, dos sistemas de permisos y dos "
        "cosas que monitorear."),
      H2("7.2 Éticas"),
      B("<b>Separar la identidad es una medida de privacidad, no solo de rendimiento.</b> La telemetría en MongoDB no contiene "
        "nombre, documento ni EPS. Una fuga de esa base expone curvas de SpO<sub>2</sub> de episodios, no personas. El cruce con la "
        "identidad solo ocurre en PostgreSQL, que tiene permisos por rol y auditoría (Ley 1581 de 2012, datos sensibles)."),
      B("<b>Seudónimo no es anónimo.</b> Con la edad, el sexo, la subregión y la fecha de ingreso de la vista analítica, un "
        "paciente de un municipio pequeño puede ser reidentificado. La vista debe usarse con agregación mínima y supresión de "
        "celdas pequeñas, como se propuso en la Unidad 3."),
      B("<b>La consistencia eventual tiene consecuencias clínicas.</b> Un tablero que muestra la SpO<sub>2</sub> de hace 30 segundos es "
        "aceptable; una alarma que llega tarde no. Las alarmas críticas (oclusión de bomba, desaturación) deberían ir por un "
        "canal con garantía de entrega, no depender de la analítica."),
      B("<b>Descartar datos es una decisión clínica.</b> La ingesta descartó 72 lecturas fuera de rango. Un artefacto (FC = 400) "
        "se descarta bien; pero un umbral mal puesto podría ocultar un evento real. Los descartes deben contarse y auditarse, "
        "como hace el script, no desaparecer en silencio."),
      B("<b>Retención.</b> La telemetría cruda se borra a los 2 años (TTL); la historia clínica se conserva según la Res. "
        "1995/1999. Lo clínicamente relevante de la telemetría (episodios de desaturación, alarmas) debe pasar a la historia "
        "antes de que expire."),
      B("<b>Datos sintéticos e IA.</b> Ningún dato real se envió a la herramienta de IA. Los patrones son plausibles, pero no son "
        "evidencia epidemiológica."),
      PageBreak()]

# =================================================================== 8. Repo y video
S += [H1("8. Distribución del trabajo, repositorio y video"),
      P(("Este trabajo se realizó de forma <b>individual</b>: todas las actividades estuvieron a cargo del autor, con el apoyo "
         "de IA documentado en la sección 6." if INDIVIDUAL else "Cada integrante participó como se detalla:")),
      tabla([["Integrante", "Rol"]] + [[i["nombre"], i["rol"]] for i in cfg["integrantes"]], [4 * cm, 13 * cm]),
      Spacer(1, 8),
      H2("8.1 Repositorio digital"),
      P("Enlace: " + enlace(cfg.get("repositorio_url"), "pendiente")),
      code('''Grupo_AE4_U3_Entrega/
├─ Grupo''' + cfg["grupo"] + '''_AE4_U3.pdf               <- este informe
├─ README.md                           <- cómo levantar los dos motores y reproducir
├─ scripts/  conexion.py
│            01_postgres_esquema.sql   02_cargar_postgres.py      (capa ACID)
│            03_mongo_esquema.js       04_ingesta_telemetria.py   (capa BASE + ingesta B1)
│            05_analisis_comparativo.py                            (B1-B5, T1)
│            06_graficas_y_diagrama.py 07_generar_capturas.py
├─ datos_origen/                       <- datos de la Unidad 3 (JSON) que alimentan PostgreSQL
├─ resultados/                         <- salidas reales (.txt), metricas.csv / .json, b1_ingesta.json
├─ capturas/                           <- diagrama, capturas de ejecución y gráficas
├─ ia_evidencia/EVIDENCIA_IA.md        <- prompts, errores reales y aporte de la IA
├─ video/GUION_VIDEO.md                <- guion del video (8-10 min)
└─ informe_fuente/                     <- código que genera este PDF y config.json'''),
      H2("8.2 Video demostrativo"),
      P("Enlace: " + enlace(cfg.get("video_url"), "pendiente")),
      P("Duración de 8 a 10 minutos: arquitectura y división ACID/BASE, ejecución de los scripts en los dos motores, cada prueba "
        "comparativa con su resultado, la demostración de atomicidad, la evidencia de IA y la reflexión. El video no tiene "
        "narración: la explicación va en subtítulos (9 min 30 s), con música de fondo original generada por código."),
      H1("9. Conclusiones"),
      B(f"La arquitectura híbrida se justificó con mediciones: para telemetría, MongoDB ingirió {num(x_ing, 1)} veces más rápido, "
        f"usó {num(x_disco, 0)} veces menos disco y analizó todo el hospital {num(x_b4, 1)} veces más rápido que PostgreSQL con JSONB."),
      B("PostgreSQL sigue siendo indispensable como sistema de registro: la regla «una cama, un paciente activo» y la "
        "atomicidad de la admisión solo las garantizó la capa ACID."),
      B("La llave puente (" + M("dispositivo_id") + " + " + M("hospitalizacion_id") + ") permite analizar la telemetría sin "
        "exponer la identidad del paciente: la separación técnica es también una medida de privacidad."),
      B("El costo de la arquitectura híbrida es la complejidad: dos motores, consistencia entre ellos a cargo de la aplicación y "
        "validación que el motor BASE no hace. Esta base queda lista para el Proyecto Integrador.")]

doc = SimpleDocTemplate(SALIDA, pagesize=letter, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=2 * cm,
                        title=f"Grupo{cfg['grupo']}_AE4_U3 - Construyendo y comparando ecosistemas híbridos", author=", ".join(AUTORES))
doc.build(S, onFirstPage=pie, onLaterPages=pie)
print("PDF generado:", SALIDA)
