"""
Smart ID Card Attendance System (RFID Version)
==============================================
Uses Serial communication to read UIDs from an ESP32 + RC522.
Requires: pyserial, mysql-connector-python
"""

import serial
import time
import mysql.connector
from datetime import datetime, timedelta

# ─────────────────────────────────────────────
# SERIAL & DB CONFIG
# ─────────────────────────────────────────────
SERIAL_PORT = 'COM5' 
BAUD_RATE = 115200

DB_CONFIG = dict(
    host="localhost",
    user="root",
    password="Abhishek_05", # Your password from the provided code
    database="smart_id_card"
)

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2) # Allow ESP32 to reset
except Exception as e:
    print(f"[Serial] ERROR: Could not open {SERIAL_PORT}. {e}")
    ser = None

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)

# ─────────────────────────────────────────────
# RFID SCANNER (Replaces QR Scanner)
# ─────────────────────────────────────────────
def scan_rfid_from_serial():
    if not ser:
        print("[Scanner] ERROR: Serial port not available.")
        return None

    print("[Scanner] Waiting for RFID tap...")
    ser.reset_input_buffer() 
    
    while True:
        if ser.in_waiting > 0:
            try:
                raw_line = ser.readline().decode('utf-8').strip()
                if "UID:" in raw_line:
                    rfid_value = raw_line.replace("UID: ", "").strip()
                    print(f"[Scanner] Scanned RFID: {rfid_value}")
                    return rfid_value
            except Exception as e:
                print(f"[Scanner] Data Error: {e}")
        
        time.sleep(0.1)

# ─────────────────────────────────────────────
# ATTENDANCE LOGIC (Keep your existing functions)
# ─────────────────────────────────────────────

def calculate_total_classes(cursor, subject, department):
    start_date = datetime(2026, 4, 3)
    today = datetime.now()
    total = 0
    current = start_date
    while current <= today:
        day_name = current.strftime("%A")
        cursor.execute("SELECT COUNT(*) FROM timetable WHERE day_of_week = %s AND subject_name = %s AND department = %s", 
                       (day_name, subject, department))
        total += cursor.fetchone()[0]
        current += timedelta(days=1)
    return total

def has_already_marked(cursor, student_id, subject):
    today = datetime.now().date()
    cursor.execute("SELECT id FROM attendance_logs WHERE student_id = %s AND subject_name = %s AND log_date = %s", 
                   (student_id, subject, today))
    return cursor.fetchone() is not None

def fetch_student(cursor, scanned_value):
    # This query looks for the RFID UID in three possible columns
    cursor.execute("""
        SELECT student_id, name, srn, department
        FROM   students
        WHERE  rfid_uid = %s OR student_id = %s OR srn = %s
    """, (scanned_value, scanned_value, scanned_value))
    return cursor.fetchone()

def get_current_classes(cursor, department):
    now = datetime.now()
    day_name = now.strftime("%A")
    cursor.execute("SELECT subject_name, start_time, end_time FROM timetable WHERE day_of_week = %s AND department = %s", 
                   (day_name, department))
    active, late = [], []
    for subject, start, end in cursor.fetchall():
        start_dt = datetime.combine(now.date(), (datetime.min + start).time())
        end_dt = datetime.combine(now.date(), (datetime.min + end).time())
        late_limit = start_dt + timedelta(minutes=80)
        if start_dt <= now <= late_limit: active.append(subject)
        elif late_limit < now <= end_dt: late.append(subject)
    return active, late

def mark_attendance(cursor, student_id, active_subjects, department):
    updated = []
    for subject in active_subjects:
        cursor.execute("SELECT id, total_classes, attended_classes FROM attendance WHERE student_id = %s AND subject_name = %s", 
                       (student_id, subject))
        row = cursor.fetchone()
        new_total = calculate_total_classes(cursor, subject, department)
        if row:
            rec_id, _, attended = row
            new_attended = attended + 1
            cursor.execute("UPDATE attendance SET total_classes=%s, attended_classes=%s, percentage=%s WHERE id=%s", 
                           (new_total, new_attended, round((new_attended/new_total)*100, 2), rec_id))
        else:
            cursor.execute("INSERT INTO attendance (student_id, subject_name, total_classes, attended_classes, percentage) VALUES (%s, %s, %s, 1, %s)", 
                           (student_id, subject, new_total, round((1/new_total)*100, 2)))
        updated.append(subject)
    return updated

def display_summary(cursor, student, updated_subjects):
    student_id = student[0]
    cursor.execute("SELECT subject_name, total_classes, attended_classes, percentage FROM attendance WHERE student_id = %s ORDER BY subject_name", (student_id,))
    records = cursor.fetchall()
    print("\n" + "=" * 54 + "\n  STUDENT DETAILS\n" + "=" * 54)
    print(f"  Name: {student[1]}\n  SRN: {student[2]}\n  Dept: {student[3]}\n" + "=" * 54)
    if not records: print("  No records found.")
    else:
        print(f"  {'Subject':<25} {'Present':>8} {'Total':>6} {'%':>8}\n  " + "-" * 50)
        for sub, tot, att, pct in records:
            marker = "  ✓" if sub in updated_subjects else ""
            print(f"  {sub:<25} {att:>8} {tot:>6} {pct:>7.2f}%{marker}")
    print("=" * 54)

# ─────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────
def process_scan(scanned_value):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        student = fetch_student(cursor, scanned_value)
        if not student:
            # Send error message to LCD
            ser.write(b"INVALID CARD,Access Denied\n")
            print(f"\n[!] No student found for: '{scanned_value}'\n")
            cursor.close(); conn.close()
            return

        student_name = student[1]
        department = student[3]
        active_subjects, late_subjects = get_current_classes(cursor, department)

        if active_subjects:
            valid_to_mark = [s for s in active_subjects if not has_already_marked(cursor, student[0], s)]
            
            if not valid_to_mark:
                # Already marked today
                ser.write(f"{student_name},ALREADY MARKED\n".encode())
                updated_subjects = []
            else:
                updated_subjects = mark_attendance(cursor, student[0], valid_to_mark, department)
                # Success: Send Name and "Marked" to LCD
                ser.write(f"{student_name},PRESENT MARKED\n".encode())
                
                for sub in updated_subjects:
                    cursor.execute("""
                        INSERT INTO attendance_logs (student_id, subject_name, log_date)
                        VALUES (%s, %s, %s)
                    """, (student[0], sub, datetime.now().date()))
                conn.commit()

        elif late_subjects:
            # Late: Send warning to LCD
            ser.write(f"{student_name},LATE: BLOCKED\n".encode())
            updated_subjects = []

        else:
            # No class: Send status to LCD
            ser.write(f"{student_name},NO ACTIVE CLASS\n".encode())
            updated_subjects = []

        display_summary(cursor, student, updated_subjects)
        cursor.close()
        conn.close()

    except Exception as e:
        print(f"[Error] {e}")
        if ser: ser.write(b"SYSTEM ERROR,Check Logs\n")

def main():
    print("=" * 54 + "\n  RFID Attendance System Active\n" + "=" * 54)
    print("  Press ENTER -> Scan RFID Card\n  Type 'exit' -> Quit\n" + "=" * 54)

    while True:
        user_input = input(">> ").strip()
        if user_input.lower() == "exit": break
        
        # If user presses enter, it triggers the RFID scan
        scanned_value = scan_rfid_from_serial() if user_input == "" else user_input
        
        if scanned_value:
            process_scan(scanned_value)

if __name__ == "__main__":
    main()