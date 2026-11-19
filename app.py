# app.py
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from flask_cors import CORS
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from posture import analyze_posture
from database import get_db_connection

app = Flask(__name__)
app.secret_key = 'super_secret_key_123' 
CORS(app)

UPLOAD_FOLDER = 'uploads'
PROFILE_FOLDER = 'static/images/profiles'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROFILE_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROFILE_FOLDER'] = PROFILE_FOLDER

# ==========================================
# 1. Routes (Views)
# ==========================================

@app.route('/')
def welcome():
    return render_template('welcome.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/register')
def register_page():
    return render_template('register.html')

@app.route('/scan')
def scan():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('scan.html')

# === Dashboard එක (අලුත් ලොජික් එක) ===
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
        
    user_id = session['user_id']
    
    # මුලින්ම Default අගයන් 0 කරමු
    latest_score = 0
    latest_status = "No scans yet"
    avg_score = 0
    compliance_status = "N/A"
    
    # යූසර් මේ ලොගින් එකේදී ස්කෑන් එකක් කරලා තියෙනවා නම් විතරක් Database එකෙන් දත්ත ගන්නවා
    if session.get('has_scanned', False):
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT TOP 1 PostureScore, PostureStatus FROM PostureSessions WHERE UserID = ? ORDER BY SessionID DESC", (user_id,))
            latest = cursor.fetchone()
            if latest:
                latest_score = latest[0]
                latest_status = latest[1]
                
            cursor.execute("SELECT AVG(PostureScore) FROM PostureSessions WHERE UserID = ?", (user_id,))
            avg = cursor.fetchone()
            if avg and avg[0] is not None:
                avg_score = int(avg[0])
                
            conn.close()
            
        if avg_score >= 80: compliance_status = "Good"
        elif avg_score >= 50: compliance_status = "Needs Attention"
        elif avg_score > 0: compliance_status = "Poor"

    return render_template('dashboard.html', 
                           latest_score=latest_score, 
                           latest_status=latest_status, 
                           avg_score=avg_score,
                           compliance_status=compliance_status)

