# from fastapi import APIRouter, UploadFile, File, HTTPException
# from app.agents.data_curator import DataCuratorAgent
# from app.agents.policy_agent import PolicyComplianceAgent
# from app.agents.timetable_generator import TimetableGeneratorAgent
# from app.agents.negotiator import NegotiatorAgent  # Add this import
# import os
# import shutil
# import json

# router = APIRouter(prefix="/timetable", tags=["timetable"])

# @router.post("/upload/{table_name}")
# async def upload_data(table_name: str, file: UploadFile = File(...)):
#     if file.content_type != "text/csv":
#         raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
#     temp_path = f"temp_{file.filename}"
#     with open(temp_path, "wb") as buffer:
#         shutil.copyfileobj(file.file, buffer)
    
#     try:
#         curator = DataCuratorAgent()
#         cleaned_df, errors = curator.validate_and_clean(temp_path, table_name)
#         if not errors:
#             result = curator.save_to_supabase(cleaned_df, table_name)
#             os.remove(temp_path)
#             return {"message": "Data uploaded successfully", "details": result, "errors": errors}
#         else:
#             os.remove(temp_path)
#             return {"message": "Data processed with warnings", "errors": errors}
#     except Exception as e:
#         os.remove(temp_path)
#         raise HTTPException(status_code=500, detail=f"Error processing upload: {str(e)}")

# @router.get("/validate-constraints")
# async def validate_constraints():
#     try:
#         agent = PolicyComplianceAgent()
#         result = agent.validate_constraints()
#         return {
#             "message": "Constraints validated",
#             "violations": result["violations"]
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error validating constraints: {str(e)}")

# @router.post("/generate/{program}")
# async def generate_timetable(program: str):
#     try:
#         agent = TimetableGeneratorAgent()
#         timetable = agent.generate_timetable(program)
#         return {
#             "message": f"Timetable generated for {program}",
#             "timetable": timetable
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error generating timetable: {str(e)}")

# @router.post("/negotiate/{program}")
# async def negotiate_timetable(program: str):
#     try:
#         agent = NegotiatorAgent()
#         result = agent.resolve_conflicts(program)
#         return {
#             "message": f"Timetable negotiated for {program}",
#             "conflicts": result["conflicts"],
#             "timetable": result["timetable"]
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error negotiating timetable: {str(e)}")


from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd
import io
from app.agents.data_curator import DataCuratorAgent

router = APIRouter(prefix="/timetable", tags=["timetable"])

@router.post("/upload/{table_name}")
async def upload_csv(table_name: str, file: UploadFile = File(...)):
    # Basic validation
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")

    try:
        # Read the file content
        contents = await file.read()
        # Decode and read with pandas
        df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        
        if df.empty:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        # Log for debugging
        print(f"Received {len(df)} rows for table {table_name}")
        print(f"Columns: {list(df.columns)}")
        print(f"First row: {df.iloc[0].to_dict()}")

        # Use the agent
        agent = DataCuratorAgent()
        cleaned_df, errors = agent.clean_and_validate(df, table_name)

        if errors:
            return JSONResponse(
                status_code=400,
                content={
                    "message": "Validation errors",
                    "errors": errors,
                    "preview": cleaned_df.head(5).to_dict(orient="records")
                }
            )

        # Upload to Supabase
        result = agent.upload_to_supabase(cleaned_df, table_name)
        
        return {
            "message": f"Successfully uploaded {len(cleaned_df)} records to {table_name}",
            "details": result,
            "errors": []
        }

    except pd.errors.EmptyDataError:
        raise HTTPException(status_code=400, detail="CSV file is empty or invalid")
    except pd.errors.ParserError as e:
        raise HTTPException(status_code=400, detail=f"CSV parsing error: {str(e)}")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")  # This will show in terminal
        raise HTTPException(status_code=500, detail="Internal server error - check terminal logs")

from app.agents.timetable_generator import TimetableGeneratorAgent

@router.post("/generate/{program}")
async def generate_timetable(program: str = "FYUP"):
    agent = TimetableGeneratorAgent()
    try:
        timetable = agent.generate(program)
        return {"message": f"Timetable generated for {program}", "count": len(timetable), "timetable": timetable}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")
    
from app.agents.negotiator import NegotiatorAgent

@router.post("/negotiate/{program}")
async def negotiate_timetable(program: str = "FYUP"):
    agent = NegotiatorAgent()
    try:
        result = agent.negotiate(program)
        # Return the same timetable that was just generated
        # We'll improve this later
        return {
            "message": "Timetable finalized",
            "timetable": result.get("timetable", []),
            "conflicts": []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/faculty")
async def get_faculty():
    from supabase import create_client
    from app.config import settings

    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    try:
        response = client.table("faculty").select("*").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching faculty: {str(e)}")

@router.get("/timetable/{program}")
async def get_timetable(program: str = "FYUP"):
    from supabase import create_client
    from app.config import settings

    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    try:
        response = client.table("timetables").select("*").eq("program", program).execute()
        return {"timetable": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching timetable: {str(e)}")