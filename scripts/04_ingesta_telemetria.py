"""04_ingesta_telemetria.py - Simula la ingesta masiva de telemetria clinica y la carga en las DOS capas.

Coherencia clinica: cada lectura se interpola entre las tomas de signos vitales REALES del episodio en la HCE de la
Unidad 3 (datos_origen/hospitalizaciones.json), con ruido determinista. Si el paciente con neumonia llego con SpO2 88 %
y salio con 96 %, su oximetro muestra esa curva. Los glucometros siguen el perfil de un diabetico descompensado que
se controla, y las bombas emiten eventos (inicio, cambio de velocidad, alarma de oclusion).

La MISMA lista de lecturas se inserta en:
  * MongoDB  hce_telemetria.telemetria   (coleccion time series, insert_many por lotes)
  * PostgreSQL hce.telemetria_jsonb      (JSONB, execute_values por lotes; tabla solo de comparacion)
y se mide el tiempo de cada una (prueba B1 del analisis comparativo).
Uso: python scripts/04_ingesta_telemetria.py"""
import json, math, os, random, sys, time
from datetime import datetime, timedelta, timezone
from psycopg2.extras import execute_values, Json

sys.path.insert(0, os.path.dirname(__file__))
from conexion import pg, mongo, BASE

LOTE = 5000
CORTE = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)           # misma fecha de corte que la U3
rnd = random.Random(866)


EPOCA = datetime(1970, 1, 1, tzinfo=timezone.utc)


def fecha(v):
    v = v["$date"]
    if isinstance(v, dict): return EPOCA + timedelta(milliseconds=int(v["$numberLong"]))   # admite fechas < 1970 en Windows
    return datetime.fromisoformat(v.replace("Z", "+00:00"))


hosp = {h["_id"]: h for h in json.load(open(os.path.join(BASE, "datos_origen", "hospitalizaciones.json"), encoding="utf-8"))}
con = pg(); cur = con.cursor()
cur.execute("""SELECT d.dispositivo_id, d.tipo, d.frecuencia_seg, a.hospitalizacion_id, a.desde, coalesce(a.hasta, %s)
               FROM dispositivo d JOIN asignacion_dispositivo a USING (dispositivo_id) ORDER BY 1""", (CORTE,))
asignaciones = cur.fetchall()


def serie(h):
    """Tomas reales de signos vitales del episodio, ordenadas: [(t, {fc, fr, spo2, tas, tad, temp})]."""
    out = []
    for s in sorted(h["signos_vitales"], key=lambda s: fecha(s["fecha"])):
        out.append((fecha(s["fecha"]), {"fc": s["fc"], "fr": s["fr"], "spo2": s["spo2"], "tas": s["ta_sistolica"],
                                        "tad": s["ta_diastolica"], "temp": float(s["temperatura"])}))
    return out


def interp(sv, t):
    if t <= sv[0][0]: return sv[0][1]
    if t >= sv[-1][0]: return sv[-1][1]
    for (t0, a), (t1, b) in zip(sv, sv[1:]):
        if t0 <= t <= t1:
            k = (t - t0) / (t1 - t0) if t1 > t0 else 0
            return {c: a[c] + (b[c] - a[c]) * k for c in a}


def valida(l):
    """La coleccion time series no admite validador: los rangos se controlan aqui."""
    return all(lo <= l[c] <= hi for c, lo, hi in (("spo2", 50, 100), ("fc", 20, 250), ("fr", 4, 80), ("glucosa", 20, 600)) if c in l)


