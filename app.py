import os
from datetime import date
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session
from sqlalchemy import or_

from models import Booking, Trek, User, db


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


def parse_date(value):
    if not value:
        return None
    return date.fromisoformat(value)


def get_trek_form_data():
    assigned_staff_id = request.form.get("assigned_staff_id") or None
    if assigned_staff_id:
        assigned_staff_id = int(assigned_staff_id)
        staff = db.session.get(User, assigned_staff_id)
        if not staff or staff.role != "staff" or staff.status != "approved":
            raise ValueError

    return {
        "name": request.form.get("name"),
        "location": request.form.get("location"),
        "difficulty": request.form.get("difficulty"),
        "duration_days": int(request.form.get("duration_days") or 0),
        "available_slots": int(request.form.get("available_slots") or 0),
        "start_date": parse_date(request.form.get("start_date")),
        "end_date": parse_date(request.form.get("end_date")),
        "assigned_staff_id": assigned_staff_id,
    }


def apply_search(query, model, name_column):
    if not query:
        return model.query

    search_text = f"%{query}%"
    filters = [name_column.ilike(search_text)]

    if query.isdigit():
        filters.append(model.id == int(query))

    return model.query.filter(or_(*filters))


def get_staff_dashboard_context(selected_participant_trek=None, selected_bookings=None):
    user = db.session.get(User, session["user_id"])
    assigned_treks = (
        Trek.query.filter_by(assigned_staff_id=session["user_id"])
        .order_by(Trek.start_date.asc())
        .all()
    )
    total_registered_trekkers = sum(len(trek.bookings) for trek in assigned_treks)

    return {
        "user": user,
        "assigned_treks": assigned_treks,
        "total_assigned_treks": len(assigned_treks),
        "total_registered_trekkers": total_registered_trekkers,
        "selected_participant_trek": selected_participant_trek,
        "selected_bookings": selected_bookings or [],
    }


def get_staff_assigned_trek(trek_id):
    trek = db.session.get(Trek, trek_id)
    if not trek or trek.assigned_staff_id != session["user_id"]:
        return None
    return trek


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
    search_query = request.args.get("q", "").strip()

    trek_query = apply_search(search_query, Trek, Trek.name)
    staff_query = apply_search(search_query, User, User.name).filter_by(role="staff")
    trekker_query = apply_search(search_query, User, User.name).filter_by(role="trekker")

    total_treks = Trek.query.count()
    total_trekkers = User.query.filter_by(role="trekker").count()
    total_staff = User.query.filter_by(role="staff").count()
    pending_staff_count = User.query.filter_by(role="staff", status="pending").count()

    treks = trek_query.order_by(Trek.id.desc()).all()
    staff_members = staff_query.order_by(User.id.desc()).all()
    trekkers = trekker_query.order_by(User.id.desc()).all()
    approved_staff = User.query.filter_by(role="staff", status="approved").order_by(User.name).all()

    return render_template(
        "admin_dashboard.html",
        user=user,
        search_query=search_query,
        total_treks=total_treks,
        total_trekkers=total_trekkers,
        total_staff=total_staff,
        pending_staff_count=pending_staff_count,
        treks=treks,
        staff_members=staff_members,
        trekkers=trekkers,
        approved_staff=approved_staff,
    )


@app.route("/admin/trek/add", methods=["GET", "POST"])
@login_required
@role_required("admin")
def add_trek():
    if request.method == "GET":
        return redirect("/admin/dashboard")

    try:
        trek = Trek(**get_trek_form_data())
    except ValueError:
        flash("Please enter valid trek details.", "danger")
        return redirect("/admin/dashboard")

    db.session.add(trek)
    db.session.commit()
    flash("Trek added successfully.", "success")
    return redirect("/admin/dashboard")


