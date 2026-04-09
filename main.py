from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
import psycopg2.extras
import os

app = FastAPI(title="Calc API", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# --- DB connection ---
# Reads the DATABASE_URL we set in docker-compose environment
# e.g. postgresql://skander:llstylish@db:5432/calcdb
# "db" is the hostname — docker resolves it to the postgres container

def get_db():
    conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
    return conn


# --- Create table on startup ---
# Runs once when FastAPI starts
# CREATE TABLE IF NOT EXISTS means it won't crash if table already exists

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id         SERIAL PRIMARY KEY,
            operation  TEXT NOT NULL,
            a          FLOAT NOT NULL,
            b          FLOAT NOT NULL,
            result     FLOAT,
            error      TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()


# --- Models ---

class TwoNumbers(BaseModel):
    a: float
    b: float


# --- Helper to save every calculation ---
# %s is the postgres placeholder (sqlite used ?)
# result and error are optional — one will always be None

def save(operation, a, b, result=None, error=None):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO history (operation, a, b, result, error) VALUES (%s, %s, %s, %s, %s)",
        (operation, a, b, result, error)
    )
    conn.commit()
    cur.close()
    conn.close()


# --- Health ---

@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0"}


# --- Calculations ---
# Each endpoint does the math, saves to db, returns result

@app.post("/add")
def add(payload: TwoNumbers):
    result = payload.a + payload.b
    save("add", payload.a, payload.b, result=result)
    return {"result": result}

@app.post("/subtract")
def subtract(payload: TwoNumbers):
    result = payload.a - payload.b
    save("subtract", payload.a, payload.b, result=result)
    return {"result": result}

@app.post("/multiply")
def multiply(payload: TwoNumbers):
    result = payload.a * payload.b
    save("multiply", payload.a, payload.b, result=result)
    return {"result": result}

@app.post("/divide")
def divide(payload: TwoNumbers):
    if payload.b == 0:
        save("divide", payload.a, payload.b, error="Division by zero")
        raise HTTPException(status_code=400, detail="Division by zero")
    result = payload.a / payload.b
    save("divide", payload.a, payload.b, result=result)
    return {"result": result}

@app.post("/power")
def power(payload: TwoNumbers):
    result = payload.a ** payload.b
    save("power", payload.a, payload.b, result=result)
    return {"result": result}


# --- History endpoints ---

# GET /history — returns last 20 calculations by default
# ?limit=50 to get more, e.g. curl http://localhost:8080/api/history?limit=50
@app.get("/history")
def history(limit: int = 20):
    conn = get_db()
    # RealDictCursor makes rows return as dicts instead of tuples
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM history ORDER BY created_at DESC LIMIT %s", (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# DELETE /history — wipes all records
@app.delete("/history")
def clear_history():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM history")
    conn.commit()
    cur.close()
    conn.close()
    return {"message": "History cleared"}