lecturas, descartadas = [], 0
for did, tipo, seg, hid, desde, hasta in asignaciones:
    h = hosp[hid]; sv = serie(h)
    if tipo == "BOMBA_INFUSION":                           # eventos, no periodo
        t = desde + timedelta(minutes=20); vel = 125
        while t < hasta:
            ev = rnd.choices(["CAMBIO_VELOCIDAD", "ALARMA_OCLUSION", "BOLO"], [0.7, 0.15, 0.15])[0]
            if ev == "CAMBIO_VELOCIDAD": vel = max(20, min(250, vel + rnd.choice([-25, 25])))
            lecturas.append({"ts": t, "meta": {"dispositivo_id": did, "tipo": tipo, "hosp": hid},
                             "evento": ev, "ml_h": vel, "medicamento_id": "MED-009",
                             **({"resuelta_en_s": rnd.randint(30, 400)} if ev == "ALARMA_OCLUSION" else {})})
            t += timedelta(minutes=rnd.randint(40, 240))
        continue
    t, i = desde, 0
    while t < hasta:
        base = interp(sv, t); r = math.sin(i / 7.0)            # variacion suave + ruido determinista
        if tipo == "OXIMETRO_WEARABLE":
            l = {"spo2": int(round(min(100, base["spo2"] + r * 0.8 + rnd.uniform(-0.6, 0.6)))),
                 "fc": int(round(base["fc"] + r * 3 + rnd.uniform(-2, 2))),
                 "pi": round(rnd.uniform(1.2, 6.5), 1), "bateria": max(5, 100 - i // 60), "movimiento": rnd.random() < 0.08}
        elif tipo == "MONITOR_MULTIPARAMETRO":
            l = {"fc": int(round(base["fc"] + r * 3 + rnd.uniform(-2, 2))), "fr": int(round(base["fr"] + rnd.uniform(-1, 1))),
                 "spo2": int(round(min(100, base["spo2"] + rnd.uniform(-0.6, 0.6)))),
                 "ta": {"s": int(round(base["tas"] + rnd.uniform(-4, 4))), "d": int(round(base["tad"] + rnd.uniform(-3, 3)))},
                 "temp": round(base["temp"] + rnd.uniform(-0.1, 0.1), 1)}
            if rnd.random() < 0.0004: l["fc"] = 400            # artefacto de sensor (cable suelto): debe descartarse
        else:                                                  # GLUCOMETRO_CGM: de hiperglucemia a control
            k = min(1, (t - desde) / timedelta(days=3))
            g = 340 - 190 * k + 25 * math.sin(i / 9) + rnd.uniform(-8, 8)
            l = {"glucosa": int(round(g)), "tendencia": "BAJANDO" if k < 1 else "ESTABLE"}
        if valida(l):
            lecturas.append({"ts": t, "meta": {"dispositivo_id": did, "tipo": tipo, "hosp": hid}, **l})
        else:
            descartadas += 1
        t += timedelta(seconds=seg); i += 1

# Teleconsultas de seguimiento (semiestructuradas): 1 o 2 por egreso, con campos distintos segun el caso.
telec = []
for hid, h in hosp.items():
    if h["estado"] != "EGRESADA": continue
    alta = fecha(h["alta"]["fecha"])
    for k in range(rnd.choice([1, 1, 2])):
        f = alta + timedelta(days=7 * (k + 1), hours=rnd.randint(8, 16))
        if f > CORTE: break
        doc = {"hosp": hid, "fecha": f, "modalidad": rnd.choice(["VIDEO", "VIDEO", "TELEFONO", "MENSAJERIA"]),
               "especialidad": {"PEDIATRIA": "Pediatría", "CIRUGIA": "Cirugía general", "UCI": "Cardiología"}.get(h["servicio"], "Medicina interna"),
               "duracion_min": rnd.randint(8, 25), "motivo": "Control posterior al egreso"}
        if rnd.random() < 0.6: doc["signos_reportados"] = {"spo2_domicilio": rnd.randint(93, 98), "dolor_0_10": rnd.randint(0, 4)}
        if rnd.random() < 0.4: doc["adjuntos"] = [{"tipo": "foto", "descripcion": "Herida quirúrgica" if h["servicio"] == "CIRUGIA" else "Fórmula médica"}]
        if rnd.random() < 0.3: doc["reconsulta_urgencias"] = True
        telec.append(doc)

print(f"Lecturas generadas: {len(lecturas)}  (descartadas por fuera de rango: {descartadas})  | teleconsultas: {len(telec)}")
por_tipo = {}
for l in lecturas: por_tipo[l["meta"]["tipo"]] = por_tipo.get(l["meta"]["tipo"], 0) + 1
print("  por tipo: " + ", ".join(f"{k}={v}" for k, v in sorted(por_tipo.items(), key=lambda x: -x[1])))

# ---------------- B1: ingesta en MongoDB ----------------
m = mongo()
m.telemetria.delete_many({}); m.teleconsultas.delete_many({})
t0 = time.perf_counter()
for i in range(0, len(lecturas), LOTE):
    m.telemetria.insert_many([dict(x) for x in lecturas[i:i + LOTE]], ordered=False)
t_mongo = time.perf_counter() - t0
m.teleconsultas.insert_many(telec)

# ---------------- B1: misma ingesta en PostgreSQL JSONB ----------------
cur.execute("TRUNCATE telemetria_jsonb RESTART IDENTITY"); con.commit()
t0 = time.perf_counter()
for i in range(0, len(lecturas), LOTE):
    filas = [(x["meta"]["dispositivo_id"], x["ts"], x["meta"]["tipo"],
              Json({k: v for k, v in x.items() if k not in ("ts", "meta")})) for x in lecturas[i:i + LOTE]]
    execute_values(cur, "INSERT INTO telemetria_jsonb (dispositivo_id, ts, tipo, lectura) VALUES %s", filas, page_size=LOTE)
    con.commit()
t_pg = time.perf_counter() - t0
cur.execute("ANALYZE telemetria_jsonb"); con.commit()

n = len(lecturas)
m.client.admin.command("fsync")                       # fuerza el checkpoint para que el tamano en disco sea real
time.sleep(2)
st = next(m.telemetria.aggregate([{"$collStats": {"storageStats": {}}}]))["storageStats"]
cur.execute("SELECT pg_total_relation_size('telemetria_jsonb'), pg_relation_size('telemetria_jsonb')")
pg_total, pg_tabla = cur.fetchone()
res = {"lecturas": n, "descartadas": descartadas, "teleconsultas": len(telec), "lote": LOTE,
       "mongo_s": round(t_mongo, 2), "pg_s": round(t_pg, 2),
       "mongo_lect_s": round(n / t_mongo), "pg_lect_s": round(n / t_pg),
       "mongo_buckets": st.get("timeseries", {}).get("bucketCount"),
       "mongo_mb_logico": round(st.get("size", 0) / 2**20, 1),
       "mongo_mb_disco": round((st.get("storageSize", 0) + st.get("totalIndexSize", 0)) / 2**20, 1),
       "pg_mb_disco": round(pg_total / 2**20, 1), "pg_mb_tabla": round(pg_tabla / 2**20, 1), "por_tipo": por_tipo}
json.dump(res, open(os.path.join(BASE, "resultados", "b1_ingesta.json"), "w", encoding="utf-8"), indent=2)
print(f"B1 MongoDB   : {n} lecturas en {t_mongo:6.2f} s -> {n / t_mongo:8.0f} lecturas/s | disco {res['mongo_mb_disco']} MB (datos+indices; {res['mongo_buckets']} buckets, {res['mongo_mb_logico']} MB logicos)")
print(f"B1 PostgreSQL: {n} lecturas en {t_pg:6.2f} s -> {n / t_pg:8.0f} lecturas/s | disco {res['pg_mb_disco']} MB (tabla+indices)")
print(f"Conteo final: MongoDB {m.telemetria.count_documents({})} | PostgreSQL ", end="")
cur.execute("SELECT count(*) FROM telemetria_jsonb"); print(cur.fetchone()[0])