@app.route("/admin/trek/edit/<int:id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def edit_trek(id):
    if request.method == "GET":
        return redirect("/admin/dashboard")

    trek = db.session.get(Trek, id)
    if not trek:
        flash("Trek not found.", "danger")
        return redirect("/admin/dashboard")

    try:
        trek_data = get_trek_form_data()
    except ValueError:
        flash("Please enter valid trek details.", "danger")
        return redirect("/admin/dashboard")

    for field, value in trek_data.items():
        setattr(trek, field, value)

    db.session.commit()
    flash("Trek updated successfully.", "success")
    return redirect("/admin/dashboard")


@app.route("/admin/trek/delete/<int:id>", methods=["POST"])
@login_required
@role_required("admin")
def delete_trek(id):
    trek = db.session.get(Trek, id)
    if not trek:
        flash("Trek not found.", "danger")
        return redirect("/admin/dashboard")

    db.session.delete(trek)
    db.session.commit()
    flash("Trek deleted successfully.", "success")
    return redirect("/admin/dashboard")


@app.route("/admin/staff/approve/<int:id>", methods=["POST"])
@login_required
@role_required("admin")
def approve_staff(id):
    staff = db.session.get(User, id)
    if not staff or staff.role != "staff":
        flash("Staff member not found.", "danger")
        return redirect("/admin/dashboard")

    staff.status = "approved"
    db.session.commit()
    flash("Staff member approved successfully.", "success")
    return redirect("/admin/dashboard")


@app.route("/admin/staff/blacklist/<int:id>", methods=["POST"])
@login_required
@role_required("admin")
def blacklist_staff(id):
    staff = db.session.get(User, id)
    if not staff or staff.role != "staff":
        flash("Staff member not found.", "danger")
        return redirect("/admin/dashboard")

    staff.status = "blacklisted"
    db.session.commit()
    flash("Staff member blacklisted.", "warning")
    return redirect("/admin/dashboard")


@app.route("/admin/user/blacklist/<int:id>", methods=["POST"])
@login_required
@role_required("admin")
def blacklist_user(id):
    user = db.session.get(User, id)
    if not user or user.role != "trekker":
        flash("Trekker not found.", "danger")
        return redirect("/admin/dashboard")

    user.status = "blacklisted"
    db.session.commit()
    flash("Trekker blacklisted.", "warning")
    return redirect("/admin/dashboard")


@app.route("/admin/user/reactivate/<int:id>", methods=["POST"])
@login_required
@role_required("admin")
def reactivate_user(id):
    user = db.session.get(User, id)
    if not user or user.role != "trekker":
        flash("Trekker not found.", "danger")
        return redirect("/admin/dashboard")

    user.status = "approved"
    db.session.commit()
    flash("Trekker reactivated successfully.", "success")
    return redirect("/admin/dashboard")


@app.route("/staff/dashboard")
@login_required
@role_required("staff")
def staff_dashboard():
    return render_template("staff_dashboard.html", **get_staff_dashboard_context())


@app.route("/staff/trek/update/<int:trek_id>", methods=["POST"])
@login_required
@role_required("staff")
def update_staff_trek(trek_id):
    trek = get_staff_assigned_trek(trek_id)
    if not trek:
        flash("You can update only treks assigned to you.", "danger")
        return redirect("/staff/dashboard")

    status = request.form.get("status")
    if status not in ("Open", "Closed", "Completed"):
        flash("Please select a valid trek status.", "danger")
        return redirect("/staff/dashboard")

    try:
        available_slots = int(request.form.get("available_slots") or 0)
    except ValueError:
        flash("Please enter a valid number of available slots.", "danger")
        return redirect("/staff/dashboard")

    if available_slots < 0:
        flash("Available slots cannot be negative.", "danger")
        return redirect("/staff/dashboard")

    trek.available_slots = available_slots
    trek.status = status
    db.session.commit()
    flash("Trek details updated successfully.", "success")
    return redirect("/staff/dashboard")


@app.route("/staff/trek/participants/<int:trek_id>")
@login_required
@role_required("staff")
def staff_trek_participants(trek_id):
    trek = get_staff_assigned_trek(trek_id)
    if not trek:
        flash("You can view participants only for treks assigned to you.", "danger")
        return redirect("/staff/dashboard")

    selected_bookings = (
        Booking.query.filter_by(trek_id=trek.id).order_by(Booking.booking_date.desc()).all()
    )
    return render_template(
        "staff_dashboard.html",
        **get_staff_dashboard_context(
            selected_participant_trek=trek,
            selected_bookings=selected_bookings,
        ),
    )


@app.route("/user/dashboard")
@login_required
@role_required("trekker")
def user_dashboard():
    user = db.session.get(User, session["user_id"])
    return render_template("user_dashboard.html", user=user)


if __name__ == "__main__":
    app.run(debug=True)
