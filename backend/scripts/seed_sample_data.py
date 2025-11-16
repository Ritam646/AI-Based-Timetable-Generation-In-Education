import sys
import os
from pathlib import Path
import logging

sys.path.append(str(Path(__file__).parent.parent))

from app.agents.data_curator import DataCuratorAgent
from app.agents.policy_agent import PolicyComplianceAgent
from app.agents.timetable_generator import TimetableGeneratorAgent
from app.agents.negotiator import NegotiatorAgent
from supabase import create_client
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sample_files = {
    "students": "../../data/samples/students_sample.csv",
    "faculty": "../../data/samples/faculty_sample.csv",
    "courses": "../../data/samples/courses_sample.csv",
    "rooms": "../../data/samples/rooms_sample.csv"
}

def clear_tables():
    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    tables = ["timetables", "constraints", "students", "faculty", "courses", "rooms"]
    for table in tables:
        try:
            supabase.table(table).delete().neq("id", 0).execute()
            logger.info(f"Cleared table {table}")
        except Exception as e:
            logger.error(f"Failed to clear table {table}: {str(e)}")

def seed_data():
    clear_tables()
    curator = DataCuratorAgent()
    for table_name, file_path in sample_files.items():
        if os.path.exists(file_path):
            cleaned_df, errors = curator.validate_and_clean(file_path, table_name)
            if not errors:
                result = curator.save_to_supabase(cleaned_df, table_name)
                logger.info(f"Seeded {table_name}: {result}")
            else:
                logger.warning(f"Errors in {table_name}: {errors}")
        else:
            logger.error(f"File not found: {file_path}")
    
    policy_agent = PolicyComplianceAgent()
    try:
        result = policy_agent.validate_constraints()
        logger.info(f"Constraint validation: {result}")
    except Exception as e:
        logger.error(f"Constraint validation failed: {str(e)}")

    generator = TimetableGeneratorAgent()
    try:
        timetable = generator.generate_timetable("FYUP")
        logger.info(f"Timetable for FYUP: {timetable}")
    except Exception as e:
        logger.error(f"Timetable generation failed: {str(e)}")

    negotiator = NegotiatorAgent()
    try:
        result = negotiator.resolve_conflicts("FYUP")
        logger.info(f"Negotiated timetable for FYUP: {result}")
    except Exception as e:
        logger.error(f"Timetable negotiation failed: {str(e)}")

if __name__ == "__main__":
    seed_data()