import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Container, Tabs, Tab, Table, Button, Spinner, Alert } from 'react-bootstrap';
import 'bootstrap/dist/css/bootstrap.min.css';
import { Bar } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

function App() {
  const [activeTab, setActiveTab] = useState('master');
  const [timetable, setTimetable] = useState([]);
  const [faculty, setFaculty] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // CHANGE THIS TO YOUR ACTUAL BACKEND URL
  const API_URL = 'https://redesigned-dollop-wrxr757765gqcv4wj-8000.app.github.dev';

  const loadData = async () => {
  setLoading(true);
  setError('');
  try {
    // Generate the timetable
    await axios.post(`${API_URL}/timetable/generate/FYUP`);
    
    // Negotiate (optional, keep it)
    await axios.post(`${API_URL}/timetable/negotiate/FYUP`);
    
    // Now fetch the actual timetable from database
    const ttRes = await axios.get(`${API_URL}/timetable/timetable/FYUP`);
    setTimetable(ttRes.data.timetable || []);

    // Load faculty
    const fac = await axios.get(`${API_URL}/timetable/faculty`);
    setFaculty(fac.data || []);
  } catch (err) {
    setError('Failed to load timetable. Check console.');
    console.error(err);
  } finally {
    setLoading(false);
  }
};

  useEffect(() => {
    loadData();
  }, []);

  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
  const slots = [
    '9:00-10:00', '10:00-11:00', '11:00-12:00',
    '13:00-14:00', '14:00-15:00', '15:00-16:00'
  ];

  const workloadData = {
    labels: faculty.map(f => f.name),
    datasets: [{
      label: 'Total Periods',
      data: faculty.map(f => f.max_workload),
      backgroundColor: 'rgba(54, 162, 235, 0.8)',
    }]
  };

  return (
    <Container className="my-5">
      <div className="text-center mb-5">
        <h1 className="display-4 fw-bold text-primary">
          🏫 NEP 2020 AI Timetable Generator
        </h1>
        <h3 className="text-secondary">
          Rajnagar Srinathgram Bani Vidyapith (H.S.)
        </h3>
        <p className="lead text-muted">Session 2026 • Teacher-wise Provisional Allotment</p>
        
        <Button 
          variant="success" 
          size="lg" 
          onClick={loadData} 
          disabled={loading}
        >
          {loading ? (
            <> <Spinner animation="border" size="sm" /> Generating...</>
          ) : (
            '🔄 Generate New Timetable'
          )}
        </Button>
      </div>

      {error && <Alert variant="danger" className="text-center">{error}</Alert>}

      <Tabs activeKey={activeTab} onSelect={(k) => setActiveTab(k)} className="mb-4 justify-content-center" fill>
        <Tab eventKey="master" title="📅 Master Timetable">
          <h3 className="text-center my-4">Class-wise Master Timetable</h3>
          <div className="table-responsive">
            <Table bordered hover>
              <thead className="table-dark">
                <tr>
                  <th className="text-center">Time Slot</th>
                  {days.map(day => <th key={day} className="text-center">{day}</th>)}
                </tr>
              </thead>
              <tbody>
                {slots.map(slot => (
                  <tr key={slot}>
                    <td className="text-center fw-bold">{slot}</td>
                    {days.map(day => {
                      const entry = timetable.find(t => t.day === day && t.time_slot === slot);
                      return (
                        <td key={day + slot} className="text-center">
                          {entry ? (
                            <div>
                              <strong>{entry.course_code}</strong><br />
                              <small>Room {entry.room_id} • {faculty.find(f => f.id === entry.faculty_id)?.name || 'Teacher'}</small>
                            </div>
                          ) : '—'}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        </Tab>

        <Tab eventKey="teachers" title="👩‍🏫 Teacher-wise Allotment">
          <h3 className="text-center my-4">Teacher-wise Provisional Allotment</h3>
          <Table striped bordered hover responsive>
            <thead className="table-primary">
              <tr>
                <th>Sl No</th>
                <th>Teacher Initials</th>
                <th>Subjects Taught</th>
                <th>Total Periods</th>
              </tr>
            </thead>
            <tbody>
              {faculty.map((teacher, index) => (
                <tr key={teacher.id}>
                  <td className="text-center">{index + 1}</td>
                  <td className="fw-bold">{teacher.name}</td>
                  <td>{teacher.expertise}</td>
                  <td className="text-center fw-bold">{teacher.max_workload}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Tab>

        <Tab eventKey="analytics" title="📊 Analytics">
          <h3 className="text-center my-4">Faculty Workload Distribution</h3>
          <div className="mx-auto" style={{ maxWidth: '900px' }}>
            <Bar data={workloadData} options={{ responsive: true }} />
          </div>
        </Tab>
      </Tabs>

      <div className="text-center mt-5 text-muted">
        <p>Powered by AI • Built with FastAPI, React, Supabase & Google OR-Tools</p>
        <p>Made for Indian Schools 🇮🇳</p>
      </div>
    </Container>
  );
}

export default App;