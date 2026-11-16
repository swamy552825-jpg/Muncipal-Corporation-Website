from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import uuid


# =========================================================
# FLASK APPLICATION
# =========================================================

app = Flask(__name__)

app.secret_key = "municipal-development-secret-key"


# =========================================================
# DATABASE CONFIGURATION
# =========================================================

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///municipal.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = os.path.join(app.static_folder, "uploads")
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

db = SQLAlchemy(app)


def save_uploaded_image(file_storage, prefix):
    """Save an allowed image with a non-guessable filename, or return None."""
    if not file_storage or not file_storage.filename:
        return None
    extension = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Upload a JPG, PNG, or WEBP image (maximum 8 MB).")
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    filename = f"{prefix}_{uuid.uuid4().hex}.{extension}"
    file_storage.save(os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(filename)))
    return filename


# =========================================================
# USER MODEL
# =========================================================

class User(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    phone = db.Column(
        db.String(15),
        nullable=False
    )

    password = db.Column(
        db.String(200),
        nullable=False
    )

    role = db.Column(
        db.String(20),
        nullable=False,
        default="citizen"
    )

# =========================================================
# COMPLAINT MODEL
# =========================================================

class Complaint(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    complaint_number = db.Column(
        db.String(30),
        unique=True,
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    assigned_worker_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True
    )

    category = db.Column(
        db.String(100),
        nullable=False
    )

    description = db.Column(
        db.Text,
        nullable=False
    )

    severity = db.Column(
        db.String(20),
        nullable=False
    )

    address = db.Column(
        db.String(300),
        nullable=False
    )

    latitude = db.Column(
        db.Float,
        nullable=True
    )

    longitude = db.Column(
        db.Float,
        nullable=True
    )

    status = db.Column(
        db.String(30),
        nullable=False,
        default="Submitted"
    )

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.now()
    )

    # Worker completion report
    completion_report = db.Column(
        db.Text,
        nullable=True
    )

    # Date and time when worker completed the task
    completed_at = db.Column(
        db.DateTime,
        nullable=True
    )

    issue_photo = db.Column(db.String(255), nullable=True)
    completion_photo = db.Column(db.String(255), nullable=True)

    @property
    def priority_rank(self):
        return {"Emergency": 0, "High": 1, "Medium": 2, "Low": 3}.get(self.severity, 4)
# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# CITIZEN REGISTRATION
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        password = request.form["password"]

        existing_user = User.query.filter_by(
            email=email
        ).first()

        if existing_user:

            return render_template(
                "register.html",
                error="An account with this email already exists."
            )

        hashed_password = generate_password_hash(
            password
        )

        new_user = User(
            name=name,
            email=email,
            phone=phone,
            password=hashed_password,
            role="citizen"
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect(
            url_for("home")
        )

    return render_template(
        "register.html"
    )


# =========================================================
# CITIZEN LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(
            email=email
        ).first()

        if user:

            try:
                password_correct = check_password_hash(
                    user.password,
                    password
                )
            except ValueError:
                password_correct = False

            if password_correct:

                session["user_id"] = user.id
                session["user_name"] = user.name

                return redirect(
                    url_for("dashboard")
                )

        return render_template(
            "login.html",
            error="Invalid email or password."
        )

    return render_template(
        "login.html"
    )


# =========================================================
# CITIZEN DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    complaints = Complaint.query.filter_by(user_id=session["user_id"]).all()
    return render_template("dashboard.html", user_name=session["user_name"],
                           complaint_count=len(complaints),
                           active_count=sum(c.status != "Completed" for c in complaints),
                           completed_count=sum(c.status == "Completed" for c in complaints))


# =========================================================
# REPORT MUNICIPAL ISSUE
# =========================================================

@app.route("/report-issue", methods=["GET", "POST"])
def report_issue():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if request.method == "POST":

        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        severity = request.form.get("severity", "").strip()
        address = request.form.get("address", "").strip()

        if not all([category, description, severity, address]) or severity not in {"Low", "Medium", "High", "Emergency"}:
            return render_template("complaint.html", error="Please complete all required fields and select a valid priority.")

        latitude = request.form.get("latitude")

        longitude = request.form.get("longitude")

        # Convert latitude
        try:
            latitude = float(latitude) if latitude else None
        except ValueError:
            latitude = None

        # Convert longitude
        try:
            longitude = float(longitude) if longitude else None
        except ValueError:
            longitude = None

        # Generate complaint number
        complaint_count = Complaint.query.count() + 1

        complaint_number = (
            f"MC-2026-{complaint_count:06d}"
        )

        try:
            issue_photo = save_uploaded_image(request.files.get("issue_photo"), "issue")
        except ValueError as error:
            return render_template("complaint.html", error=str(error))

        new_complaint = Complaint(

            complaint_number=complaint_number,

            user_id=session["user_id"],

            category=category,

            description=description,

            severity=severity,

            address=address,

            latitude=latitude,

            longitude=longitude,

            status="Submitted",
            assigned_worker_id=None,
            issue_photo=issue_photo
        )

        db.session.add(new_complaint)

        db.session.commit()

        return render_template(
            "complaint_success.html",
            complaint=new_complaint
        )

    return render_template(
        "complaint.html"
    )


# =========================================================
# MY COMPLAINTS
# =========================================================

@app.route("/my-complaints")
def my_complaints():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    complaints = Complaint.query.filter_by(
        user_id=session["user_id"]
    ).order_by(
        Complaint.created_at.desc()
    ).all()

    return render_template(
        "my_complaints.html",
        complaints=complaints
    )


# =========================================================
# CITIZEN LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("home")
    )


