\import os
import re
import csv
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from email_validator import validate_email, EmailNotValidError
import psycopg2

app = Flask(__name__)

grades = {}
students = {}
class_students = {}
history = {}

def get_db_connection():
    return psycopg2.connect(
        dbname='Catalog',
        user='postgres',
        password='1q2w3e',
        host='localhost'
    )

def validate_grade(grade):
    return 0 <= grade <= 100

def validate_student_id(student_id):
    return bool(re.match(r'^[A-Za-z0-9_\-]+$', student_id))

def validate_subject(subject):
    return subject.strip() != ""

def validate_name(name):
    return bool(re.match(r'^[A-Za-z\s]+$', name.strip()))

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')

    try:
        validate_email(email)
    except EmailNotValidError:
        return "Invalid email format."

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT password, role FROM users WHERE username = %s", (email,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user is None:
        return "User not found."

    db_password_hash, role = user
    if not check_password_hash(db_password_hash, password):
        return "Incorrect password."

    if role == 'student':
        return redirect(url_for('student_dashboard', student_id=email))
    elif role == 'teacher':
        return redirect(url_for('teacher_dashboard'))
    else:
        return "Unknown role."

@app.route('/teacher')
def teacher_dashboard():
    return render_template('teacher.html', grades=grades, students=students)

@app.route('/teacher/add_grade', methods=['POST'])
def add_grade():
    student_id = request.form.get('student_id')
    subject = request.form.get('subject')
    try:
        grade = float(request.form.get('grade'))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid grade format'}), 400

    if not validate_student_id(student_id) or not validate_subject(subject) or not validate_grade(grade):
        return jsonify({'error': 'Invalid input'}), 400

    grades.setdefault(student_id, {}).setdefault(subject, []).append(grade)
    history.setdefault(student_id, {}).setdefault(subject, []).append(('add', grade, "timestamp_placeholder"))

    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/edit_grade', methods=['POST'])
def edit_grade():
    student_id = request.form.get('student_id')
    subject = request.form.get('subject')
    try:
        old_grade = float(request.form.get('old_grade'))
        new_grade = float(request.form.get('new_grade'))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid grade format'}), 400

    if not validate_grade(new_grade) or not validate_student_id(student_id) or not validate_subject(subject):
        return jsonify({'error': 'Invalid input'}), 400

    if student_id in grades and subject in grades[student_id]:
        grades[student_id][subject] = [
            new_grade if grade == old_grade else grade for grade in grades[student_id][subject]
        ]
        history.setdefault(student_id, {}).setdefault(subject, []).append(('edit', old_grade, new_grade, "timestamp_placeholder"))

    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/delete_grade', methods=['POST'])
def delete_grade():
    student_id = request.form.get('student_id')
    subject = request.form.get('subject')
    try:
        grade_to_delete = float(request.form.get('grade_to_delete'))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid grade format'}), 400

    if not validate_student_id(student_id) or not validate_subject(subject):
        return jsonify({'error': 'Invalid input'}), 400

    if student_id in grades and subject in grades[student_id]:
        grades[student_id][subject] = [grade for grade in grades[student_id][subject] if grade != grade_to_delete]
        history.setdefault(student_id, {}).setdefault(subject, []).append(('delete', grade_to_delete, "timestamp_placeholder"))

    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/upload_bulk_grades', methods=['POST'])
def upload_bulk_grades():
    file = request.files['file']
    if file and file.filename.endswith('.csv'):
        try:
            reader = csv.reader(file.stream.read().decode("utf-8").splitlines())
            for row in reader:
                if len(row) != 3:
                    continue
                student_id, subject, grade = row
                try:
                    grade = float(grade)
                except ValueError:
                    continue
                if validate_student_id(student_id) and validate_subject(subject) and validate_grade(grade):
                    grades.setdefault(student_id, {}).setdefault(subject, []).append(grade)
                    history.setdefault(student_id, {}).setdefault(subject, []).append(('add', grade, "timestamp_placeholder"))
        except Exception:
            return "Error processing file.", 400

    return redirect(url_for('teacher_dashboard'))

@app.route('/backup/<table_name>', methods=['GET'])
def backup_table(table_name):
    conn = get_db_connection()
    cur = conn.cursor()

    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    filename = f"{table_name}_backup_{timestamp}.csv"
    filepath = os.path.join("backups", filename)

    os.makedirs("backups", exist_ok=True)

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            cur.copy_expert(f"COPY {table_name} TO STDOUT WITH CSV HEADER", f)
    except Exception:
        cur.close()
        conn.close()
        return "Failed to backup table.", 500

    cur.close()
    conn.close()
    return send_file(filepath, as_attachment=True)

@app.route('/teacher/add_student', methods=['POST'])
def add_student():
    student_id = request.form.get('student_id')
    name = request.form.get('name')
    email = request.form.get('email')
    classes = request.form.getlist('classes')

    if not (validate_student_id(student_id) and validate_name(name)):
        return "Invalid student data", 400

    try:
        validate_email(email)
    except EmailNotValidError:
        return "Invalid email format.", 400

    students[student_id] = {'name': name, 'email': email, 'classes': classes}
    for class_name in classes:
        class_students.setdefault(class_name, []).append(student_id)

    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/remove_student', methods=['POST'])
def remove_student():
    student_id = request.form.get('student_id')
    classes = students.get(student_id, {}).get('classes', [])

    for class_name in classes:
        if class_name in class_students and student_id in class_students[class_name]:
            class_students[class_name].remove(student_id)

    students.pop(student_id, None)
    return redirect(url_for('teacher_dashboard'))

@app.route('/student/<student_id>')
def student_dashboard(student_id):
    student_grades = grades.get(student_id, {})

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT subject, action, old_grade, new_grade, timestamp
        FROM grade_history
        WHERE student_id = %s
        ORDER BY timestamp DESC
    """, (student_id,))
    history_records = cur.fetchall()
    cur.close()
    conn.close()

    student_averages = {
        subject: (sum(grades_list) / len(grades_list)) if grades_list else None
        for subject, grades_list in student_grades.items()
    }

    student_history = {}
    for subject, action, old_grade, new_grade, timestamp in history_records:
        student_history.setdefault(subject, [])
        if action == 'add':
            student_history[subject].append(('add', new_grade, timestamp))
        elif action == 'edit':
            student_history[subject].append(('edit', old_grade, new_grade, timestamp))
        elif action == 'delete':
            student_history[subject].append(('delete', old_grade, timestamp))

    return render_template('student.html',
        student_id=student_id,
        student_grades=student_grades,
        student_averages=student_averages,
        student_history=student_history
    )

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        email = request.form.get('email')
        new_password = request.form.get('new_password')

        try:
            validate_email(email)
        except EmailNotValidError:
            return "Invalid email format."

        if len(new_password) < 8:
            return "Password must be at least 8 characters."

        hashed_password = generate_password_hash(new_password)

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET password = %s WHERE username = %s", (hashed_password, email))
        conn.commit()
        cur.close()
        conn.close()

        return "Password successfully updated. <a href='/'>Return to login</a>"

    return render_template('reset_password.html')

if __name__ == '__main__':
    app.run(debug=True)
