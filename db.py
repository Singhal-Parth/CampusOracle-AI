"""
db.py — Database Layer for AI College Data Assistant

This module handles:
  1. SQLite database creation and connection
  2. Schema definition (students, attendance, marks)
  3. Seeding with 25 sample students and their records
  4. Query helper functions used by the Decision Engine

The database is auto-created and seeded on first import.
"""

import sqlite3
import os

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Database file lives next to this script
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "college.db")


# ---------------------------------------------------------------------------
# Connection Helper
# ---------------------------------------------------------------------------

def get_connection():
    """Return a new SQLite connection with row-factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Allows dict-like access to columns
    return conn


# ---------------------------------------------------------------------------
# Schema Creation
# ---------------------------------------------------------------------------

def create_tables():
    """Create the three core tables if they don't already exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # Students table — core identity
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            branch TEXT NOT NULL,
            year INTEGER NOT NULL
        )
    """)

    # Attendance table — one row per student
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            student_id INTEGER PRIMARY KEY,
            percentage REAL NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """)

    # Marks table — one row per student per subject
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            score INTEGER NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """)

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Sample Data — 25 students across 4 branches, 4 years
# ---------------------------------------------------------------------------

SAMPLE_STUDENTS = [
    # CSE Branch
    ("Aarav Sharma", "CSE", 1),
    ("Priya Patel", "CSE", 1),
    ("Rohan Mehta", "CSE", 2),
    ("Ananya Singh", "CSE", 2),
    ("Vikram Reddy", "CSE", 3),
    ("Sneha Gupta", "CSE", 3),
    ("Arjun Nair", "CSE", 4),
    # ECE Branch
    ("Kavya Iyer", "ECE", 1),
    ("Rahul Joshi", "ECE", 2),
    ("Diya Verma", "ECE", 2),
    ("Aditya Kumar", "ECE", 3),
    ("Meera Bhat", "ECE", 3),
    ("Siddharth Rao", "ECE", 4),
    # ME Branch
    ("Pooja Desai", "ME", 1),
    ("Karan Malhotra", "ME", 1),
    ("Nisha Agarwal", "ME", 2),
    ("Amit Tiwari", "ME", 3),
    ("Ritu Saxena", "ME", 3),
    ("Deepak Chauhan", "ME", 4),
    # CE Branch
    ("Ishita Bansal", "CE", 1),
    ("Manav Kapoor", "CE", 2),
    ("Swati Pillai", "CE", 2),
    ("Harsh Pandey", "CE", 3),
    ("Neha Mishra", "CE", 4),
    ("Rajat Srivastava", "CE", 4),
]

# Attendance percentages (index-matched to SAMPLE_STUDENTS)
SAMPLE_ATTENDANCE = [
    82.5, 91.0, 55.0, 78.3, 45.2, 88.7, 72.1,   # CSE
    67.8, 93.5, 58.4, 76.0, 49.3, 85.6,           # ECE
    71.2, 42.8, 89.1, 53.6, 95.0, 60.5,           # ME
    83.4, 47.9, 74.6, 62.3, 38.7, 90.2,           # CE
]

# Marks: 3 subjects per student (Math, Physics, Programming/Domain)
SAMPLE_MARKS = [
    # CSE
    [(1, "Mathematics", 78), (1, "Physics", 65), (1, "Programming", 85)],
    [(2, "Mathematics", 92), (2, "Physics", 88), (2, "Programming", 95)],
    [(3, "Mathematics", 45), (3, "Physics", 38), (3, "Programming", 52)],
    [(4, "Mathematics", 72), (4, "Physics", 70), (4, "Programming", 80)],
    [(5, "Mathematics", 35), (5, "Physics", 42), (5, "Programming", 48)],
    [(6, "Mathematics", 88), (6, "Physics", 82), (6, "Programming", 91)],
    [(7, "Mathematics", 68), (7, "Physics", 55), (7, "Programming", 73)],
    # ECE
    [(8, "Mathematics", 60), (8, "Physics", 58), (8, "Electronics", 65)],
    [(9, "Mathematics", 90), (9, "Physics", 85), (9, "Electronics", 92)],
    [(10, "Mathematics", 42), (10, "Physics", 48), (10, "Electronics", 55)],
    [(11, "Mathematics", 70), (11, "Physics", 75), (11, "Electronics", 68)],
    [(12, "Mathematics", 38), (12, "Physics", 35), (12, "Electronics", 40)],
    [(13, "Mathematics", 82), (13, "Physics", 79), (13, "Electronics", 85)],
    # ME
    [(14, "Mathematics", 65), (14, "Physics", 70), (14, "Thermodynamics", 62)],
    [(15, "Mathematics", 30), (15, "Physics", 35), (15, "Thermodynamics", 28)],
    [(16, "Mathematics", 85), (16, "Physics", 80), (16, "Thermodynamics", 88)],
    [(17, "Mathematics", 48), (17, "Physics", 45), (17, "Thermodynamics", 42)],
    [(18, "Mathematics", 95), (18, "Physics", 92), (18, "Thermodynamics", 90)],
    [(19, "Mathematics", 55), (19, "Physics", 52), (19, "Thermodynamics", 58)],
    # CE
    [(20, "Mathematics", 78), (20, "Physics", 82), (20, "Structures", 75)],
    [(21, "Mathematics", 40), (21, "Physics", 38), (21, "Structures", 45)],
    [(22, "Mathematics", 72), (22, "Physics", 68), (22, "Structures", 70)],
    [(23, "Mathematics", 58), (23, "Physics", 55), (23, "Structures", 52)],
    [(24, "Mathematics", 32), (24, "Physics", 28), (24, "Structures", 35)],
    [(25, "Mathematics", 88), (25, "Physics", 90), (25, "Structures", 85)],
]


def seed_data():
    """Insert sample students, attendance, and marks if DB is empty."""
    conn = get_connection()
    cursor = conn.cursor()

    # Only seed if students table is empty
    cursor.execute("SELECT COUNT(*) FROM students")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    # Insert students
    cursor.executemany(
        "INSERT INTO students (name, branch, year) VALUES (?, ?, ?)",
        SAMPLE_STUDENTS
    )

    # Insert attendance
    for idx, pct in enumerate(SAMPLE_ATTENDANCE, start=1):
        cursor.execute(
            "INSERT INTO attendance (student_id, percentage) VALUES (?, ?)",
            (idx, pct)
        )

    # Insert marks
    for student_marks in SAMPLE_MARKS:
        cursor.executemany(
            "INSERT INTO marks (student_id, subject, score) VALUES (?, ?, ?)",
            student_marks
        )

    conn.commit()
    conn.close()
    print(f"[OK] Database seeded with {len(SAMPLE_STUDENTS)} students")


# ---------------------------------------------------------------------------
# Query Helpers — Used by the Decision Engine
# ---------------------------------------------------------------------------

def execute_query(sql: str, params: tuple = ()):
    """
    Execute an arbitrary SQL query and return results as list of dicts.
    Used by the Decision Engine for dynamically-built queries.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    # Convert sqlite3.Row objects to plain dicts
    results = [dict(row) for row in rows]
    conn.close()
    return results


