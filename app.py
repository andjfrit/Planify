# app.py

from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime,timedelta,date
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, SelectField, TextAreaField, BooleanField, DateField, HiddenField
from wtforms.validators import DataRequired, EqualTo, Length, Optional

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'  # Replace with a secure key

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database connection function
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# User model for Flask-Login
class User(UserMixin):
    def __init__(self, user_row):
        self.id = user_row['id']
        self.username = user_row['username']
        self.password = user_row['password']

# User loader callback
@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user_row = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user_row:
        return User(user_row)
    else:
        return None

# Registration form
class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(max=150)])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

# Login form
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(max=150)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

# Habit form
class HabitForm(FlaskForm):
    name = StringField('Habit Name', validators=[DataRequired(), Length(max=150)])
    frequency = IntegerField('Frequency', validators=[DataRequired()])
    period = SelectField('Period', choices=[('day', 'Day'), ('week', 'Week'), ('month', 'Month'), ('year', 'Year')], validators=[DataRequired()])
    submit = SubmitField('Add Habit')

class TaskForm(FlaskForm):
    name = StringField('Task Name', validators=[DataRequired(), Length(max=150)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    date = DateField('Date', validators=[Optional()], format='%Y-%m-%d')
    habit_id = HiddenField('Habit ID', validators=[Optional()])
    submit = SubmitField('Add Task')

# Route: Home (Redirect to Dashboard or Login)
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))

# Route: Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        conn = get_db_connection()
        hashed_password = generate_password_hash(form.password.data, method='pbkdf2:sha256')
        try:
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                         (form.username.data, hashed_password))
            conn.commit()
            flash('Registration successful. Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists. Please choose a different one.', 'danger')
        finally:
            conn.close()
    return render_template('register.html', form=form)

# Route: Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        conn = get_db_connection()
        user_row = conn.execute('SELECT * FROM users WHERE username = ?', (form.username.data,)).fetchone()
        conn.close()
        if user_row and check_password_hash(user_row['password'], form.password.data):
            user = User(user_row)
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html', form=form)

# Route: Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Route: Dashboard
@app.route('/dashboard')
@login_required
def dashboard():
    today = date.today().strftime('%A, %B %d, %Y')
    return render_template('dashboard.html', date=today)

@app.route('/habits', methods=['GET', 'POST'])
@login_required
def habits():
    form = HabitForm()
    conn = get_db_connection()
    editing_habit = None

    # Handle form submission
    if request.method == 'POST':
        habit_id = request.form.get('habit_id')
        if habit_id:  # Update existing habit
            if form.validate_on_submit():
                conn.execute('''
                    UPDATE habits
                    SET name = ?, frequency = ?, period = ?
                    WHERE id = ? AND user_id = ?
                ''', (form.name.data, form.frequency.data, form.period.data, habit_id, current_user.id))
                conn.commit()
                flash('Habit updated successfully.', 'success')
                return redirect(url_for('habits'))
        else:  # Add new habit
            if form.validate_on_submit():
                conn.execute('''
                    INSERT INTO habits (user_id, name, frequency, period, times_completed)
                    VALUES (?, ?, ?, ?, 0)
                ''', (current_user.id, form.name.data, form.frequency.data, form.period.data))
                conn.commit()
                flash('Habit added successfully.', 'success')
                return redirect(url_for('habits'))

    # Handle editing habit
    edit_habit_id = request.args.get('edit')
    if edit_habit_id:
        editing_habit = conn.execute('SELECT * FROM habits WHERE id = ? AND user_id = ?', (edit_habit_id, current_user.id)).fetchone()
        if editing_habit:
            form.name.data = editing_habit['name']
            form.frequency.data = editing_habit['frequency']
            form.period.data = editing_habit['period']
        else:
            flash('Habit not found.', 'danger')

    habits = conn.execute('SELECT * FROM habits WHERE user_id = ?', (current_user.id,)).fetchall()
    conn.close()
    return render_template('habits.html', form=form, habits=habits, editing_habit=editing_habit)

