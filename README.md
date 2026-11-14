# Ecosistema híbrido PostgreSQL + MongoDB: HCE básica, hospitalización

Bases de Datos II (G101), Unidad 3, tarea **«Construyendo y comparando ecosistemas híbridos»**. Henry Taborda, trabajo individual.

El proyecto toma los datos de la Unidad 3 y los reparte en dos capas:

- **Capa ACID (PostgreSQL):** identidad del paciente, profesionales, catálogos, camas, hospitalizaciones y registro de dispositivos.
- **Capa BASE (MongoDB):** telemetría de monitores, oxímetros, glucómetros continuos y bombas de infusión, más las teleconsultas.

La misma operación se mide en los dos motores.

| Archivo | Qué hace |
|---|---|
| `Grupo1_AE4_U3.pdf` | Informe técnico |
| `scripts/01_postgres_esquema.sql` | Esquema `hce`: tablas, FK, CHECK, índices únicos parciales y vista seudonimizada |
| `scripts/02_cargar_postgres.py` | Carga los datos de la U3 (`datos_origen/`) y los dispositivos en **una transacción** |
| `scripts/03_mongo_esquema.js` | Base `hce_telemetria`: colección *time series* `telemetria` y `teleconsultas` |
| `scripts/04_ingesta_telemetria.py` | Genera unas 306 mil lecturas coherentes con cada episodio y las ingiere en los dos motores (B1) |
| `scripts/05_analisis_comparativo.py` | Pruebas B1–B5 (mediana y p95 de 15 ejecuciones) y la prueba de atomicidad T1 |
| `scripts/06_graficas_y_diagrama.py` | Diagrama de arquitectura y gráficas a partir de las métricas |
| `scripts/07_generar_capturas.py` | Capturas estilo consola de las salidas reales |
| `resultados/` | Salidas reales (`salida_0X_*.txt`), `metricas.csv`, `metricas.json` y `b1_ingesta.json` |
| `ia_evidencia/EVIDENCIA_IA.md` | Prompts, errores reales y aporte de la IA |
| `video/GUION_VIDEO.md` | Guion del video. Video (sin narración, con subtítulos): https://youtu.be/3SBGj9TeUA8 |
| `video/subtitulos/`, `video/musica_fondo.py` | Texto de los subtítulos y generador de la música de fondo original |

## Reproducir

**Requisitos:** Docker, MongoDB 8.x en `127.0.0.1:27017`, Python 3.11+ con `psycopg2-binary pymongo matplotlib pillow reportlab`.

```bash
# 1. PostgreSQL (cualquier imagen 16+; se probó con 17.11)
docker run -d --name hce_pg -e POSTGRES_PASSWORD=hce_local -p 127.0.0.1:5433:5432 postgres:17
docker exec hce_pg psql -U postgres -c "CREATE DATABASE hce_hibrido"
docker exec -i hce_pg psql -U postgres -d hce_hibrido < scripts/01_postgres_esquema.sql

# 2. Capa ACID, capa BASE e ingesta
python scripts/02_cargar_postgres.py
mongosh --file scripts/03_mongo_esquema.js
python scripts/04_ingesta_telemetria.py

# 3. Comparación, gráficas, capturas e informe
python scripts/05_analisis_comparativo.py
python scripts/06_graficas_y_diagrama.py
python scripts/07_generar_capturas.py
python informe_fuente/generar_informe.py
```

La conexión se puede cambiar con las variables `HCE_PG_DSN` y `HCE_MONGO_URI` (ver `scripts/conexion.py`).

Los datos generados son siempre los mismos (semilla 866). Los tiempos sí cambian según el equipo: el informe lee las cifras de `resultados/`.

## Resultados principales

Medidos en un portátil con Windows 11, con los demás contenedores de Docker en pausa. Los valores exactos están en `resultados/metricas.csv`.

| Prueba | Resultado |
|---|---|
| B1, ingesta | MongoDB más rápido |
| Disco | MongoDB más de 30 veces menor (buckets comprimidos frente a JSONB con índices) |
| B2–B3, consultas puntuales con índice | Tiempos parecidos en los dos motores |
| B4, análisis de todo el hospital | MongoDB unas 3 veces más rápido. PostgreSQL hace *Seq Scan* porque el GIN `jsonb_path_ops` no sirve para rangos |
| B5, tablero híbrido frente a solo PostgreSQL | Mismo orden de magnitud |
| T1, cama ocupada | PostgreSQL rechaza la admisión y hace ROLLBACK completo. MongoDB guarda 4 de 5 lecturas (escritura parcial) |

Todos los datos son **ficticios**. La identidad del paciente no sale de PostgreSQL: MongoDB solo guarda `dispositivo_id` y el `hospitalizacion_id` del episodio.

Documentación generada y revisada con apoyo de IA (Claude Code), según `ia_evidencia/EVIDENCIA_IA.md`.
