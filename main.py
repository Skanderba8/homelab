from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Calc API", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# --- Models ---

class TwoNumbers(BaseModel):
    a: float
    b: float


# --- Health ---

@app.get("/health")
def health():
    return {"status": "ok"}


# --- Calculations ---

@app.post("/add")
def add(payload: TwoNumbers):
    return {"result": payload.a + payload.b}


@app.post("/subtract")
def subtract(payload: TwoNumbers):
    return {"result": payload.a - payload.b}


@app.post("/multiply")
def multiply(payload: TwoNumbers):
    return {"result": payload.a * payload.b}


@app.post("/divide")
def divide(payload: TwoNumbers):
    if payload.b == 0:
        raise HTTPException(status_code=400, detail="Division by zero")
    return {"result": payload.a / payload.b}


@app.post("/power")
def power(payload: TwoNumbers):
    return {"result": payload.a ** payload.b}