# backend-rp/rag_utils.py
import os
import re
import random
import traceback
import pandas as pd
from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader, TextLoader, CSVLoader, Docx2txtLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_groq import ChatGroq
from langchain.chains import RetrievalQA
from supabase import create_client, Client
from groq import Groq

# Supabase and Groq setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# create_client will error if the key is not present; it's safer to let callers
# initialize the client with environment config in production.
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
# Do NOT store API keys in source. Use environment variables and secure secrets.
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY", "")
client = Groq()

# Robust loaders
class RobustPDFLoader(PyPDFLoader):
    def load(self):
        try:
            return super().load()
        except Exception as e:
            print(f"[PDF] PyPDFLoader failed: {e}")
            return []

def load_excel_to_documents(file_path: str) -> list[Document]:
    docs = []
    try:
        xls = pd.ExcelFile(file_path)
        for sheet_name in xls.sheet_names:
            df = xls.parse(sheet_name)
            text = df.to_csv(index=False)
            if text.strip():
                docs.append(Document(
                    page_content=text,
                    metadata={"source": str(file_path), "sheet": sheet_name, "loader": "pandas_excel"}
                ))
    except Exception as e:
        print(f"[EXCEL] Failed: {e}")
    return docs

def load_file_to_documents(file_path: str) -> list[Document]:
    ext = Path(file_path).suffix.lower()
    try:
        if ext == ".pdf":
            return RobustPDFLoader(file_path).load()
        elif ext in [".txt", ".md", ".log"]:
            return TextLoader(file_path, autodetect_encoding=True).load()
        elif ext == ".csv":
            return CSVLoader(file_path).load()
        elif ext in [".xls", ".xlsx"]:
            return load_excel_to_documents(file_path)
        elif ext == ".docx":
            return Docx2txtLoader(file_path).load()
        else:
            return []
    except Exception as e:
        print(f"[LOAD ERR]: {e}")
        return []

def gather_documents_recursive(root_dir: str, allowed_ext=None) -> list[Document]:
    if allowed_ext is None:
        allowed_ext = {".pdf", ".txt", ".csv", ".xls", ".xlsx", ".docx"}
    all_docs = []
    for dirpath, _, filenames in os.walk(root_dir):
        for name in filenames:
            ext = Path(name).suffix.lower()
            if ext in allowed_ext:
                fpath = os.path.join(dirpath, name)
                docs = load_file_to_documents(fpath)
                for d in docs:
                    d.metadata.setdefault("source", fpath)
                    d.metadata["relpath"] = os.path.relpath(fpath, root_dir)
                    d.metadata["subfolder"] = os.path.relpath(dirpath, root_dir)
                all_docs.extend(docs)
    return all_docs

# RAG Pipeline
def build_vectorstore(root_dir: str, embeddings_model="sentence-transformers/all-MiniLM-L6-v2"):
    docs = gather_documents_recursive(root_dir)
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_documents(docs)
    embeddings = HuggingFaceEmbeddings(model_name=embeddings_model)
    vectorstore = FAISS.from_documents(chunks, embeddings)
    return vectorstore

def build_rag_chain(vectorstore, model="llama-3.1-70b-versatile"):
    llm = ChatGroq(model=model)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        chain_type="stuff",
        return_source_documents=True
    )
    return qa_chain

def rag_query(qa_chain, query: str):
    result = qa_chain.invoke({"query": query})
    return result

# Extract contact hours
def extract_contact_hours(response):
    if not response or "don't know" in response.lower():
        return None
    match = re.search(r'(\d+[LTP](?:\+?\d*[LTP]?)?(?:/week)?)', response)
    return match.group(0) if match else None

