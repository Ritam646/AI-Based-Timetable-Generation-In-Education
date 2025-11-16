# backend-rp/main.py
from fastapi import FastAPI
from rag_utils import generate_timetable

app = FastAPI()

@app.get("/generate_timetable")
def get_timetable(dept: str, sem: str):
    routine = generate_timetable(dept, sem)
    return {"routine": routine}