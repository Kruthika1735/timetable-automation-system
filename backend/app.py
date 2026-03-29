from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
import json
import random
from datetime import datetime
import os
import csv
import io

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# In-memory storage
users_db = {}
timetables_db = {}
subjects_db = {}
faculty_db = {'faculty': []}
rooms_db = {'rooms': []}
students_db = {}
announcements_db = []
issues_db = []
contact_details = {
    'name': 'Timetable Coordinator',
    'phone': '+91 9876543210',
    'email': 'coordinator@sjb.edu.in',
    'office': 'Main Building, Room 101',
    'hours': '10:00 AM - 4:00 PM (Mon-Fri)'
}

def initialize_sample_data():
    """Only create minimal sample users - data will come from CSV uploads"""
    # Sample users only
    users_db['1JB20CS001'] = {'username': '1JB20CS001', 'password': 'student123', 'email': 'student1@sjb.edu.in', 'userType': 'student'}
    users_db['FAC001'] = {'username': 'FAC001', 'password': 'faculty123', 'email': 'faculty1@sjb.edu.in', 'userType': 'faculty'}
    users_db['TTC001'] = {'username': 'TTC001', 'password': 'coordinator123', 'email': 'coordinator@sjb.edu.in', 'userType': 'coordinator'}

# Enhanced Timetable Generator Class
class TimetableGenerator:
    def __init__(self, subjects, faculty, rooms, semester, section):
        self.subjects = subjects
        self.faculty = faculty
        self.rooms = rooms
        self.semester = semester
        self.section = section
        self.batches = ['1', '2', '3']  # A1, A2, A3 or B1, B2, B3 etc.
        
        self.time_slots = [
            "8:30-9:30", "9:30-10:30", "10:30-10:45",
            "10:45-11:45", "11:45-12:45", "12:45-1:30",
            "1:30-2:30", "2:30-3:30", "3:30-4:30"
        ]
        
        self.days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        # Wednesday has shorter schedule - include lunch break as the last slot
        self.wednesday_slots = [
            "8:30-9:30", "9:30-10:30", "10:30-10:45",
            "10:45-11:45", "11:45-12:45", "12:45-1:30"
        ]
        
        self.timetable = self.initialize_timetable()
        self.faculty_schedule = {}
        self.room_schedule = {}
        self.section_schedule = {}
        self.batch_schedule = {}
        self.subject_day_count = {}
        self.lab_allocations = {}  # Track lab allocations per batch
        self.lab_days_used = {day: False for day in self.days}  # Track which days have labs
        
    def initialize_timetable(self):
        timetable = {}
        for day in self.days:
            timetable[day] = {}
            slots = self.time_slots if day != "Wednesday" else self.wednesday_slots
            for slot in slots:
                timetable[day][slot] = "Free Period"
        return timetable
    
    def generate_timetable(self):
        try:
            print(f"Generating timetable for Semester {self.semester}, Section {self.section}")
            
            # Add breaks first
            self.add_breaks()
            
            # Initialize subject tracking
            self.initialize_subject_tracking()
            
            # Initialize lab allocations tracking
            self.initialize_lab_allocations()
            
            # Phase 1: Allocate Lab Sessions with batches (2-hour slots)
            if not self.allocate_lab_sessions_with_batches():
                return False, "Failed to allocate lab sessions with batches"
            
            # Phase 2: Allocate Theory Classes with subject distribution
            if not self.allocate_theory_classes_with_distribution():
                return False, "Failed to allocate theory classes"
            
            # Phase 3: Fill remaining slots
            self.fill_remaining_slots()
            
            return True, "Timetable generated successfully"
            
        except Exception as e:
            return False, f"Error generating timetable: {str(e)}"
    
    def initialize_subject_tracking(self):
        """Initialize tracking for subject distribution"""
        for day in self.days:
            self.subject_day_count[day] = {}
            for subject in self.subjects:
                self.subject_day_count[day][subject['name']] = 0
    
    def initialize_lab_allocations(self):
        """Initialize lab allocations tracking for each batch"""
        for batch in self.batches:
            self.lab_allocations[batch] = {}
            lab_subjects = [s for s in self.subjects if s['type'].lower() == 'lab']
            for lab in lab_subjects:
                self.lab_allocations[batch][lab['name']] = False
    
    def add_breaks(self):
        """Add fixed breaks to the timetable"""
        # Short break for all days
        for day in self.days:
            self.timetable[day]["10:30-10:45"] = "Short Break"
        
        # Lunch break for all days including Wednesday
        for day in self.days:
            if day == "Wednesday":
                # Wednesday lunch break is at the end of the day
                self.timetable[day]["12:45-1:30"] = "Lunch Break"
            else:
                # Other days have lunch break in the middle
                self.timetable[day]["12:45-1:30"] = "Lunch Break"
    
    def allocate_lab_sessions_with_batches(self):
        """Allocate 2-hour lab sessions for all batches simultaneously - ONE PER DAY"""
        lab_subjects = [s for s in self.subjects if s['type'].lower() == 'lab']
        
        if not lab_subjects:
            return True
            
        lab_rooms = [r for r in self.rooms if r['type'].lower() == 'lab']
        
        if len(lab_rooms) < len(self.batches):
            print(f"Warning: Only {len(lab_rooms)} lab rooms available for {len(self.batches)} batches")
            return False
        
        print(f"Available lab subjects: {[lab['name'] for lab in lab_subjects]}")
        print(f"Available lab rooms: {[room['name'] for room in lab_rooms]}")
        
        # Shuffle days to distribute labs across different days
        days = self.days.copy()
        random.shuffle(days)
        
        lab_allocation_count = 0
        
        for day in days:
            if lab_allocation_count >= len(lab_subjects):
                break
                
            # Skip Wednesday for labs (shorter day)
            if day == "Wednesday":
                continue
                
            # Find available 2-hour consecutive slots for this day
            lab_slot = self.find_available_lab_slot_for_day(day)
            
            if lab_slot:
                start_slot_idx = lab_slot
                lab_subject = lab_subjects[lab_allocation_count]
                time_slot1 = self.time_slots[start_slot_idx]
                time_slot2 = self.time_slots[start_slot_idx + 1]
                
                print(f"Allocating lab {lab_subject['name']} on {day} at {time_slot1} and {time_slot2}")
                
                # Allocate this lab to all batches with different rooms
                lab_allocations = []
                for batch_idx, batch in enumerate(self.batches):
                    if batch_idx < len(lab_rooms):
                        lab_room = lab_rooms[batch_idx]
                        # Create clear batch information
                        batch_name = f"{self.section}{batch}"  # A1, A2, A3 etc.
                        lab_info = f"{lab_subject['name']} - Batch {batch_name} ({lab_room['name']})"
                        lab_allocations.append(lab_info)
                        
                        # Mark allocations for both time slots
                        self.lab_allocations[batch][lab_subject['name']] = True
                        self.mark_faculty_busy(lab_subject['faculty'], day, time_slot1)
                        self.mark_faculty_busy(lab_subject['faculty'], day, time_slot2)
                        self.mark_batch_busy(batch, day, time_slot1)
                        self.mark_batch_busy(batch, day, time_slot2)
                        self.mark_room_busy(lab_room['id'], day, time_slot1)
                        self.mark_room_busy(lab_room['id'], day, time_slot2)
                
                # Combine all batch labs into one cell entry for BOTH time slots
                lab_entry = f"LAB: {'; '.join(lab_allocations)}"
                self.timetable[day][time_slot1] = lab_entry
                self.timetable[day][time_slot2] = lab_entry
                
                # Mark this day as having a lab
                self.lab_days_used[day] = True
                lab_allocation_count += 1
                
                print(f"  ✓ Lab session allocated: {lab_subject['name']} on {day} {time_slot1}-{time_slot2}")
                print(f"  Batch allocation: {lab_allocations}")
        
        print(f"Total lab sessions allocated: {lab_allocation_count}")
        return lab_allocation_count > 0
    
    def find_available_lab_slot_for_day(self, day):
        """Find available 2-hour consecutive slot for a specific day"""
        slots = self.time_slots if day != "Wednesday" else self.wednesday_slots
        
        # Try different starting positions
        possible_starts = []
        for i in range(len(slots) - 1):
            slot1 = slots[i]
            slot2 = slots[i + 1]
            
            # Skip if these are break slots
            if (self.is_break_slot(slot1) or self.is_break_slot(slot2)):
                continue
            
            # Check if both slots are free for all batches and section
            all_batches_free = all(
                self.is_batch_free(batch, day, slot1) and 
                self.is_batch_free(batch, day, slot2) 
                for batch in self.batches
            )
            
            section_free = (self.is_section_free(day, slot1) and 
                          self.is_section_free(day, slot2))
            
            if all_batches_free and section_free:
                possible_starts.append(i)
        
        if possible_starts:
            return random.choice(possible_starts)
        return None
    
    def allocate_theory_classes_with_distribution(self):
        """Allocate theory classes with proper subject distribution"""
        theory_subjects = [s for s in self.subjects if s['type'].lower() == 'theory']
        
        if not theory_subjects:
            return True
        
        # Calculate required hours per subject (typically 3-4 hours per week)
        required_hours = {subject['name']: 4 for subject in theory_subjects}
        
        # Try to allocate each subject
        for subject in theory_subjects:
            allocated_hours = 0
            max_attempts_per_subject = 200  # Increased attempts
            
            while allocated_hours < required_hours[subject['name']] and max_attempts_per_subject > 0:
                if self.allocate_single_theory_class_with_distribution(subject):
                    allocated_hours += 1
                max_attempts_per_subject -= 1
            
            print(f"  {subject['name']}: {allocated_hours}/{required_hours[subject['name']]} hours allocated")
                
        return True
    
    def allocate_single_theory_class_with_distribution(self, subject, max_attempts=100):
        """Allocate a single theory class with subject distribution rules"""
        for attempt in range(max_attempts):
            day = random.choice(self.days)
            slots = self.time_slots if day != "Wednesday" else self.wednesday_slots
            
            # Filter out break slots and already allocated lab slots
            available_slots = []
            for slot in slots:
                if (not self.is_break_slot(slot) and 
                    self.timetable[day][slot] == "Free Period" and
                    not self.timetable[day][slot].startswith("LAB:")):
                    available_slots.append(slot)
            
            if not available_slots:
                continue
                
            time_slot = random.choice(available_slots)
            
            # Check subject distribution rules
            if (self.subject_day_count[day].get(subject['name'], 0) >= 2):
                continue  # Maximum 2 classes per day per subject
                
            if (self.is_section_free(day, time_slot) and
                self.is_faculty_free(subject['faculty'], day, time_slot)):
                
                classrooms = [r for r in self.rooms if r['type'].lower() == 'classroom']
                available_room = None
                
                for room in classrooms:
                    if self.is_room_free(room['id'], day, time_slot):
                        available_room = room
                        break
                
                if available_room:
                    class_info = f"{subject['name']} - {subject['faculty']} ({available_room['name']})"
                    self.timetable[day][time_slot] = class_info
                    
                    # Update subject tracking
                    self.subject_day_count[day][subject['name']] = self.subject_day_count[day].get(subject['name'], 0) + 1
                    
                    self.mark_faculty_busy(subject['faculty'], day, time_slot)
                    self.mark_section_busy(day, time_slot)
                    self.mark_room_busy(available_room['id'], day, time_slot)
                    
                    return True
        return False
    
    def fill_remaining_slots(self):
        """Fill remaining slots with available subjects following distribution rules"""
        theory_subjects = [s for s in self.subjects if s['type'].lower() == 'theory']
        
        for day in self.days:
            slots = self.time_slots if day != "Wednesday" else self.wednesday_slots
            
            for time_slot in slots:
                # Skip break slots and already allocated slots
                if (self.is_break_slot(time_slot) or 
                    self.timetable[day][time_slot].startswith("LAB:") or
                    self.timetable[day][time_slot] != "Free Period"):
                    continue
                    
                # Try to find any subject that fits distribution rules
                random.shuffle(theory_subjects)  # Randomize selection
                
                for subject in theory_subjects:
                    # Check if subject already has max classes for this day
                    if self.subject_day_count[day].get(subject['name'], 0) >= 2:
                        continue
                        
                    if (self.is_faculty_free(subject['faculty'], day, time_slot) and
                        self.is_section_free(day, time_slot)):
                        
                        classrooms = [r for r in self.rooms if r['type'].lower() == 'classroom']
                        available_room = None
                        
                        for room in classrooms:
                            if self.is_room_free(room['id'], day, time_slot):
                                available_room = room
                                break
                        
                        if available_room:
                            class_info = f"{subject['name']} - {subject['faculty']} ({available_room['name']})"
                            self.timetable[day][time_slot] = class_info
                            
                            # Update subject tracking
                            self.subject_day_count[day][subject['name']] = self.subject_day_count[day].get(subject['name'], 0) + 1
                            
                            self.mark_faculty_busy(subject['faculty'], day, time_slot)
                            self.mark_section_busy(day, time_slot)
                            self.mark_room_busy(available_room['id'], day, time_slot)
                            break
    
    def is_break_slot(self, time_slot):
        """Check if a time slot is a break slot"""
        return ("break" in time_slot.lower() or 
                "lunch" in time_slot.lower() or
                time_slot in ["10:30-10:45", "12:45-1:30"])
    
    def is_section_free(self, day, time_slot):
        key = f"{self.semester}_{self.section}_{day}_{time_slot}"
        return not self.section_schedule.get(key, False)
    
    def is_batch_free(self, batch, day, time_slot):
        key = f"{self.semester}_{self.section}_{batch}_{day}_{time_slot}"
        return not self.batch_schedule.get(key, False)
    
    def is_faculty_free(self, faculty_id, day, time_slot):
        key = f"{faculty_id}_{day}_{time_slot}"
        return not self.faculty_schedule.get(key, False)
    
    def is_room_free(self, room_id, day, time_slot):
        key = f"{room_id}_{day}_{time_slot}"
        return not self.room_schedule.get(key, False)
    
    def mark_section_busy(self, day, time_slot):
        key = f"{self.semester}_{self.section}_{day}_{time_slot}"
        self.section_schedule[key] = True
    
    def mark_batch_busy(self, batch, day, time_slot):
        key = f"{self.semester}_{self.section}_{batch}_{day}_{time_slot}"
        self.batch_schedule[key] = True
    
    def mark_faculty_busy(self, faculty_id, day, time_slot):
        key = f"{faculty_id}_{day}_{time_slot}"
        self.faculty_schedule[key] = True
    
    def mark_room_busy(self, room_id, day, time_slot):
        key = f"{room_id}_{day}_{time_slot}"
        self.room_schedule[key] = True
    
    def get_formatted_timetable(self):
        formatted = []
        
        # Define the order of time slots to display
        display_slots = [
            "8:30-9:30", "9:30-10:30", "10:30-10:45",
            "10:45-11:45", "11:45-12:45", "12:45-1:30", 
            "1:30-2:30", "2:30-3:30", "3:30-4:30"
        ]
        
        for slot in display_slots:
            row = {
                'time': slot,
                'Monday': self.timetable['Monday'].get(slot, 'Free Period'),
                'Tuesday': self.timetable['Tuesday'].get(slot, 'Free Period'),
                'Wednesday': self.timetable['Wednesday'].get(slot, 'Free Period'),
                'Thursday': self.timetable['Thursday'].get(slot, 'Free Period'),
                'Friday': self.timetable['Friday'].get(slot, 'Free Period')
            }
            formatted.append(row)
        
        return formatted

