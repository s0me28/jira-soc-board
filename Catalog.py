import os
import csv
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_file, session
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import re



def is_valid_email(email):
    return bool(re.match(r"^[^@]+@[^@]+\.[^@]+$", email))

app = Flask(__name__)
app.secret_key = 'ambmw'  # required for session

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

def is_common_password(password):
    common_passwords = {
        '123456', 'password', '123456789', '12345678', '12345',
        '111111', '1234567', 'sunshine', 'qwerty', 'iloveyou',
        'admin', 'welcome', 'monkey', 'login', 'abc123'
    }
    return password.lower() in common_passwords

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

    db_password_hash, role = user

    if db_password_hash != password:
        return "Incorrect password."

    session['user'] = email
    session['role'] = role

    if role == 'student':
        return redirect(url_for('student_dashboard', student_id=email))
    elif role == 'teacher':
        return redirect(url_for('teacher_dashboard'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')

        if not is_valid_email(email):
            return "Invalid email format."

        if len(password) < 8:
            return "Password must be at least 8 characters long."

        if is_common_password(password):
            return "Password is too common."

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                        (email, password, role))
            conn.commit()
        except Exception as e:
            conn.rollback()
            return f"Registration failed: {e}"
        finally:
            cur.close()
            conn.close()

        return "Registration successful. <a href='/'>Return to login</a>"

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/teacher', methods=['GET', 'POST'])
def teacher_dashboard():
    if session.get('role') != 'teacher':
        return redirect(url_for('home'))

    student_classes = []
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT class_name FROM student_classes WHERE student_id = %s
        """, (student_id,))
        student_classes = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()

    return render_template('teacher.html', grades=grades, students=students, student_classes=student_classes)



@app.route('/teacher/add_grade', methods=['POST'])
def add_grade():
    student_id = request.form.get('student_id')
    subject = request.form.get('subject')
    try:
        grade = float(request.form.get('grade'))
    except ValueError:
        return jsonify({'error': 'Invalid grade input'}), 400

    if not validate_grade(grade):
        return jsonify({'error': 'Invalid grade. Must be between 0 and 100'}), 400

    grades.setdefault(student_id, {}).setdefault(subject, []).append(grade)
    history.setdefault(student_id, {}).setdefault(subject, []).append(('add', grade, "timestamp_placeholder"))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO grade_history (student_id, subject, action, old_grade, new_grade, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (student_id, subject, 'add', None, grade, datetime.now()))
    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('teacher_dashboard'))


@app.route('/teacher/edit_grade', methods=['POST'])
def edit_grade():
    student_id = request.form.get('student_id')
    subject = request.form.get('subject')

    try:
        old_grade = float(request.form.get('old_grade'))
        new_grade = float(request.form.get('new_grade'))
    except ValueError:
        return jsonify({'error': 'Invalid grade input'}), 400

    if not validate_grade(new_grade):
        return jsonify({'error': 'Invalid grade. Must be between 0 and 100'}), 400

    if student_id in grades and subject in grades[student_id]:
        grades[student_id][subject] = [new_grade if grade == old_grade else grade for grade in grades[student_id][subject]]
        history.setdefault(student_id, {}).setdefault(subject, []).append(('edit', old_grade, new_grade, "timestamp_placeholder"))

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO grade_history (student_id, subject, action, old_grade, new_grade, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (student_id, subject, 'edit', old_grade, new_grade, datetime.now()))
        conn.commit()
        cur.close()
        conn.close()

    return redirect(url_for('teacher_dashboard'))


@app.route('/teacher/delete_grade', methods=['POST'])
def delete_grade():
    student_id = request.form.get('student_id')
    subject = request.form.get('subject')

    try:
        grade_to_delete = float(request.form.get('grade_to_delete'))
    except ValueError:
        return jsonify({'error': 'Invalid grade input'}), 400

    if student_id in grades and subject in grades[student_id]:
        grades[student_id][subject] = [grade for grade in grades[student_id][subject] if grade != grade_to_delete]
        history.setdefault(student_id, {}).setdefault(subject, []).append(('delete', grade_to_delete, "timestamp_placeholder"))


        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO grade_history (student_id, subject, action, old_grade, new_grade, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (student_id, subject, 'delete', grade_to_delete, None, datetime.now()))
        conn.commit()
        cur.close()
        conn.close()

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
                if validate_grade(grade):
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

    if not is_valid_email(email):
        return "Invalid student email."

    students[student_id] = {'name': name, 'email': email, 'classes': classes}
    for class_name in classes:
        class_students.setdefault(class_name, []).append(student_id)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        for class_name in classes:
            cur.execute("INSERT INTO student_classes (student_id, class_name) VALUES (%s, %s)",
                        (student_id, class_name))
        conn.commit()
    except Exception as e:
        conn.rollback()
        return f"Failed to save student classes: {e}"
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('teacher_dashboard'))


@app.route('/teacher/remove_student_from_class', methods=['POST'])
def remove_student_from_class():
    student_id = request.form.get('student_id')
    class_name = request.form.get('class_name')

    # Remove from in-memory dictionary (if present)
    if class_name in class_students and student_id in class_students[class_name]:
        class_students[class_name].remove(student_id)

    if student_id in students:
        if class_name in students[student_id].get('classes', []):
            students[student_id]['classes'].remove(class_name)

    # Remove from the database
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            DELETE FROM student_classes
            WHERE student_id = %s AND class_name = %s
        """, (student_id, class_name))
        conn.commit()
    except Exception as e:
        conn.rollback()
        return f"Error removing student from class: {e}"
    finally:
        cur.close()
        conn.close()

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

    # Fetch enrolled classes from DB
    cur.execute("""
        SELECT class_name FROM student_classes
        WHERE student_id = %s
    """, (student_id,))
    student_classes = [row[0] for row in cur.fetchall()]

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
        student_history=student_history,
        student_classes=student_classes
    )



@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        email = request.form.get('email')
        new_password = request.form.get('new_password')

        if not is_valid_email(email):
            return "Invalid email format."

        if len(new_password) < 8:
            return "Password must be at least 8 characters long."

        if is_common_password(new_password):
            return "Password is too common. Please choose a more secure password."

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
