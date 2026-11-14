// =====================================================================
// 03_mongo_esquema.js  -  Capa BASE de la arquitectura hibrida (MongoDB 8.x)
// Ejecutar: mongosh --file scripts/03_mongo_esquema.js
//
// Que vive aqui (y por que):
//   * telemetria: lecturas de monitores, wearables, glucometros continuos y
//     bombas de infusion. Llegan cada 30 s - 5 min por dispositivo, nunca se
//     modifican, cada tipo trae campos distintos y el volumen crece sin parar.
//     Se usa una coleccion TIME SERIES: MongoDB agrupa internamente las lecturas
//     por dispositivo y ventana de tiempo (buckets) y las comprime.
//   * teleconsultas: eventos de seguimiento posteriores al alta, con estructura
//     variable (adjuntos, signos reportados por el paciente, transcripcion).
// Las lecturas solo guardan el dispositivo_id y el episodio (seudonimo): la
// identidad del paciente NO sale de PostgreSQL.
// =====================================================================
const t = db.getSiblingDB("hce_telemetria");
t.dropDatabase();

t.createCollection("telemetria", {
  timeseries: { timeField: "ts", metaField: "meta", granularity: "seconds" },
  expireAfterSeconds: 60 * 60 * 24 * 365 * 2      // retencion de la telemetria cruda: 2 anos (el resumen clinico queda en la HCE)
});
// Limitacion encontrada: MongoDB rechaza validadores $jsonSchema en colecciones
// time series ("option not supported on a time-series collection: validator").
// Por eso la validacion de rangos (SpO2 50-100, FC 20-250, glucosa 20-600) se hace
// en la capa de ingesta (04_ingesta_telemetria.py, funcion valida) y cada lectura
// descartada se cuenta. Es el precio de la ingesta rapida: el motor no protege el dato.
t.telemetria.createIndex({ "meta.dispositivo_id": 1, ts: -1 }, { name: "ix_dispositivo_ts" });
t.telemetria.createIndex({ "meta.hosp": 1, ts: -1 }, { name: "ix_episodio_ts" });

t.createCollection("teleconsultas", { validator: { $jsonSchema: {
  bsonType: "object", required: ["hosp", "fecha", "modalidad", "especialidad"],
  properties: { hosp: { bsonType: "string" }, fecha: { bsonType: "date" },
    modalidad: { enum: ["VIDEO", "TELEFONO", "MENSAJERIA"] }, especialidad: { bsonType: "string" },
    duracion_min: { bsonType: "int", minimum: 1 }, adjuntos: { bsonType: "array" } } } } });
t.teleconsultas.createIndex({ hosp: 1, fecha: -1 }, { name: "ix_teleconsulta_episodio" });

print("Base 'hce_telemetria' creada:");
t.getCollectionInfos().forEach(c => print("  " + c.name.padEnd(28) + c.type + (c.options.timeseries ? "  " + JSON.stringify(c.options.timeseries) : "")));
["telemetria", "teleconsultas"].forEach(c => t[c].getIndexes().forEach(i => print("  indice " + c.padEnd(15) + i.name)));