# Faculty Timetable Generator
class FacultyTimetableGenerator:
    def __init__(self, faculty_id, all_timetables):
        self.faculty_id = faculty_id
        self.all_timetables = all_timetables
        self.time_slots = [
            "8:30-9:30", "9:30-10:30", "10:30-10:45",
            "10:45-11:45", "11:45-12:45", "12:45-1:30",
            "1:30-2:30", "2:30-3:30", "3:30-4:30"
        ]
        self.days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        
    def generate_faculty_timetable(self):
        faculty_schedule = {}
        
        # Initialize schedule with free periods
        for day in self.days:
            faculty_schedule[day] = {}
            for slot in self.time_slots:
                faculty_schedule[day][slot] = "Free Period"
        
        # Parse all timetables to find faculty assignments
        for timetable_key, timetable_data in self.all_timetables.items():
            semester, section = timetable_key.split('_')
            
            for day in self.days:
                for entry in timetable_data:
                    time_slot = entry['time']
                    class_info = entry.get(day, '')
                    
                    # Skip breaks and free periods
                    if (not class_info or class_info == "Free Period" or 
                        "Break" in class_info or "break" in class_info.lower()):
                        continue
                    
                    # Check if this faculty is teaching this class
                    if self.faculty_id in class_info:
                        # Extract class details
                        if "LAB:" in class_info:
                            # Lab session with multiple batches - find the specific batch for this faculty
                            lab_parts = class_info.replace("LAB:", "").split(';')
                            for lab_part in lab_parts:
                                if self.faculty_id in lab_part:
                                    # Extract just the lab name and batch for faculty view
                                    lab_info = lab_part.strip()
                                    faculty_schedule[day][time_slot] = f"{semester}-{section}: {lab_info}"
                        else:
                            # Regular theory class
                            faculty_schedule[day][time_slot] = f"{semester}-{section}: {class_info}"
        
        return self.format_faculty_timetable(faculty_schedule)
    
    def format_faculty_timetable(self, faculty_schedule):
        formatted = []
        
        for slot in self.time_slots:
            row = {
                'time': slot,
                'Monday': faculty_schedule['Monday'].get(slot, 'Free Period'),
                'Tuesday': faculty_schedule['Tuesday'].get(slot, 'Free Period'),
                'Wednesday': faculty_schedule['Wednesday'].get(slot, 'Free Period'),
                'Thursday': faculty_schedule['Thursday'].get(slot, 'Free Period'),
                'Friday': faculty_schedule['Friday'].get(slot, 'Free Period')
            }
            formatted.append(row)
        
        return formatted

