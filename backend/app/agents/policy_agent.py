import pandas as pd
from supabase import create_client, Client
from typing import Dict, List
from fastapi import HTTPException
from app.config import settings

class PolicyComplianceAgent:
    def __init__(self):
        self.supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

    def fetch_data(self) -> Dict[str, pd.DataFrame]:
        """Fetch data from Supabase tables."""
        try:
            tables = ["students", "faculty", "courses", "rooms"]
            data = {}
            for table in tables:
                response = self.supabase.table(table).select("*").execute()
                data[table] = pd.DataFrame(response.data)
            return data
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching data: {str(e)}")

    def validate_constraints(self) -> Dict[str, List[Dict]]:
        """Validate NEP 2020 and institutional constraints, return violations."""
        data = self.fetch_data()
        students_df = data["students"]
        faculty_df = data["faculty"]
        courses_df = data["courses"]
        rooms_df = data["rooms"]
        violations = []

        # Rule 1: Student credit limit (NEP 2020)
        for _, student in students_df.iterrows():
            electives = eval(student["electives"])  # Convert string to list
            total_credits = sum(courses_df[courses_df["code"].isin(electives)]["credit_hours"])
            if total_credits > student["credit_limit"]:
                violations.append({
                    "constraint_type": "credit_limit",
                    "details": {
                        "roll_no": student["roll_no"],
                        "total_credits": total_credits,
                        "credit_limit": student["credit_limit"]
                    }
                })

        # Rule 2: Faculty workload
        for _, faculty in faculty_df.iterrows():
            assigned_credits = sum(courses_df[courses_df["code"].isin(eval(faculty["expertise"]))]["credit_hours"])
            if assigned_credits > faculty["max_workload"]:
                violations.append({
                    "constraint_type": "faculty_workload",
                    "details": {
                        "name": faculty["name"],
                        "assigned_credits": assigned_credits,
                        "max_workload": faculty["max_workload"]
                    }
                })

        # Rule 3: Room type (lab for practicals)
        for _, course in courses_df.iterrows():
            if course["is_practical"]:
                if not rooms_df[rooms_df["is_lab"] == True].any().get("is_lab", False):
                    violations.append({
                        "constraint_type": "room_type",
                        "details": {
                            "course_code": course["code"],
                            "error": "No lab available for practical course"
                        }
                    })

        # Rule 4: Placeholder for scheduling conflicts (to be expanded in Phase 3)
        # This will check student/faculty/room clashes once timetable drafts exist

        # Save violations to Supabase
        if violations:
            self.supabase.table("constraints").insert([
                {"constraint_type": v["constraint_type"], "details": v["details"]}
                for v in violations
            ]).execute()

        return {"violations": violations}