# SmartRoutineGenerator class
class SmartRoutineGenerator:
    DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
    TIME_SLOTS = ['9-10', '10-11', '11-12', '12-1', '2-3', '3-4', '4-5']
    
    def __init__(self):
        self.faculty_df = None
        self.room_df = None
        self.student_df = None
    
    def load_data(self, faculty_file, room_file, student_file):
        try:
            self.faculty_df = pd.read_csv(faculty_file)
            self.room_df = pd.read_csv(room_file)
            self.student_df = pd.read_csv(student_file)
            
            self.faculty_df.columns = self.faculty_df.columns.str.strip()
            self.room_df.columns = self.room_df.columns.str.strip()
            self.student_df.columns = self.student_df.columns.str.strip()
            return True
        except Exception as e:
            print(f"[ERROR] Load data: {e}")
            return False

    def parse_contact_hours(self, contact_hour_string):
        if not contact_hour_string or contact_hour_string == "Unknown":
            return {'L': 1, 'T': 0, 'P': 0}
        contact_hour_string = contact_hour_string.replace('/week', '').strip()
        hours = {'L': 0, 'T': 0, 'P': 0}
        matches = re.findall(r'(\d+)([LTP])', contact_hour_string)
        for count, type_char in matches:
            hours[type_char] = int(count)
        return hours
    
    def parse_unavailable_slots(self, unavailable_str):
        if pd.isna(unavailable_str) or unavailable_str == "":
            return []
        slots = []
        for slot in str(unavailable_str).split('|'):
            slot = slot.strip()
            if ':' in slot:
                parts = slot.split()
                if len(parts) >= 2:
                    day = parts[0]
                    time_range = parts[1]
                    if '10:00-12:00' in time_range:
                        slots.extend([(day, '10-11'), (day, '11-12')])
                    elif '14:00-16:00' in time_range:
                        slots.extend([(day, '2-3'), (day, '3-4')])
                    elif '09:00-10:00' in time_range:
                        slots.append((day, '9-10'))
                    elif '11:00-13:00' in time_range:
                        slots.extend([(day, '11-12'), (day, '12-1')])
                    elif '13:00-15:00' in time_range:
                        slots.extend([(day, '12-1'), (day, '2-3')])
        return slots
    
    def get_suitable_rooms(self, subject_name, department, student_count):
        room_type = 'Lab' if 'Lab' in subject_name or 'lab' in subject_name.lower() else 'Classroom'
        suitable_rooms = self.room_df[
            (self.room_df['room_type'].str.contains(room_type, case=False, na=False)) &
            (self.room_df['capacity'] >= student_count) &
            ((self.room_df['department'].str.upper() == department.upper()) | 
             (self.room_df['department'].str.upper() == 'GENERAL'))
        ]['room_name'].tolist()
        if not suitable_rooms:
            suitable_rooms = self.room_df[self.room_df['capacity'] >= student_count]['room_name'].tolist()
        if not suitable_rooms:
            suitable_rooms = self.room_df['room_name'].tolist()[:3]
        return suitable_rooms or ['DefaultRoom']
    
    def get_qualified_faculty(self, subject_name, department, year):
        qualified_faculty = []
        for _, faculty in self.faculty_df.iterrows():
            faculty_subjects = str(faculty.get('subjects', '')).lower()
            faculty_name = faculty.get('name', '')
            subject_keywords = []
            if 'biology' in subject_name.lower():
                subject_keywords.extend(['biology', 'bio'])
            elif 'computer architecture' in subject_name.lower():
                subject_keywords.extend(['computer architecture', 'architecture', 'computer'])
            elif 'lab' in subject_name.lower():
                subject_keywords.extend(['lab', 'laboratory', 'practical'])
            elif 'algorithm' in subject_name.lower():
                subject_keywords.extend(['algorithm', 'algorithms'])
            elif 'discrete mathematics' in subject_name.lower():
                subject_keywords.extend(['discrete', 'mathematics', 'math'])
            elif 'environmental' in subject_name.lower():
                subject_keywords.extend(['environmental', 'environment'])
            elif 'formal language' in subject_name.lower() or 'automata' in subject_name.lower():
                subject_keywords.extend(['formal', 'language', 'automata', ' theory'])
            else:
                subject_keywords = [word.lower().strip('()[]') for word in subject_name.split() 
                                  if len(word.strip('()[]')) > 2]
            
            if any(keyword in faculty_subjects for keyword in subject_keywords) or 'general' in faculty_subjects or 'all' in faculty_subjects:
                faculty_dept = str(faculty.get('department', '')).upper()
                faculty_year = str(faculty.get('year_to_teach', ''))
                if (faculty_dept in [department.upper(), 'GENERAL', 'ALL'] and 
                    (str(year) in faculty_year or faculty_year.upper() == 'ALL' or faculty_year == '')):
                    qualified_faculty.append({
                        'name': faculty_name,
                        'max_load_hours': faculty.get('max_load_hours', 20),
                        'unavailable_slots': self.parse_unavailable_slots(faculty.get('unavailable_slots', ''))
                    })
        
        return qualified_faculty or [{
            'name': faculty['name'],
            'max_load_hours': 20,
            'unavailable_slots': []
        } for _, faculty in self.faculty_df.head(2).iterrows()]
    
    def is_faculty_available(self, faculty_name, day, time_slot, faculty_schedule):
        return faculty_schedule.get(faculty_name, {}).get(day, {}).get(time_slot) is None
    
    def is_room_available(self, room_name, day, time_slot, room_schedule):
        return room_schedule.get(room_name, {}).get(day, {}).get(time_slot) is None
    
    def assign_class(self, subject_name, contact_hours, faculty_list, rooms, 
                    section, day, time_slot, faculty_schedule, room_schedule, 
                    faculty_workload, section_schedule):
        available_faculty = [
            f for f in faculty_list
            if self.is_faculty_available(f['name'], day, time_slot, faculty_schedule) and
            (day, time_slot) not in f['unavailable_slots'] and
            faculty_workload.get(f['name'], 0) < f['max_load_hours']
        ]
        if not available_faculty:
            return False
        
        chosen_faculty = random.choice(available_faculty)
        faculty_name = chosen_faculty['name']
        available_rooms = [room for room in rooms if self.is_room_available(room, day, time_slot, room_schedule)]
        if not available_rooms:
            return False
        
        chosen_room = random.choice(available_rooms)
        
        faculty_schedule.setdefault(faculty_name, {}).setdefault(day, {})[time_slot] = f"{subject_name} - {section}"
        room_schedule.setdefault(chosen_room, {}).setdefault(day, {})[time_slot] = f"{subject_name} - {section}"
        faculty_workload[faculty_name] = faculty_workload.get(faculty_name, 0) + 1
        section_schedule.setdefault(section, {}).setdefault(day, {})[time_slot] = {
            'subject': subject_name,
            'faculty': faculty_name,
            'room': chosen_room
        }
        return True
    
    def distribute_classes(self, subject_requirements, sections, faculty_schedule, 
                         room_schedule, faculty_workload, section_schedules):
        assignments_made = {f"{subject_name}-{section}": 0 
                          for subject_name in subject_requirements for section in sections}
        
        for subject_name, (contact_hours, faculty_list, rooms) in subject_requirements.items():
            total_hours = sum(contact_hours.values())
            for section in sections:
                hours_assigned = 0
                for day in self.DAYS:
                    if hours_assigned >= total_hours:
                        break
                    for time_slot in [t for t in self.TIME_SLOTS if t != "12-1"]:
                        if section_schedules[section][day].get(time_slot):
                            continue
                        if self.assign_class(subject_name, contact_hours, faculty_list, rooms, 
                                          section, day, time_slot, faculty_schedule, 
                                          room_schedule, faculty_workload, section_schedules):
                            assignments_made[f"{subject_name}-{section}"] += 1
                            hours_assigned += 1
                            if hours_assigned >= total_hours:
                                break
        return section_schedules
    
    def export_to_csv(self, section_schedules, sem):
        output_dir = 'backend-rp/data/output/'
        os.makedirs(output_dir, exist_ok=True)
        
        for section in sorted(section_schedules.keys()):
            timetable_data = []
            for time_slot in self.TIME_SLOTS:
                row = {'Time': time_slot}
                for day in self.DAYS:
                    slot_info = section_schedules[section][day].get(time_slot)
                    if time_slot == "12-1":
                        row[day] = "BREAK"
                    elif slot_info:
                        row[day] = f"{slot_info['subject']} by {slot_info['faculty']} in {slot_info['room']}"
                    else:
                        row[day] = "FREE"
                timetable_data.append(row)
            
            timetable_df = pd.DataFrame(timetable_data)
            timetable_df.to_csv(os.path.join(output_dir, f'timetable_section_{section}.csv'), index=False)
        
        summary_data = []
        faculty_workload = {}
        for section in sorted(section_schedules.keys()):
            total_classes = 0
            subject_count = {}
            for day in self.DAYS:
                for time_slot in self.TIME_SLOTS:
                    if time_slot == "12-1":
                        continue
                    slot_info = section_schedules[section][day].get(time_slot)
                    if slot_info:
                        total_classes += 1
                        subject = slot_info['subject']
                        faculty = slot_info['faculty']
                        subject_count[subject] = subject_count.get(subject, 0) + 1
                        faculty_workload[faculty] = faculty_workload.get(faculty, 0) + 1
            
            summary_data.append({'Section': section, 'Total Classes': total_classes})
            for subject, count in sorted(subject_count.items()):
                summary_data.append({'Section': '', 'Subject': subject, 'Hours/Week': count})
        
        for faculty, hours in sorted(faculty_workload.items()):
            summary_data.append({'Section': '', 'Faculty': faculty, 'Workload (Hours/Week)': hours})
        
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_csv(os.path.join(output_dir, 'timetable_summary.csv'), index=False)
    
    def format_routine_output_table(self, section_schedules, sem):
        output = []
        for section in sorted(section_schedules.keys()):
            output.append(f"\n{'='*100}")
            output.append(f"ROUTINE FOR SECTION {section} - CSE {sem}th Semester")
            output.append(f"{'='*100}")
            output.append(f"{'Time':<8}│{'Monday':<20}│{'Tuesday':<20}│{'Wednesday':<20}│{'Thursday':<20}│{'Friday':<20}")
            output.append("─" * 8 + "┼" + "─" * 20 + "┼" + "─" * 20 + "┼" + "─" * 20 + "┼" + "─" * 20 + "┼" + "─" * 20)
            
            for time_slot in self.TIME_SLOTS:
                if time_slot == "12-1":
                    output.append(f"{'12-1':<8}│{'BREAK':<20}│{'BREAK':<20}│{'BREAK':<20}│{'BREAK':<20}│{'BREAK':<20}")
                else:
                    lines = ["", "", ""]
                    for day in self.DAYS:
                        slot_info = section_schedules[section][day].get(time_slot)
                        if slot_info:
                            subject = slot_info['subject'][:17] + "..." if len(slot_info['subject']) > 17 else slot_info['subject']
                            faculty = slot_info['faculty'][:17] + "..." if len(slot_info['faculty']) > 17 else slot_info['faculty'] 
                            room = slot_info['room'][:17] + "..." if len(slot_info['room']) > 17 else slot_info['room']
                            lines[0] += f"│{subject:<20}"
                            lines[1] += f"│{faculty:<20}"
                            lines[2] += f"│{room:<20}"
                        else:
                            lines[0] += f"│{'FREE':<20}"
                            lines[1] += f"│{'':<20}"
                            lines[2] += f"│{'':<20}"
                    
                    output.append(f"{time_slot:<8}{lines[0]}")
                    output.append(f"{'':<8}{lines[1]}")
                    output.append(f"{'':<8}{lines[2]}")
                output.append("─" * 8 + "┼" + "─" * 20 + "┼" + "─" * 20 + "┼" + "─" * 20 + "┼" + "─" * 20 + "┼" + "─" * 20)
            
            output.append("")
        
        output.append(f"\n{'='*100}")
        output.append("TIMETABLE SUMMARY")
        output.append(f"{'='*100}")
        
        faculty_workload = {}
        for section in sorted(section_schedules.keys()):
            total_classes = 0
            subject_count = {}
            for day in self.DAYS:
                for time_slot in self.TIME_SLOTS:
                    if time_slot == "12-1":
                        continue
                    slot_info = section_schedules[section][day].get(time_slot)
                    if slot_info:
                        total_classes += 1
                        subject = slot_info['subject']
                        faculty = slot_info['faculty']
                        subject_count[subject] = subject_count.get(subject, 0) + 1
                        faculty_workload[faculty] = faculty_workload.get(faculty, 0) + 1
            
            output.append(f"\nSection {section}: {total_classes} classes scheduled")
            for subject, count in sorted(subject_count.items()):
                output.append(f"  • {subject}: {count} hours/week")
        
        output.append(f"\n{'-'*50}")
        output.append("FACULTY WORKLOAD DISTRIBUTION")
        output.append(f"{'-'*50}")
        for faculty, hours in sorted(faculty_workload.items()):
            output.append(f"{faculty:<25}: {hours} hours/week")
        
        return "\n".join(output)
    
    def generate_routine(self, dept, sem, contact_hours_dict):
        try:
            year = int(sem)
            sections_data = self.student_df[
                (self.student_df['department'] == dept) & 
                (self.student_df['year'] == year)
            ]
            
            if sections_data.empty:
                print(f"[ERROR] No sections found for {dept} Year {year}")
                return f"No sections found for {dept} Year {year}"
            
            sections = sections_data['section'].tolist()
            faculty_schedule = {}
            room_schedule = {}
            faculty_workload = {}
            section_schedules = {section: {day: {} for day in self.DAYS} for section in sections}
            
            student_count = sections_data.iloc[0].get('total_number_of_students', 
                                                   sections_data.iloc[0].get('total_students', 50))
            
            subject_requirements = {}
            for subject_name, contact_hours_str in contact_hours_dict.items():
                contact_hours = self.parse_contact_hours(contact_hours_str)
                qualified_faculty = self.get_qualified_faculty(subject_name, dept, year)
                suitable_rooms = self.get_suitable_rooms(subject_name, dept, student_count)
                subject_requirements[subject_name] = (contact_hours, qualified_faculty, suitable_rooms)
            
            if not subject_requirements:
                print(f"[ERROR] No valid subjects to schedule")
                return "No valid subjects to schedule"
            
            section_schedules = self.distribute_classes(subject_requirements, sections, 
                                                     faculty_schedule, room_schedule, 
                                                     faculty_workload, section_schedules)
            
            self.export_to_csv(section_schedules, sem)
            
            return self.format_routine_output_table(section_schedules, sem)
        except Exception as e:
            print(f"[ERROR] Error in generate_routine: {e}")
            return f"Failed to generate routine: {e}"