# === History එක (මේක හැමවෙලේම ඔක්කොම දත්ත පෙන්නනවා) ===
@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
        
    user_id = session['user_id']
    conn = get_db_connection()
    sessions = []
    
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT SessionID, CreatedAt, PostureScore, PostureStatus 
            FROM PostureSessions 
            WHERE UserID = ? 
            ORDER BY SessionID DESC
        """, (user_id,))
        
        rows = cursor.fetchall()
        for row in rows:
            date_str = row[1].strftime('%b %d, %Y - %I:%M %p') if row[1] else 'N/A'
            sessions.append({
                'id': row[0],
                'date': date_str,
                'score': row[2],
                'status': row[3]
            })
        conn.close()
        
    return render_template('history.html', sessions=sessions)

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
        
    user_id = session['user_id']
    conn = get_db_connection()
    user_data = None
    
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT UserID, FullName, Email, CreatedAt, ProfileImage FROM Users WHERE UserID = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            date_str = row[3].strftime('%m/%d/%Y') if row[3] else 'N/A'
            user_data = {
                'id': row[0],
                'name': row[1],
                'email': row[2],
                'joined': date_str,
                'image': row[4] if row[4] else None 
            }
        conn.close()
        
    return render_template('profile.html', user=user_data)

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
        
    user_id = session['user_id']
    conn = get_db_connection()
    
    if request.method == 'POST':
        fullname = request.form.get('fullname')
        email = request.form.get('email')
        file = request.files.get('profile_image')
        
        new_image_path = None
        
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['PROFILE_FOLDER'], filename)
            file.save(filepath)
            new_image_path = f"/{PROFILE_FOLDER}/{filename}"
            
        if conn:
            cursor = conn.cursor()
            try:
                if new_image_path:
                    cursor.execute("UPDATE Users SET FullName = ?, Email = ?, ProfileImage = ? WHERE UserID = ?", (fullname, email, new_image_path, user_id))
                else:
                    cursor.execute("UPDATE Users SET FullName = ?, Email = ? WHERE UserID = ?", (fullname, email, user_id))
                
                conn.commit()
                flash('Profile updated successfully!', 'success')
                return redirect(url_for('profile'))
            except Exception as e:
                conn.rollback()
                flash('Error updating profile. Email might be taken.', 'error')
            finally:
                conn.close()
                
    user_data = None
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT FullName, Email, ProfileImage FROM Users WHERE UserID = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            user_data = {'name': row[0], 'email': row[1], 'image': row[2]}
        conn.close()
        
    return render_template('edit_profile.html', user=user_data)

# === Recommendations (ලොගින් වුණාට පස්සේ ස්කෑන් කරලා නැත්නම් No Scans Yet පෙන්නනවා) ===
@app.route('/recommendations')
def recommendations():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
        
    user_id = session['user_id']
    req_session_id = request.args.get('session_id')
    
    
    if not session.get('has_scanned', False) and not req_session_id:
        empty_recs = [{"title": "No Scans Yet", "desc": "Please go to the Posture Scan page and complete a scan to get personalized recommendations.", "type": "Notice", "image_url": None, "video_url": None}]
        return render_template('recommendations.html', score=0, status="No scans yet", issues=[], recs=empty_recs)

    conn = get_db_connection()
    latest_issues = []
    latest_score = 0
    latest_status = "No scans yet"
    
    if conn:
        cursor = conn.cursor()
        
        if req_session_id:
            cursor.execute("SELECT PostureScore, PostureStatus FROM PostureSessions WHERE SessionID = ? AND UserID = ?", (req_session_id, user_id))
            session_data = cursor.fetchone()
            if session_data:
                latest_score = session_data[0]
                latest_status = session_data[1]
                cursor.execute("SELECT IssueName FROM PostureIssues WHERE SessionID = ?", (req_session_id,))
                for row in cursor.fetchall():
                    latest_issues.append(row[0])
        else:
            cursor.execute("SELECT TOP 1 SessionID, PostureScore, PostureStatus FROM PostureSessions WHERE UserID = ? ORDER BY SessionID DESC", (user_id,))
            session_data = cursor.fetchone()
            if session_data:
                session_id = session_data[0]
                latest_score = session_data[1]
                latest_status = session_data[2]
                cursor.execute("SELECT IssueName FROM PostureIssues WHERE SessionID = ?", (session_id,))
                for row in cursor.fetchall():
                    latest_issues.append(row[0])
                    
        conn.close()
        
    recommendations_data = []
    
    if "Forward Head Position" in latest_issues:
        recommendations_data.append({"title": "Correct Position: Forward Head", "desc": "Your head is leaning too far forward. The correct position is keeping your ears aligned directly over your shoulders. Tuck your chin slightly.", "type": "Correction", "image_url": "https://images.unsplash.com/photo-1599819811279-d5ad9cccf838?auto=format&fit=crop&w=400&q=80", "video_url": "https://www.youtube.com/results?search_query=chin+tuck+exercise"})
        recommendations_data.append({"title": "Chin Tucks Exercise", "desc": "Strengthen your neck muscles to maintain the correct head position and relieve tension.", "type": "Exercise", "image_url": "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?auto=format&fit=crop&w=400&q=80", "video_url": "https://www.youtube.com/results?search_query=how+to+do+chin+tucks"})
        
    if "Uneven Shoulders" in latest_issues:
        recommendations_data.append({"title": "Correct Position: Uneven Shoulders", "desc": "Your shoulders are not level. Ensure your armrests are adjusted so both shoulders can relax and drop down equally.", "type": "Correction", "image_url": "https://images.unsplash.com/photo-1505751172876-fa1923c5c528?auto=format&fit=crop&w=400&q=80", "video_url": "https://www.youtube.com/results?search_query=how+to+fix+uneven+shoulders"})
        recommendations_data.append({"title": "Shoulder Blade Squeezes", "desc": "Squeeze your shoulder blades together as if holding a pencil between them. Hold for 5 seconds.", "type": "Exercise", "image_url": "https://images.unsplash.com/photo-1571019614242-c5c5dee9f50b?auto=format&fit=crop&w=400&q=80", "video_url": "https://www.youtube.com/results?search_query=shoulder+blade+squeeze+exercise"})
        
    if not latest_issues and latest_score > 0:
        recommendations_data.append({"title": "Maintain Your Good Posture", "desc": "Your posture is excellent! Keep your monitor at eye level and your feet flat on the floor.", "type": "Maintenance", "image_url": "https://images.unsplash.com/photo-1587560699334-cc4ff634909a?auto=format&fit=crop&w=400&q=80", "video_url": "https://www.youtube.com/results?search_query=proper+sitting+posture+at+desk"})
        recommendations_data.append({"title": "Daily Stretching Routine", "desc": "Even with good posture, taking short breaks to stretch prevents stiffness.", "type": "Exercise", "image_url": "https://images.unsplash.com/photo-1518611012118-696072aa579a?auto=format&fit=crop&w=400&q=80", "video_url": "https://www.youtube.com/results?search_query=desk+stretching+routine"})

    return render_template('recommendations.html', score=latest_score, status=latest_status, issues=latest_issues, recs=recommendations_data)

@app.route('/logout')
def logout():
    session.clear() # මේකෙන් ලොගින් වෙච්ච විස්තර ඔක්කොම ඩිලීට් වෙනවා
    return redirect(url_for('welcome'))

# ==========================================
# 2. API Routes (Backend Logic)
# ==========================================

@app.route('/api/register', methods=['POST'])
def register():
    fullname = request.form.get('fullname')
    email = request.form.get('email')
    password = request.form.get('password')

    if not fullname or not email or not password:
        flash('Please fill all fields', 'error')
        return redirect(url_for('register_page'))

    hashed_password = generate_password_hash(password)
    conn = get_db_connection()
    
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO Users (FullName, Email, PasswordHash) VALUES (?, ?, ?)", (fullname, email, hashed_password))
            conn.commit()
            conn.close()
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login_page'))
        except Exception as e:
            conn.close()
            flash('Email already exists or database error.', 'error')
            return redirect(url_for('register_page'))
            
    flash('Database connection failed', 'error')
    return redirect(url_for('register_page'))

@app.route('/api/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')

    conn = get_db_connection()
    
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT UserID, FullName, PasswordHash FROM Users WHERE Email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session.clear() # පරණ සෙෂන් එක අයින් කරනවා
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['has_scanned'] = False # මේ ලොගින් එකේදී තාම ස්කෑන් කරලා නැහැ කියලා මාක් කරනවා
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'error')
            return redirect(url_for('login_page'))

    flash('Database connection failed', 'error')
    return redirect(url_for('login_page'))

@app.route('/api/analyze', methods=['POST'])
def analyze():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized. Please log in."}), 401

    if 'image' not in request.files:
        return jsonify({"error": "No image part in the request"}), 400
        
    file = request.files['image']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    if file:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        
        result = analyze_posture(filepath)
        os.remove(filepath)
        
        if "error" in result:
            return jsonify(result), 400
            
        user_id = session['user_id']
        score = result['score']
        status = result['status']
        issues = result['issues']
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO PostureSessions (UserID, PostureScore, PostureStatus) OUTPUT INSERTED.SessionID VALUES (?, ?, ?)", 
                    (user_id, score, status)
                )
                row = cursor.fetchone()
                session_id = int(row[0])
                
                for issue in issues:
                    cursor.execute("INSERT INTO PostureIssues (SessionID, IssueName, Severity) VALUES (?, ?, ?)", (session_id, issue, "Moderate"))
                
                conn.commit()
                result['session_id'] = session_id
                
                # === මේක තමයි වැදගත්ම කොටස: ස්කෑන් කළාම True කරනවා ===
                session['has_scanned'] = True 
                
            except Exception as e:
                print(f"DB Error: {e}")
                conn.rollback()
                return jsonify({"error": f"Database Error: {str(e)}"}), 500
            finally:
                conn.close()

        return jsonify(result), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)