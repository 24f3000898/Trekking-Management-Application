import os
import sys
import unittest
from datetime import date, timedelta
from io import StringIO
import csv

# Set testing environment before importing app
os.environ["FLASK_ENV"] = "testing"

from app import app, db
from models import User, Trek, Booking, TrekChangeRequest


class QAApplicationAuditTestCase(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
        self.ctx = app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        self.client = app.test_client()
        self._seed_initial_data()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _seed_initial_data(self):
        # Create Admin
        self.admin = User(
            name="System Admin",
            email="admin@trek.com",
            password="adminpassword",
            role="admin",
            status="approved",
        )

        # Create Staff (Approved)
        self.staff = User(
            name="John Staff",
            email="staff@trek.com",
            password="staffpassword",
            role="staff",
            status="approved",
        )

        # Create Staff (Pending)
        self.pending_staff = User(
            name="Pending Staff",
            email="pending_staff@trek.com",
            password="staffpassword",
            role="staff",
            status="pending",
        )

        # Create Trekker (Approved)
        self.trekker = User(
            name="Alice Trekker",
            email="trekker@trek.com",
            password="userpassword",
            role="trekker",
            status="approved",
        )

        db.session.add_all([self.admin, self.staff, self.pending_staff, self.trekker])
        db.session.commit()

        # Create Treks
        today = date.today()
        self.trek1 = Trek(
            name="Kedarkantha Trek",
            location="Uttarakhand",
            difficulty="Moderate",
            duration_days=6,
            available_slots=10,
            start_date=today + timedelta(days=10),
            end_date=today + timedelta(days=16),
            status="Open",
            assigned_staff_id=self.staff.id,
        )

        self.trek2 = Trek(
            name="Triund Trail",
            location="Himachal Pradesh",
            difficulty="Easy",
            duration_days=3,
            available_slots=0,
            start_date=today + timedelta(days=5),
            end_date=today + timedelta(days=8),
            status="Closed",
            assigned_staff_id=self.staff.id,
        )

        db.session.add_all([self.trek1, self.trek2])
        db.session.commit()

    def _login(self, email, password):
        return self.client.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=True,
        )

    # ----------------------------------------------------
    # 1. Security Logic & Route Protection Audit (RBAC)
    # ----------------------------------------------------
    def test_01_unauthenticated_access_protection(self):
        """Verify unauthenticated access to protected routes redirects to /login with warning flash."""
        protected_routes = [
            "/user/dashboard",
            "/staff/dashboard",
            "/admin/dashboard",
            "/user/treks",
            "/admin/add_trek",
            "/admin/trek/add",
        ]

        for route in protected_routes:
            res = self.client.get(route, follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"/login", res.request.path.encode())
            self.assertTrue(
                b"Please login to continue." in res.data or b"Please log in first" in res.data,
                f"Expected login warning for route {route}"
            )

    def test_02_role_isolation(self):
        """Verify role isolation for Trekker and Staff accessing unauthorized dashboards."""
        # Log in as Trekker
        self._login("trekker@trek.com", "userpassword")

        # Trekker tries to access Admin dashboard
        res_admin = self.client.get("/admin/dashboard", follow_redirects=True)
        self.assertEqual(res_admin.status_code, 200)
        self.assertIn(b"/user/dashboard", res_admin.request.path.encode())
        self.assertIn(b"Unauthorized access", res_admin.data)

        # Trekker tries to access Staff dashboard
        res_staff = self.client.get("/staff/dashboard", follow_redirects=True)
        self.assertEqual(res_staff.status_code, 200)
        self.assertIn(b"/user/dashboard", res_staff.request.path.encode())
        self.assertIn(b"Unauthorized access", res_staff.data)

        # Log out
        self.client.get("/logout")

        # Log in as Staff
        self._login("staff@trek.com", "staffpassword")

        # Staff tries to access Admin dashboard
        res_staff_admin = self.client.get("/admin/dashboard", follow_redirects=True)
        self.assertEqual(res_staff_admin.status_code, 200)
        self.assertIn(b"/staff/dashboard", res_staff_admin.request.path.encode())
        self.assertIn(b"Unauthorized access", res_staff_admin.data)

    def test_03_blacklisted_account_handling(self):
        """Verify blacklisted user cannot log in and active blacklisted sessions are terminated."""
        # Log in as Admin and blacklist Trekker
        self._login("admin@trek.com", "adminpassword")
        res = self.client.post(f"/admin/user/blacklist/{self.trekker.id}", follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify DB state
        with app.app_context():
            u = db.session.get(User, self.trekker.id)
            assert u is not None
            self.assertEqual(u.status, "blacklisted")

        self.client.get("/logout")

        # Attempt to log in as blacklisted Trekker
        res_login = self._login("trekker@trek.com", "userpassword")
        self.assertIn(b"Account blacklisted. Contact support.", res_login.data)
        self.assertIn(b"/login", res_login.request.path.encode())

    # ----------------------------------------------------
    # 2. Trekker (User) Journey Test
    # ----------------------------------------------------
    def test_04_trek_discovery_and_search_filtering(self):
        """Verify trek search by name, difficulty, and location filter on /user/treks."""
        self._login("trekker@trek.com", "userpassword")

        # Search by trek name "Kedarkantha"
        res = self.client.get("/user/treks?q=Kedarkantha")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Kedarkantha Trek", res.data)

        # Filter by Difficulty="Moderate" & Location="Uttarakhand"
        res_filter = self.client.get("/user/treks?difficulty=Moderate&location=Uttarakhand")
        self.assertEqual(res_filter.status_code, 200)
        self.assertIn(b"Kedarkantha Trek", res_filter.data)

        # Search for non-existent trek
        res_empty = self.client.get("/user/treks?q=NonExistentTrekName")
        self.assertEqual(res_empty.status_code, 200)
        self.assertIn(b"No open treks with available slots matched your search", res_empty.data)

    def test_05_booking_engine_and_capacity_verification(self):
        """Verify booking trek decrements slots, shows on user dashboard, and blocks double/overbooking."""
        self._login("trekker@trek.com", "userpassword")

        # Book Trek 1 (Kedarkantha, 10 slots)
        res_book = self.client.post(f"/user/book/{self.trek1.id}", follow_redirects=True)
        self.assertEqual(res_book.status_code, 200)
        self.assertIn(b"Trek booked successfully.", res_book.data)

        # Verify slots decremented to 9
        with app.app_context():
            t = db.session.get(Trek, self.trek1.id)
            assert t is not None
            self.assertEqual(t.available_slots, 9)

        # Verify appears on user dashboard under Upcoming Treks
        res_dash = self.client.get("/user/dashboard")
        self.assertIn(b"Kedarkantha Trek", res_dash.data)

        # Attempt double-booking same trek
        res_double = self.client.post(f"/user/book/{self.trek1.id}", follow_redirects=True)
        self.assertIn(b"You have already booked this trek", res_double.data)

        # Attempt booking Closed trek with 0 slots
        res_closed = self.client.post(f"/user/book/{self.trek2.id}", follow_redirects=True)
        self.assertIn(b"No slots available", res_closed.data)

    def test_06_booking_cancellation_workflow(self):
        """Verify cancellation updates booking status/deletes and increments slots back by +1."""
        self._login("trekker@trek.com", "userpassword")

        # Book trek
        self.client.post(f"/user/book/{self.trek1.id}")

        with app.app_context():
            b = Booking.query.filter_by(user_id=self.trekker.id, trek_id=self.trek1.id).first()
            assert b is not None
            booking_id = b.id

        # Cancel booking
        res_cancel = self.client.post(f"/user/booking/cancel/{booking_id}", follow_redirects=True)
        self.assertEqual(res_cancel.status_code, 200)
        self.assertIn(b"Booking cancelled successfully.", res_cancel.data)

        # Verify slot incremented back to 10
        with app.app_context():
            t = db.session.get(Trek, self.trek1.id)
            assert t is not None
            self.assertEqual(t.available_slots, 10)
            b_check = db.session.get(Booking, booking_id)
            self.assertIsNone(b_check)

    # ----------------------------------------------------
    # 3. Staff Portal Test
    # ----------------------------------------------------
    def test_07_staff_dashboard_metrics_and_assigned_treks(self):
        """Verify staff dashboard metric cards and capacity progress bar ratios."""
        self._login("staff@trek.com", "staffpassword")

        res = self.client.get("/staff/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Total Assigned Treks", res.data)
        self.assertIn(b"Registered Trekkers", res.data)
        self.assertIn(b"Kedarkantha Trek", res.data)

    def test_08_staff_trek_capacity_and_status_updates(self):
        """Verify staff updating slots and toggling status Open -> Closed via Change Request."""
        self._login("staff@trek.com", "staffpassword")

        # Update trek1: slots to 5, status to Closed
        res_update = self.client.post(
            f"/staff/trek/update/{self.trek1.id}",
            data={"available_slots": 5, "status": "Closed"},
            follow_redirects=True,
        )
        self.assertEqual(res_update.status_code, 200)
        self.assertIn(b"Change request submitted to Admin for approval.", res_update.data)

        self.client.get("/logout")

        # Admin approves change request
        self._login("admin@trek.com", "adminpassword")
        with app.app_context():
            req = TrekChangeRequest.query.filter_by(trek_id=self.trek1.id).first()
            assert req is not None
            req_id = req.id
        res_app = self.client.post(f"/admin/change_request/approve/{req_id}", follow_redirects=True)
        self.assertEqual(res_app.status_code, 200)
        self.assertIn(b"Change request approved successfully.", res_app.data)

        self.client.get("/logout")

        # Trekker checks /user/treks - trek1 should now be hidden since it's Closed
        self._login("trekker@trek.com", "userpassword")
        res_treks = self.client.get("/user/treks")
        self.assertNotIn(b"Kedarkantha Trek", res_treks.data)

    def test_09_staff_csv_export_and_participant_modal(self):
        """Verify participant modal and staff CSV export header structure."""
        self._login("staff@trek.com", "staffpassword")

        # Trigger participant view
        res_part = self.client.get(f"/staff/trek/participants/{self.trek1.id}")
        self.assertEqual(res_part.status_code, 200)

        # Download Participant CSV
        res_csv = self.client.get(f"/staff/export/participants/{self.trek1.id}")
        self.assertEqual(res_csv.status_code, 200)
        self.assertTrue(res_csv.content_type.startswith("text/csv"))
        csv_lines = res_csv.data.decode("utf-8").splitlines()
        self.assertTrue(len(csv_lines) >= 1)
        self.assertEqual(csv_lines[0].strip(), "Trekker Name,Email,Booking Date,Status")

    # ----------------------------------------------------
    # 4. Admin Management Center Test
    # ----------------------------------------------------
    def test_10_admin_global_analytics_metric_cards(self):
        """Verify admin dashboard metric cards render without division by zero when db metrics are checked."""
        self._login("admin@trek.com", "adminpassword")

        res = self.client.get("/admin/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(b"capacity utilization" in res.data.lower() or b"total booking" in res.data.lower())

    def test_11_admin_full_crud_on_treks_and_cascade_delete(self):
        """Verify Admin Create, Read/Search, Update, and Cascade Delete on Treks."""
        self._login("admin@trek.com", "adminpassword")

        # 1. Create Trek
        today = date.today()
        new_trek_data = {
            "name": "Roopkund Trail",
            "location": "Uttarakhand",
            "difficulty": "Hard",
            "duration_days": 8,
            "available_slots": 15,
            "start_date": (today + timedelta(days=20)).isoformat(),
            "end_date": (today + timedelta(days=28)).isoformat(),
            "assigned_staff_id": self.staff.id,
        }
        res_create = self.client.post("/admin/trek/add", data=new_trek_data, follow_redirects=True)
        self.assertEqual(res_create.status_code, 200)
        self.assertIn(b"Trek added successfully.", res_create.data)

        with app.app_context():
            created_trek = Trek.query.filter_by(name="Roopkund Trail").first()
            assert created_trek is not None
            created_id = created_trek.id

        # 2. Read/Search
        res_search = self.client.get("/admin/dashboard?q=Roopkund")
        self.assertIn(b"Roopkund Trail", res_search.data)

        # 3. Update Trek
        new_trek_data["name"] = "Roopkund Trail Updated"
        res_edit = self.client.post(f"/admin/trek/edit/{created_id}", data=new_trek_data, follow_redirects=True)
        self.assertIn(b"Trek updated successfully.", res_edit.data)

        # 4. Add a booking to created trek and test CASCADE Delete
        with app.app_context():
            b = Booking(user_id=self.trekker.id, trek_id=created_id, status="Confirmed")
            db.session.add(b)
            db.session.commit()

        res_delete = self.client.post(f"/admin/trek/delete/{created_id}", follow_redirects=True)
        self.assertEqual(res_delete.status_code, 200)
        self.assertIn(b"Trek deleted successfully.", res_delete.data)

        with app.app_context():
            self.assertIsNone(db.session.get(Trek, created_id))

    def test_12_admin_user_and_staff_moderation(self):
        """Verify approving pending staff and blacklisting/reactivating users."""
        self._login("admin@trek.com", "adminpassword")

        # Approve Pending Staff
        res_app = self.client.post(f"/admin/staff/approve/{self.pending_staff.id}", follow_redirects=True)
        self.assertIn(b"Staff member approved successfully.", res_app.data)

        # Blacklist Trekker
        res_black = self.client.post(f"/admin/user/blacklist/{self.trekker.id}", follow_redirects=True)
        self.assertIn(b"Trekker blacklisted.", res_black.data)

        # Reactivate Trekker
        res_react = self.client.post(f"/admin/user/reactivate/{self.trekker.id}", follow_redirects=True)
        self.assertIn(b"Trekker reactivated successfully.", res_react.data)

    def test_13_admin_global_csv_export(self):
        """Verify global bookings CSV export content & headers."""
        self._login("admin@trek.com", "adminpassword")

        res_csv = self.client.get("/admin/export/bookings")
        self.assertEqual(res_csv.status_code, 200)
        self.assertTrue(res_csv.content_type.startswith("text/csv"))
        csv_lines = res_csv.data.decode("utf-8").splitlines()
        self.assertTrue(len(csv_lines) >= 1)
        self.assertEqual(
            csv_lines[0].strip(),
            "Booking ID,Trek Name,Trekker Name,Trekker Email,Booking Date,Status"
        )

    # ----------------------------------------------------
    # 5. Data Integrity & Edge Case Checks
    # ----------------------------------------------------
    def test_14_url_query_parameter_tampering(self):
        """Verify sending invalid or manipulated IDs gracefully returns flash errors or 404 without 500 error."""
        self._login("trekker@trek.com", "userpassword")

        # Attempt to cancel non-existent booking ID 99999
        res1 = self.client.post("/user/booking/cancel/99999", follow_redirects=True)
        self.assertEqual(res1.status_code, 200)
        self.assertIn(b"Booking not found.", res1.data)

        res2 = self.client.post("/user/cancel_booking/99999", follow_redirects=True)
        self.assertEqual(res2.status_code, 200)
        self.assertIn(b"Booking not found.", res2.data)

        self.client.get("/logout")
        self._login("admin@trek.com", "adminpassword")

        # Attempt to edit or delete non-existent trek ID 99999
        res3 = self.client.post("/admin/trek/delete/99999", follow_redirects=True)
        self.assertEqual(res3.status_code, 200)
        self.assertIn(b"Trek not found.", res3.data)

    def test_15_form_validation_and_negative_number_prevention(self):
        """Verify negative numbers or invalid values in form inputs are rejected gracefully."""
        self._login("staff@trek.com", "staffpassword")

        # Submit negative available slots
        res = self.client.post(
            f"/staff/trek/update/{self.trek1.id}",
            data={"available_slots": -5, "status": "Open"},
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Available slots cannot be negative.", res.data)

    def test_16_staff_dashboard_trek_state_badges_alerts_and_locking(self):
        """Verify Trek State badges, pending change request alert, and form control edit locking."""
        today = date.today()

        t1 = db.session.get(Trek, self.trek1.id)
        assert t1 is not None
        t1.start_date = today - timedelta(days=1)
        t1.end_date = today + timedelta(days=5)

        t2 = db.session.get(Trek, self.trek2.id)
        assert t2 is not None
        t2.start_date = today + timedelta(days=10)
        t2.end_date = today + timedelta(days=15)

        cr = TrekChangeRequest(
            trek_id=t2.id,
            staff_id=self.staff.id,
            requested_available_slots=12,
            requested_status="Open",
            status="pending",
        )
        db.session.add(cr)
        db.session.commit()

        self._login("staff@trek.com", "staffpassword")
        res = self.client.get("/staff/dashboard")
        self.assertEqual(res.status_code, 200)

        # Check Trek State badge for Ongoing
        self.assertIn(b"Ongoing", res.data)

        # Check pending change request alert banner
        self.assertIn(b"Change request pending Admin approval", res.data)
        self.assertIn(b"Proposed: 12 slots", res.data)

        # Check form locking for ongoing trek
        self.assertIn(b"Edits disabled for ongoing or completed treks", res.data)



if __name__ == "__main__":
    unittest.main(verbosity=2)


