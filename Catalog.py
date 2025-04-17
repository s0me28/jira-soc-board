import os, datetime

import os, datetime

from flask import Flask, request, jsonify, render_template, redirect, url_for, send_file
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

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT password, role FROM users WHERE username = %s", (email,))
    user = cur.fetchone()

    cur.close()
    conn.close()

    if user is None:
        return "User not found."

    db_password, role = user

    if password != db_password:
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
    grade = float(request.form.get('grade'))

    if not validate_grade(grade):
        return jsonify({'error': 'Invalid grade. Must be between 0 and 100'}), 400

    if student_id not in grades:
        grades[student_id] = {}
    if subject not in grades[student_id]:
        grades[student_id][subject] = []
    grades[student_id][subject].append(grade)

    action = ('add', grade, "timestamp_placeholder")
    if student_id not in history:
        history[student_id] = {}
    if subject not in history[student_id]:
        history[student_id][subject] = []
    history[student_id][subject].append(action)

    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/edit_grade', methods=['POST'])
def edit_grade():
    student_id = request.form.get('student_id')
    subject = request.form.get('subject')
    old_grade = float(request.form.get('old_grade'))
    new_grade = float(request.form.get('new_grade'))

    if not validate_grade(new_grade):
        return jsonify({'error': 'Invalid grade. Must be between 0 and 100'}), 400

    if student_id in grades and subject in grades[student_id]:
        grades[student_id][subject] = [new_grade if grade == old_grade else grade for grade in grades[student_id][subject]]

        action = ('edit', old_grade, new_grade, "timestamp_placeholder")
        if student_id not in history:
            history[student_id] = {}
        if subject not in history[student_id]:
            history[student_id][subject] = []
        history[student_id][subject].append(action)

    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/delete_grade', methods=['POST'])
def delete_grade():
    student_id = request.form.get('student_id')
    subject = request.form.get('subject')
    grade_to_delete = float(request.form.get('grade_to_delete'))

    if student_id in grades and subject in grades[student_id]:
        grades[student_id][subject] = [grade for grade in grades[student_id][subject] if grade != grade_to_delete]

        action = ('delete', grade_to_delete, "timestamp_placeholder")
        if student_id not in history:
            history[student_id] = {}
        if subject not in history[student_id]:
            history[student_id][subject] = []
        history[student_id][subject].append(action)

    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/upload_bulk_grades', methods=['POST'])
def upload_bulk_grades():
    file = request.files['file']
    if file:
        import csv
        reader = csv.reader(file)
        for row in reader:
            student_id, subject, grade = row
            grade = float(grade)
            if validate_grade(grade):
                if student_id not in grades:
                    grades[student_id] = {}
                if subject not in grades[student_id]:
                    grades[student_id][subject] = []
                grades[student_id][subject].append(grade)

                action = ('add', grade, "timestamp_placeholder")
                if student_id not in history:
                    history[student_id] = {}
                if subject not in history[student_id]:
                    history[student_id][subject] = []
                history[student_id][subject].append(action)

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

    except Exception as e:
        cur.close()
        conn.close()
        return jsonify({'error': str(e)}), 500

    cur.close()
    conn.close()

    return send_file(filepath, as_attachment=True)
@app.route('/teacher/add_student', methods=['POST'])
def add_student():
    student_id = request.form.get('student_id')
    name = request.form.get('name')
    email = request.form.get('email')
    classes = request.form.getlist('classes')

    students[student_id] = {'name': name, 'email': email, 'classes': classes}
    for class_name in classes:
        if class_name not in class_students:
            class_students[class_name] = []
        class_students[class_name].append(student_id)

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

    student_averages = {}
    for subject, grades_list in student_grades.items():
        student_averages[subject] = sum(grades_list) / len(grades_list) if grades_list else None
#
    student_history = {}
    for subject, action, old_grade, new_grade, timestamp in history_records:
        if subject not in student_history:
            student_history[subject] = []
        if action == 'add':
            student_history[subject].append(('add', new_grade, timestamp))
        elif action == 'edit':
            student_history[subject].append(('edit', old_grade, new_grade, timestamp))
        elif action == 'delete':
            student_history[subject].append(('delete', old_grade, timestamp))

    cur.close()
    conn.close()

    return render_template('student.html', student_id=student_id, student_grades=student_grades, student_averages=student_averages, student_history=student_history)


if __name__ == '__main__':
    app.run(debug=True)