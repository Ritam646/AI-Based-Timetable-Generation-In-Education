# from ortools.sat.python import cp_model
# import pandas as pd
# import json
# import logging
# from supabase import create_client, Client
# from typing import Dict, List
# from fastapi import HTTPException
# from app.config import settings

# # Set up logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# class TimetableGeneratorAgent:
#     def __init__(self):
#         self.supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
#         self.days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
#         self.time_slots = ["9:00-10:00", "10:00-11:00", "11:00-12:00", "13:00-14:00", "14:00-15:00", "15:00-16:00"]

#     def fetch_data(self) -> Dict[str, pd.DataFrame]:
#         try:
#             tables = ["students", "faculty", "courses", "rooms"]
#             data = {}
#             for table in tables:
#                 response = self.supabase.table(table).select("*").execute()
#                 data[table] = pd.DataFrame(response.data if response.data else [])
#                 logger.info(f"Fetched {len(data[table])} rows from {table}")
#             return data
#         except Exception as e:
#             logger.error(f"Error fetching data: {str(e)}")
#             raise HTTPException(status_code=500, detail=f"Error fetching data: {str(e)}")

#     def generate_timetable(self, program: str = "FYUP") -> List[Dict]:
#         data = self.fetch_data()
#         students_df = data["students"]
#         faculty_df = data["faculty"]
#         courses_df = data["courses"]
#         rooms_df = data["rooms"]

#         if students_df.empty or faculty_df.empty or courses_df.empty or rooms_df.empty:
#             logger.error("Missing data in one or more tables")
#             raise HTTPException(status_code=400, detail="Missing data in one or more tables")

#         program_students = students_df[students_df["program"] == program]
#         if program_students.empty:
#             logger.error(f"No students found for program {program}")
#             raise HTTPException(status_code=400, detail=f"No students found for program {program}")

#         logger.info(f"Generating timetable for {program} with {len(program_students)} students")

#         model = cp_model.CpModel()
#         solver = cp_model.CpSolver()
#         assignments = {}

#         for _, course in courses_df.iterrows():
#             for day in self.days:
#                 for slot in self.time_slots:
#                     for _, faculty in faculty_df.iterrows():
#                         try:
#                             expertise = json.loads(faculty["expertise"]) if isinstance(faculty["expertise"], str) else faculty["expertise"]
#                             if course["code"] in expertise:
#                                 for _, room in rooms_df.iterrows():
#                                     if course["is_practical"] == room["is_lab"]:
#                                         assignments[(course["code"], day, slot, faculty["id"], room["id"])] = model.NewBoolVar(
#                                             f"{course['code']}_{day}_{slot}_{faculty['id']}_{room['id']}"
#                                         )
#                         except json.JSONDecodeError:
#                             logger.warning(f"Invalid expertise format for faculty {faculty['id']}")
#                             continue

#         # Constraint 1: Each course assigned exactly once
#         for _, course in courses_df.iterrows():
#             model.AddExactlyOne(
#                 assignments[(course["code"], day, slot, faculty["id"], room["id"])]
#                 for day in self.days
#                 for slot in self.time_slots
#                 for _, faculty in faculty_df.iterrows()
#                 if course["code"] in (json.loads(faculty["expertise"]) if isinstance(faculty["expertise"], str) else faculty["expertise"])
#                 for _, room in rooms_df.iterrows()
#                 if course["is_practical"] == room["is_lab"]
#             )

#         # Constraint 2: No faculty teaches multiple courses at the same time
#         for _, faculty in faculty_df.iterrows():
#             for day in self.days:
#                 for slot in self.time_slots:
#                     model.AddAtMostOne(
#                         assignments[(course["code"], day, slot, faculty["id"], room["id"])]
#                         for _, course in courses_df.iterrows()
#                         if course["code"] in (json.loads(faculty["expertise"]) if isinstance(faculty["expertise"], str) else faculty["expertise"])
#                         for _, room in rooms_df.iterrows()
#                         if course["is_practical"] == room["is_lab"]
#                     )

#         # Constraint 3: No room used for multiple courses at the same time
#         for _, room in rooms_df.iterrows():
#             for day in self.days:
#                 for slot in self.time_slots:
#                     model.AddAtMostOne(
#                         assignments[(course["code"], day, slot, faculty["id"], room["id"])]
#                         for _, course in courses_df.iterrows()
#                         for _, faculty in faculty_df.iterrows()
#                         if course["code"] in (json.loads(faculty["expertise"]) if isinstance(faculty["expertise"], str) else faculty["expertise"])
#                         if course["is_practical"] == room["is_lab"]
#                     )

#         # Constraint 4: Student no-clash
#         for _, student in program_students.iterrows():
#             try:
#                 electives = json.loads(student["electives"]) if isinstance(student["electives"], str) else student["electives"]
#                 logger.info(f"Processing electives for student {student['roll_no']}: {electives}")
#                 for day in self.days:
#                     for slot in self.time_slots:
#                         model.AddAtMostOne(
#                             assignments[(course[1]["code"], day, slot, faculty["id"], room["id"])]
#                             for course in courses_df[courses_df["code"].isin(electives)].iterrows()
#                             for _, faculty in faculty_df.iterrows()
#                             if course[1]["code"] in (json.loads(faculty["expertise"]) if isinstance(faculty["expertise"], str) else faculty["expertise"])
#                             for _, room in rooms_df.iterrows()
#                             if course[1]["is_practical"] == room["is_lab"]
#                         )
#             except json.JSONDecodeError:
#                 logger.warning(f"Invalid electives format for student {student['roll_no']}")
#                 continue

