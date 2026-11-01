"""
GradSphere website - Clean Pure SQLite Version (No Supabase needed)
"""
import os
import random
from datetime import datetime
from functools import wraps
import sqlite3
import resend

from flask import (Flask, render_template, request, redirect,
                    url_for, session, flash, g)
from werkzeug.security import generate_password_hash, check_password_hash

import content as c

# ------------------------- APP INITIALIZATION -------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "GradSphereSecretKey2026#")

# Configure Resend API Key from Environment
resend.api_key = os.environ.get("RESEND_API_KEY") 
SENDER_EMAIL = "onboarding@resend.dev"

# Admin Contact Details
ADMIN_EMAIL = "gradspherecareers@gmail.com"
ADMIN_PHONE = "+91 7708944301"


# ------------------------- DATABASE HELPER (Pure SQLite) -------------------------
def get_db():
    if "db" not in g:
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gradsphere.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False):
    """SQLite helper function"""
    db = get_db()
    cur = db.cursor()
    cur.execute(query, args)
    
    if query.strip().upper().startswith("SELECT"):
        rv = cur.fetchall()
        cur.close()
        return (rv[0] if rv else None) if one else rv
    else:
        db.commit()
        cur.close()
        return None


def init_db():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gradsphere.db")
    with sqlite3.connect(db_path) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                reset_code TEXT,
                created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, email TEXT, phone TEXT,
                service TEXT, message TEXT, created TEXT);
        """)
        try:
            db.execute("ALTER TABLE users ADD COLUMN reset_code TEXT")
            db.commit()
        except sqlite3.OperationalError:
            pass


# ------------------------- HELPERS -------------------------
@app.context_processor
def inject_globals():
    return dict(site=c.SITE, services=c.SERVICES, year=datetime.now().year)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


# ------------------------- PUBLIC PAGES -------------------------
@app.route("/")
def home():
    return render_template("home.html", hero=c.HERO, stats=c.STATS, why=c.WHY_US,
                           process=c.PROCESS, testimonials=c.TESTIMONIALS, faqs=c.FAQS)


@app.route("/about")
def about():
    return render_template("about.html", about=c.ABOUT, values=c.VALUES,
                           milestones=c.MILESTONES, stats=c.STATS)


@app.route("/services")
def services_page():
    return render_template("services.html", why=c.WHY_US, process=c.PROCESS)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        f = request.form
        if not f.get("name") or not f.get("email") or not f.get("message"):
            flash("Please fill in name, email and message.", "error")
        else:
            name = f["name"]
            email = f["email"]
            phone = f.get("phone", "Not provided")
            service = f.get("service", "General")
            message_body = f["message"]

            # 1. Save to Local SQLite Database
            try:
                query_db(
                    "INSERT INTO messages(name,email,phone,service,message,created) VALUES(?,?,?,?,?,?)",
                    (name, email, phone, service, message_body, datetime.now().isoformat(timespec="seconds"))
                )
            except Exception as db_err:
                print(f"Database error: {db_err}")

            # 2. Send Email Notification via Resend API to Admin
            try:
                resend.Emails.send({
                    "from": SENDER_EMAIL,
                    "to": ADMIN_EMAIL,
                    "subject": f"New Inquiry: {name} ({email})",
                    "html": f"""
                        <h3>New Client Inquiry on GradSphere Website</h3>
                        <p><strong>Name:</strong> {name}</p>
                        <p><strong>Email:</strong> {email}</p>
                        <p><strong>Phone:</strong> {phone}</p>
                        <p><strong>Service:</strong> {service}</p>
                        <p><strong>Message:</strong><br>{message_body}</p>
                    """
                })
            except Exception as e:
                print(f"Resend Email error: {e}")

            flash("Thank you! We have received your message and will reply soon.", "success")
            return redirect(url_for("contact"))
            
    return render_template("contact.html", faqs=c.FAQS)


# ------------------------- USER ACCOUNTS -------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        
        existing_user = query_db("SELECT 1 FROM users WHERE email=?", (email,), one=True)
        
        if not name or not email or len(password) < 6:
            flash("Enter name, email and a password of at least 6 characters.", "error")
        elif existing_user:
            flash("This email is already registered. Please log in.", "error")
        else:
            query_db(
                "INSERT INTO users(name,email,password,created) VALUES(?,?,?,?)",
                (name, email, generate_password_hash(password),
                 datetime.now().isoformat(timespec="seconds")))
            flash("Account created! You can log in now.", "success")
            return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = query_db("SELECT * FROM users WHERE email=?", (email,), one=True)
        
        if user and check_password_hash(user["password"], request.form.get("password", "")):
            session["user_id"], session["user_name"] = user["id"], user["name"]
            
            # Send Login Notification via Resend API to Admin
            try:
                resend.Emails.send({
                    "from": SENDER_EMAIL,
                    "to": ADMIN_EMAIL,
                    "subject": f"Login Alert: {user['name']} ({user['email']})",
                    "html": f"""
                        <h3>User Login Alert on GradSphere</h3>
                        <p><strong>Name:</strong> {user['name']}</p>
                        <p><strong>Email:</strong> {user['email']}</p>
                        <p><strong>Login Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    """
                })
            except Exception as e:
                print(f"Resend Login Email error: {e}")

            return redirect(url_for("dashboard"))
            
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = query_db("SELECT * FROM users WHERE email=?", (email,), one=True)
        
        if not user:
            flash("This email is not registered with us.", "error")
            return redirect(url_for("forgot_password"))
        
        # Generate 6-digit random code
        code = str(random.randint(100000, 999999))
        
        # Save code in DB
        query_db("UPDATE users SET reset_code=? WHERE email=?", (code, email))
        
        # Send OTP code via Resend to Admin
        try:
            resend.Emails.send({
                "from": SENDER_EMAIL,
                "to": ADMIN_EMAIL,
                "subject": f"GradSphere Password Reset OTP for {email}",
                "html": f"""
                    <div style="font-family: Arial, sans-serif; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
                        <h2 style="color: #4f46e5;">GradSphere Security</h2>
                        <p>Hello,</p>
                        <p>Reset request for account: <strong>{email}</strong></p>
                        <p>Verification Code:</p>
                        <div style="background: #f3f4f6; padding: 12px 20px; font-size: 24px; font-weight: bold; letter-spacing: 4px; display: inline-block; border-radius: 6px; color: #111;">
                            {code}
                        </div>
                    </div>
                """
            })
            session["reset_email"] = email
            flash("OTP code has been sent to support email!", "success")
            return redirect(url_for("verify_code"))
        except Exception as e:
            print(f"Resend Error: {e}")
            flash(f"Email delivery error. Contact Admin at {ADMIN_EMAIL}.", "error")
            
    return render_template("forgot_password.html")


@app.route("/verify-code", methods=["GET", "POST"])
def verify_code():
    if "reset_email" not in session:
        return redirect(url_for("forgot_password"))
        
    if request.method == "POST":
        entered_code = request.form.get("code", "").strip()
        new_password = request.form.get("new_password", "").strip()
        
        if len(new_password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("verify_code.html")
            
        email = session["reset_email"]
        user = query_db("SELECT * FROM users WHERE email=?", (email,), one=True)
        
        if user and user["reset_code"] == entered_code:
            hashed_pw = generate_password_hash(new_password)
            query_db("UPDATE users SET password=?, reset_code=NULL WHERE email=?", (hashed_pw, email))
            
            session.pop("reset_email", None)
            flash("Password successfully updated! You can log in now.", "success")
            return redirect(url_for("login"))
        else:
            flash("Invalid OTP code. Please try again.", "error")
            
    return render_template("verify_code.html")


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


# Initialize DB on start
try:
    init_db()
except Exception as e:
    print(f"DB Init error: {e}")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
