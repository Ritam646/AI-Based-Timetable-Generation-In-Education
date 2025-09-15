from fastapi import APIRouter, UploadFile, File, HTTPException
from app.agents.data_curator import DataCuratorAgent
from app.agents.policy_agent import PolicyComplianceAgent
from app.agents.timetable_generator import TimetableGeneratorAgent
from app.agents.negotiator import NegotiatorAgent  # Add this import
import os
import shutil
import json

router = APIRouter(prefix="/timetable", tags=["timetable"])

@router.post("/upload/{table_name}")
async def upload_data(table_name: str, file: UploadFile = File(...)):
    if file.content_type != "text/csv":
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        curator = DataCuratorAgent()
        cleaned_df, errors = curator.validate_and_clean(temp_path, table_name)
        if not errors:
            result = curator.save_to_supabase(cleaned_df, table_name)
            os.remove(temp_path)
            return {"message": "Data uploaded successfully", "details": result, "errors": errors}
        else:
            os.remove(temp_path)
            return {"message": "Data processed with warnings", "errors": errors}
    except Exception as e:
        os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"Error processing upload: {str(e)}")

@router.get("/validate-constraints")
async def validate_constraints():
    try:
        agent = PolicyComplianceAgent()
        result = agent.validate_constraints()
        return {
            "message": "Constraints validated",
            "violations": result["violations"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating constraints: {str(e)}")

@router.post("/generate/{program}")
async def generate_timetable(program: str):
    try:
        agent = TimetableGeneratorAgent()
        timetable = agent.generate_timetable(program)
        return {
            "message": f"Timetable generated for {program}",
            "timetable": timetable
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating timetable: {str(e)}")

@router.post("/negotiate/{program}")
async def negotiate_timetable(program: str):
    try:
        agent = NegotiatorAgent()
        result = agent.resolve_conflicts(program)
        return {
            "message": f"Timetable negotiated for {program}",
            "conflicts": result["conflicts"],
            "timetable": result["timetable"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error negotiating timetable: {str(e)}")