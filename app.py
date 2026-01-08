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

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

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
                evidence TEXT,
                PRIMARY KEY (week, day)
            )
        ''')
        
        # Comprehensive column check and migration
        columns = [info[1] for info in db.execute("PRAGMA table_info(daily_content)").fetchall()]
        
        needed_columns = {
            'activities': 'TEXT',
            'links': 'TEXT',
            'files': 'TEXT',
            'description': 'TEXT',
            'title': 'TEXT',
            'evidence': 'TEXT'
        }
        
        for col, col_type in needed_columns.items():
            if col not in columns:
                try:
                    db.execute(f'ALTER TABLE daily_content ADD COLUMN {col} {col_type}')
                except sqlite3.OperationalError:
                    pass
                    
        db.commit()

ADMIN_USER = 'yaquehernandez'
ADMIN_PASS = '32272940'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/week/<int:week_num>')
def week_view(week_num):
    if not (1 <= week_num <= 15):
        return redirect(url_for('index'))
    
    days_data = {}
    for i in range(1, 4):
        row = query_db('SELECT * FROM daily_content WHERE week = ? AND day = ?', (week_num, i), one=True)
        if row:
            days_data[i] = {
                'title': row['title'] or f'Día {i}',
                'description': row['description'] or '',
                'activities': json.loads(row['activities']) if row['activities'] else [],
                'links': json.loads(row['links']) if row['links'] else [],
                'files': json.loads(row['files']) if row['files'] else [],
                'evidence': json.loads(row['evidence']) if row['evidence'] else []
            }
        else:
            days_data[i] = {'title': f'Día {i}', 'description': '', 'activities': [], 'links': [], 'files': [], 'evidence': []}
            
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
        title = request.form.get('title', f'Día {day_num}')
        description = request.form.get('description', '')
        activities_text = request.form.get('activities', '')
        links_text = request.form.get('links', '')
        
        activities_list = [a.strip() for a in activities_text.splitlines() if a.strip()]
        links_list = [l.strip() for l in links_text.splitlines() if l.strip()]
        
        row = query_db('SELECT files, evidence FROM daily_content WHERE week = ? AND day = ?', (week_num, day_num), one=True)
        existing_files = json.loads(row['files']) if row and row['files'] else []
        existing_evidence = json.loads(row['evidence']) if row and row['evidence'] else []
        
        files_to_remove = request.form.getlist('remove_files')
        existing_files = [f for f in existing_files if f['saved'] not in files_to_remove]
        
        evidence_to_remove = request.form.getlist('remove_evidence')
        existing_evidence = [e for e in existing_evidence if e['saved'] not in evidence_to_remove]

        uploaded_files = request.files.getlist('new_files')
        for file in uploaded_files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4()}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                existing_files.append({'original': filename, 'saved': unique_filename})
        
        uploaded_evidence = request.files.getlist('new_evidence')
        for file in uploaded_evidence:
            if file and file.filename:
                filename = secure_filename(file.filename)
                unique_filename = f"evidence_{uuid.uuid4()}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                existing_evidence.append({'original': filename, 'saved': unique_filename})
        
        db.execute('''
            INSERT OR REPLACE INTO daily_content (week, day, title, description, activities, links, files, evidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (week_num, day_num, title, description, json.dumps(activities_list), json.dumps(links_list), json.dumps(existing_files), json.dumps(existing_evidence)))
        db.commit()
        
        flash('¡Contenido actualizado!')
        return redirect(url_for('admin_dashboard'))
    
    row = query_db('SELECT * FROM daily_content WHERE week = ? AND day = ?', (week_num, day_num), one=True)
    content = {
        'title': row['title'] if row and row['title'] else f'Día {day_num}',
        'description': row['description'] if row and row['description'] else '',
        'activities': '\n'.join(json.loads(row['activities'])) if row and row['activities'] else '',
        'links': '\n'.join(json.loads(row['links'])) if row and row['links'] else '',
        'files': json.loads(row['files']) if row and row['files'] else [],
        'evidence': json.loads(row['evidence']) if row and row['evidence'] else []
    }
    
    return render_template('edit_day.html', week_num=week_num, day_num=day_num, content=content)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('index.html'), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template('index.html'), 500

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
