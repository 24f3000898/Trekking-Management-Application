from datetime import datetime

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
    available_slots = db.Column(db.Integer)
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

    def __repr__(self):
        return f"<Booking user_id={self.user_id} trek_id={self.trek_id}>"