def get_low_attendance(threshold: float = 60.0):
    """Get students with attendance below the given threshold."""
    sql = """
        SELECT s.id, s.name, s.branch, s.year, a.percentage
        FROM students s
        JOIN attendance a ON s.id = a.student_id
        WHERE a.percentage < ?
        ORDER BY a.percentage ASC
    """
    return execute_query(sql, (threshold,))


def get_students_by_branch_year(branch: str = None, year: int = None):
    """Get students filtered by branch and/or year."""
    sql = """
        SELECT s.id, s.name, s.branch, s.year, a.percentage as attendance
        FROM students s
        JOIN attendance a ON s.id = a.student_id
        WHERE 1=1
    """
    params = []
    if branch:
        sql += " AND UPPER(s.branch) = UPPER(?)"
        params.append(branch)
    if year:
        sql += " AND s.year = ?"
        params.append(year)
    sql += " ORDER BY s.name"
    return execute_query(sql, tuple(params))


def get_student_marks(student_id: int = None, branch: str = None, year: int = None):
    """Get marks, optionally filtered by student, branch, or year."""
    sql = """
        SELECT s.id, s.name, s.branch, s.year, m.subject, m.score
        FROM students s
        JOIN marks m ON s.id = m.student_id
        WHERE 1=1
    """
    params = []
    if student_id:
        sql += " AND s.id = ?"
        params.append(student_id)
    if branch:
        sql += " AND UPPER(s.branch) = UPPER(?)"
        params.append(branch)
    if year:
        sql += " AND s.year = ?"
        params.append(year)
    sql += " ORDER BY s.name, m.subject"
    return execute_query(sql, tuple(params))


