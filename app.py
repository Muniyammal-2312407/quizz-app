from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash
import json, os, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from datetime import datetime

app = Flask(__name__)
app.secret_key = "supersecretkey"

def load_quizzes():
    if os.path.exists("quizzes.json"):
        with open("quizzes.json") as f:
            return json.load(f)
    return {}

quizzes = load_quizzes()

def update_leaderboard(name, topic, score, total):
    data = []
    if os.path.exists("leaderboard.json"):
        with open("leaderboard.json", "r") as f:
            data = json.load(f)

    data.append({
        "name": name,
        "topic": topic,
        "score": score,
        "total": total,
        "date": datetime.now().strftime("%d-%m-%Y %H:%M")
    })

    data = sorted(data, key=lambda x: x["score"], reverse=True)
    with open("leaderboard.json", "w") as f:
        json.dump(data[:50], f, indent=4)

def send_email_certificate(to_email, name, topic, file_path, score, total):
    from_email = "youremail@gmail.com"        
    app_password = "your-app-password-here"   

    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = f"🎓 {topic.title()} Quiz Certificate - EduQuiz"

    body = f"""
Hi {name},

🎉 Congratulations on completing your {topic.title()} Quiz!

✅ Score: {score}/{total}
📜 Your Certificate is attached below.

Best wishes,
EduQuiz Team
"""
    msg.attach(MIMEText(body, "plain"))

    with open(file_path, "rb") as f:
        pdf = MIMEApplication(f.read(), _subtype="pdf")
        pdf.add_header("Content-Disposition", "attachment", filename=os.path.basename(file_path))
        msg.attach(pdf)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(from_email, app_password)
        server.send_message(msg)

def generate_certificate(name, topic, score, total):
    folder = "certificates"
    os.makedirs(folder, exist_ok=True)
    file_path = os.path.join(folder, f"certificate_{name}_{topic}.pdf")

    c = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4

    c.setFillColorRGB(0.9, 0.95, 1)
    c.rect(0, 0, width, height, fill=True, stroke=False)
    c.setStrokeColorRGB(0.2, 0.3, 0.7)
    c.setLineWidth(5)
    c.rect(30, 30, width - 60, height - 60)

    c.setFont("Helvetica-Bold", 28)
    c.setFillColorRGB(0.1, 0.1, 0.4)
    c.drawCentredString(width / 2, height - 120, "Certificate of Achievement")

    c.setFont("Helvetica", 18)
    c.drawCentredString(width / 2, height - 180, "This certifies that")

    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(width / 2, height - 210, name)

    c.setFont("Helvetica", 16)
    c.drawCentredString(width / 2, height - 250, f"has successfully completed the {topic.title()} Quiz")
    c.drawCentredString(width / 2, height - 270, f"with a score of {score}/{total}")

    c.setFont("Helvetica-Oblique", 14)
    c.drawCentredString(width / 2, height - 310, f"Date: {datetime.now().strftime('%d-%m-%Y')}")
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, height - 340, "Authorized by EduQuiz Portal")

    c.save()
    return file_path

@app.route("/")
def index():
    user = session.get("user")
    return render_template("index.html", topics=list(quizzes.keys()), user=user)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        users = {}
        if os.path.exists("users.json"):
            with open("users.json", "r") as f:
                users = json.load(f)

        if email in users:
            flash("Email already registered!", "danger")
            return redirect(url_for("login"))

        users[email] = {"name": name, "email": email, "password": password, "role": "user"}
        with open("users.json", "w") as f:
            json.dump(users, f, indent=4)

        flash("Registered successfully! Please login.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        users = {}
        if os.path.exists("users.json"):
            with open("users.json", "r") as f:
                users = json.load(f)

        user = users.get(email)
        if user and user["password"] == password:
            session["user"] = user
            flash("Login successful!", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid credentials!", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Logged out successfully.", "info")
    return redirect(url_for("index"))

@app.route("/quiz/<topic>", methods=["GET", "POST"])
def quiz(topic):
    if "user" not in session:
        flash("Please login to take the quiz!", "warning")
        return redirect(url_for("login"))

    questions = quizzes.get(topic, [])
    if request.method == "POST":
        score = 0
        for i, q in enumerate(questions, start=1):
            ans = request.form.get(f"q{i}")
            if ans and ans.strip().lower() == q["answer"].strip().lower():
                score += 1

        total = len(questions)
        name = session["user"]["name"]
        email = session["user"]["email"]

        update_leaderboard(name, topic, score, total)

        if score >= total / 2:
            file_path = generate_certificate(name, topic, score, total)
            try:
                send_email_certificate(email, name, topic, file_path, score, total)
                flash("🎉 Certificate sent to your email!", "success")
            except Exception as e:
                flash(f"⚠️ Certificate email failed: {str(e)}", "warning")

        return render_template("result.html", topic=topic, score=score, total=total)

    return render_template("quiz.html", topic=topic, questions=questions)

@app.route("/download_certificate/<topic>/<int:score>/<int:total>")
def download_certificate(topic, score, total):
    if "user" not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    name = session["user"]["name"]
    file_path = generate_certificate(name, topic, score, total)
    return send_file(file_path, as_attachment=True)

@app.route("/leaderboard")
def leaderboard():
    topic = request.args.get("topic")
    current_user = session.get("user", {}).get("name")

    if os.path.exists("leaderboard.json"):
        with open("leaderboard.json", "r") as f:
            data = json.load(f)
    else:
        data = []

    if topic:
        data = [d for d in data if d["topic"].lower() == topic.lower()]

    return render_template("leaderboard.html",
                           data=data,
                           topics=list(quizzes.keys()),
                           selected_topic=topic,
                           current_user=current_user)

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        if email == "admin@gmail.com" and password == "admin123":
            session["admin"] = True
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid admin credentials!", "danger")

    return render_template("admin_login.html")

@app.route("/dashboard")
def dashboard():
    if not session.get("admin"):
        return redirect(url_for("admin"))
    return render_template("dashboard.html", quizzes=quizzes)

@app.route("/add_question/<topic>", methods=["GET", "POST"])
def add_question(topic):
    if not session.get("admin"):
        return redirect(url_for("admin"))

    if request.method == "POST":
        question = request.form["question"]
        options = [request.form["opt1"], request.form["opt2"], request.form["opt3"], request.form["opt4"]]
        answer = request.form["answer"]

        if topic not in quizzes:
            quizzes[topic] = []

        quizzes[topic].append({"question": question, "options": options, "answer": answer})

        with open("quizzes.json", "w") as f:
            json.dump(quizzes, f, indent=4)

        flash("Question added successfully!", "success")
        return redirect(url_for("dashboard"))

    return render_template("add_question.html", topic=topic)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