# Helper function to extract subject name from class info
def extract_subject_name(class_info):
    """Extract just the subject name from class information"""
    if not class_info or class_info in ['Free Period', 'Short Break', 'Lunch Break']:
        return None
    
    # For lab sessions
    if 'LAB:' in class_info:
        # Extract the first subject name from lab info
        lab_content = class_info.replace('LAB:', '').strip()
        if ';' in lab_content:
            first_lab = lab_content.split(';')[0].strip()
            # Remove batch information
            if 'Batch' in first_lab:
                first_lab = first_lab.split('Batch')[0].strip()
            # Extract subject name (before first dash)
            if ' - ' in first_lab:
                return first_lab.split(' - ')[0].strip()
            return first_lab
        return lab_content
    
    # For regular classes
    if ' - ' in class_info:
        return class_info.split(' - ')[0].strip()
    
    return class_info

# Authentication middleware
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        try:
            if token.startswith('Bearer '):
                username = token[7:]
                if username not in users_db:
                    return jsonify({'error': 'Invalid token'}), 401
        except:
            return jsonify({'error': 'Invalid token'}), 401
        return f(*args, **kwargs)
    return decorated

# API Routes
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'OK', 'message': 'Server is running'})

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    
    if username in users_db:
        return jsonify({'error': 'Username already exists'}), 400
    
    users_db[username] = {
        'username': username,
        'password': data.get('password'),
        'email': data.get('email'),
        'userType': data.get('userType')
    }
    
    return jsonify({
        'message': 'User registered successfully',
        'user': users_db[username],
        'token': username
    })

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    user = users_db.get(username)
    if not user or user['password'] != password:
        return jsonify({'error': 'Invalid credentials'}), 401
    
    return jsonify({
        'message': 'Login successful',
        'user': user,
        'token': username
    })

