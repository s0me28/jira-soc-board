from flask import Flask, request, jsonify, render_template, redirect, url_for

app = Flask(__name__)

grades = {}  # Dictionary to store grades {student_id: {subject: [grades]}}


def validate_grade(grade):
    return 0 <= grade <= 100


@app.route('/')
def home():
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')

    if email.endswith('@student.ambmw.ro'):
        return redirect(url_for('student_menu'))
    elif email.endswith('@teacher.ambmw.ro'):
        return redirect(url_for('teacher_menu'))
    else:
        return render_template('login.html', error='Invalid email domain. Use a student or teacher email.')


@app.route('/teacher')
def teacher_menu():
    return render_template('teacher.html')


@app.route('/student')
def student_menu():
    return render_template('student.html')


@app.route('/grades', methods=['POST'])
def add_grade():
    data = request.form
    student_id = data.get('student_id')
    subject = data.get('subject')
    grade = data.get('grade')

    try:
        grade = float(grade)
        if not validate_grade(grade):
            return jsonify({'error': 'Invalid grade. Must be between 0 and 100'}), 400
    except ValueError:
        return jsonify({'error': 'Grade must be a number'}), 400

    if student_id not in grades:
        grades[student_id] = {}
    if subject not in grades[student_id]:
        grades[student_id][subject] = []

    grades[student_id][subject].append(grade)
    return render_template('teacher.html', message='Grade added successfully!')


@app.route('/grades/<student_id>', methods=['GET'])
def get_grades(student_id):
    student_grades = grades.get(student_id, {})
    return jsonify(student_grades)


@app.route('/grades/<student_id>/average', methods=['GET'])
def get_average(student_id):
    student_grades = grades.get(student_id, {})

    total, count = 0, 0
    for subject in student_grades:
        total += sum(student_grades[subject])
        count += len(student_grades[subject])

    average = total / count if count > 0 else 0
    return jsonify({'average': average})


if __name__ == '__main__':
    app.run(debug=True)
