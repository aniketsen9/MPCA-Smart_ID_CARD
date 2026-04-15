<<<<<<< HEAD
"""
Smart ID Card Attendance System
================================
Uses OpenCV's built-in BarcodeDetector (no pyzbar / ZBar DLL needed).
Requires: opencv-python >= 4.8, mysql-connector-python

Install:
    pip install opencv-python mysql-connector-python
"""

import cv2
import mysql.connector
from datetime import datetime
from datetime import timedelta
def calculate_total_classes(cursor, subject, department):
    from datetime import datetime, timedelta

    start_date = datetime(2026, 4, 3)
    today = datetime.now()

    total = 0
    current = start_date

    while current <= today:
        day_name = current.strftime("%A")

        cursor.execute("""
            SELECT COUNT(*)
            FROM timetable
            WHERE day_of_week = %s
            AND subject_name = %s
            AND department = %s
        """, (day_name, subject, department))

        count = cursor.fetchone()[0]
        total += count

        current += timedelta(days=1)

    return total
# ─────────────────────────────────────────────
# DB CONFIG
# ─────────────────────────────────────────────
DB_CONFIG = dict(
    host="localhost",
    user="root",
    password="Abhishek_05",
    database="smart_id_card"
)


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


# ─────────────────────────────────────────────
# BARCODE SCANNER  (OpenCV only — no pyzbar)
# ─────────────────────────────────────────────
def scan_qr_from_webcam(camera_index=0):
    cap = cv2.VideoCapture(camera_index)
    detector = cv2.QRCodeDetector()

    if not cap.isOpened():
        print("[Camera] ERROR: Cannot open webcam")
        return None

    print("[Scanner] Show QR code to camera. Press 'q' to cancel.")
    scanned_value = None

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[Camera] Failed to read frame")
            break

        data, bbox, _ = detector.detectAndDecode(frame)

        if data:
            scanned_value = data.strip()
            print("[Scanner] Scanned:", scanned_value)
            break

        cv2.imshow("QR Scanner | Press Q to cancel", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("[Scanner] Cancelled")
            break

    cap.release()
    cv2.destroyAllWindows()
    return scanned_value

#avoid duplicate
def has_already_marked(cursor, student_id, subject):
    today = datetime.now().date()
    # Assuming you have an 'attendance_logs' table with columns: student_id, subject, date
    cursor.execute("""
        SELECT id FROM attendance_logs 
        WHERE student_id = %s AND subject_name = %s AND log_date = %s
    """, (student_id, subject, today))
    return cursor.fetchone() is not None

# ─────────────────────────────────────────────
# DB HELPERS
# ─────────────────────────────────────────────
def fetch_student(cursor, scanned_value):
    cursor.execute("""
        SELECT student_id, name, srn, department
        FROM   students
        WHERE  student_id = %s OR srn = %s
    """, (scanned_value, scanned_value))
    return cursor.fetchone()

def get_current_classes(cursor, department):
    now = datetime.now()
    day_name = now.strftime("%A")

    cursor.execute("""
        SELECT subject_name, start_time, end_time
        FROM timetable
        WHERE day_of_week = %s
        AND department = %s
    """, (day_name, department))

    active_subjects = []
    late_subjects = []

    for subject, start, end in cursor.fetchall():
        start_dt = datetime.combine(now.date(), (datetime.min + start).time())
        end_dt = datetime.combine(now.date(), (datetime.min + end).time())

        late_limit = start_dt + timedelta(minutes=80)

        # Case 1: within 15 min → allowed
        if start_dt <= now <= late_limit:
            active_subjects.append(subject)

        # Case 2: after 15 min but before class ends → late
        elif late_limit < now <= end_dt:
            late_subjects.append(subject)

    return active_subjects, late_subjects


def mark_attendance(cursor, student_id, active_subjects, department):
    updated = []
    for subject in active_subjects:
        cursor.execute("""
            SELECT id, total_classes, attended_classes
            FROM   attendance
            WHERE  student_id = %s AND subject_name = %s
        """, (student_id, subject))
        row = cursor.fetchone()
        if row:
            rec_id, total, attended = row
            new_total = calculate_total_classes(cursor, subject, department)
            new_attended = attended + 1
            new_pct      = round((new_attended / new_total) * 100, 2)
            cursor.execute("""
                UPDATE attendance
                SET    total_classes    = %s,
                       attended_classes = %s,
                       percentage       = %s
                WHERE  id = %s
            """, (new_total, new_attended, new_pct, rec_id))
        else:
            total = calculate_total_classes(cursor, subject, department)

            cursor.execute("""
                INSERT INTO attendance
                (student_id, subject_name, total_classes, attended_classes, percentage)
                VALUES (%s, %s, %s, 1, %s)
            """, (student_id, subject, total, round((1 / total) * 100, 2)))
        updated.append(subject)
    return updated


def display_summary(cursor, student, updated_subjects):
    student_id = student[0]
    cursor.execute("""
        SELECT subject_name, total_classes, attended_classes, percentage
        FROM   attendance
        WHERE  student_id = %s
        ORDER  BY subject_name
    """, (student_id,))
    records = cursor.fetchall()

    print("\n" + "=" * 54)
    print("  STUDENT DETAILS")
    print("=" * 54)
    print(f"  Name       : {student[1]}")
    print(f"  SRN        : {student[2]}")
    print(f"  Department : {student[3]}")
    print("=" * 54)

    if not records:
        print("  No attendance records found.")
    else:
        print(f"  {'Subject':<25} {'Present':>8} {'Total':>6} {'%':>8}")
        print("  " + "-" * 50)
        tot_attended = tot_classes = 0
        for subject, total, attended, pct in records:
            marker = "  ✓" if subject in updated_subjects else ""
            print(f"  {subject:<25} {attended:>8} {total:>6} {pct:>7.2f}%{marker}")
            tot_attended += attended
            tot_classes  += total
        print("  " + "-" * 50)
        overall = round((tot_attended / tot_classes) * 100, 2) if tot_classes else 0
        print(f"  {'OVERALL':<25} {tot_attended:>8} {tot_classes:>6} {overall:>7.2f}%")
        if overall < 75:
            print("  ⚠ Attendance Low Warning!")

    print("=" * 54)
    if updated_subjects:
        print(f"  Marked present: {', '.join(updated_subjects)}")
    else:
        print("  (No attendance updated this scan)")
    print("=" * 54 + "\n")


# ─────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────
def process_scan(scanned_value):
    try:
        conn   = get_connection()
        cursor = conn.cursor()

        student = fetch_student(cursor, scanned_value)
        if not student:
            print(f"\n[!] No student found for: '{scanned_value}'\n")
            cursor.close(); conn.close()
            return

        department = student[3]
        now = datetime.now()
        print(f"\n[Time] {now.strftime('%A, %Y-%m-%d  %H:%M:%S')}")

        active_subjects, late_subjects = get_current_classes(cursor, department)

        # Inside process_scan(scanned_value):
        if active_subjects:
            # Filter out subjects where attendance was already marked today
            valid_to_mark = [s for s in active_subjects if not has_already_marked(cursor, student[0], s)]
            
            if not valid_to_mark:
                print("[!] Attendance already recorded for today's active session.")
                updated_subjects = []
            else:
                print(f"[Timetable] Active class(es): {', '.join(valid_to_mark)}")
                updated_subjects = mark_attendance(cursor, student[0], valid_to_mark, department)
                
                # IMPORTANT: Log this session so has_already_marked works next time
                for sub in updated_subjects:
                    cursor.execute("""
                        INSERT INTO attendance_logs (student_id, subject_name, log_date)
                        VALUES (%s, %s, %s)
                    """, (student[0], sub, datetime.now().date()))
                
                conn.commit()

        elif late_subjects:
            print(f"[Timetable] ⚠ Late for class: {', '.join(late_subjects)}")
            print("[Attendance] Not allowed after 15 minutes.")
            updated_subjects = []

        else:
            print("[Timetable] No class scheduled right now.")
            updated_subjects = []

        display_summary(cursor, student, updated_subjects)
        cursor.close()
        conn.close()

    except mysql.connector.Error as err:
        print(f"[DB Error] {err}")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
def main():
    print("=" * 54)
    print("  Smart ID Card Attendance System")
    print("=" * 54)
    print("  Press ENTER  -> open webcam barcode scanner")
    print("  Type SRN/ID  -> manual entry")
    print("  Type 'exit'  -> quit")
    print("=" * 54 + "\n")

    while True:
        user_input = input(">> ").strip()

        if user_input.lower() == "exit":
            print("Goodbye!")
            break

        if user_input == "":
            scanned_value = scan_qr_from_webcam(camera_index=0)
            if not scanned_value:
                scanned_value = input("   [Manual fallback] Enter SRN or Student ID: ").strip()
        else:
            scanned_value = user_input

        if not scanned_value:
            print("[!] Nothing entered. Try again.\n")
            continue

        process_scan(scanned_value)


if __name__ == "__main__":
    main()
=======
from flask import Flask, request, jsonify
import mysql.connector
from datetime import datetime

app = Flask(__name__)

# -----------------------------
# DB CONNECTION
# -----------------------------
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Aniketh#05",   # 🔴 CHANGE THIS
        database="attendance_db"
    )

