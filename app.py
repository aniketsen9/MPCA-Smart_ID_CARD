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