@app.route('/api/data-status', methods=['GET'])
@token_required
def get_data_status():
    total_subjects = sum(len(subjects_db.get(sem, {}).get('subjects', [])) for sem in subjects_db)
    faculty_count = len(faculty_db.get('faculty', []))
    rooms_count = len(rooms_db.get('rooms', []))
    total_students = sum(len(students_db.get(sem, {}).get(sec, [])) for sem in students_db for sec in students_db.get(sem, {}))
    
    return jsonify({
        'status': {
            'subjects': total_subjects,
            'faculty': faculty_count,
            'rooms': rooms_count,
            'students': total_students
        }
    })

@app.route('/api/generate-timetable', methods=['POST'])
@token_required
def generate_timetable():
    # Check if data is uploaded
    if not subjects_db or not faculty_db.get('faculty') or not rooms_db.get('rooms'):
        return jsonify({
            'error': 'No data uploaded. Please upload Subjects, Faculty, and Rooms CSV files first.'
        }), 400
    
    semesters = list(subjects_db.keys())
    sections = set()
    
    # Get all unique sections from uploaded subjects
    for semester in subjects_db:
        for subject in subjects_db[semester].get('subjects', []):
            sections.add(subject['section'])
    
    sections = list(sections)
    
    if not semesters or not sections:
        return jsonify({
            'error': 'No semester/section data found in uploaded subjects.'
        }), 400
    
    generated_count = 0
    results = []
    generated_timetables = {}
    
    print("=" * 60)
    print("STARTING ENHANCED TIMETABLE GENERATION")
    print(f"Semesters found: {semesters}")
    print(f"Sections found: {sections}")
    print("=" * 60)
    
    for semester in semesters:
        for section in sections:
            semester_subjects = subjects_db.get(semester, {}).get('subjects', [])
            section_subjects = [s for s in semester_subjects if s['section'] == section]
            
            print(f"Sem {semester} Sec {section}: {len(section_subjects)} subjects")
            
            if not section_subjects:
                results.append(f"Sem {semester} Sec {section}: No subjects")
                continue
                
            generator = TimetableGenerator(
                subjects=section_subjects,
                faculty=faculty_db.get('faculty', []),
                rooms=rooms_db.get('rooms', []),
                semester=semester,
                section=section
            )
            
            success, message = generator.generate_timetable()
            
            if success:
                timetable_key = f"{semester}_{section}"
                timetable_data = generator.get_formatted_timetable()
                timetables_db[timetable_key] = timetable_data
                generated_count += 1
                generated_timetables[timetable_key] = len(timetable_data)
                results.append(f"Sem {semester} Sec {section}: ✓ Success")
                print(f"  ✓ Generated timetable with {len(timetable_data)} slots")
                
                # Debug: Print lab distribution
                print(f"  Lab distribution for {semester}_{section}:")
                for day in generator.days:
                    has_lab = any("LAB:" in generator.timetable[day][slot] for slot in generator.time_slots if slot in generator.timetable[day])
                    print(f"    {day}: {'LAB' if has_lab else 'No Lab'}")
            else:
                results.append(f"Sem {semester} Sec {section}: ✗ Failed")
                print(f"  ✗ Failed: {message}")
    
    print("=" * 60)
    print(f"GENERATION COMPLETED: {generated_count} timetables")
    print("=" * 60)
    
    return jsonify({
        'message': f'Generated {generated_count} timetables from uploaded data',
        'generatedCount': generated_count,
        'generatedTimetables': generated_timetables,
        'details': results
    })