#         status = solver.Solve(model)
#         if status not in [cp_model.FEASIBLE, cp_model.OPTIMAL]:
#             logger.error("No feasible timetable found")
#             raise HTTPException(status_code=400, detail="No feasible timetable found")

#         timetable = []
#         for (course_code, day, slot, faculty_id, room_id), var in assignments.items():
#             if solver.Value(var):
#                 timetable.append({
#                     "program": program,
#                     "course_code": course_code,
#                     "faculty_id": faculty_id,
#                     "room_id": room_id,
#                     "day": day,
#                     "time_slot": slot
#                 })

#         if timetable:
#             try:
#                 self.supabase.table("timetables").insert(timetable).execute()
#                 logger.info(f"Saved {len(timetable)} timetable entries to Supabase")
#             except Exception as e:
#                 logger.error(f"Error saving timetable: {str(e)}")
#                 raise HTTPException(status_code=500, detail=f"Error saving timetable: {str(e)}")

#         return timetable

from ortools.sat.python import cp_model
from supabase import create_client
from fastapi import HTTPException
from app.config import settings
import pandas as pd

class TimetableGeneratorAgent:
    def __init__(self):
        self.supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        self.days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
        self.slots = ["9:00-10:00", "10:00-11:00", "11:00-12:00", "13:00-14:00", "14:00-15:00", "15:00-16:00"]

    def fetch_data(self):
        try:
            faculty = self.supabase.table("faculty").select("*").execute().data
            courses = self.supabase.table("courses").select("*").execute().data
            rooms = self.supabase.table("rooms").select("*").execute().data
            students = self.supabase.table("students").select("*").execute().data

            return pd.DataFrame(faculty), pd.DataFrame(courses), pd.DataFrame(rooms), pd.DataFrame(students)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Data fetch error: {str(e)}")

    def generate(self, program="FYUP"):
        faculty_df, courses_df, rooms_df, students_df = self.fetch_data()

        if faculty_df.empty or courses_df.empty or rooms_df.empty:
            raise HTTPException(status_code=400, detail="Missing required data")

        # Filter students for program
        program_students = students_df[students_df["program"] == program]
        if program_students.empty:
            raise HTTPException(status_code=400, detail=f"No students for program {program}")

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0  # Limit solve time

        assignments = {}

        # Create variables: course, day, slot, faculty, room -> bool
        for _, course in courses_df.iterrows():
            for day in self.days:
                for slot in self.slots:
                    for _, faculty in faculty_df.iterrows():
                        if course["code"] in faculty["expertise"]:
                            for _, room in rooms_df.iterrows():
                                if course["is_practical"] == room["is_lab"]:
                                    var_name = f"{course['code']}_{day}_{slot}_{faculty['name']}_{room['name']}"
                                    assignments[(course["code"], day, slot, faculty["id"], room["id"])] = model.NewBoolVar(var_name)

        # Constraint 1: Each course exactly once
        for _, course in courses_df.iterrows():
            exprs = []
            for day in self.days:
                for slot in self.slots:
                    for _, faculty in faculty_df.iterrows():
                        if course["code"] in faculty["expertise"]:
                            for _, room in rooms_df.iterrows():
                                if course["is_practical"] == room["is_lab"]:
                                    key = (course["code"], day, slot, faculty["id"], room["id"])
                                    if key in assignments:
                                        exprs.append(assignments[key])
            if exprs:
                model.AddExactlyOne(exprs)

        # Constraint 2: No faculty clash
        for _, faculty in faculty_df.iterrows():
            for day in self.days:
                for slot in self.slots:
                    exprs = []
                    for _, course in courses_df.iterrows():
                        if course["code"] in faculty["expertise"]:
                            for _, room in rooms_df.iterrows():
                                if course["is_practical"] == room["is_lab"]:
                                    key = (course["code"], day, slot, faculty["id"], room["id"])
                                    if key in assignments:
                                        exprs.append(assignments[key])
                    model.AddAtMostOne(exprs)

        # Constraint 3: No room clash
        for _, room in rooms_df.iterrows():
            for day in self.days:
                for slot in self.slots:
                    exprs = []
                    for _, course in courses_df.iterrows():
                        if course["is_practical"] == room["is_lab"]:
                            for _, faculty in faculty_df.iterrows():
                                if course["code"] in faculty["expertise"]:
                                    key = (course["code"], day, slot, faculty["id"], room["id"])
                                    if key in assignments:
                                        exprs.append(assignments[key])
                    model.AddAtMostOne(exprs)

        # Solve
        status = solver.Solve(model)

        if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            raise HTTPException(status_code=400, detail="No feasible timetable found with current data")

        # Extract solution
        timetable = []
        for key, var in assignments.items():
            if solver.Value(var):
                course_code, day, slot, faculty_id, room_id = key
                timetable.append({
                    "program": program,
                    "course_code": course_code,
                    "faculty_id": faculty_id,
                    "room_id": room_id,
                    "day": day,
                    "time_slot": slot
                })

        # Save to Supabase
        if timetable:
            try:
                self.supabase.table("timetables").delete().eq("program", program).execute()  # Clear old
                self.supabase.table("timetables").insert(timetable).execute()
            except Exception as e:
                print("Save error:", str(e))  # Log but continue

        return timetable