# -----------------------------
# ADD STUDENT
# -----------------------------
@app.route("/add_student", methods=["POST"])
def add_student():
    data = request.json
    student_id = data["id"]
    name = data["name"]

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO students (id, name) VALUES (%s, %s)",
            (student_id, name)
        )
        conn.commit()
        msg = "Student added"
    except:
        msg = "Student already exists"

    conn.close()
    return jsonify({"message": msg})


# -----------------------------
# ADD MULTIPLE STUDENTS
# -----------------------------
@app.route("/add_students_bulk", methods=["POST"])
def add_students_bulk():
    data = request.json

    conn = get_db()
    cursor = conn.cursor()

    added = []
    skipped = []

    for student in data:
        try:
            cursor.execute(
                "INSERT INTO students (id, name) VALUES (%s, %s)",
                (student["id"], student["name"])
            )
            added.append(student["name"])
        except:
            skipped.append(student["name"])

    conn.commit()
    conn.close()

    return jsonify({
        "added": added,
        "skipped": skipped
    })


# -----------------------------
# SCAN → MARK PRESENT
# -----------------------------
@app.route("/scan", methods=["POST"])
def scan():
    data = request.json
    student_id = data["student_id"]
    subject = data["subject"]

    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M:%S")

    conn = get_db()
    cursor = conn.cursor()

    # Check student
    cursor.execute(
        "SELECT name FROM students WHERE id=%s",
        (student_id,)
    )
    student = cursor.fetchone()

    if not student:
        return jsonify({"error": "Student not found"})

    # Prevent duplicate
    cursor.execute("""
        SELECT * FROM attendance
        WHERE student_id=%s AND subject=%s AND date=%s
    """, (student_id, subject, date))

    if cursor.fetchone():
        return jsonify({"message": "Already marked today"})

    # Insert present
    cursor.execute("""
        INSERT INTO attendance (student_id, subject, date, time, status)
        VALUES (%s, %s, %s, %s, %s)
    """, (student_id, subject, date, time, "Present"))

    conn.commit()
    conn.close()

    return jsonify({
        "message": f"Attendance marked for {student[0]}",
        "time": time
    })