# Function to get subjects
def get_subjects(dept, sem, data_dir):
    cse_file = os.path.join(data_dir, 'CSE_Syllabus_Complete.xlsx')
    ece_file = os.path.join(data_dir, 'ECE_Syllabus_Final.xlsx')
    it_file = os.path.join(data_dir, 'IT_Complete_Syllabus.xlsx')

    def load_df(file_path, dept):
        df = pd.read_excel(file_path)
        df['Department'] = dept
        df['Semester'] = pd.to_numeric(df['Semester'], errors='coerce')
        df = df.dropna(subset=['Semester'])
        return df

    try:
        cse_df = load_df(cse_file, 'CSE')
        ece_df = load_df(ece_file, 'ECE')
        it_df = load_df(it_file, 'IT')
    except Exception as e:
        print(f"[ERROR] Failed to load syllabus files: {e}")
        return []

    all_df = pd.concat([cse_df, ece_df, it_df], ignore_index=True)

    def parse_data(df):
        data = {}
        for _, row in df.iterrows():
            sem = int(row['Semester'])
            if 'Subject (with Paper Code)' in df.columns and pd.notna(row.get('Subject (with Paper Code)', None)):
                subject = row['Subject (with Paper Code)']
            elif 'Subject' in df.columns and pd.notna(row.get('Subject', None)):
                subject = row['Subject']
            else:
                continue
            dept = row['Department']
            if pd.isna(subject):
                continue
            subject = re.sub(r'\s+', ' ', str(subject)).strip()
            if not subject:
                continue
            if dept not in data:
                data[dept] = {}
            if sem not in data[dept]:
                data[dept][sem] = []
            if subject not in data[dept][sem]:
                data[dept][sem].append(subject)
        return data

    all_data = parse_data(all_df)
    dept = dept.upper()
    try:
        sem = int(sem)
    except ValueError:
        print(f"[ERROR] Invalid semester: {sem}")
        return []
    if dept in all_data and sem in all_data[dept]:
        return all_data[dept][sem]
    return []

