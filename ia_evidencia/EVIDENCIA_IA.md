# Evidencia del uso de IA: Unidad 3, ecosistema híbrido (PostgreSQL + MongoDB)

- **Herramienta:** Claude Code (Anthropic, modelo Claude Opus 5.5). Corrió en el equipo del autor con acceso a la terminal, a los archivos del proyecto, a PostgreSQL 17.11 (contenedor Docker local) y a MongoDB 8.3.7 local.
- **Fechas:** del 8 al 12 de noviembre de 2026.
- **Regla de trabajo:** todo lo que la IA propuso se ejecutó contra los dos motores reales. Las cifras del informe salen de las salidas guardadas en `resultados/`, no de texto escrito a mano.

## Interacción 1: diseño de la división ACID/BASE

> «Haz la tarea "Construyendo y comparando ecosistemas híbridos" siguiendo lo que ya hicimos en la asignatura. [Enunciado completo, insumo "Integración de PostgreSQL con NoSQL para IoT y big data" y libro "Arquitecturas NoSQL e híbridas"]»

**Resultado.** La IA leyó la entrega de la Unidad 3 (modelo documental de hospitalización en MongoDB) y propuso no empezar de cero:

- **Capa ACID (PostgreSQL).** Lleva la identidad del paciente, los profesionales, los catálogos, las camas y las hospitalizaciones. Todos se exportaron de la U3.
- **Capa BASE (MongoDB).** Lleva la telemetría de cuatro tipos de dispositivo y las teleconsultas.
- **Puente nuevo.** El registro de dispositivos (`dispositivo` + `asignacion_dispositivo`) vive en PostgreSQL. Es lo que permite saber a qué episodio pertenece cada lectura sin copiar la identidad del paciente en MongoDB.

**Aporte.** La arquitectura continúa el proyecto. Cada tabla y cada colección tiene una razón explícita para estar donde está.

## Interacción 2: telemetría coherente con la historia clínica

**Prompt:** «Los datos de los sensores tienen que tener sentido clínico, no ser aleatorios».

**Resultado.** La ingesta (`04_ingesta_telemetria.py`) **interpola entre las tomas de signos vitales reales** de cada episodio de la U3. Por eso cada curva coincide con su historia:

- El paciente con neumonía (HOSP-2026-0029) muestra SpO₂ de 87–88 % en su monitor.
- El glucómetro del diabético baja de ~340 a ~150 mg/dL.

La IA también inyectó artefactos de sensor (`fc = 400`, cable suelto) para demostrar la validación de rangos: se descartaron 72.

## Interacción 3: errores reales y cómo se corrigieron

| Error | Causa | Corrección |
|---|---|---|
| `option not supported on a time-series collection: validator` | MongoDB no admite `$jsonSchema` en colecciones *time series* | La validación de rangos pasó a la ingesta (`valida()`) y se documentó la limitación en `03_mongo_esquema.js`. |
| `value too long for type character varying(20)` | `MONITOR_MULTIPARAMETRO` tiene 22 caracteres | `tipo` se amplió a `VARCHAR(24)`. La carga hizo **ROLLBACK completo**: no quedó ninguna tabla a medias, una demostración involuntaria de atomicidad. |
| `[Errno 22] Invalid argument` en `fromtimestamp` | Windows no convierte milisegundos negativos (nacimientos antes de 1970) | Se cambió a `EPOCA + timedelta(milliseconds=…)`. |
| `collStats` devolvía 0 MB para la telemetría | En *time series* el tamaño vive en los *buckets* y solo se refleja tras el checkpoint | Se usa `fsync` + `$collStats.storageStats`. |
| `permission denied to execute CHECKPOINT` | El rol del contenedor no es superusuario | Se eliminó: `pg_total_relation_size` no lo necesita. |
| `SyntaxError: 'yield' inside list comprehension` | Generador recursivo mal escrito por la IA | Se reescribió como función generadora normal. |

## Interacción 4: una comparación que la IA tuvo que corregir

**Lo que pasó.** La primera ejecución de B5 imprimió `mismo resultado en las dos versiones: False`.

**Análisis de la IA.** Comparó fila por fila y encontró la diferencia: solo en HOSP-2026-0032 la «última SpO₂» daba 98 en MongoDB y 97 en PostgreSQL. El oxímetro y el monitor del paciente reportan **en el mismo segundo**, y cada motor desempataba de forma distinta.

**Corrección.** Se agregó un desempate determinista por `dispositivo_id` en los dos motores (`$sort {ts, meta.dispositivo_id}` y `ORDER BY ts DESC, dispositivo_id`). Ahora el resultado es idéntico.

**Aporte.** Sin esta verificación, el tablero habría mostrado valores distintos según el motor. Comparar latencias solo tiene sentido si las dos consultas devuelven lo mismo.

## Interacción 5: índices sugeridos y verificados con el plan de ejecución

**Prompt:** «Sugiere los índices de cada motor y comprueba si se usan».

**Índices sugeridos:**

- **MongoDB:** `{meta.dispositivo_id, ts}` y `{meta.hosp, ts}`.
- **PostgreSQL:** `(dispositivo_id, ts)` y un GIN `jsonb_path_ops` sobre `lectura`, como en el insumo del curso.

**Verificación.** `EXPLAIN ANALYZE` de B4 mostró `Seq Scan telemetria_jsonb`: el índice GIN **no se usa** con `(lectura->>'spo2')::int < 90`, porque `jsonb_path_ops` solo acelera la contención (`@>`), no los rangos.

**Aporte.** El informe explica que el índice del insumo sirve para buscar «lecturas con este valor exacto», no «SpO₂ menor que 90». En PostgreSQL un rango sobre un atributo del JSON necesita un índice de expresión o una columna tipada.

## Interacción 6: medición honesta

**Lo que pasó.** La IA midió primero con el equipo ocupado (Docker y la síntesis de voz corriendo a la vez) y los tiempos variaron hasta tres veces.

**Decisión.** La IA revisó `docker stats` y encontró otro clúster de Docker consumiendo unos 4 núcleos en la misma máquina virtual que PostgreSQL: con esa carga, B4 en PostgreSQL pasaba de unos 30 ms a más de 700 ms, mientras MongoDB (nativo) casi no cambiaba. Con autorización del autor, el clúster se pausó solo durante la medición y se reanudó al terminar. Se reporta **mediana y p95 de 15 ejecuciones**, con 3 de calentamiento, en lugar de una sola corrida. El informe aclara que son mediciones de laboratorio en un portátil, no una prueba de carga de producción.

## Prompts reutilizables

- «Esta consulta da resultados distintos en PostgreSQL y en MongoDB: compárame fila por fila y dime por qué».
- «Muéstrame el plan de ejecución de esta consulta y dime si usa el índice; si no, explica por qué».
- «¿Qué dato de este modelo debe vivir en una capa ACID y cuál en una BASE? Justifica con consistencia, volumen y frecuencia de cambio».
- «Genera un pipeline de agregación que resuma la telemetría de las últimas 6 horas por episodio».

## Responsabilidad humana

Todos los datos son sintéticos y la IA nunca recibió datos reales de pacientes. El autor revisó cada script, puede explicarlo y es responsable de las decisiones de diseño.
