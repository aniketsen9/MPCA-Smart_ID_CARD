## Smart ID Card Attendance System

A lightweight, automated attendance solution using **OpenCV** for QR/Barcode scanning and **MySQL** for data persistence.

----

### 🚀 Features
* **No-DLL Scanning:** Uses OpenCV’s native `QRCodeDetector` (no `pyzbar` or ZBar dependencies required).
* **Dynamic Timetable:** Attendance is only granted if a student scans during their department's scheduled class time.
* **Late Policy:** Automatically enforces a **15-minute** late-entry threshold.
* **Duplicate Prevention:** Integrated `attendance_logs` to prevent multiple entries for the same class on the same day.
* **Manual Fallback:** Supports manual SRN/ID entry if the webcam is unavailable.

----

### 🛠️ Tech Stack
* **Language:** Python 3.8+
* **Library:** `opencv-python`, `mysql-connector-python`
* **Database:** MySQL

----

### 📋 Prerequisites
1.  **Install Libraries:**
    ```bash
    pip install opencv-python mysql-connector-python
    ```
2.  **Database Setup:** Create a database named `smart_id_card` and ensure the following tables exist:
    * `students`: (`student_id`, `name`, `srn`, `department`)
    * `timetable`: (`day_of_week`, `subject_name`, `start_time`, `end_time`, `department`)
    * `attendance`: (`student_id`, `subject_name`, `total_classes`, `attended_classes`, `percentage`)
    * `attendance_logs`: (`student_id`, `subject_name`, `log_date`)

----

### ⚙️ Configuration
Update the `DB_CONFIG` dictionary in the script with your MySQL credentials:
```python
DB_CONFIG = dict(
    host="localhost",
    user="root",
    password="YOUR_PASSWORD",
    database="smart_id_card"
)
```

----

### 🚦 How to Use
1.  **Run the script:** `python attendance_system.py`
2.  **Scan:** Press **ENTER** to trigger the webcam. Hold the QR code in view.
3.  **Manual Entry:** Type the **SRN** directly into the console and press Enter.
4.  **Exit:** Type `exit` to close the application.

----

### ⚠️ Important Note
The system calculates `total_classes` based on a semester start date of **April 3, 2026**. Modify the `start_date` variable in `calculate_total_classes()` to match your academic calendar.
