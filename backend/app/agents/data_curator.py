# import pandas as pd
# import json
# from supabase import create_client, Client
# from typing import Dict, List, Tuple
# from fastapi import HTTPException
# from app.config import settings

# class DataCuratorAgent:
#     def __init__(self):
#         self.supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

#     def validate_and_clean(self, file_path: str, table_name: str) -> Tuple[pd.DataFrame, List[str]]:
#         try:
#             df = pd.read_csv(file_path)
#             errors = []

#             if table_name == "students":
#                 required_columns = ["roll_no", "program", "electives", "credit_limit"]
#                 if not all(col in df.columns for col in required_columns):
#                     errors.append(f"Missing required columns for students: {required_columns}")
#                 if df["roll_no"].duplicated().any():
#                     errors.append("Duplicate roll_no found")
#                     df = df.drop_duplicates(subset="roll_no")
#                 if not df["credit_limit"].apply(lambda x: isinstance(x, int) and x > 0).all():
#                     errors.append("Invalid credit_limit (must be positive integer)")
#                 df["electives"] = df["electives"].apply(lambda x: json.dumps(eval(x)) if isinstance(x, str) else x)
#             elif table_name == "faculty":
#                 required_columns = ["name", "availability", "max_workload", "expertise"]
#                 if not all(col in df.columns for col in required_columns):
#                     errors.append(f"Missing required columns for faculty: {required_columns}")
#                 if df["name"].duplicated().any():
#                     errors.append("Duplicate name found")
#                     df = df.drop_duplicates(subset="name")
#                 df["expertise"] = df["expertise"].apply(lambda x: json.dumps(eval(x)) if isinstance(x, str) else x)
#                 df["availability"] = df["availability"].apply(lambda x: json.dumps(eval(x)) if isinstance(x, str) else x)
#             elif table_name == "courses":
#                 required_columns = ["code", "credit_hours", "is_elective", "is_practical"]
#                 if not all(col in df.columns for col in required_columns):
#                     errors.append(f"Missing required columns for courses: {required_columns}")
#             elif table_name == "rooms":
#                 required_columns = ["name", "capacity", "is_lab"]
#                 if not all(col in df.columns for col in required_columns):
#                     errors.append(f"Missing required columns for rooms: {required_columns}")
#             else:
#                 errors.append(f"Unknown table: {table_name}")

#             return df, errors
#         except Exception as e:
#             raise HTTPException(status_code=400, detail=f"Error processing CSV: {str(e)}")

#     def save_to_supabase(self, df: pd.DataFrame, table_name: str) -> Dict:
#         try:
#             data = df.to_dict(orient="records")
#             if table_name == "students":
#                 response = self.supabase.table(table_name).upsert(data, on_conflict="roll_no").execute()
#             elif table_name == "faculty":
#                 response = self.supabase.table(table_name).upsert(data, on_conflict="name").execute()
#             else:
#                 response = self.supabase.table(table_name).insert(data).execute()
#             return {"status": "success", "inserted_or_updated": len(response.data)}
#         except Exception as e:
#             raise HTTPException(status_code=500, detail=f"Error saving to Supabase: {str(e)}")



import pandas as pd
from supabase import create_client
from fastapi import HTTPException
from typing import List
from app.config import settings

class DataCuratorAgent:
    def __init__(self):
        self.supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

    def clean_and_validate(self, df: pd.DataFrame, table_name: str) -> tuple[pd.DataFrame, List[str]]:
        errors = []

        if df.empty:
            errors.append("DataFrame is empty after reading CSV")

        # Simple validation - just check required columns exist
        if table_name == "faculty":
            required = ["name", "max_workload"]
            missing = [col for col in required if col not in df.columns]
            if missing:
                errors.append(f"Missing required columns: {missing}")

        elif table_name == "courses":
            required = ["code", "credit_hours"]
            missing = [col for col in required if col not in df.columns]
            if missing:
                errors.append(f"Missing required columns: {missing}")

        elif table_name == "rooms":
            required = ["name", "capacity"]
            missing = [col for col in required if col not in df.columns]
            if missing:
                errors.append(f"Missing required columns: {missing}")

        elif table_name == "students":
            required = ["roll_no", "program", "credit_limit"]
            missing = [col for col in required if col not in df.columns]
            if missing:
                errors.append(f"Missing required columns: {missing}")

        return df, errors

    def upload_to_supabase(self, df: pd.DataFrame, table_name: str):
        if df.empty:
            raise HTTPException(status_code=400, detail="No data to upload")

        # Convert all to string to avoid type issues
        data = df.astype(str).to_dict(orient="records")
        
        try:
            response = self.supabase.table(table_name).upsert(data).execute()
            return {"success": True, "count": len(response.data)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")