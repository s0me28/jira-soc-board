from flask import Flask, request, jsonify, render_template, redirect, url_for

app = Flask(__name__)

grades = {}
students = {}
class_students = {}
history = {}


def validate_grade(grade):
    return 0 <= grade <= 100


@app.route('/')
def home():
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    if '@student.ambmw.ro' in email:
        return redirect(url_for('student_dashboard', student_id=email))
    elif '@teacher.ambmw.ro' in email:
        return redirect(url_for('teacher_dashboard'))
    else:
        return "Invalid email domain. Please use a valid student or teacher email."



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

    action = ('add', grade, "timestamp_placeholder")  # Timestamp can be added here
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
        grades[student_id][subject] = [new_grade if grade == old_grade else grade for grade in
                                       grades[student_id][subject]]

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
        # Assuming file is a CSV of student_id, subject, grade
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


@app.route('/teacher/add_student', methods=['POST'])
def add_student():
    student_id = request.form.get('student_id')
    name = request.form.get('name')
    email = request.form.get('email')
    classes = request.form.getlist('classes')  # list of class names

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
    return render_template('student.html', student_id=student_id, student_grades=student_grades)




if __name__ == '__main__':
    app.run(debug=True)
