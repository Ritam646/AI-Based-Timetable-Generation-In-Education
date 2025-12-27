# from fastapi import FastAPI
# from app.api.timetable import router as timetable_router

# app = FastAPI(title="NEP Timetable Generator")

# app.include_router(timetable_router)

# @app.get("/")
# async def root():
#     return {"message": "Welcome to the NEP 2020 Timetable Generator!"}

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.timetable import router as timetable_router

app = FastAPI(
    title="NEP 2020 AI Timetable Generator",
    description="Automated timetable for schools under NEP 2020",
    version="1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(timetable_router)

@app.get("/")
def home():
    return {"message": "Welcome to NEP 2020 AI Timetable Generator! Visit /docs for API"}