"""05_analisis_comparativo.py - La misma operacion en PostgreSQL (ACID) y en MongoDB (BASE), medida.

Cada consulta se ejecuta 3 veces de calentamiento y 15 medidas; se reporta mediana y p95 en milisegundos.
  B1  Ingesta por lotes (50.000 lecturas, 5 repeticiones, en tablas/colecciones temporales)
  B2  Ultima lectura de un dispositivo
  B3  Promedio horario de FC y SpO2 de un episodio activo (ultimas 24 h)
  B4  Episodios con desaturacion (SpO2 < 90 %) en los ultimos 7 dias, en todo el hospital
  B5  Tablero de pacientes activos: identidad/episodio de PostgreSQL + resumen de telemetria de 6 h
      (a) hibrido: PostgreSQL + MongoDB unidos en la aplicacion  (b) todo en PostgreSQL con JSONB
  T1  Atomicidad: admision en cama ocupada (PostgreSQL revierte todo) vs. lote con una lectura invalida
      en MongoDB (se guardan las validas: escritura parcial)
Salidas: resultados/metricas.csv, resultados/metricas.json, resultados/salida_05_analisis.txt (via tee), capturas/*.png
Uso: python scripts/05_analisis_comparativo.py"""
import csv, json, os, statistics, sys, time
from datetime import datetime, timedelta, timezone
import psycopg2
from psycopg2.extras import execute_values, Json

sys.path.insert(0, os.path.dirname(__file__))
from conexion import pg, mongo, BASE

CORTE = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)
HOSP = "HOSP-2026-0029"                 # neumonia con deterioro (NEWS2 = 11 en la U3), Medicina Interna, activa
con = pg(); cur = con.cursor(); m = mongo()
cur.execute("SELECT dispositivo_id FROM asignacion_dispositivo JOIN dispositivo USING (dispositivo_id) "
            "WHERE hospitalizacion_id=%s AND tipo='MONITOR_MULTIPARAMETRO'", (HOSP,))
MONITOR = cur.fetchone()[0]
filas = []


def medir(nombre, motor, fn, rep=15, cal=3):
    for _ in range(cal): fn()
    t = []
    for _ in range(rep):
        t0 = time.perf_counter(); r = fn(); t.append((time.perf_counter() - t0) * 1000)
    t.sort()
    med, p95 = statistics.median(t), t[int(round(0.95 * (len(t) - 1)))]
    filas.append({"prueba": nombre, "motor": motor, "mediana_ms": round(med, 2), "p95_ms": round(p95, 2), "n": rep})
    print(f"  {nombre:3} {motor:24} mediana {med:9.2f} ms   p95 {p95:9.2f} ms")
    return r


def titulo(t): print("\n==================== " + t + " ====================")


# ------------------------------------------------------------------ B1
titulo("B1. Ingesta por lotes: 50.000 lecturas x 5 repeticiones")
muestra = list(m.telemetria.find({}, {"_id": 0}).sort("ts", 1).limit(50000))
m.drop_collection("tmp_ingesta")
def ing_mongo():
    m.drop_collection("tmp_ingesta")
    m.create_collection("tmp_ingesta", timeseries={"timeField": "ts", "metaField": "meta", "granularity": "seconds"})
    t0 = time.perf_counter()
    for i in range(0, len(muestra), 5000): m.tmp_ingesta.insert_many([dict(x) for x in muestra[i:i + 5000]], ordered=False)
    return time.perf_counter() - t0
def ing_pg():
    cur.execute("DROP TABLE IF EXISTS tmp_ingesta; CREATE TABLE tmp_ingesta (LIKE telemetria_jsonb INCLUDING ALL)"); con.commit()
    t0 = time.perf_counter()
    for i in range(0, len(muestra), 5000):
        execute_values(cur, "INSERT INTO tmp_ingesta (dispositivo_id, ts, tipo, lectura) VALUES %s",
                       [(x["meta"]["dispositivo_id"], x["ts"], x["meta"]["tipo"], Json({k: v for k, v in x.items() if k not in ("ts", "meta")}))
                        for x in muestra[i:i + 5000]], page_size=5000)
        con.commit()
    return time.perf_counter() - t0
