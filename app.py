import os
import uuid
import bleach
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g
from flask_socketio import SocketIO, join_room, emit
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(32).hex())
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
app.config['ALLOWED_EXTENSIONS'] = {'.png', '.jpg', '.jpeg', '.gif'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
socketio = SocketIO(app, cors_allowed_origins="*")
DB_NAME = 'crew.db'

# === DATABASE ===
def get_db():
    db = getattr(g, '_db', None)
    if db is None:
        db = g._db = sqlite3.connect(DB_NAME)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_db(e=None):
    db = getattr(g, '_db', None)
    if db: db.close()

def init_db():
    with app.app_context():
        with open('schema.sql', 'r') as f:
            get_db().cursor().executescript(f.read())
        get_db().commit()

# === FILE UPLOAD ===
def save_upload(file):
    if not file or not file.filename: return None
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in app.config['ALLOWED_EXTENSIONS']: return None
    filename = f"{uuid.uuid4().hex}{ext}"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return filename

# === ROUTES ===
@app.route('/')
def home():
    return redirect(url_for('login')) if 'user_id' not in session else redirect(url_for('dashboard'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        if get_db().execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
            flash("Email already registered!", "danger")
            return render_template('register.html')
        pic = save_upload(request.files.get('profile_pic'))
        hashed = generate_password_hash(request.form['password'])
        db = get_db()
        db.execute("""
            INSERT INTO users (name,email,password,role,city,experience,projects,contact,profile_pic)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            request.form['name'], email, hashed, request.form['role'], request.form['city'],
            request.form.get('experience'), request.form.get('projects'), request.form.get('contact'), pic
        ))
        db.commit()
        flash("Registered! Login now.", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = get_db().execute("SELECT * FROM users WHERE email=?", (request.form['email'],)).fetchone()
        if user and check_password_hash(user['password'], request.form['password']):
            session['user_id'] = user['id']
            return redirect(url_for('dashboard'))
        flash("Invalid credentials.", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    crew = db.execute("SELECT * FROM users WHERE id != ?", (user_id,)).fetchall()

    # Check team membership
    crew_with_status = []
    for c in crew:
        shared_team = db.execute("""
            SELECT 1 FROM team_members tm1
            JOIN team_members tm2 ON tm1.team_id = tm2.team_id
            WHERE tm1.user_id = ? AND tm2.user_id = ?
        """, (user_id, c['id'])).fetchone()
        crew_with_status.append({**dict(c), 'in_same_team': bool(shared_team)})

    requests = db.execute("""
        SELECT tr.id, u.name FROM team_requests tr
        JOIN users u ON tr.sender_id = u.id
        WHERE tr.receiver_id = ? AND status = 'pending'
    """, (user_id,)).fetchall()

    teams = db.execute("""
        SELECT t.* FROM teams t
        JOIN team_members tm ON t.id = tm.team_id
        WHERE tm.user_id = ?
    """, (user_id,)).fetchall()

    return render_template('dashboard.html', user=user, crew=crew_with_status, requests=requests, teams=teams)

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']
    db = get_db()
    if request.method == 'POST':
        pic = save_upload(request.files.get('profile_pic'))
        fields = ['name', 'role', 'city', 'contact', 'experience', 'projects']
        values = [request.form[f] for f in fields]
        if pic:
            fields.append('profile_pic')
            values.append(pic)
        values.append(user_id)
        db.execute(f"UPDATE users SET {', '.join(f'{f}=?' for f in fields)} WHERE id=?", values)
        db.commit()
        flash("Profile updated!", "success")
        return redirect(url_for('dashboard'))
    user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return render_template('edit_profile.html', user=user)

@app.route('/user/<int:user_id>')
def view_profile(user_id):
    user = get_db().execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return render_template('profile_modal.html', user=user)

# === CREATE TEAM & ADD MEMBER ===
@app.route('/create_team', methods=['POST'])
def create_team():
    if 'user_id' not in session: return jsonify({'success': False}), 403
    data = request.get_json()
    team_name = bleach.clean(data['name'][:50])
    member_id = data['member_id']

    db = get_db()
    cur = db.execute("INSERT INTO teams (name, created_by) VALUES (?,?)", (team_name, session['user_id']))
    team_id = cur.lastrowid
    db.execute("INSERT INTO team_members (team_id, user_id) VALUES (?,?)", (team_id, session['user_id']))
    db.execute("INSERT INTO team_members (team_id, user_id) VALUES (?,?)", (team_id, member_id))
    db.commit()

    socketio.emit('team_joined', {'team_id': team_id}, room=f"team_{team_id}")
    return jsonify({'success': True, 'team_id': team_id})

# === EDIT TEAM NAME ===
@app.route('/edit_team_name', methods=['POST'])
def edit_team_name():
    if 'user_id' not in session: return jsonify({'success': False}), 403
    data = request.get_json()
    team_id = data['team_id']
    new_name = bleach.clean(data['name'][:50])

    db = get_db()
    member = db.execute("SELECT 1 FROM team_members WHERE team_id=? AND user_id=?", (team_id, session['user_id'])).fetchone()
    if not member: return jsonify({'success': False}), 403

    db.execute("UPDATE teams SET name=? WHERE id=?", (new_name, team_id))
    db.commit()
    socketio.emit('team_name_updated', {'team_id': team_id, 'name': new_name}, room=f"team_{team_id}")
    return jsonify({'success': True})

# === CHAT ROUTES ===
@app.route('/get_dm/<int:other_id>')
def get_dm(other_id):
    if 'user_id' not in session: return ""
    db = get_db()
    msgs = db.execute("""
        SELECT m.*, u.name, u.id as sender_id
        FROM messages m JOIN users u ON m.sender_id = u.id
        WHERE (m.sender_id = ? AND m.receiver_id = ?) OR (m.sender_id = ? AND m.receiver_id = ?)
        ORDER BY m.id
    """, (session['user_id'], other_id, other_id, session['user_id'])).fetchall()
    html = ""
    for m in msgs:
        is_sent = m['sender_id'] == session['user_id']
        html += f'<div class="msg {"sent" if is_sent else "received"}"><strong>{m["name"]}:</strong> {m["message"]}</div>'
    return html

@app.route('/get_team_messages/<int:team_id>')
def get_team_messages(team_id):
    if 'user_id' not in session: return ""
    db = get_db()
    msgs = db.execute("""
        SELECT m.*, u.name, u.id as sender_id
        FROM messages m JOIN users u ON m.sender_id = u.id
        WHERE m.team_id = ? ORDER BY m.id
    """, (team_id,)).fetchall()
    html = ""
    for m in msgs:
        is_sent = m['sender_id'] == session['user_id']
        html += f'<div class="msg {"sent" if is_sent else "received"}"><strong>{m["name"]}:</strong> {m["message"]}</div>'
    return html

@app.route('/get_dm_users')
def get_dm_users():
    if 'user_id' not in session: return jsonify([])
    db = get_db()
    user_id = session['user_id']
    users = db.execute("""
        SELECT DISTINCT u.id, u.name
        FROM users u
        JOIN messages m ON (u.id = m.sender_id AND m.receiver_id = ?) OR (u.id = m.receiver_id AND m.sender_id = ?)
        WHERE u.id != ?
        GROUP BY u.id
    """, (user_id, user_id, user_id)).fetchall()
    return jsonify([{'id': u['id'], 'name': u['name']} for u in users])

@app.route('/get_inbox')
def get_inbox():
    if 'user_id' not in session: return jsonify([])
    db = get_db()
    user_id = session['user_id']
    dm_chats = db.execute("""
        SELECT u.id, u.name, 'dm' as type
        FROM users u
        JOIN messages m ON (u.id = m.sender_id AND m.receiver_id = ?) OR (u.id = m.receiver_id AND m.sender_id = ?)
        WHERE u.id != ?
        GROUP BY u.id
    """, (user_id, user_id, user_id)).fetchall()
    team_chats = db.execute("""
        SELECT t.id, t.name as team_name, 'team' as type
        FROM teams t
        JOIN team_members tm ON t.id = tm.team_id
        WHERE tm.user_id = ?
    """, (user_id,)).fetchall()
    chats = []
    for row in dm_chats:
        chats.append({'id': row['id'], 'name': row['name'], 'type': 'dm'})
    for row in team_chats:
        chats.append({'id': row['id'], 'name': row['team_name'], 'type': 'team'})
    return jsonify(chats)

# === SOCKETIO ===
@socketio.on('join_team')
def on_join(data):
    join_room(f"team_{data['team_id']}")

@socketio.on('send_message')
def handle_message(data):
    msg = bleach.clean(data['message'][:500])
    db = get_db()
    db.execute("INSERT INTO messages (team_id, sender_id, message) VALUES (?,?,?)",
               (data['team_id'], session['user_id'], msg))
    db.commit()
    sender = db.execute("SELECT name FROM users WHERE id=?", (session['user_id'],)).fetchone()
    emit('new_message', {
        'name': sender['name'], 'message': msg, 'sender_id': session['user_id']
    }, room=f"team_{data['team_id']}")

@socketio.on('send_dm')
def handle_dm(data):
    msg = bleach.clean(data['message'][:500])
    db = get_db()
    db.execute("INSERT INTO messages (sender_id, receiver_id, message) VALUES (?,?,?)",
               (session['user_id'], data['receiver_id'], msg))
    db.commit()
    sender = db.execute("SELECT name FROM users WHERE id=?", (session['user_id'],)).fetchone()
    room = f"dm_{min(session['user_id'], data['receiver_id'])}_{max(session['user_id'], data['receiver_id'])}"
    emit('new_dm', {
        'name': sender['name'], 'message': msg, 'sender_id': session['user_id']
    }, room=room)

if __name__ == '__main__':
    with app.app_context():
        init_db()
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)