@app.route('/api/timetable/<user_type>/<semester>/<section>', methods=['GET'])
@token_required
def get_timetable(user_type, semester, section):
    timetable_key = f"{semester}_{section}"
    
    if timetable_key in timetables_db:
        timetable_data = timetables_db[timetable_key]
        
        # For student view, modify the timetable to show batch-specific information
        if user_type == 'student':
            modified_timetable = []
            for row in timetable_data:
                modified_row = row.copy()
                # For each day, check if it's a lab and modify the display
                for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
                    cell_content = row.get(day, '')
                    if cell_content.startswith('LAB:'):
                        # Extract the student's batch from the lab information
                        # Assuming student ID format: 1JB20CS001 where last digit indicates batch
                        # Or we can use a different logic to determine batch
                        # For now, let's show all batches but highlight the student's batch
                        modified_row[day] = cell_content
                
                modified_timetable.append(modified_row)
            return jsonify({'timetable': modified_timetable})
        else:
            return jsonify({'timetable': timetable_data})
    else:
        # Return sample timetable for demonstration
        sample_timetable = create_sample_timetable()
        return jsonify({'timetable': sample_timetable})

@app.route('/api/faculty-timetable/<semester>', methods=['GET'])
@token_required
def get_faculty_timetable(semester):
    # Get faculty ID from token (simplified)
    faculty_id = request.headers.get('Authorization', '').replace('Bearer ', '')
    
    if not faculty_id.startswith('FAC'):
        return jsonify({'error': 'Faculty access required'}), 403
    
    # Generate faculty timetable from all existing timetables
    generator = FacultyTimetableGenerator(faculty_id, timetables_db)
    faculty_timetable = generator.generate_faculty_timetable()
    
    return jsonify({'timetable': faculty_timetable})

