from datetime import date, timedelta
from app import app, db
from models import User, Trek

def reset_and_seed_database():
    with app.app_context():
        # 1. Recreate all database tables
        db.drop_all()
        db.create_all()
        print("🗑️ Old database dropped and clean tables created!")

        # 2. Mandatory IIT Madras Admin Credential
        admin = User(
            name="System Admin",
            email="admin@trek.com",
            password="adminpassword",
            role="admin",
            status="approved"
        )

        # 3. Default Staff & Trekker Accounts for Testing
        staff = User(
            name="Rahul Sharma",
            email="staff@trek.com",
            password="staffpassword",
            role="staff",
            status="approved"
        )

        user = User(
            name="Ravi Paribrajak",
            email="user@gmail.com",
            password="123",
            role="trekker",
            status="approved"
        )

        db.session.add_all([admin, staff, user])
        db.session.commit()
        print("👤 Mandatory Admin, Staff, and User accounts created!")

        # 4. Sample Production Treks
        today = date.today()
        sample_treks = [
            Trek(
                name="Kedarkantha Trek",
                location="Uttarakhand",
                difficulty="Moderate",
                duration_days=5,
                total_slots=20,
                available_slots=15,
                start_date=today + timedelta(days=5),
                end_date=today + timedelta(days=10),
                status="Open",
                assigned_staff_id=staff.id,
                image_url="https://images.unsplash.com/photo-1544735716-392fe2489ffa?q=80&w=800"
            ),
            Trek(
                name="Triund Trek",
                location="Himachal Pradesh",
                difficulty="Easy",
                duration_days=2,
                total_slots=25,
                available_slots=25,
                start_date=today + timedelta(days=7),
                end_date=today + timedelta(days=9),
                status="Open",
                assigned_staff_id=staff.id,
                image_url="https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?q=80&w=800"
            ),
            Trek(
                name="Kashmir Great Lakes Trek",
                location="Jammu & Kashmir",
                difficulty="Hard",
                duration_days=7,
                total_slots=15,
                available_slots=11,
                start_date=today + timedelta(days=12),
                end_date=today + timedelta(days=19),
                status="Open",
                assigned_staff_id=staff.id,
                image_url="https://images.unsplash.com/photo-1506744038136-46273834b3fb?q=80&w=800"
            ),
            Trek(
                name="Valley of Flowers Expedition",
                location="Uttarakhand",
                difficulty="Moderate",
                duration_days=6,
                total_slots=18,
                available_slots=14,
                start_date=today + timedelta(days=15),
                end_date=today + timedelta(days=21),
                status="Open",
                assigned_staff_id=staff.id,
                image_url="https://images.unsplash.com/photo-1486870591958-9b9d0d1dda99?q=80&w=800"
            )
        ]

        db.session.add_all(sample_treks)
        db.session.commit()
        print("🏔️ Sample Treks seeded successfully!")
        print("\n✨ Database is now 100% ready for submission & evaluation!")

if __name__ == "__main__":
    reset_and_seed_database()