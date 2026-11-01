"""
GradSphere website - Flask application.
Run with:  python app.py    then open http://127.0.0.1:5000
"""
import os
import sqlite3
from datetime import datetime
from functools import wraps
import requests
import smtplib
from email.message import EmailMessage

from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, g)
from werkzeug.security import generate_password_hash, check_password_hash

import content as c

# ------------------------- APP INITIALIZATION -------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

# Vercel serverless requires using /tmp for SQLite databases since the root is read-only
if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    DB_PATH = "/tmp/gradsphere.db"
else:
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gradsphere.db")


# ------------------------- DATABASE -------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, email TEXT, phone TEXT,
                service TEXT, message TEXT, created TEXT);
        """)


# ------------------------- HELPERS -------------------------
@app.context_processor
def inject_globals():
    """Variables available in every template."""
    return dict(site=c.SITE, services=c.SERVICES, year=datetime.now().year)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def send_sms(message_text):
    """Helper function to send SMS via Fast2SMS"""
    try:
        url = "https://www.fast2sms.com/dev/bulkV2"
        querystring = {
            "authorization": "YOUR_FAST2SMS_API_KEY",  # <--- Put your Fast2SMS API key here
            "route": "q",
            "message": message_text,
            "language": "english",
            "flash": "0",
            "numbers": "918072806231"  # Your phone number
        }
        headers = {'cache-control': "no-cache"}
        requests.request("GET", url, headers=headers, params=querystring, timeout=3)
    except Exception as e:
        print(f"SMS error: {e}")


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

            # 1. Save to Database
            try:
                db = get_db()
                db.execute(
                    "INSERT INTO messages(name,email,phone,service,message,created) VALUES(?,?,?,?,?,?)",
                    (name, email, phone, service, message_body, datetime.now().isoformat(timespec="seconds"))
                )
                db.commit()
            except Exception as db_err:
                print(f"Database error: {db_err}")

            # 2. Send Email Notification to Inbox (with timeout & exception handling for serverless)
            try:
                msg = EmailMessage()
                msg.set_content(
                    f"New Client Inquiry on GradSphere Website:\n\n"
                    f"Name: {name}\n"
                    f"Email: {email}\n"
                    f"Phone: {phone}\n"
                    f"Service: {service}\n\n"
                    f"Message:\n{message_body}"
                )
                msg["Subject"] = f"New Inquiry: {name} ({email})"
                msg["From"] = "gradspherecareers@gmail.com"
                msg["Reply-To"] = email
                msg["To"] = "gradspherecareers@gmail.com"

                # 5-second timeout prevents Vercel serverless from hanging indefinitely
                with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=5) as server:
                    server.login("gradspherecareers@gmail.com", "ugwpiwtixxrywcgq")
                    server.send_message(msg)
            except Exception as e:
                print(f"Email error (SMTP blocked on serverless): {e}")

            # 3. Send SMS Alert to Phone
            send_sms(f"New Inquiry! Name: {name}, Service: {service}")

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
        if not name or not email or len(password) < 6:
            flash("Enter name, email and a password of at least 6 characters.", "error")
        elif get_db().execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            flash("This email is already registered. Please log in.", "error")
        else:
            get_db().execute(
                "INSERT INTO users(name,email,password,created) VALUES(?,?,?,?)",
                (name, email, generate_password_hash(password),
                 datetime.now().isoformat(timespec="seconds")))
            get_db().commit()
            flash("Account created! You can log in now.", "success")
            return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password"], request.form.get("password", "")):
            session["user_id"], session["user_name"] = user["id"], user["name"]
            
            # 1. Send Email Notification for Login
            try:
                msg = EmailMessage()
                msg.set_content(
                    f"User Login Alert on GradSphere:\n\n"
                    f"Name: {user['name']}\n"
                    f"Email: {user['email']}\n"
                    f"Login Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                msg["Subject"] = f"Login Alert: {user['name']} ({user['email']})"
                msg["From"] = "gradspherecareers@gmail.com"
                msg["To"] = "gradspherecareers@gmail.com"

                with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=5) as server:
                    server.login("gradspherecareers@gmail.com", "ugwpiwtixxrywcgq")
                    server.send_message(msg)
            except Exception as e:
                print(f"Login Email error: {e}")

            # 2. Send SMS Alert for Login
            send_sms(f"Login Alert: {user['name']} ({user['email']}) logged in.")

            return redirect(url_for("dashboard"))
            
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


# Initialize DB on start (handles /tmp creation on Vercel cold starts)
try:
    init_db()
except Exception as e:
    print(f"DB Init error: {e}")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