# =========================================================
# CREATE ADMIN ACCOUNT
# =========================================================

@app.route("/create-admin")
def create_admin():

    existing_admin = User.query.filter_by(
        email="admin@municipal.gov"
    ).first()

    if existing_admin:

        return "Admin account already exists."

    admin = User(

        name="Municipal Administrator",

        email="admin@municipal.gov",

        phone="9999999999",

        password=generate_password_hash(
            "Admin@12345"
        ),

        role="admin"
    )

    db.session.add(admin)

    db.session.commit()

    return "Admin account created successfully."


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        email = request.form["email"]

        password = request.form["password"]

        admin = User.query.filter_by(
            email=email,
            role="admin"
        ).first()

        if admin:

            try:
                password_correct = check_password_hash(
                    admin.password,
                    password
                )
            except ValueError:
                password_correct = False

            if password_correct:

                session["admin_id"] = admin.id

                session["admin_name"] = admin.name

                return redirect(
                    url_for("admin_dashboard")
                )

        return render_template(
            "admin_login.html",
            error="Invalid administrator credentials."
        )

    return render_template(
        "admin_login.html"
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin-dashboard")
def admin_dashboard():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    complaints = Complaint.query.all()
    return render_template("admin_dashboard.html", admin_name=session["admin_name"],
                           total_count=len(complaints),
                           urgent_count=sum(c.severity in ("Emergency", "High") and c.status != "Completed" for c in complaints),
                           unassigned_count=sum(c.assigned_worker_id is None and c.status != "Completed" for c in complaints),
                           completed_count=sum(c.status == "Completed" for c in complaints),
                           worker_count=User.query.filter_by(role="worker").count())


# =========================================================
# ADMIN - VIEW COMPLAINTS
# =========================================================

@app.route("/admin-complaints")
def admin_complaints():

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
    complaints.sort(key=lambda complaint: (complaint.status == "Completed", complaint.priority_rank, -complaint.id))

    workers = User.query.filter_by(
        role="worker"
    ).all()

    return render_template(
        "admin_complaints.html",
        complaints=complaints,
        workers=workers
    )

# =========================================================
# ADMIN - ASSIGN COMPLAINT TO WORKER
# =========================================================

@app.route("/assign-complaint/<int:complaint_id>", methods=["POST"])
def assign_complaint(complaint_id):

    if "admin_id" not in session:

        return redirect(
            url_for("admin_login")
        )

    complaint = Complaint.query.get_or_404(
        complaint_id
    )

    worker_id = request.form.get(
        "worker_id"
    )

    if not worker_id:

        return redirect(
            url_for("admin_complaints")
        )

    worker = User.query.filter_by(
        id=worker_id,
        role="worker"
    ).first()

    if not worker:

        return redirect(
            url_for("admin_complaints")
        )

    complaint.assigned_worker_id = worker.id

    complaint.status = "Assigned" if complaint.status == "Submitted" else complaint.status

    db.session.commit()

    return redirect(
        url_for("admin_complaints")
    )

# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.route("/admin-logout")
def admin_logout():

    session.pop(
        "admin_id",
        None
    )

    session.pop(
        "admin_name",
        None
    )

    return redirect(
        url_for("admin_login")
    )


# =========================================================
# CREATE WORKER ACCOUNT
# =========================================================

@app.route("/create-worker")
def create_worker():

    existing_worker = User.query.filter_by(
        email="worker@municipal.gov"
    ).first()

    if existing_worker:

        return "Worker account already exists."

    worker = User(

        name="Municipal Worker",

        email="worker@municipal.gov",

        phone="8888888888",

        password=generate_password_hash(
            "Worker@12345"
        ),

        role="worker"
    )

    db.session.add(worker)

    db.session.commit()

    return "Worker account created successfully."


# =========================================================
# WORKER LOGIN
# =========================================================

@app.route("/worker-login", methods=["GET", "POST"])
def worker_login():

    if request.method == "POST":

        email = request.form.get("email")

        password = request.form.get("password")

        worker = User.query.filter_by(
            email=email,
            role="worker"
        ).first()

        if worker:

            try:
                password_correct = check_password_hash(
                    worker.password,
                    password
                )
            except ValueError:
                password_correct = False

            if password_correct:

                session["worker_id"] = worker.id

                session["worker_name"] = worker.name

                return redirect(
                    url_for("worker_dashboard")
                )

        return render_template(
            "worker_login.html",
            error="Invalid worker credentials."
        )

    return render_template(
        "worker_login.html"
    )


# =========================================================
# WORKER DASHBOARD
# =========================================================

@app.route("/worker-dashboard")
def worker_dashboard():

    if "worker_id" not in session:

        return redirect(
            url_for("worker_login")
        )

    worker_id = session["worker_id"]

    complaints = Complaint.query.filter_by(
        assigned_worker_id=worker_id
    ).order_by(
        Complaint.id.desc()
    ).all()

    return render_template(
        "worker_dashboard.html",
        complaints=complaints,
        worker_name=session.get("worker_name")
    )


# =========================================================
# WORKER LOGOUT
# =========================================================

@app.route("/worker-logout")
def worker_logout():

    session.pop(
        "worker_id",
        None
    )

    session.pop(
        "worker_name",
        None
    )

    return redirect(
        url_for("worker_login")
    )
# =========================================================
# WORKER - VIEW AND UPDATE TASK
# =========================================================
@app.route("/worker-task/<int:complaint_id>", methods=["GET", "POST"])
def worker_task(complaint_id):

    if "worker_id" not in session:
        return redirect(url_for("worker_login"))

    complaint = Complaint.query.get_or_404(complaint_id)

    if complaint.assigned_worker_id != session["worker_id"]:
        return "You are not authorized to view this task.", 403

    if request.method == "POST":

        status = request.form.get("status")
        report = request.form.get("completion_report", "").strip()

        if status not in {"Assigned", "In Progress", "Completed"}:
            return render_template("worker_task.html", complaint=complaint, error="Select a valid task status.")
        if status == "Completed" and not report:
            return render_template("worker_task.html", complaint=complaint, error="A completion report is required before closing a task.")
        try:
            completion_photo = save_uploaded_image(request.files.get("completion_photo"), "completion")
        except ValueError as error:
            return render_template("worker_task.html", complaint=complaint, error=str(error))

        complaint.status = status

        if report:
            complaint.completion_report = report
        if completion_photo:
            complaint.completion_photo = completion_photo

        if status == "Completed":
            complaint.completed_at = complaint.completed_at or datetime.now()
        else:
            complaint.completed_at = None

        db.session.commit()

        return redirect(
            url_for(
                "worker_task",
                complaint_id=complaint.id
            )
        )

    return render_template(
        "worker_task.html",
        complaint=complaint
    )
# =========================================================
# CREATE DATABASE AND START SERVER
# =========================================================

if __name__ == "__main__":

    with app.app_context():

        db.create_all()
        # Lightweight migration for installations created before photo support.
        columns = {row[1] for row in db.session.connection().exec_driver_sql("PRAGMA table_info(complaint)")}
        if "issue_photo" not in columns:
            db.session.connection().exec_driver_sql("ALTER TABLE complaint ADD COLUMN issue_photo VARCHAR(255)")
        if "completion_photo" not in columns:
            db.session.connection().exec_driver_sql("ALTER TABLE complaint ADD COLUMN completion_photo VARCHAR(255)")

    app.run(
        debug=True
    )
