from app import app
from models import User, db


with app.app_context():
    db.create_all()

    admin = User.query.filter_by(email="admin@trek.com").first()

    if not admin:
        admin = User(
            name="System Admin",
            email="admin@trek.com",
            password="adminpassword",
            role="admin",
            status="approved",
        )
        db.session.add(admin)
        db.session.commit()
        print("Database initialized and default admin user created.")
    else:
        print("Database initialized. Default admin user already exists.")
