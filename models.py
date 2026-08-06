from datetime import date, datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False)

    bookings = db.relationship("Booking", back_populates="user")
    assigned_treks = db.relationship(
        "Trek",
        back_populates="assigned_staff",
        foreign_keys="Trek.assigned_staff_id",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.status:
            self.status = "pending" if self.role == "staff" else "approved"

    def __repr__(self):
        return f"<User {self.email}>"


class Trek(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    difficulty = db.Column(db.String(20))
    duration_days = db.Column(db.Integer)
    total_slots = db.Column(db.Integer)
    available_slots = db.Column(db.Integer)
    image_url = db.Column(db.String(255))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    status = db.Column(db.String(20), nullable=False, default="Open")
    assigned_staff_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    bookings = db.relationship("Booking", back_populates="trek", cascade="all, delete-orphan")
    assigned_staff = db.relationship(
        "User",
        back_populates="assigned_treks",
        foreign_keys=[assigned_staff_id],
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def state(self):
        """Computes Trek State dynamically based on current date: Upcoming, Ongoing, or Completed."""
        today = date.today()
        if self.end_date and self.end_date < today:
            return "Completed"
        if self.start_date and self.start_date <= today <= self.end_date:
            return "Ongoing"
        return "Upcoming"

    @property
    def duration(self):
        return self.duration_days

    def __repr__(self):
        return f"<Trek {self.name}>"


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    trek_id = db.Column(db.Integer, db.ForeignKey("trek.id"), nullable=False)
    booking_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default="Booked")

    user = db.relationship("User", back_populates="bookings")
    trek = db.relationship("Trek", back_populates="bookings")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f'<Booking trek_id="{self.trek_id}" user_id="{self.user_id}">'


class TrekChangeRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trek_id = db.Column(db.Integer, db.ForeignKey("trek.id"), nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    requested_available_slots = db.Column(db.Integer, nullable=False)
    requested_status = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending, approved, rejected
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    trek = db.relationship("Trek", backref=db.backref("change_requests", cascade="all, delete-orphan"))
    staff = db.relationship("User")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f'<TrekChangeRequest status="{self.status}" trek_id="{self.trek_id}">'
