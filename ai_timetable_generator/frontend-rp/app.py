# frontend-rp/app.py
import streamlit as st
import requests
import pandas as pd
import os
import re

# Set page config for better layout
st.set_page_config(
    page_title="AI-Powered Timetable Generator",
    page_icon="📅",
    layout="wide"
)

# Custom CSS for styling
st.markdown("""
    <style>
    .main-title {
        font-size: 2.5em;
        color: #2c3e50;
        text-align: center;
        margin-bottom: 0.5em;
    }
    .sidebar .sidebar-content {
        background-color: #f8f9fa;
    }
    .stButton>button {
        background-color: #3498db;
        color: white;
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #2980b9;
    }
    .stTextInput>div>input {
        border-radius: 5px;
    }
    .error-box {
        background-color: #ffe6e6;
        padding: 10px;
        border-radius: 5px;
        color: #c0392b;
    }
    .success-box {
        background-color: #e6ffed;
        padding: 10px;
        border-radius: 5px;
        color: #27ae60;
    }
    .timetable-table {
        font-size: 0.9em;
        border-collapse: collapse;
        width: 100%;
    }
    .timetable-table th, .timetable-table td {
        border: 1px solid #ddd;
        padding: 8px;
        text-align: left;
    }
    .timetable-table th {
        background-color: #3498db;
        color: white;
    }
    .timetable-table tr:nth-child(even) {
        background-color: #f2f2f2;
    }
    </style>
""", unsafe_allow_html=True)

# Sidebar for inputs
with st.sidebar:
    st.header("Timetable Parameters")
    dept = st.selectbox(
        "Department",
        ["CSE", "ECE", "IT"],
        help="Select the department (e.g., CSE, ECE, IT)"
    )
    sem = st.selectbox(
        "Semester",
        [str(i) for i in range(1, 9)],
        help="Select the semester (1-8)"
    )
    generate_button = st.button("Generate Timetable")

# Main content
st.markdown("<h1 class='main-title'>AI-Powered Timetable Generator</h1>", unsafe_allow_html=True)
st.write("Generate a timetable for your department and semester using AI-driven scheduling.")

# Function to format timetable as a table
def format_timetable_to_df(routine):
    if not routine or "No subjects found" in routine or "Failed" in routine:
        return None
    
    # Parse the routine string into a DataFrame
    lines = routine.split("\n")
    timetable_data = []
    current_section = None
    current_row = None
    time_slots = ["9-10", "10-11", "11-12", "12-1", "2-3", "3-4", "4-5"]
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    
    for line in lines:
        if line.startswith("ROUTINE FOR SECTION"):
            current_section = line.split("SECTION ")[1].split(" -")[0]
        elif line.startswith("Time") and "│" in line:
            continue  # Skip header
        elif any(time_slot in line for time_slot in time_slots):
            parts = line.split("│")
            time = parts[0].strip()
            row = {"Time": time, "Section": current_section}
            for i, day in enumerate(days, 1):
                cell = parts[i].strip()
                if cell == "BREAK" or cell == "FREE":
                    row[day] = cell
                else:
                    # Extract subject, faculty, room
                    match = re.match(r"(.+?)\.\.\.?\sby\s(.+?)\.\.\.?\sin\s(.+?)\.\.\.?", cell)
                    if match:
                        row[day] = f"{match.group(1)} ({match.group(2)}, {match.group(3)})"
                    else:
                        row[day] = cell
            timetable_data.append(row)
    
    if timetable_data:
        df = pd.DataFrame(timetable_data)
        return df.set_index(["Section", "Time"])
    return None

# Handle timetable generation
if generate_button:
    if dept and sem:
        with st.spinner("Generating timetable... This may take a moment."):
            try:
                response = requests.get(f"http://localhost:8000/generate_timetable?dept={dept}&sem={sem}")
                if response.status_code == 200:
                    routine = response.json()["routine"]
                    if "No subjects found" in routine or "Failed" in routine:
                        st.markdown(f"<div class='error-box'>Error: {routine}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown("<div class='success-box'>Timetable generated successfully!</div>", unsafe_allow_html=True)
                        
                        # Display timetable as a table
                        timetable_df = format_timetable_to_df(routine)
                        if timetable_df is not None:
                            st.markdown("### Generated Timetable")
                            st.dataframe(
                                timetable_df,
                                use_container_width=True,
                                column_config={
                                    day: st.column_config.TextColumn(day, width="medium")
                                    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
                                }
                            )
                            
                            # Provide download link for CSV
                            csv_file = f"backend-rp/data/output/timetable_summary.csv"
                            if os.path.exists(csv_file):
                                with open(csv_file, "rb") as file:
                                    st.download_button(
                                        label="Download Timetable Summary (CSV)",
                                        data=file,
                                        file_name="timetable_summary.csv",
                                        mime="text/csv"
                                    )
                        else:
                            st.text_area("Raw Timetable Output", routine, height=500)
                else:
                    st.markdown("<div class='error-box'>Error generating timetable: Server responded with an error.</div>", unsafe_allow_html=True)
            except Exception as e:
                st.markdown(f"<div class='error-box'>Error: {str(e)}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='error-box'>Please select both department and semester.</div>", unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown("Developed with using Streamlit and FastAPI | Powered by Team Processor")