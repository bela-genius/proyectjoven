from flask import Flask, render_template, request, redirect, url_for, session, flash, g
import sqlite3
import os
import json
from werkzeug.utils import secure_filename
import uuid

app = Flask(__name__)
app.secret_key = 'jovenes_en_paz_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

DATABASE = 'database.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''
            CREATE TABLE IF NOT EXISTS daily_content (
                week INTEGER,
                day INTEGER,
                title TEXT,
                description TEXT,
                activities TEXT,
                links TEXT,
                files TEXT,
                PRIMARY KEY (week, day)
            )
        ''')
        db.commit()

ADMIN_USER = 'yaquehernandez'
ADMIN_PASS = '32272940'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/week/<int:week_num>')
def week_view(week_num):
    if week_num < 1 or week_num > 15:
        return redirect(url_for('index'))
    
    db = get_db()
    days_data = {}
    for i in range(1, 4):
        cur = db.execute('SELECT * FROM daily_content WHERE week = ? AND day = ?', (week_num, i))
        row = cur.fetchone()
        if row:
            days_data[i] = {
                'title': row['title'],
                'description': row['description'],
                'activities': json.loads(row['activities']) if row['activities'] else [],
                'links': json.loads(row['links']) if row['links'] else [],
                'files': json.loads(row['files']) if row['files'] else []
            }
        else:
            days_data[i] = {'title': f'Día {i}', 'description': '', 'activities': [], 'links': [], 'files': []}
            
    return render_template('week.html', week_num=week_num, days=days_data)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == ADMIN_USER and request.form['password'] == ADMIN_PASS:
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        flash('Credenciales incorrectas')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

@app.route('/admin')
def admin_dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('admin.html')

@app.route('/admin/edit/<int:week_num>/<int:day_num>', methods=['GET', 'POST'])
def edit_day(week_num, day_num):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    db = get_db()
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        
        # Activities (one per line)
        activities_text = request.form['activities']
        activities_list = [a.strip() for a in activities_text.splitlines() if a.strip()]
        
        # Links
        links_text = request.form['links']
        links_list = [l.strip() for l in links_text.splitlines() if l.strip()]
        
        # Existing Files
        cur = db.execute('SELECT files FROM daily_content WHERE week = ? AND day = ?', (week_num, day_num))
        row = cur.fetchone()
        existing_files = json.loads(row['files']) if row and row['files'] else []
        
        # Remove files if requested
        files_to_remove = request.form.getlist('remove_files')
        existing_files = [f for f in existing_files if f['saved'] not in files_to_remove]

        # New uploads
        uploaded_files = request.files.getlist('new_files')
        for file in uploaded_files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4()}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                existing_files.append({'original': filename, 'saved': unique_filename})
        
        db.execute('''
            INSERT OR REPLACE INTO daily_content (week, day, title, description, activities, links, files)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (week_num, day_num, title, description, json.dumps(activities_list), json.dumps(links_list), json.dumps(existing_files)))
        db.commit()
        
        return redirect(url_for('admin_dashboard'))
    
    cur = db.execute('SELECT * FROM daily_content WHERE week = ? AND day = ?', (week_num, day_num))
    row = cur.fetchone()
    content = {
        'title': row['title'] if row else f'Actividad Día {day_num}',
        'description': row['description'] if row else '',
        'activities': '\n'.join(json.loads(row['activities'])) if row and row['activities'] else '',
        'links': '\n'.join(json.loads(row['links'])) if row and row['links'] else '',
        'files': json.loads(row['files']) if row and row['files'] else []
    }
    
    return render_template('edit_day.html', week_num=week_num, day_num=day_num, content=content)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
