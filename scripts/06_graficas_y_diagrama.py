"""06_graficas_y_diagrama.py - Diagrama de la arquitectura hibrida y graficas de las metricas reales.
Lee resultados/b1_ingesta.json y resultados/metricas.json (generados por 04 y 05); escribe capturas/*.png
Uso: python scripts/06_graficas_y_diagrama.py"""
import json, os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CAP = os.path.join(BASE, "capturas"); os.makedirs(CAP, exist_ok=True)
PG_C, MG_C, APP_C = "#336791", "#3f9142", "#7d3c98"

# ------------------------------------------------------------------ diagrama
fig, ax = plt.subplots(figsize=(14, 8.4)); ax.set_xlim(0, 14); ax.set_ylim(0, 8.4); ax.axis("off")


def caja(x, y, w, h, titulo, lineas, fc, ec, fs=8):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", fc=fc, ec=ec, lw=1.6))
    ax.text(x + w / 2, y + h - 0.25, titulo, ha="center", va="center", fontsize=10.5, fontweight="bold", color=ec)
    for i, l in enumerate(lineas):
        ax.text(x + 0.15, y + h - 0.6 - i * 0.26, l, fontsize=fs, va="center", family="monospace")


# Fuentes
caja(0.2, 4.0, 3.3, 1.8, "Fuentes de eventos", ["monitor multiparametro 60 s", "oximetro wearable 120 s",
                                                "glucometro CGM 300 s", "bomba de infusion (eventos)"], "#fff8e1", "#c98a00")
caja(0.2, 6.3, 3.3, 1.8, "Usuarios clinicos", ["admision / alta / traslado", "asignar dispositivo", "tablero de pacientes",
                                              "registrar teleconsulta"], "#fff8e1", "#c98a00")
caja(0.2, 0.9, 3.3, 2.5, "Ingesta (04_ingesta)", ["valida rangos fisiologicos", "(time series no admite", " $jsonSchema)", "descarta artefactos",
                                                 "insert_many lotes 5000", "ordered=False"], "#f4ecf7", APP_C)
# Capa ACID
ax.add_patch(FancyBboxPatch((4.3, 3.7), 4.6, 4.45, boxstyle="round,pad=0.02,rounding_size=0.15", fc="#eaf1f8", ec=PG_C, lw=2.2))
ax.text(6.6, 7.9, "PostgreSQL 17 - capa ACID (System of Record)", ha="center", fontsize=9.4, fontweight="bold", color=PG_C)
for i, l in enumerate(["esquema hce", "paciente (identidad, Ley 1581)", "  paciente_alergia", "profesional  cie10  medicamento",
                       "cama", "hospitalizacion", "  ux_cama_activa / ux_paciente_activo", "dispositivo", "asignacion_dispositivo",
                       "  ux_dispositivo_vigente", "VIEW v_episodio_analitico", "  (edad, sexo, subregion; sin nombre)"]):
    ax.text(4.45, 7.5 - i * 0.3, l, fontsize=8.2, family="monospace", color="#1b2a3a")
# Capa BASE
ax.add_patch(FancyBboxPatch((4.3, 0.4), 4.6, 2.95, boxstyle="round,pad=0.02,rounding_size=0.15", fc="#edf7ee", ec=MG_C, lw=2.2))
ax.text(6.6, 3.1, "MongoDB 8.3 - capa BASE (System of Insight)", ha="center", fontsize=9.4, fontweight="bold", color=MG_C)
for i, l in enumerate(["db hce_telemetria", "telemetria  (TIME SERIES)", "  ts + meta{dispositivo_id, tipo, hosp}",
                       "  buckets comprimidos, TTL 2 anos", "teleconsultas ($jsonSchema)", "  campos variables: adjuntos, signos..."]):
    ax.text(4.45, 2.72 - i * 0.3, l, fontsize=8.2, family="monospace", color="#1b3a1f")
# App / analitica
caja(9.8, 4.6, 4.0, 3.5, "Aplicacion / analitica", ["B5 tablero de activos:", " 1. PG: episodios activos", "    (vista seudonimizada)",
                                                    " 2. Mongo: resumen 6 h por", "    hosp ($in de ids)", " 3. une en memoria por", "    hospitalizacion_id",
                                                    "", "B2-B4 consultas de", "telemetria en Mongo"], "#f4ecf7", APP_C)
caja(9.8, 0.4, 4.0, 3.6, "Llave puente", ["dispositivo_id  y  hosp", "(hospitalizacion_id)", "", "Mongo NO guarda nombre,", "documento ni EPS:",
                                          "la identidad solo vive", "en PostgreSQL.", "Sin FK entre motores:", "la app valida el puente."], "#fdecea", "#b03a2e")
