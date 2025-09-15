from fastapi import FastAPI
from app.api.timetable import router as timetable_router

app = FastAPI(title="NEP Timetable Generator")

app.include_router(timetable_router)

@app.get("/")
async def root():
    return {"message": "Welcome to the NEP 2020 Timetable Generator!"}