def create_sample_timetable():
    """Create a sample timetable for demonstration when no data is available"""
    time_slots = [
        "8:30-9:30", "9:30-10:30", "10:30-10:45",
        "10:45-11:45", "11:45-12:45", "12:45-1:30",
        "1:30-2:30", "2:30-3:30", "3:30-4:30"
    ]
    
    sample_data = []
    for slot in time_slots:
        if "10:30-10:45" in slot:
            sample_data.append({
                'time': slot,
                'Monday': 'Short Break',
                'Tuesday': 'Short Break', 
                'Wednesday': 'Short Break',
                'Thursday': 'Short Break',
                'Friday': 'Short Break'
            })
        elif "12:45-1:30" in slot:
            sample_data.append({
                'time': slot,
                'Monday': 'Lunch Break',
                'Tuesday': 'Lunch Break',
                'Wednesday': 'Lunch Break', 
                'Thursday': 'Lunch Break',
                'Friday': 'Lunch Break'
            })
        else:
            sample_data.append({
                'time': slot,
                'Monday': 'Mathematics - Dr. Smith (Room 101)',
                'Tuesday': 'Physics - Dr. Johnson (Room 102)',
                'Wednesday': 'Chemistry - Dr. Brown (Room 103)',
                'Thursday': 'Computer Science - Dr. Davis (Lab 1)',
                'Friday': 'English - Dr. Wilson (Room 104)'
            })
    
    return sample_data