# Main generation function
def generate_timetable(dept, sem):
    data_dir = 'backend-rp/data/syllabus-data-new/'
    rag_dir = 'backend-rp/data/full-final-rag-nep/MAKAUT_Syllabus'
    college_data_dir = 'backend-rp/data/college-data/'

    query_results = get_subjects(dept, sem, data_dir)
    if not query_results:
        return "No subjects found"

    vs = build_vectorstore(rag_dir)
    rag_chain = build_rag_chain(vs)

    contact_hours_dict = {}
    for subject in query_results:
        query = f"Contact hours/week of {subject}"
        response = rag_query(rag_chain, query)
        contact_hours = extract_contact_hours(response.get('result', '') if isinstance(response, dict) else response)
        contact_hours_dict[subject] = contact_hours if contact_hours else "Unknown"

    generator = SmartRoutineGenerator()
    faculty_file = os.path.join(college_data_dir, 'faculty_assignments.csv')
    room_file = os.path.join(college_data_dir, 'room_assignments.csv')
    student_file = os.path.join(college_data_dir, 'student_sections.csv')

    if not os.path.exists(faculty_file) or not os.path.exists(room_file) or not os.path.exists(student_file):
        print(f"[ERROR] One or more data files missing")
        return "Required data files are missing"

    if generator.load_data(faculty_file, room_file, student_file):
        routine = generator.generate_routine(dept, sem, contact_hours_dict)
        return routine
    else:
        return "Failed to load data"