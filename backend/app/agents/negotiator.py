import pandas as pd
import json
from supabase import create_client, Client
from typing import Dict, List
from fastapi import HTTPException
from app.config import settings


class NegotiatorAgent:
    def __init__(self):
        self.supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

    def fetch_data(self) -> Dict[str, pd.DataFrame]:
        """Fetch data from Supabase tables."""
        try:
            tables = ["timetables", "faculty", "courses", "rooms"]
            data = {}
            for table in tables:
                response = self.supabase.table(table).select("*").execute()
                data[table] = pd.DataFrame(response.data if response.data else [])
            return data
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching data: {str(e)}")

    def resolve_conflicts(self, program: str = "FYUP") -> List[Dict]:
        """Resolve conflicts and optimize timetable."""
        data = self.fetch_data()
        timetables_df = data["timetables"][data["timetables"]["program"] == program]
        faculty_df = data["faculty"]
        courses_df = data["courses"]
        rooms_df = data["rooms"]

        if timetables_df.empty:
            raise HTTPException(status_code=400, detail=f"No timetable found for program {program}")

        conflicts = []
        optimized_timetable = timetables_df.to_dict(orient="records")

        # Rule 1: Check faculty availability conflicts
        for i, entry in enumerate(optimized_timetable):
            faculty = faculty_df[faculty_df["id"] == entry["faculty_id"]]
            if faculty.empty:
                conflicts.append({
                    "type": "faculty_missing",
                    "details": {
                        "course_code": entry["course_code"],
                        "faculty_id": entry["faculty_id"]
                    }
                })
                continue
            try:
                availability = (
                    json.loads(faculty.iloc[0]["availability"])
                    if isinstance(faculty.iloc[0]["availability"], str)
                    else faculty.iloc[0]["availability"]
                )
                day_slots = availability.get(entry["day"], [])
                slot_time = entry["time_slot"].split("-")[0]  # e.g., "9:00" from "9:00-10:00"
                if not any(slot_time in slot for slot in day_slots):
                    conflicts.append({
                        "type": "faculty_availability",
                        "details": {
                            "course_code": entry["course_code"],
                            "faculty_id": entry["faculty_id"],
                            "day": entry["day"],
                            "time_slot": entry["time_slot"]
                        }
                    })
                    # Reassign to an available slot (simplified: pick first available)
                    if day_slots:
                        new_slot = day_slots[0].split("-")[0] + "-10:00"  # Example reassignment
                        optimized_timetable[i]["time_slot"] = new_slot
            except json.JSONDecodeError:
                conflicts.append({
                    "type": "invalid_availability",
                    "details": {
                        "faculty_id": entry["faculty_id"],
                        "error": "Invalid availability format"
                    }
                })

        # Rule 2: Optimize for senior faculty (prefer morning slots, e.g., before 12:00)
        for i, entry in enumerate(optimized_timetable):
            faculty = faculty_df[faculty_df["id"] == entry["faculty_id"]]
            if faculty.empty:
                continue
            max_workload = faculty.iloc[0]["max_workload"]
            slot_hour = int(entry["time_slot"].split(":")[0])
            if max_workload > 25 and slot_hour >= 12:  # Senior faculty, afternoon slot
                # Try moving to morning slot
                for slot in ["9:00-10:00", "10:00-11:00", "11:00-12:00"]:
                    if not any(
                        t["time_slot"] == slot
                        and t["day"] == entry["day"]
                        and t["room_id"] == entry["room_id"]
                        for t in optimized_timetable
                    ):
                        optimized_timetable[i]["time_slot"] = slot
                        break

        # Rule 3: Ensure room capacity for courses
        for i, entry in enumerate(optimized_timetable):
            course = courses_df[courses_df["code"] == entry["course_code"]]
            room = rooms_df[rooms_df["id"] == entry["room_id"]]
            if course.empty or room.empty:
                continue
            student_count = len(
                data["students"][
                    (data["students"]["program"] == program)
                    & (data["students"]["electives"].apply(
                        lambda x: entry["course_code"] in (
                            json.loads(x) if isinstance(x, str) else x
                        )
                    ))
                ]
            )
            if student_count > room.iloc[0]["capacity"]:
                conflicts.append({
                    "type": "room_capacity",
                    "details": {
                        "course_code": entry["course_code"],
                        "room_id": entry["room_id"],
                        "student_count": student_count,
                        "capacity": room.iloc[0]["capacity"]
                    }
                })
                # Reassign to a larger room if available
                larger_room = rooms_df[
                    (rooms_df["is_lab"] == course.iloc[0]["is_practical"])
                    & (rooms_df["capacity"] >= student_count)
                ]
                if not larger_room.empty:
                    optimized_timetable[i]["room_id"] = larger_room.iloc[0]["id"]

        # Save conflicts to constraints table
        if conflicts:
            try:
                self.supabase.table("constraints").insert([
                    {"constraint_type": c["type"], "details": c["details"]}
                    for c in conflicts
                ]).execute()
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error saving conflicts: {str(e)}")

        # Update timetable status to final
        if optimized_timetable:
            try:
                self.supabase.table("timetables").update({"status": "final"}).eq("program", program).execute()
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error updating timetable: {str(e)}")

        return {"conflicts": conflicts, "timetable": optimized_timetable}