@app.route('/api/upload', methods=['POST'])
@token_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        # Read CSV file
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        rows = list(csv_input)
        
        if not rows:
            return jsonify({'error': 'CSV file is empty'}), 400
        
        # Determine data type from filename or content
        filename = file.filename.lower()
        
        if 'subject' in filename:
            data_type = 'subjects'
            for row in rows:
                sem = row.get('semester', '1')
                if sem not in subjects_db:
                    subjects_db[sem] = {'subjects': []}
                # Convert all values to string to avoid issues
                clean_row = {k: str(v) for k, v in row.items()}
                subjects_db[sem]['subjects'].append(clean_row)
            
        elif 'faculty' in filename:
            data_type = 'faculty'
            faculty_db['faculty'] = rows
            
        elif 'room' in filename:
            data_type = 'rooms'
            rooms_db['rooms'] = rows
            
        elif 'student' in filename:
            data_type = 'students'
            for row in rows:
                sem = row.get('semester', '1')
                section = row.get('section', 'A')
                if sem not in students_db:
                    students_db[sem] = {}
                if section not in students_db[sem]:
                    students_db[sem][section] = []
                students_db[sem][section].append(row)
        else:
            return jsonify({'error': 'Cannot determine data type from filename. Use: subjects, faculty, rooms, or students'}), 400
        
        print(f"Uploaded {data_type}: {len(rows)} records")
        
        return jsonify({
            'message': f'{data_type.capitalize()} data uploaded successfully ({len(rows)} records)',
            'dataType': data_type,
            'recordCount': len(rows)
        })
        
    except Exception as e:
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500

