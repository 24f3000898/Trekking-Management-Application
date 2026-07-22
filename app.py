import os
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session

from models import User, db


app = Flask(__name__)
app.secret_key = "super-secret-key"

os.makedirs(app.instance_path, exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///" + os.path.join(app.instance_path, "trekking.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)


def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login to continue.", "warning")
            return redirect("/login")
        return function(*args, **kwargs)

    return wrapper


def role_required(role_name):
    def decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            if session.get("role") != role_name:
                flash("You are not allowed to access this page.", "danger")
                return redirect(get_dashboard_url(session.get("role")))
            return function(*args, **kwargs)

        return wrapper

    return decorator


def get_dashboard_url(role):
    if role == "admin":
        return "/admin/dashboard"
    if role == "staff":
        return "/staff/dashboard"
    if role == "trekker":
        return "/user/dashboard"
    return "/login"


def normalize_role(role):
    role = (role or "").strip().lower()
    if role in ("staff", "trek staff", "trek_staff"):
        return "staff"
    if role == "trekker":
        return "trekker"
    return role


@app.route("/")
def home():
    if "user_id" in session:
        return redirect(get_dashboard_url(session.get("role")))
    return redirect("/login")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        role = normalize_role(request.form.get("role"))

        if role == "admin":
            flash("Admin registration is not allowed.", "danger")
            return redirect("/register")

        if role not in ("trekker", "staff"):
            flash("Please select a valid role.", "danger")
            return redirect("/register")

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email is already registered.", "danger")
            return redirect("/register")

        status = "pending" if role == "staff" else "approved"
        user = User(
            name=name,
            email=email,
            password=password,
            role=role,
            status=status,
        )
        db.session.add(user)
        db.session.commit()

        if role == "staff":
            flash("Registration successful. Please wait for Admin approval.", "info")
        else:
            flash("Registration successful. Please login.", "success")
        return redirect("/login")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email, password=password).first()
        if not user:
            flash("Invalid email or password.", "danger")
            return redirect("/login")

        if user.role == "staff" and user.status == "pending":
            flash("Your account is pending Admin approval.", "warning")
            return redirect("/login")

        if user.status == "blacklisted":
            flash("Your account has been deactivated.", "danger")
            return redirect("/login")

        session["user_id"] = user.id
        session["name"] = user.name
        session["role"] = user.role

        flash("Login successful.", "success")
        return redirect(get_dashboard_url(user.role))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect("/login")


@app.route("/admin/dashboard")
@login_required
@role_required("admin")
def admin_dashboard():
    user = db.session.get(User, session["user_id"])
    return render_template("admin_dashboard.html", user=user)


@app.route("/staff/dashboard")
@login_required
@role_required("staff")
def staff_dashboard():
    user = db.session.get(User, session["user_id"])
    return render_template("staff_dashboard.html", user=user)


@app.route("/user/dashboard")
@login_required
@role_required("trekker")
def user_dashboard():
    user = db.session.get(User, session["user_id"])
    return render_template("user_dashboard.html", user=user)


if __name__ == "__main__":
    app.run(debug=True)