# Route: Delete Habit
@app.route('/delete_habit/<int:habit_id>', methods=['POST'])
@login_required
def delete_habit(habit_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM habits WHERE id = ? AND user_id = ?', (habit_id, current_user.id))
    conn.commit()
    conn.close()
    flash('Habit deleted successfully.', 'success')
    return redirect(url_for('habits'))



@app.route('/tasks', methods=['GET', 'POST'])
@login_required
def tasks():
    task_form = TaskForm()
    conn = get_db_connection()
    editing_task = None

    # Determine the current view
    view_type = request.args.get('view', 'day')
    today = date.today()
    dates = []

    if view_type == 'day':
        dates.append(today)
    elif view_type == '3day':
        for i in range(3):
            dates.append(today + timedelta(days=i))
    elif view_type == 'week':
        # Start from Sunday
        start_day = today - timedelta(days=today.weekday() + 1 if today.weekday() != 6 else 0)
        for i in range(7):
            dates.append(start_day + timedelta(days=i))

    # Handle form submission
    if request.method == 'POST':
        task_id = request.form.get('task_id')
        habit_id = task_form.habit_id.data or None
        habit_id = int(habit_id) if habit_id else None

        if task_id:  # Update existing task
            if task_form.validate_on_submit():
                conn.execute('''
                    UPDATE tasks
                    SET habit_id = ?, name = ?, description = ?, date = ?
                    WHERE id = ? AND user_id = ?
                ''', (
                    habit_id,
                    task_form.name.data,
                    task_form.description.data,
                    task_form.date.data.isoformat() if task_form.date.data else None,
                    task_id,
                    current_user.id
                ))
                conn.commit()
                flash('Task updated successfully.', 'success')
                return redirect(url_for('tasks', view=view_type))
        else:  # Add new task
            if task_form.validate_on_submit():
                conn.execute('''
                    INSERT INTO tasks (user_id, habit_id, name, description, date, completed)
                    VALUES (?, ?, ?, ?, ?, 0)
                ''', (
                    current_user.id,
                    habit_id,
                    task_form.name.data,
                    task_form.description.data,
                    task_form.date.data.isoformat() if task_form.date.data else None
                ))
                conn.commit()
                flash('Task added successfully.', 'success')
                return redirect(url_for('tasks', view=view_type))

    # Handle editing task
    edit_task_id = request.args.get('edit')
    if edit_task_id:
        editing_task = conn.execute('SELECT * FROM tasks WHERE id = ? AND user_id = ?', (edit_task_id, current_user.id)).fetchone()
        if editing_task:
            task_form.name.data = editing_task['name']
            task_form.description.data = editing_task['description']
            task_form.date.data = datetime.strptime(editing_task['date'], '%Y-%m-%d').date() if editing_task['date'] else None
            task_form.habit_id.data = str(editing_task['habit_id']) if editing_task['habit_id'] else ''
        else:
            flash('Task not found.', 'danger')

    # Retrieve habits and tasks
    habits = conn.execute('SELECT * FROM habits WHERE user_id = ?', (current_user.id,)).fetchall()

    undated_tasks = conn.execute('''
        SELECT * FROM tasks
        WHERE user_id = ? AND date IS NULL
    ''', (current_user.id,)).fetchall()

    dated_tasks = conn.execute('''
        SELECT * FROM tasks
        WHERE user_id = ? AND date IS NOT NULL
    ''', (current_user.id,)).fetchall()

    # Prepare tasks by date
    tasks_by_date = {d.strftime('%Y-%m-%d'): [] for d in dates}

    for task in dated_tasks:
        task_date_str = task['date']
        if task_date_str in tasks_by_date:
            tasks_by_date[task_date_str].append(task)

    conn.close()

    return render_template('tasks.html', task_form=task_form, habits=habits,
                           undated_tasks=undated_tasks, tasks_by_date=tasks_by_date,
                           dates=dates, view_type=view_type, editing_task=editing_task, today=today)
# Route: Delete Task
@app.route('/delete_task/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM tasks WHERE id = ? AND user_id = ?', (task_id, current_user.id))
    conn.commit()
    conn.close()
    flash('Task deleted successfully.', 'success')
    return redirect(url_for('tasks'))

@app.route('/toggle_task/<int:task_id>', methods=['POST'])
@login_required
def toggle_task(task_id):
    view_type = request.args.get('view', 'day')
    conn = get_db_connection()
    task = conn.execute('SELECT * FROM tasks WHERE id = ? AND user_id = ?', (task_id, current_user.id)).fetchone()
    if task:
        new_status = 0 if task['completed'] else 1
        conn.execute('UPDATE tasks SET completed = ? WHERE id = ? AND user_id = ?', (new_status, task_id, current_user.id))
        conn.commit()
        # Adjust habit completion if necessary
        if task['habit_id']:
            if new_status == 1:
                conn.execute('''
                    UPDATE habits
                    SET times_completed = times_completed + 1
                    WHERE id = ? AND user_id = ?
                ''', (task['habit_id'], current_user.id))
            else:
                conn.execute('''
                    UPDATE habits
                    SET times_completed = times_completed - 1
                    WHERE id = ? AND user_id = ? AND times_completed > 0
                ''', (task['habit_id'], current_user.id))
            conn.commit()
        flash('Task status updated.', 'success')
    else:
        flash('Task not found.', 'danger')
    conn.close()
    return redirect(url_for('tasks', view=view_type))

if __name__ == '__main__':
    app.run()