def get_all_students_with_details():
    """Get comprehensive data: student info + attendance + average marks."""
    sql = """
        SELECT s.id, s.name, s.branch, s.year,
               a.percentage as attendance,
               ROUND(AVG(m.score), 1) as avg_marks
        FROM students s
        JOIN attendance a ON s.id = a.student_id
        JOIN marks m ON s.id = m.student_id
        GROUP BY s.id
        ORDER BY s.name
    """
    return execute_query(sql)


def get_weak_students(attendance_threshold: float = 60.0, marks_threshold: float = 50.0):
    """
    Identify 'weak' students: attendance < threshold OR average marks < threshold.
    Returns data with flags explaining why each student is flagged.
    """
    sql = """
        SELECT s.id, s.name, s.branch, s.year,
               a.percentage as attendance,
               ROUND(AVG(m.score), 1) as avg_marks
        FROM students s
        JOIN attendance a ON s.id = a.student_id
        JOIN marks m ON s.id = m.student_id
        GROUP BY s.id
        HAVING a.percentage < ? OR AVG(m.score) < ?
        ORDER BY AVG(m.score) ASC
    """
    results = execute_query(sql, (attendance_threshold, marks_threshold))

    # Add explainability flags
    for student in results:
        reasons = []
        if student["attendance"] < attendance_threshold:
            reasons.append(f"attendance {student['attendance']}% < {attendance_threshold}%")
        if student["avg_marks"] < marks_threshold:
            reasons.append(f"avg marks {student['avg_marks']} < {marks_threshold}")
        student["flagged_reasons"] = " AND ".join(reasons)

    return results


def get_top_performers(top_n: int = 5):
    """Get top N students by average marks."""
    sql = """
        SELECT s.id, s.name, s.branch, s.year,
               a.percentage as attendance,
               ROUND(AVG(m.score), 1) as avg_marks
        FROM students s
        JOIN attendance a ON s.id = a.student_id
        JOIN marks m ON s.id = m.student_id
        GROUP BY s.id
        ORDER BY AVG(m.score) DESC
        LIMIT ?
    """
    return execute_query(sql, (top_n,))


# ---------------------------------------------------------------------------
# Auto-initialize on import
# ---------------------------------------------------------------------------

def init_db():
    """Create tables and seed data. Safe to call multiple times."""
    create_tables()
    seed_data()


# Allow running this file directly to set up the database
if __name__ == "__main__":
    init_db()
    print(f"[OK] Database ready at: {DB_PATH}")

    # Quick verification
    students = get_all_students_with_details()
    print(f"[INFO] Total students: {len(students)}")
    for s in students[:5]:
        print(f"   {s['name']} | {s['branch']} Year {s['year']} | "
              f"Attendance: {s['attendance']}% | Avg Marks: {s['avg_marks']}")
