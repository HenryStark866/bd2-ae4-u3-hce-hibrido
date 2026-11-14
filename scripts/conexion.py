"""Conexiones compartidas por los scripts. Entorno local de pruebas: PostgreSQL 17.11 en Docker (puerto 5433; sirve 16+)
y MongoDB 8.3 local. La clave por defecto es solo del contenedor de pruebas; en otro entorno use variables."""
import os
import psycopg2
from pymongo import MongoClient

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PG_DSN = os.environ.get("HCE_PG_DSN", "host=127.0.0.1 port=5433 dbname=hce_hibrido user=postgres password=hce_local")
MONGO_URI = os.environ.get("HCE_MONGO_URI", "mongodb://127.0.0.1:27017")


def pg():
    con = psycopg2.connect(PG_DSN)
    with con.cursor() as c:
        c.execute("SET search_path TO hce")
    return con


def mongo():
    return MongoClient(MONGO_URI)["hce_telemetria"]