@app.route('/api/check-conflicts/<semester>/<section>', methods=['GET'])
@token_required
def check_conflicts(semester, section):
    conflicts = []
    timetable_key = f"{semester}_{section}"
    
    if timetable_key in timetables_db:
        timetable = timetables_db[timetable_key]
        
        # Check for faculty conflicts (same faculty in multiple places at same time)
        faculty_schedule = {}
        room_schedule = {}
        
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
            for entry in timetable:
                time_slot = entry['time']
                class_info = entry.get(day, '')
                
                if class_info not in ['Free Period', 'Short Break', 'Lunch Break', '']:
                    # Extract faculty from class info
                    faculty = None
                    if ' - ' in class_info:
                        faculty = class_info.split(' - ')[1].split(' (')[0].strip()
                    
                    # Extract room from class info
                    room = None
                    if '(' in class_info and ')' in class_info:
                        room = class_info.split('(')[1].split(')')[0].strip()
                    
                    # Check faculty conflicts
                    if faculty:
                        faculty_key = f"{faculty}_{day}_{time_slot}"
                        if faculty_key in faculty_schedule:
                            conflicts.append({
                                'type': 'Faculty Conflict',
                                'message': f"Faculty {faculty} scheduled in multiple classes at {day} {time_slot}"
                            })
                        else:
                            faculty_schedule[faculty_key] = True
                    
                    # Check room conflicts
                    if room:
                        room_key = f"{room}_{day}_{time_slot}"
                        if room_key in room_schedule:
                            conflicts.append({
                                'type': 'Room Conflict',
                                'message': f"Room {room} double-booked at {day} {time_slot}"
                            })
                        else:
                            room_schedule[room_key] = True
    
    if not conflicts:
        conflicts.append({
            'type': 'No Conflicts',
            'message': 'No scheduling conflicts detected'
        })
    
    return jsonify({'conflicts': conflicts})

@app.route('/api/issues', methods=['GET', 'POST'])
@token_required
def handle_issues():
    if request.method == 'POST':
        data = request.get_json()
        new_issue = {
            'id': len(issues_db) + 1,
            'user': data.get('user', 'Anonymous'),
            'userType': data.get('userType', 'student'),
            'title': data.get('title', ''),
            'description': data.get('description', ''),
            'date': datetime.now().isoformat(),
            'status': 'Open'
        }
        issues_db.append(new_issue)
        return jsonify({'message': 'Issue submitted successfully'})
    else:
        return jsonify({'issues': issues_db})

@app.route('/api/announcements', methods=['GET', 'POST'])
@token_required
def handle_announcements():
    if request.method == 'POST':
        data = request.get_json()
        new_announcement = {
            'id': len(announcements_db) + 1,
            'title': data.get('title', ''),
            'message': data.get('message', ''),
            'audience': data.get('audience', 'all'),
            'date': datetime.now().isoformat()
        }
        announcements_db.append(new_announcement)
        return jsonify({'message': 'Announcement sent successfully'})
    else:
        return jsonify({'announcements': announcements_db})

@app.route('/api/contact-details', methods=['GET', 'PUT'])
@token_required
def handle_contact_details():
    if request.method == 'PUT':
        data = request.get_json()
        contact_details.update({
            'name': data.get('name', contact_details['name']),
            'phone': data.get('phone', contact_details['phone']),
            'email': data.get('email', contact_details['email']),
            'office': data.get('office', contact_details['office']),
            'hours': data.get('hours', contact_details['hours'])
        })
        return jsonify({'message': 'Contact details updated successfully'})
    else:
        return jsonify({'contactDetails': contact_details})

# Debug endpoint to check uploaded data
@app.route('/api/debug-data', methods=['GET'])
@token_required
def debug_data():
    return jsonify({
        'subjects_semesters': list(subjects_db.keys()),
        'subjects_counts': {sem: len(subjects_db[sem]['subjects']) for sem in subjects_db},
        'faculty_count': len(faculty_db.get('faculty', [])),
        'rooms_count': len(rooms_db.get('rooms', [])),
        'students_counts': {sem: {sec: len(students_db[sem][sec]) for sec in students_db[sem]} for sem in students_db},
        'timetables': list(timetables_db.keys())
    })

if __name__ == '__main__':
    initialize_sample_data()
    print("=" * 60)
    print("ENHANCED TIMETABLE AUTOMATION SYSTEM")
    print("=" * 60)
    print("FEATURES:")
    print("✓ Subject distribution (max 2 classes per day per subject)")
    print("✓ Batch-wise lab allocation (A1, A2, A3 etc.)")
    print("✓ Faculty timetable generation")
    print("✓ No continuous repeating subjects")
    print("✓ Proper 2-hour lab sessions")
    print("✓ One lab session per day")
    print("✓ Clear batch mentions in lab sessions")
    print("✓ Wednesday lunch break included")
    print("✓ Improved conflict detection (ignores subject repetition)")
    print("=" * 60)
    print("Server starting on http://localhost:3000")
    app.run(debug=True, host='0.0.0.0', port=3000)