for motor, fn in (("MongoDB time series", ing_mongo), ("PostgreSQL JSONB", ing_pg)):
    ts = sorted(fn() for _ in range(5)); med = statistics.median(ts)
    filas.append({"prueba": "B1", "motor": motor, "mediana_ms": round(med * 1000, 1), "p95_ms": round(ts[-1] * 1000, 1), "n": 5,
                  "lecturas_s": round(len(muestra) / med)})
    print(f"  B1  {motor:24} mediana {med:6.2f} s  -> {len(muestra) / med:8.0f} lecturas/s  (min {ts[0]:.2f} s, max {ts[-1]:.2f} s)")
m.drop_collection("tmp_ingesta"); cur.execute("DROP TABLE tmp_ingesta"); con.commit()

# ------------------------------------------------------------------ B2
titulo(f"B2. Ultima lectura del monitor {MONITOR} ({HOSP})")
r = medir("B2", "MongoDB", lambda: m.telemetria.find_one({"meta.dispositivo_id": MONITOR}, {"_id": 0}, sort=[("ts", -1)]))
print("     MongoDB    ->", {k: r[k] for k in ("ts", "fc", "fr", "spo2", "ta")})
def b2_pg():
    cur.execute("SELECT ts, lectura FROM telemetria_jsonb WHERE dispositivo_id=%s ORDER BY ts DESC LIMIT 1", (MONITOR,)); return cur.fetchone()
r = medir("B2", "PostgreSQL", b2_pg)
print("     PostgreSQL ->", r[0], {k: r[1][k] for k in ("fc", "fr", "spo2", "ta")})

# ------------------------------------------------------------------ B3
titulo(f"B3. Promedio horario de FC y SpO2 de {HOSP} en las ultimas 24 h")
desde = CORTE - timedelta(hours=24)
P3 = [{"$match": {"meta.hosp": HOSP, "meta.tipo": "MONITOR_MULTIPARAMETRO", "ts": {"$gte": desde, "$lt": CORTE}}},
      {"$group": {"_id": {"$dateTrunc": {"date": "$ts", "unit": "hour"}}, "fc": {"$avg": "$fc"}, "spo2": {"$avg": "$spo2"}, "n": {"$sum": 1}}},
      {"$sort": {"_id": 1}}]
rm = medir("B3", "MongoDB", lambda: list(m.telemetria.aggregate(P3)))
SQL3 = """SELECT date_trunc('hour', t.ts) AS hora, avg((t.lectura->>'fc')::int) AS fc, avg((t.lectura->>'spo2')::int) AS spo2, count(*)
          FROM telemetria_jsonb t JOIN asignacion_dispositivo a USING (dispositivo_id)
          WHERE a.hospitalizacion_id = %s AND t.tipo = 'MONITOR_MULTIPARAMETRO' AND t.ts >= %s AND t.ts < %s
          GROUP BY 1 ORDER BY 1"""
def b3_pg(): cur.execute(SQL3, (HOSP, desde, CORTE)); return cur.fetchall()
rp = medir("B3", "PostgreSQL", b3_pg)
print(f"     horas: MongoDB {len(rm)} | PostgreSQL {len(rp)}; primeras 3 (hora, FC, SpO2, n):")
for a, b in zip(rm[:3], rp[:3]):
    print(f"       Mongo {a['_id']:%d-%m %H:%M}  {a['fc']:6.1f} {a['spo2']:5.1f} {a['n']:3} | PG {b[0]:%d-%m %H:%M}  {float(b[1]):6.1f} {float(b[2]):5.1f} {b[3]:3}")
iguales3 = all(abs(a["fc"] - float(b[1])) < 1e-6 and a["n"] == b[3] for a, b in zip(rm, rp)) and len(rm) == len(rp)
print("     mismo resultado en los dos motores:", iguales3)

