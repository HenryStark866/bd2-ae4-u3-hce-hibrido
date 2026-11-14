"""02_cargar_postgres.py - Puebla la capa ACID con los datos de la Unidad 3 (datos_origen/, exportados de MongoDB).
La identidad del paciente, los catalogos, las camas y los episodios pasan a PostgreSQL; el detalle clinico
semiestructurado (notas, signos tomados a mano) sigue en el documento de MongoDB de la U3.
Todo se carga en UNA transaccion: si algo falla (una FK, un CHECK), no queda nada a medias.
Uso: python scripts/02_cargar_postgres.py      (requiere psycopg2 y el esquema de 01_postgres_esquema.sql)"""
import json, os, sys
from datetime import datetime, timedelta, timezone
import psycopg2

sys.path.insert(0, os.path.dirname(__file__))
from conexion import pg, BASE

def leer(n): return json.load(open(os.path.join(BASE, "datos_origen", n + ".json"), encoding="utf-8"))
EPOCA = datetime(1970, 1, 1, tzinfo=timezone.utc)


def fecha(v):
    if v is None: return None
    v = v["$date"]
    if isinstance(v, dict): return EPOCA + timedelta(milliseconds=int(v["$numberLong"]))   # admite fechas < 1970 en Windows
    return datetime.fromisoformat(v.replace("Z", "+00:00"))

hosp = leer("hospitalizaciones")
con = pg(); cur = con.cursor()
try:
    cur.executemany("INSERT INTO cie10 VALUES (%s,%s,%s,%s)",
                    [(c["_id"], c["descripcion"], c["capitulo"], c.get("notificacion_obligatoria", False)) for c in leer("catalogo_cie10")])
    cur.executemany("INSERT INTO medicamento VALUES (%s,%s,%s,%s,%s,%s)",
                    [(m["_id"], m["nombre_generico"], m["atc"], m.get("forma"), m.get("concentracion"), m.get("familia_alergia"))
                     for m in leer("catalogo_medicamentos")])
    pacs = leer("pacientes")
    cur.executemany("INSERT INTO paciente (paciente_id,tipo_documento,documento,nombres,apellidos,fecha_nacimiento,sexo,"
                    "grupo_sanguineo,municipio,subregion,eps,regimen) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    [(p["_id"], p["tipo_documento"], p["documento"], p["nombres"], p["apellidos"], fecha(p["fecha_nacimiento"]).date(),
                      p["sexo"], p.get("grupo_sanguineo"), p["contacto"]["municipio"], p["contacto"]["subregion"],
                      p["aseguramiento"]["eps"], p["aseguramiento"]["regimen"]) for p in pacs])
    cur.executemany("INSERT INTO paciente_alergia VALUES (%s,%s)", [(p["_id"], a) for p in pacs for a in p.get("alergias", [])])
    cur.executemany("INSERT INTO profesional VALUES (%s,%s,%s,%s,%s)",
                    [(p["_id"], p["nombre"], p["rol"], p.get("especialidad"), p["registro_medico"]) for p in leer("profesionales")])
    cur.executemany("INSERT INTO cama VALUES (%s,%s,%s,%s)", [(c["_id"], c["ips"], c["servicio"], c["estado"]) for c in leer("camas")])
    filas = []
    for h in hosp:
        dx = next((d["cie10"] for d in h["diagnosticos"] if d["tipo"] == "PRINCIPAL"), h["diagnosticos"][0]["cie10"])
        egreso = fecha(h["alta"]["fecha"]) if h.get("alta") else None
        filas.append((h["_id"], h["paciente_id"], h["medico_tratante_id"], h["cama"], h["servicio"], fecha(h["fecha_admision"]),
                      egreso, dx, h["estado"]))
    cur.executemany("INSERT INTO hospitalizacion VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", filas)

    # Dispositivos: cada episodio recibe los que su servicio y diagnostico justifican.
    disp, asig, n = [], [], 0
    def nuevo(tipo, modelo, seg, h):
        global n
        n += 1; did = f"DSP-{n:04d}"
        disp.append((did, tipo, modelo, seg))
        asig.append((did, h["_id"], fecha(h["fecha_admision"]), fecha(h["alta"]["fecha"]) if h.get("alta") else None))
    for h in hosp:
        dxs = {d["cie10"] for d in h["diagnosticos"]}
        nuevo("OXIMETRO_WEARABLE", "Pulsera SpO2 BLE v2", 120, h)                       # todos: oximetria continua
        if h["servicio"] in ("MEDICINA_INTERNA", "UCI"):
            nuevo("MONITOR_MULTIPARAMETRO", "Monitor 5 parametros M540", 60, h)
        if any(c.startswith("E11") for c in dxs):
            nuevo("GLUCOMETRO_CGM", "Sensor CGM 14 dias", 300, h)                      # diabeticos: glucosa continua
        if h["servicio"] == "UCI" or dxs & {"A91"}:
            nuevo("BOMBA_INFUSION", "Bomba volumetrica BV-3", 1, h)                    # emite por eventos, no por periodo
    cur.executemany("INSERT INTO dispositivo VALUES (%s,%s,%s,%s)", disp)
    cur.executemany("INSERT INTO asignacion_dispositivo (dispositivo_id,hospitalizacion_id,desde,hasta) VALUES (%s,%s,%s,%s)", asig)
    con.commit()
except Exception as e:
    con.rollback(); sys.exit(f"ROLLBACK: {e}")

for t in ["cie10", "medicamento", "paciente", "paciente_alergia", "profesional", "cama", "hospitalizacion", "dispositivo",
          "asignacion_dispositivo"]:
    cur.execute(f"SELECT count(*) FROM {t}"); print(f"  {t:24}{cur.fetchone()[0]}")
cur.execute("SELECT tipo, count(*) FROM dispositivo GROUP BY tipo ORDER BY 2 DESC")
print("  dispositivos por tipo: " + ", ".join(f"{t}={c}" for t, c in cur.fetchall()))
cur.execute("SELECT count(*) FROM hospitalizacion WHERE estado='ACTIVA'"); print(f"  hospitalizaciones activas: {cur.fetchone()[0]}")
con.close()