# -----------------------------
# MARK ABSENT
# -----------------------------
@app.route("/mark_absent", methods=["POST"])
def mark_absent():
    data = request.json
    subject = data["subject"]
    date = datetime.now().strftime("%Y-%m-%d")

    conn = get_db()
    cursor = conn.cursor()

    # All students
    cursor.execute("SELECT id FROM students")
    all_students = [row[0] for row in cursor.fetchall()]

    # Present students
    cursor.execute("""
        SELECT student_id FROM attendance
        WHERE subject=%s AND date=%s AND status='Present'
    """, (subject, date))

    present_students = [row[0] for row in cursor.fetchall()]

    absent_students = set(all_students) - set(present_students)

    for student_id in absent_students:

        # Prevent duplicate
        cursor.execute("""
            SELECT * FROM attendance
            WHERE student_id=%s AND subject=%s AND date=%s
        """, (student_id, subject, date))

        if cursor.fetchone():
            continue

        cursor.execute("""
            INSERT INTO attendance (student_id, subject, date, time, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (student_id, subject, date, "00:00:00", "Absent"))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Absent marked",
        "absent_students": list(absent_students)
    })


# -----------------------------
# VIEW ATTENDANCE
# -----------------------------
@app.route("/attendance/<int:student_id>", methods=["GET"])
def get_attendance(student_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT subject, date, status
        FROM attendance
        WHERE student_id=%s
    """, (student_id,))

    records = cursor.fetchall()
    conn.close()

    return jsonify(records)


# -----------------------------
# ATTENDANCE PERCENTAGE
# -----------------------------
@app.route("/percentage/<int:student_id>", methods=["GET"])
def percentage(student_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) FROM attendance
        WHERE student_id=%s AND status='Present'
    """, (student_id,))
    present = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM attendance
        WHERE student_id=%s
    """, (student_id,))
    total = cursor.fetchone()[0]

    conn.close()

    if total == 0:
        return jsonify({"percentage": 0})

    percent = (present / total) * 100

    return jsonify({"percentage": round(percent, 2)})


# -----------------------------
# RUN SERVER
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
>>>>>>> origin/main