kw = dict(arrowprops=dict(arrowstyle="->", color="#444", lw=1.6))
ax.annotate("", xy=(1.85, 3.4), xytext=(1.85, 4.0), **kw); ax.text(1.95, 3.6, "lecturas JSON", fontsize=7.5, color="#444")
ax.annotate("", xy=(4.3, 1.9), xytext=(3.5, 1.9), **kw); ax.text(3.55, 2.05, "BASE", fontsize=7.5, color=MG_C, fontweight="bold")
ax.annotate("", xy=(4.3, 7.2), xytext=(3.5, 7.2), **kw); ax.text(3.55, 7.35, "ACID", fontsize=7.5, color=PG_C, fontweight="bold")
ax.annotate("", xy=(4.3, 1.2), xytext=(3.5, 6.5), arrowprops=dict(arrowstyle="->", color=MG_C, lw=1.2, ls=":"))
ax.text(3.62, 5.75, "teleconsulta", fontsize=7, color=MG_C, rotation=-78)
ax.annotate("", xy=(3.5, 2.9), xytext=(4.3, 4.0), arrowprops=dict(arrowstyle="->", color=PG_C, lw=1.3, ls="--"))
ax.text(3.56, 3.62, "dispositivo\n-> episodio", fontsize=6.5, color=PG_C)
ax.annotate("", xy=(9.8, 6.5), xytext=(8.9, 6.5), arrowprops=dict(arrowstyle="<->", color=PG_C, lw=1.6))
ax.annotate("", xy=(9.8, 5.0), xytext=(8.9, 2.4), arrowprops=dict(arrowstyle="<->", color=MG_C, lw=1.6))
ax.text(0.2, 0.12, "Azul = consistencia fuerte, transacciones, FK y unicidad    Verde = disponibilidad, ingesta masiva, esquema flexible    "
        "Morado = logica de aplicacion", fontsize=8.3)
ax.set_title("Arquitectura hibrida - HCE basica, hospitalizacion: PostgreSQL (ACID) + MongoDB (BASE)", fontsize=12.5, pad=6)
plt.savefig(os.path.join(CAP, "00_diagrama_arquitectura.png"), dpi=160, bbox_inches="tight"); plt.close()

# ------------------------------------------------------------------ graficas
b1 = json.load(open(os.path.join(BASE, "resultados", "b1_ingesta.json"), encoding="utf-8"))
met = json.load(open(os.path.join(BASE, "resultados", "metricas.json"), encoding="utf-8"))

fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.2))
mot = ["MongoDB\ntime series", "PostgreSQL\nJSONB"]
v = [b1["mongo_lect_s"], b1["pg_lect_s"]]
r = a1.bar(mot, v, color=[MG_C, PG_C], width=0.55)
a1.bar_label(r, labels=[f"{x:,.0f}".replace(",", ".") for x in v], padding=3, fontsize=10)
a1.set_title(f"B1. Ingesta completa: {b1['lecturas']:,} lecturas".replace(",", ".") + "\n(lecturas por segundo, mayor es mejor)", fontsize=10.5)
a1.set_ylim(0, max(v) * 1.2); a1.spines[["top", "right"]].set_visible(False)
d = [b1["mongo_mb_disco"], b1["pg_mb_disco"]]
r = a2.bar(mot, d, color=[MG_C, PG_C], width=0.55)
a2.bar_label(r, labels=[f"{x:.1f} MB" for x in d], padding=3, fontsize=10)
a2.set_title("Espacio en disco de la misma telemetria\n(datos + indices, menor es mejor)", fontsize=10.5)
a2.set_ylim(0, max(d) * 1.2); a2.spines[["top", "right"]].set_visible(False)
plt.tight_layout(); plt.savefig(os.path.join(CAP, "20_grafica_ingesta_disco.png"), dpi=150); plt.close()

etiquetas = {"B2": "B2 ultima lectura\nde un dispositivo", "B3": "B3 promedio horario\nde un episodio (24 h)",
             "B4": "B4 desaturacion\ntodo el hospital (7 d)", "B5": "B5 tablero activos\n(PG + telemetria 6 h)"}
fig, ax = plt.subplots(figsize=(12, 4.6)); w = 0.36
for k, (p, et) in enumerate(etiquetas.items()):
    fl = [f for f in met if f["prueba"] == p]
    mg = next(f for f in fl if "Mongo" in f["motor"] or "Hibrido" in f["motor"])
    pgf = next(f for f in fl if f["motor"].startswith("PostgreSQL") or f["motor"].startswith("Solo"))
    for j, (f, c) in enumerate(((mg, MG_C), (pgf, PG_C))):
        b = ax.bar(k + (j - 0.5) * w, f["mediana_ms"], w, color=c, label=(("MongoDB / hibrido" if j == 0 else "PostgreSQL") if k == 0 else None))
        ax.errorbar(k + (j - 0.5) * w, f["mediana_ms"], yerr=[[0], [f["p95_ms"] - f["mediana_ms"]]], color="#333", capsize=3, lw=1)
        ax.text(k + (j - 0.5) * w, f["p95_ms"] * 1.08, f"{f['mediana_ms']:.1f}", ha="center", fontsize=9)
ax.set_xticks(range(len(etiquetas))); ax.set_xticklabels(etiquetas.values(), fontsize=9)
ax.set_yscale("log"); ax.set_ylabel("milisegundos (escala log)")
ax.set_title("Latencia de consulta: mediana de 15 ejecuciones (barra) y p95 (linea); menor es mejor", fontsize=10.5)
ax.legend(frameon=False); ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout(); plt.savefig(os.path.join(CAP, "21_grafica_latencia.png"), dpi=150); plt.close()
print("diagrama y graficas generados en capturas/")
