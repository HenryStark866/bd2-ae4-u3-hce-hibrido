# Guion del video: AE4-U3, ecosistema híbrido

- **Duración objetivo:** 8 a 10 minutos.
- **Narración:** voz clonada de Henry Taborda, generada con IA (ElevenLabs). El video lo indica en la portada y en una franja permanente.
- **Pantalla:** salidas y métricas reales (`resultados/`), diagrama y gráficas (`capturas/`) y secciones del informe.

## a00_intro
*En pantalla:* Portada con aviso de voz IA · resumen del informe

Hola, soy Henry Taborda, de Bases de Datos Dos. Esta es mi entrega de la tarea Construyendo y comparando ecosistemas híbridos, de la unidad tres, que hice de forma individual.

Una aclaración antes de empezar: la narración de este video es mi voz clonada, generada con inteligencia artificial.

El reto es dar el paso de un solo motor a una arquitectura híbrida. En la unidad tres, la historia clínica de hospitalización vivía completa en MongoDB, con unas tres tomas de signos vitales al día por paciente. Ahora llegan monitores, oxímetros portátiles, glucómetros continuos y bombas de infusión que reportan cada uno a cinco minutos. La pregunta es qué dato debe vivir en un sistema ACID y cuál en uno BASE, y demostrarlo con mediciones.

## a01_division
*En pantalla:* Tabla ACID vs. BASE y qué dato vive en cada capa

Empiezo por la división. Tomé como referencia la tabla del libro del curso sobre arquitecturas híbridas. El modelo ACID ofrece consistencia fuerte y disponibilidad limitada, y sirve como sistema de registro. El modelo BASE ofrece disponibilidad alta y consistencia eventual, y sirve como sistema de análisis.

En la capa ACID, en Postgres, dejé lo que no puede equivocarse: la identidad del paciente, que es un dato sensible según la ley mil quinientos ochenta y uno, los profesionales, los catálogos de diagnósticos y medicamentos, las camas y las hospitalizaciones. Dos pacientes en la misma cama, o un documento duplicado, son errores clínicos.

En la capa BASE, en MongoDB, va la telemetría de los dispositivos y las teleconsultas posteriores al alta. Se escribe sin parar, nunca se modifica, cada sensor trae campos distintos y crece sin límite.

Y hay una pieza que une las dos capas: el registro de dispositivos, que vive en Postgres y dice a qué episodio pertenece cada oxímetro o cada monitor.

## a02_diagrama
*En pantalla:* Diagrama de arquitectura

Este es el diagrama de la arquitectura. A la izquierda, los usuarios clínicos escriben en Postgres: admisiones, altas y asignación de dispositivos. Los sensores, en cambio, pasan por un proceso de ingesta que valida los rangos fisiológicos y escribe por lotes en MongoDB.

La llave puente es el identificador del dispositivo y el identificador de la hospitalización. MongoDB nunca guarda el nombre, el documento ni la EPS del paciente: solo el código del episodio, que funciona como un seudónimo.

A la derecha está la aplicación, que une las dos capas. Por ejemplo, el tablero de pacientes activos pide a Postgres los episodios activos, desde una vista que no expone el nombre, pide a MongoDB el resumen de las últimas seis horas, y los une en memoria. No hay llaves foráneas entre los dos motores, así que la coherencia del puente es responsabilidad de la aplicación.

## a03_postgres
*En pantalla:* Terminal: 01_postgres_esquema.sql y 02_cargar_postgres.py

Ahora la implementación. Primero la capa ACID. Ejecuto el script del esquema en Postgres: crea diez tablas y diecinueve índices.

Lo más importante está en las restricciones. Hay dos índices únicos parciales sobre las hospitalizaciones activas: uno impide que una cama tenga dos pacientes activos, y otro impide que un paciente tenga dos ingresos activos a la vez. Además hay una vista seudonimizada, que solo muestra edad, sexo, subregión y episodio, y es lo único que se cruza con la telemetría.

Luego cargo los datos. No inventé datos nuevos: son los mismos veinticinco pacientes, nueve profesionales, treinta camas y treinta y seis hospitalizaciones de la unidad tres, con los mismos identificadores. Todo se carga en una sola transacción. Cada episodio recibe los dispositivos que su servicio justifica: oxímetro para todos, monitor en medicina interna y cuidados intensivos, glucómetro continuo si tiene diabetes, y bomba de infusión en los casos graves. En total, setenta y seis dispositivos.

## a04_mongo_ingesta
*En pantalla:* Terminal: 03_mongo_esquema.js y 04_ingesta_telemetria.py · tabla de dispositivos

Después la capa BASE. En MongoDB creo la telemetría como una colección de series de tiempo. MongoDB agrupa las lecturas de un mismo dispositivo en buckets por ventana de tiempo y las comprime.

Aquí encontré una limitación real: MongoDB no permite validadores de esquema en las colecciones de series de tiempo. Por eso la validación de rangos, como saturación entre cincuenta y cien, se hace en el script de ingesta.

La ingesta genera la telemetría a partir de los signos vitales reales de cada episodio de la unidad tres, interpolando entre una toma y la siguiente. Así, el paciente con neumonía, que en la unidad tres tenía la alerta de deterioro más alta, muestra en su monitor la misma saturación de ochenta y siete a ochenta y ocho por ciento. También inyecté artefactos de sensor, como una frecuencia cardiaca de cuatrocientos por un cable suelto, y la validación descartó setenta y dos lecturas.

El resultado: trescientas seis mil trescientas cincuenta y nueve lecturas, con el mismo conteo en los dos motores, porque la misma telemetría también se cargó en Postgres con JSONB, como propone el insumo del curso, para poder comparar.