# ------------------------------------------------------------------ B4
titulo("B4. Episodios con desaturacion (SpO2 < 90 %) en los ultimos 7 dias - todo el hospital")
d7 = CORTE - timedelta(days=7)
P4 = [{"$match": {"ts": {"$gte": d7, "$lt": CORTE}, "spo2": {"$lt": 90}}},
      {"$group": {"_id": "$meta.hosp", "lecturas": {"$sum": 1}, "spo2_min": {"$min": "$spo2"}, "ultima": {"$max": "$ts"}}},
      {"$sort": {"lecturas": -1}}]
rm = medir("B4", "MongoDB", lambda: list(m.telemetria.aggregate(P4)))
SQL4 = """SELECT a.hospitalizacion_id, count(*), min((t.lectura->>'spo2')::int), max(t.ts)
          FROM telemetria_jsonb t JOIN asignacion_dispositivo a USING (dispositivo_id)
          WHERE t.ts >= %s AND t.ts < %s AND (t.lectura->>'spo2')::int < 90
          GROUP BY 1 ORDER BY 2 DESC"""
def b4_pg(): cur.execute(SQL4, (d7, CORTE)); return cur.fetchall()
rp = medir("B4", "PostgreSQL", b4_pg)
for a in rm: print(f"     {a['_id']}  lecturas {a['lecturas']:5}  SpO2 min {a['spo2_min']}  ultima {a['ultima']:%d-%m %H:%M}")
print("     mismo resultado en los dos motores:", sorted((a["_id"], a["lecturas"]) for a in rm) == sorted((b[0], b[1]) for b in rp))
ex = m.command("explain", {"aggregate": "telemetria", "pipeline": P4, "cursor": {}}, verbosity="executionStats")
cur.execute("EXPLAIN (ANALYZE, FORMAT JSON) " + SQL4, (d7, CORTE)); plan = cur.fetchone()[0][0]
def nodos(p):
    yield p
    for h in p.get("Plans", []): yield from nodos(h)
scan = [n["Node Type"] + " " + n.get("Relation Name", n.get("Index Name", "")) for n in nodos(plan["Plan"]) if "Scan" in n["Node Type"]]
print("     plan PostgreSQL:", "; ".join(scan), f"| {plan['Execution Time']:.1f} ms")
print("     nota: el operador ->> sobre JSONB no puede usar el indice GIN (jsonb_path_ops solo sirve para @>), por eso recorre la tabla")

# ------------------------------------------------------------------ B5
titulo("B5. Tablero de pacientes activos: episodio (PostgreSQL) + telemetria de las ultimas 6 h")
d6 = CORTE - timedelta(hours=6)
def b5_hibrido():
    cur.execute("""SELECT e.hospitalizacion_id, e.servicio, e.cama_id, e.edad, e.sexo, e.dx_principal
                   FROM v_episodio_analitico e WHERE e.estado='ACTIVA' ORDER BY 1""")
    eps = cur.fetchall(); ids = [e[0] for e in eps]
    tel = {d["_id"]: d for d in m.telemetria.aggregate([
        {"$match": {"meta.hosp": {"$in": ids}, "ts": {"$gte": d6, "$lt": CORTE}, "spo2": {"$exists": True}}},
        {"$sort": {"ts": 1, "meta.dispositivo_id": -1}},
        {"$group": {"_id": "$meta.hosp", "spo2_min": {"$min": "$spo2"}, "fc_max": {"$max": "$fc"}, "ultima_spo2": {"$last": "$spo2"}, "n": {"$sum": 1}}}])}
    return [(*e, tel.get(e[0], {}).get("spo2_min"), tel.get(e[0], {}).get("fc_max"), tel.get(e[0], {}).get("ultima_spo2"), tel.get(e[0], {}).get("n")) for e in eps]
