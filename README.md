<<<<<<< HEAD
# timetable-automation-system
=======
Timetable Automation System

A full-stack web application that automatically generates optimized academic timetables for students, faculty, and coordinators.

🚀 Features
👨‍🎓 Student Dashboard
View timetable by semester & section
Download timetable as PDF
Report issues
👨‍🏫 Faculty Dashboard
View teaching schedule
Access student timetables
Download schedules
🧑‍💼 Coordinator Dashboard
Upload subjects, faculty, rooms data (CSV)
Generate timetable automatically
Detect conflicts and issues
Manage announcements
⚙️ Smart Timetable Generation
Lab allocation with batches
Faculty & room conflict avoidance
Subject distribution across days
Break & lunch scheduling
🧠 How It Works

The system uses a rule-based scheduling algorithm:

Allocates lab sessions (2-hour blocks)
Assigns theory classes with constraints:
Max classes per subject per day
Faculty availability
Room availability
Automatically fills remaining slots
Prevents clashes between:
Faculty
Rooms
Student batches
🛠️ Tech Stack
Frontend: HTML, CSS, JavaScript
Backend: Python (Flask)
Libraries:
Flask
Flask-CORS
jsPDF (for PDF generation)
>>>>>>> 3619987 (Initial commit - timetable automation system)