## a05_metodo_b1
*En pantalla:* Método y tabla de métricas · terminal B1 · gráfica de ingesta y disco

Vamos al análisis comparativo. Cada consulta se ejecuta tres veces para calentar la caché y quince veces medidas, y reporto la mediana y el percentil noventa y cinco. Antes de comparar tiempos, verifico que los dos motores devuelvan exactamente el mismo resultado.

Un detalle de honestidad: la primera vez que medí, había otro clúster corriendo en la misma máquina virtual de Docker que Postgres. Con esa carga, Postgres llegaba a ser diez veces más lento, mientras que MongoDB casi no cambiaba. Por eso pausé ese clúster solo durante la medición. Comparar con cargas distintas habría dado conclusiones falsas.

La primera prueba es la ingesta. Con la telemetría completa, MongoDB insertó unas treinta y ocho mil lecturas por segundo, y Postgres unas veinte mil: casi el doble. En las ingestas repetidas de cincuenta mil lecturas la diferencia es de más de cuatro veces. Y en disco la diferencia es enorme: la misma telemetría ocupa unos dos coma seis megas en MongoDB y unos ochenta y ocho en Postgres, más de treinta veces más.

## a06_b2_b4
*En pantalla:* Terminal: B2, B3 y B4 (con plan de ejecución) · gráfica de latencia

Las pruebas dos y tres son consultas puntuales: la última lectura de un monitor, y el promedio por hora de frecuencia cardiaca y saturación de un paciente en las últimas veinticuatro horas. Aquí Postgres fue igual o más rápido: alrededor de medio milisegundo frente a un milisegundo en la última lectura, y tiempos casi iguales en el promedio horario.

La prueba cuatro es la diferencia grande: buscar en todo el hospital los episodios con saturación menor a noventa en la última semana. MongoDB lo resolvió en unos diez milisegundos y Postgres en unos veintiocho, casi tres veces más. Los dos encuentran los mismos tres episodios. El plan de ejecución de Postgres explica por qué: recorre toda la tabla. El índice GIN del insumo, con jsonb path ops, solo sirve para buscar valores exactos por contención, no rangos como menor que noventa. Esto lo comprobé con el plan de ejecución, a partir de una revisión de índices que le pedí a la inteligencia artificial.

## a07_b5_t1
*En pantalla:* Terminal: B5 (tablero híbrido) y T1 (atomicidad)

La prueba cinco es la consulta híbrida: el tablero de los siete pacientes activos, con su servicio, cama, edad y diagnóstico desde Postgres, y su saturación mínima, frecuencia máxima y última saturación desde MongoDB. La comparé con una versión que hace todo en Postgres con JSONB. Los resultados son idénticos y los tiempos están en el mismo orden: unos once milisegundos la híbrida y unos siete la de solo Postgres. Unir dos motores no castiga la latencia de un tablero, pero sí agrega complejidad: dos conexiones, dos lenguajes de consulta y el código de unión.

Y la prueba que más importa no es de velocidad, es de atomicidad. Intento admitir a un paciente en la cama MI doscientos uno, que está ocupada, y en la misma transacción asignarle un dispositivo. Postgres rechaza la admisión por el índice único de cama activa y deshace toda la transacción: había treinta y seis hospitalizaciones antes y treinta y seis después. En MongoDB, un lote de cinco lecturas con una inválida guarda las cuatro válidas. Para telemetría eso es lo correcto: no se pierden cuatro lecturas buenas por una mala. Para una admisión sería inaceptable.

## a08_cualitativo_ia
*En pantalla:* Análisis cualitativo · tabla de evidencia de IA

En lo cualitativo: en flexibilidad, si llega un capnógrafo con un campo nuevo, en MongoDB basta con insertar; en Postgres con columnas habría que alterar la tabla, y con JSONB cada consulta necesita conversiones e índices nuevos. En integridad, Postgres protege el dato con llaves foráneas y restricciones; en MongoDB la ingesta tiene que hacerlo.

Sobre la inteligencia artificial: usé Claude Code, con acceso a los dos motores, y la regla fue ejecutar todo lo que proponía y aceptar solo lo que la ejecución confirmaba. Me ayudó a diseñar la división y a corregir errores reales: el validador rechazado en series de tiempo, un tipo de dispositivo más largo de lo permitido, que hizo un rollback completo de la carga, y fechas anteriores a mil novecientos setenta en Windows. Lo más valioso fue cuando el tablero híbrido dio resultados distintos entre motores: comparó fila por fila y encontró que el oxímetro y el monitor reportaban en el mismo segundo y cada motor desempataba distinto. Agregamos un desempate determinista y ahora coinciden.

## a09_etica_cierre
*En pantalla:* Reflexión técnica y ética · repositorio

Para cerrar, la reflexión. Separar la identidad no es solo una decisión de rendimiento, es una medida de privacidad: una fuga de la base de telemetría expone curvas de saturación de episodios, no personas. Pero seudónimo no es anónimo: con edad, sexo, subregión y fecha, un paciente de un municipio pequeño se puede reidentificar, así que los reportes deben agregar y suprimir celdas pequeñas.

La consistencia eventual también tiene consecuencias clínicas: un tablero con datos de hace treinta segundos es aceptable, una alarma que llega tarde no. Y descartar lecturas es una decisión clínica: los descartes se cuentan y se auditan, no desaparecen en silencio.

En conclusión, no hay un motor ganador, hay datos con necesidades distintas. MongoDB fue mejor para ingerir, almacenar y analizar la telemetría masiva, y Postgres fue indispensable para garantizar que una cama no se asigne dos veces. Esta arquitectura queda lista como base del proyecto integrador. Gracias.