SQL5 = """SELECT e.hospitalizacion_id, e.servicio, e.cama_id, e.edad, e.sexo, e.dx_principal,
                 s.spo2_min, s.fc_max, s.ultima_spo2, s.n
          FROM v_episodio_analitico e
          LEFT JOIN LATERAL (
             SELECT min((t.lectura->>'spo2')::int) spo2_min, max((t.lectura->>'fc')::int) fc_max,
                    (array_agg((t.lectura->>'spo2')::int ORDER BY t.ts DESC, t.dispositivo_id))[1] ultima_spo2, count(*) n
             FROM asignacion_dispositivo a JOIN telemetria_jsonb t ON t.dispositivo_id = a.dispositivo_id
             WHERE a.hospitalizacion_id = e.hospitalizacion_id AND t.ts >= %s AND t.ts < %s AND t.lectura ? 'spo2') s ON true
          WHERE e.estado='ACTIVA' ORDER BY 1"""
def b5_pg(): cur.execute(SQL5, (d6, CORTE)); return cur.fetchall()
rh = medir("B5", "Hibrido PG + MongoDB", b5_hibrido)
rp = medir("B5", "Solo PostgreSQL (JSONB)", b5_pg)
print("     episodio        servicio          cama    edad sexo dx     SpO2min FCmax SpO2ult lecturas")
for x in rh: print(f"     {x[0]}  {x[1]:16} {x[2]:7} {x[3]:4}  {x[4]}   {x[5]:6} {x[6]!s:>6} {x[7]!s:>5} {x[8]!s:>6} {x[9]!s:>7}")
print("     mismo resultado en las dos versiones:", [tuple(map(str, a)) for a in rh] == [tuple(map(str, b)) for b in rp])

# ------------------------------------------------------------------ T1
titulo("T1. Atomicidad: lo que garantiza cada capa")
cur.execute("SELECT count(*) FROM hospitalizacion"); antes = cur.fetchone()[0]
try:
    cur.execute("INSERT INTO hospitalizacion VALUES ('HOSP-2026-0037','PAC-003','PRO-001','MI-201','MEDICINA_INTERNA',%s,NULL,'J18.9','ACTIVA')", (CORTE,))
    cur.execute("INSERT INTO asignacion_dispositivo (dispositivo_id, hospitalizacion_id, desde) VALUES ('DSP-0001','HOSP-2026-0037',%s)", (CORTE,))
    con.commit(); print("  PostgreSQL: ERROR, se acepto una admision en cama ocupada")
except psycopg2.Error as e:
    con.rollback()
    cur.execute("SELECT count(*) FROM hospitalizacion"); despues = cur.fetchone()[0]
    print(f"  PostgreSQL: admision en MI-201 (ocupada por {HOSP}) rechazada -> {e.pgcode} {e.diag.constraint_name or ''}")
    print(f"              ROLLBACK de toda la transaccion: hospitalizaciones antes {antes}, despues {despues}")
lote = [{"ts": CORTE + timedelta(seconds=i), "meta": {"dispositivo_id": MONITOR, "tipo": "MONITOR_MULTIPARAMETRO", "hosp": HOSP}, "fc": 90, "spo2": 95} for i in range(4)]
lote.insert(2, {"meta": {"dispositivo_id": MONITOR, "tipo": "MONITOR_MULTIPARAMETRO", "hosp": HOSP}, "fc": 90})   # sin ts: invalida
try:
    m.telemetria.insert_many(lote, ordered=False)
except Exception as e:
    print(f"  MongoDB:    lote de 5 lecturas con 1 invalida (sin ts) -> {type(e).__name__}")
n = m.telemetria.count_documents({"meta.dispositivo_id": MONITOR, "ts": {"$gte": CORTE}})
print(f"              se guardaron {n} de 5: escritura PARCIAL, sin transaccion (aceptable para telemetria, no para una admision)")
m.telemetria.delete_many({"meta.dispositivo_id": MONITOR, "ts": {"$gte": CORTE}})

# ------------------------------------------------------------------ salida
os.makedirs(os.path.join(BASE, "resultados"), exist_ok=True)
with open(os.path.join(BASE, "resultados", "metricas.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["prueba", "motor", "mediana_ms", "p95_ms", "n", "lecturas_s"]); w.writeheader(); w.writerows(filas)
json.dump(filas, open(os.path.join(BASE, "resultados", "metricas.json"), "w", encoding="utf-8"), indent=2)
print("\nMetricas guardadas en resultados/metricas.csv")
