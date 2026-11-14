"""07_generar_capturas.py - Renderiza como imagenes (estilo consola) las salidas REALES guardadas en resultados/.
Uso: python scripts/07_generar_capturas.py"""
import os, textwrap
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.join(os.path.dirname(__file__), "..")
RES, CAP = os.path.join(BASE, "resultados"), os.path.join(BASE, "capturas")
FONT = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 15)
BG, FG, TIT, ACC, OK = (30, 30, 30), (212, 212, 212), (56, 56, 56), (78, 201, 176), (220, 220, 170)
ANCHO = 128


def render(titulo, lineas, destino):
    partidas = []
    for l in lineas:
        partidas += textwrap.wrap(l, ANCHO, subsequent_indent="    ", drop_whitespace=False) or [""]
    lh, pad = 19, 14
    w = max(900, int(max(FONT.getlength(l) for l in partidas)) + pad * 2)
    h = 34 + pad * 2 + lh * len(partidas)
    im = Image.new("RGB", (w, h), BG); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w, 30], fill=TIT)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([10 + i * 20, 9, 22 + i * 20, 21], fill=c)
    d.text((80, 7), titulo, font=FONT, fill=FG)
    y = 34 + pad
    for l in partidas:
        col = ACC if l.startswith(("$ ", "====")) else OK if ("mismo resultado" in l or "ROLLBACK" in l or "PARCIAL" in l) else FG
        d.text((pad, y), l, font=FONT, fill=col); y += lh
    im.save(destino)


def leer(n): return open(os.path.join(RES, n), encoding="utf-8").read().rstrip().splitlines()


def bloques(nombre):
    out, actual = {}, None
    for l in leer(nombre):
        if l.startswith("===================="):
            clave = l.strip("= ").split(".")[0]
            actual = out.setdefault(clave, []); actual.append(l)
        elif actual is not None and l.strip() and not l.startswith("Metricas guardadas"):
            actual.append(l)
    return out


s1 = leer("salida_01_postgres_esquema.txt")
s1 = [l for l in s1 if not l.startswith(("NOTICE", "DETAIL", "drop cascades"))]
render("psql -d hce_hibrido -f scripts/01_postgres_esquema.sql  (\\dt hce.*  y  \\di hce.*)", ["$ psql -f scripts/01_postgres_esquema.sql"] + s1,
       os.path.join(CAP, "01_postgres_esquema.png"))
render("PostgreSQL + MongoDB: carga ACID y esquema BASE",
       ["$ python scripts/02_cargar_postgres.py"] + leer("salida_02_cargar_postgres.txt") + [""] +
       ["$ mongosh --file scripts/03_mongo_esquema.js"] + leer("salida_03_mongo_esquema.txt"),
       os.path.join(CAP, "02_carga_y_esquema_mongo.png"))
render("python scripts/04_ingesta_telemetria.py", ["$ python scripts/04_ingesta_telemetria.py"] + leer("salida_04_ingesta.txt"),
       os.path.join(CAP, "03_ingesta_masiva.png"))
b = bloques("salida_05_analisis.txt")
for i, k in enumerate(["B1", "B2", "B3", "B4", "B5", "T1"]):
    render("python scripts/05_analisis_comparativo.py", b[k], os.path.join(CAP, f"{10 + i:02d}_prueba_{k}.png"))
print(sorted(os.listdir(CAP)))
