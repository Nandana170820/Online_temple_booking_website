import os
import base64
import hashlib
import hmac
import json
import re
import urllib.error
import urllib.request
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

from flask import Flask, flash, redirect, render_template, request, send_file, session, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect
from werkzeug.security import check_password_hash, generate_password_hash

from .i18n import SUPPORTED_LANGUAGES, format_date_text, format_time_text, translate_text

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import razorpay
except ImportError:
    razorpay = None

def load_local_env():
    env_path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if load_dotenv:
    load_dotenv()
else:
    load_local_env()

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "login"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    phone = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    bookings = db.relationship("Booking", backref="user", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), nullable=False, default="Vazhipadu")
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    capacity_per_slot = db.Column(db.Integer, nullable=False, default=40)
    is_active = db.Column(db.Boolean, default=True)
    bookings = db.relationship("Booking", backref="service", lazy=True)


class Slot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    slot_time = db.Column(db.Time, nullable=False)
    category = db.Column(db.String(80), nullable=False, default="Darshan")
    capacity = db.Column(db.Integer, nullable=False, default=80)
    is_active = db.Column(db.Boolean, default=True)
    bookings = db.relationship("Booking", backref="slot", lazy=True)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_code = db.Column(db.String(20), nullable=False, unique=True)
    booking_type = db.Column(db.String(30), nullable=False, default="Darshan")
    devotee_name = db.Column(db.String(120), nullable=False)
    devotee_phone = db.Column(db.String(20), nullable=False)
    devotee_email = db.Column(db.String(120), nullable=False)
    visit_date = db.Column(db.Date, nullable=False)
    participants = db.Column(db.Integer, nullable=False, default=1)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="Pending Payment")
    payment_status = db.Column(db.String(30), nullable=False, default="Pending")
    payment_mode = db.Column(db.String(30), nullable=True)
    transaction_id = db.Column(db.String(80), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=True)
    slot_id = db.Column(db.Integer, db.ForeignKey("slot.id"), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-change-this-secret"),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URL", f"sqlite:///{os.path.join(app.instance_path, 'temple.db')}"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        RAZORPAY_KEY_ID=os.environ.get("RAZORPAY_KEY_ID", "rzp_test_local_key"),
        RAZORPAY_KEY_SECRET=os.environ.get("RAZORPAY_KEY_SECRET", ""),
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        ensure_schema()
        seed_database()

    register_routes(app)
    return app


def ensure_schema():
    db.create_all()
    inspector = inspect(db.engine)

    required_columns = {
        "user": {"id", "name", "email", "phone", "password_hash", "is_admin", "created_at"},
        "service": {"id", "name", "category", "description", "price", "capacity_per_slot", "is_active"},
        "slot": {"id", "name", "slot_time", "category", "capacity", "is_active"},
        "booking": {
            "id",
            "booking_code",
            "booking_type",
            "devotee_name",
            "devotee_phone",
            "devotee_email",
            "visit_date",
            "participants",
            "total_amount",
            "status",
            "payment_status",
            "payment_mode",
            "transaction_id",
            "notes",
            "created_at",
            "user_id",
            "service_id",
            "slot_id",
        },
    }

    table_names = set(inspector.get_table_names())
    if not set(required_columns).issubset(table_names):
        db.drop_all()
        db.create_all()
        return

    for table_name, columns in required_columns.items():
        existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
        if not columns.issubset(existing_columns):
            db.drop_all()
            db.create_all()
            return

    # Keep demo deployments resilient if an older SQLite file has extra legacy tables.
    if not table_names.issubset(set(required_columns)):
        db.drop_all()
        db.create_all()


def seed_database():
    service_seeds = [
        {
            "name": "Archana",
            "category": "Vazhipadu",
            "description": "Archana offering with devotee name and nakshatra details recorded for temple office use.",
            "price": Decimal("50.00"),
            "capacity_per_slot": 60,
        },
        {
            "name": "Neyvilakku",
            "category": "Vazhipadu",
            "description": "Ghee lamp offering for family prayers, prosperity and daily worship.",
            "price": Decimal("30.00"),
            "capacity_per_slot": 100,
        },
        {
            "name": "Pushpanjali",
            "category": "Vazhipadu",
            "description": "Flower offering performed with the devotee details submitted online.",
            "price": Decimal("40.00"),
            "capacity_per_slot": 80,
        },
        {
            "name": "Bhagavathy Seva",
            "category": "Vazhipadu",
            "description": "Special Devi seva booking for household welfare and protection prayers.",
            "price": Decimal("350.00"),
            "capacity_per_slot": 25,
        },
        {
            "name": "Palpayasam",
            "category": "Vazhipadu",
            "description": "Prasadam-style sweet offering booked with devotee details and quantity.",
            "price": Decimal("120.00"),
            "capacity_per_slot": 50,
        },
        {
            "name": "Chuttuvilakku",
            "category": "Vazhipadu",
            "description": "Lamp offering for evening worship, festivals and family prayers.",
            "price": Decimal("250.00"),
            "capacity_per_slot": 20,
        },
        {
            "name": "Special Darshan",
            "category": "Darshan",
            "description": "Timed darshan entry with managed queue capacity and confirmation receipt.",
            "price": Decimal("20.00"),
            "capacity_per_slot": 120,
        },
        {
            "name": "Temple Marriage Booking",
            "category": "Marriage",
            "description": "Marriage registration slot with bride and groom details recorded for temple office verification.",
            "price": Decimal("500.00"),
            "capacity_per_slot": 1,
        },
    ]
    for seed in service_seeds:
        service = Service.query.filter_by(name=seed["name"]).first()
        if service is None:
            db.session.add(Service(**seed))

    slot_seeds = [
        ("Nirmalyam Darshan", "03:30", "Darshan", 80),
        ("Morning Darshan", "05:30", "Darshan", 120),
        ("Forenoon Darshan", "08:00", "Darshan", 100),
        ("Noon Darshan", "10:30", "Darshan", 80),
        ("Evening Darshan", "17:30", "Darshan", 120),
        ("Deeparadhana Darshan", "18:30", "Darshan", 100),
        ("Vazhipadu Morning", "07:00", "Vazhipadu", 70),
        ("Vazhipadu Evening", "18:30", "Vazhipadu", 70),
        ("Marriage Muhurtham Morning", "06:00", "Marriage", 4),
        ("Marriage Muhurtham Forenoon", "09:00", "Marriage", 4),
    ]
    for name, slot_time, category, capacity in slot_seeds:
        slot = Slot.query.filter_by(name=name, category=category).first()
        if slot is None:
            db.session.add(
                Slot(
                    name=name,
                    slot_time=datetime.strptime(slot_time, "%H:%M").time(),
                    category=category,
                    capacity=capacity,
                )
            )

    if User.query.filter_by(email="admin@temple.local").first() is None:
        admin = User(name="Temple Admin", email="admin@temple.local", phone="04885275090", is_admin=True)
        admin.set_password("admin123")
        db.session.add(admin)

    db.session.commit()


def admin_required():
    if not current_user.is_authenticated or not current_user.is_admin:
        flash("Admin access required.", "error")
        return False
    return True


def is_valid_email(email):
    return bool(email and EMAIL_PATTERN.match(email))


def booking_endpoint(booking_type):
    return {
        "Vazhipadu": "vazhipadu_booking",
        "Marriage": "marriage_booking",
    }.get(booking_type, "darshan_booking")


def razorpay_is_ready(app):
    key_id = app.config["RAZORPAY_KEY_ID"]
    key_secret = app.config["RAZORPAY_KEY_SECRET"]
    return bool(key_id and key_secret and key_id != "rzp_test_local_key")


def create_razorpay_order(app, booking):
    if not razorpay_is_ready(app):
        return None
    amount_paise = int(Decimal(booking.total_amount) * 100)
    payload = {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": booking.booking_code,
        "notes": {
            "booking_code": booking.booking_code,
            "booking_type": booking.booking_type,
            "devotee": booking.devotee_name,
        },
    }
    try:
        if razorpay:
            client = razorpay.Client(auth=(app.config["RAZORPAY_KEY_ID"], app.config["RAZORPAY_KEY_SECRET"]))
            return client.order.create(payload)

        auth = f"{app.config['RAZORPAY_KEY_ID']}:{app.config['RAZORPAY_KEY_SECRET']}".encode("utf-8")
        request_payload = json.dumps(payload).encode("utf-8")
        request_obj = urllib.request.Request(
            "https://api.razorpay.com/v1/orders",
            data=request_payload,
            method="POST",
            headers={
                "Authorization": f"Basic {base64.b64encode(auth).decode('utf-8')}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request_obj, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, Exception):
        return None


def verify_razorpay_signature(app, order_id, payment_id, signature):
    if not order_id or not payment_id or not signature or not app.config["RAZORPAY_KEY_SECRET"]:
        return False
    payload = f"{order_id}|{payment_id}".encode("utf-8")
    expected = hmac.new(app.config["RAZORPAY_KEY_SECRET"].encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def register_routes(app):
    @app.context_processor
    def inject_template_globals():
        language = session.get("language", "en")
        if language not in SUPPORTED_LANGUAGES:
            language = "en"
        return {
            "current_year": date.today().year,
            "current_language": language,
            "supported_languages": SUPPORTED_LANGUAGES,
            "t": lambda text: translate_text(text, language),
            "format_date": lambda value: format_date_text(value, language),
            "format_time": lambda value: format_time_text(value, language),
        }

    @app.route("/language/<language>")
    def set_language(language):
        if language in SUPPORTED_LANGUAGES:
            session["language"] = language
        next_url = request.referrer or url_for("index")
        if next_url.startswith(("http://", "https://")) and not next_url.startswith(request.host_url):
            next_url = url_for("index")
        return redirect(next_url)

    @app.route("/")
    def index():
        services = Service.query.filter_by(is_active=True).limit(4).all()
        return render_template("index.html", services=services)

    @app.route("/services")
    def services():
        all_services = Service.query.filter_by(is_active=True).order_by(Service.category, Service.name).all()
        return render_template("services.html", services=all_services)

    @app.route("/history")
    def history():
        return render_template("history.html")

    @app.route("/gallery")
    def gallery():
        return render_template("gallery.html")

    @app.route("/timings")
    def timings():
        slots = Slot.query.filter_by(is_active=True).order_by(Slot.slot_time).all()
        return render_template("timings.html", slots=slots)

    @app.route("/contact", methods=["GET", "POST"])
    def contact():
        if request.method == "POST":
            email = request.form.get("email", "").strip()
            if email and not is_valid_email(email):
                flash("Please enter a valid email address.", "error")
                return redirect(url_for("contact"))
            flash("Your enquiry has been noted. The temple office will contact you if follow-up is required.", "success")
            return redirect(url_for("contact"))
        return render_template("contact.html")

    @app.route("/darshan-booking", methods=["GET", "POST"])
    @login_required
    def darshan_booking():
        service = Service.query.filter_by(category="Darshan", is_active=True).first()
        slots = Slot.query.filter_by(category="Darshan", is_active=True).order_by(Slot.slot_time).all()
        if request.method == "POST":
            return create_booking("Darshan", service)
        return render_template("darshan_booking.html", service=service, slots=slots)

    @app.route("/vazhipadu-booking", methods=["GET", "POST"])
    @login_required
    def vazhipadu_booking():
        services = Service.query.filter_by(category="Vazhipadu", is_active=True).order_by(Service.name).all()
        slots = Slot.query.filter_by(category="Vazhipadu", is_active=True).order_by(Slot.slot_time).all()
        selected_service = request.args.get("service_id", type=int)
        if request.method == "POST":
            service = db.session.get(Service, request.form.get("service_id", type=int))
            return create_booking("Vazhipadu", service)
        return render_template("vazhipadu_booking.html", services=services, slots=slots, selected_service=selected_service)

    @app.route("/marriage-booking", methods=["GET", "POST"])
    @login_required
    def marriage_booking():
        service = Service.query.filter_by(category="Marriage", is_active=True).first()
        slots = Slot.query.filter_by(category="Marriage", is_active=True).order_by(Slot.slot_time).all()
        if request.method == "POST":
            required_fields = ["bride_name", "groom_name", "devotee_name", "devotee_phone", "devotee_email"]
            if any(not request.form.get(field, "").strip() for field in required_fields):
                flash("Please fill all required fields.", "error")
                return redirect(url_for("marriage_booking"))

            expected_guests = request.form.get("expected_guests", "").strip() or "Not specified"
            marriage_notes = [
                f"Bride: {request.form['bride_name'].strip()}",
                f"Groom: {request.form['groom_name'].strip()}",
                f"Bride details: {request.form.get('bride_details', '').strip() or 'Not specified'}",
                f"Groom details: {request.form.get('groom_details', '').strip() or 'Not specified'}",
                f"Expected guests: {expected_guests}",
                f"Address / ID note: {request.form.get('family_note', '').strip() or 'Not specified'}",
                f"Temple office note: {request.form.get('notes', '').strip() or 'None'}",
            ]
            return create_booking("Marriage", service, participants_override=1, notes_override="\n".join(marriage_notes))
        return render_template("marriage_booking.html", service=service, slots=slots)

    @app.route("/book")
    def book():
        return redirect(url_for("darshan_booking"))

    @app.route("/payment/<code>", methods=["GET", "POST"])
    @login_required
    def payment(code):
        booking = Booking.query.filter_by(booking_code=code, user_id=current_user.id).first_or_404()
        if request.method == "POST":
            razorpay_payment_id = request.form.get("razorpay_payment_id", "").strip()
            razorpay_order_id = request.form.get("razorpay_order_id", "").strip()
            razorpay_signature = request.form.get("razorpay_signature", "").strip()
            if razorpay_payment_id:
                if not verify_razorpay_signature(app, razorpay_order_id, razorpay_payment_id, razorpay_signature):
                    flash("Payment verification failed. Please try again or contact temple office.", "error")
                    return redirect(url_for("payment", code=booking.booking_code))
                booking.payment_mode = "Razorpay Online"
                booking.transaction_id = razorpay_payment_id
                booking.payment_status = "Paid"
                booking.status = "Confirmed"
                db.session.commit()
                flash("Payment verified and booking confirmed.", "success")
                return redirect(url_for("confirmation", code=booking.booking_code))

            flash("Please complete payment through Razorpay Checkout.", "error")
            return redirect(url_for("payment", code=booking.booking_code))

        razorpay_order = create_razorpay_order(app, booking)
        return render_template(
            "payment.html",
            booking=booking,
            razorpay_key_id=app.config["RAZORPAY_KEY_ID"],
            razorpay_order=razorpay_order,
            razorpay_ready=razorpay_order is not None,
        )

    @app.route("/confirmation/<code>")
    @login_required
    def confirmation(code):
        query = Booking.query.filter_by(booking_code=code)
        if not current_user.is_admin:
            query = query.filter_by(user_id=current_user.id)
        booking = query.first_or_404()
        return render_template("confirmation.html", booking=booking)

    @app.route("/receipt/<code>")
    @login_required
    def receipt(code):
        query = Booking.query.filter_by(booking_code=code)
        if not current_user.is_admin:
            query = query.filter_by(user_id=current_user.id)
        booking = query.first_or_404()
        return render_template("receipt.html", booking=booking)

    @app.route("/receipt/<code>.pdf")
    @login_required
    def receipt_pdf(code):
        query = Booking.query.filter_by(booking_code=code)
        if not current_user.is_admin:
            query = query.filter_by(user_id=current_user.id)
        booking = query.first_or_404()
        pdf_bytes = build_receipt_pdf(booking)
        should_download = request.args.get("download") == "1"
        return send_file(
            BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=should_download,
            download_name=f"{booking.booking_code}-receipt.pdf",
        )

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            email = request.form["email"].strip().lower()
            if not is_valid_email(email):
                flash("Please enter a valid email address.", "error")
                return redirect(url_for("register"))
            if User.query.filter_by(email=email).first():
                flash("An account already exists with this email.", "error")
                return redirect(url_for("register"))
            user = User(name=request.form["name"].strip(), email=email, phone=request.form["phone"].strip())
            user.set_password(request.form["password"])
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Account created. You can now book darshan, vazhipadu and marriage slots.", "success")
            return redirect(url_for("dashboard"))
        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form["email"].strip().lower()
            if not is_valid_email(email):
                flash("Please enter a valid email address.", "error")
                return redirect(url_for("login"))
            user = User.query.filter_by(email=email).first()
            if not user or not user.check_password(request.form["password"]):
                flash("Invalid email or password.", "error")
                return redirect(url_for("login"))
            login_user(user)
            flash("Welcome back.", "success")
            return redirect(url_for("admin") if user.is_admin else url_for("dashboard"))
        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("You have been logged out.", "success")
        return redirect(url_for("index"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.created_at.desc()).all()
        return render_template("dashboard.html", bookings=bookings)

    @app.route("/admin")
    @login_required
    def admin():
        if not admin_required():
            return redirect(url_for("dashboard"))
        bookings = Booking.query.order_by(Booking.created_at.desc()).limit(10).all()
        total_bookings = Booking.query.count()
        total_revenue = (
            db.session.query(db.func.coalesce(db.func.sum(Booking.total_amount), 0))
            .select_from(Booking)
            .filter(Booking.payment_status == "Paid")
            .scalar()
        )
        user_count = User.query.count()
        slot_count = Slot.query.count()
        return render_template("admin.html", bookings=bookings, total_bookings=total_bookings, total_revenue=total_revenue, user_count=user_count, slot_count=slot_count)

    @app.route("/admin/vazhipadu")
    @login_required
    def admin_vazhipadu():
        if not admin_required():
            return redirect(url_for("dashboard"))
        services = Service.query.order_by(Service.category, Service.name).all()
        return render_template("admin_vazhipadu.html", services=services)

    @app.route("/admin/vazhipadu/new", methods=["GET", "POST"])
    @app.route("/admin/vazhipadu/<int:service_id>/edit", methods=["GET", "POST"])
    @login_required
    def admin_vazhipadu_form(service_id=None):
        if not admin_required():
            return redirect(url_for("dashboard"))
        service = db.session.get(Service, service_id) if service_id else Service(category="Vazhipadu", is_active=True)
        if request.method == "POST":
            service.name = request.form["name"].strip()
            service.category = request.form["category"]
            service.description = request.form["description"].strip()
            service.price = Decimal(request.form["price"])
            service.capacity_per_slot = int(request.form["capacity_per_slot"])
            service.is_active = request.form.get("is_active") == "on"
            db.session.add(service)
            db.session.commit()
            flash("Service saved.", "success")
            return redirect(url_for("admin_vazhipadu"))
        return render_template("admin_vazhipadu_form.html", service=service)

    @app.route("/admin/vazhipadu/<int:service_id>/delete", methods=["POST"])
    @login_required
    def admin_vazhipadu_delete(service_id):
        if not admin_required():
            return redirect(url_for("dashboard"))
        service = db.session.get(Service, service_id)
        if service and not service.bookings:
            db.session.delete(service)
            db.session.commit()
            flash("Service deleted.", "success")
        else:
            flash("Service has bookings, so it was deactivated instead.", "error")
            if service:
                service.is_active = False
                db.session.commit()
        return redirect(url_for("admin_vazhipadu"))

    @app.route("/admin/users")
    @login_required
    def admin_users():
        if not admin_required():
            return redirect(url_for("dashboard"))
        users = User.query.order_by(User.created_at.desc()).all()
        return render_template("admin_users.html", users=users)

    @app.route("/admin/bookings")
    @login_required
    def admin_bookings():
        if not admin_required():
            return redirect(url_for("dashboard"))
        bookings = Booking.query.order_by(Booking.created_at.desc()).all()
        return render_template("admin_bookings.html", bookings=bookings)

    @app.route("/admin/slots", methods=["GET", "POST"])
    @login_required
    def admin_slots():
        if not admin_required():
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            slot = Slot(
                name=request.form["name"].strip(),
                slot_time=datetime.strptime(request.form["slot_time"], "%H:%M").time(),
                category=request.form["category"],
                capacity=int(request.form["capacity"]),
                is_active=True,
            )
            db.session.add(slot)
            db.session.commit()
            flash("Slot added.", "success")
            return redirect(url_for("admin_slots"))
        slots = Slot.query.order_by(Slot.category, Slot.slot_time).all()
        return render_template("admin_slots.html", slots=slots)

    @app.route("/admin/slots/<int:slot_id>/toggle", methods=["POST"])
    @login_required
    def admin_slot_toggle(slot_id):
        if not admin_required():
            return redirect(url_for("dashboard"))
        slot = db.session.get(Slot, slot_id)
        if slot:
            slot.is_active = not slot.is_active
            db.session.commit()
        return redirect(url_for("admin_slots"))

    @app.route("/admin/reports")
    @login_required
    def admin_reports():
        if not admin_required():
            return redirect(url_for("dashboard"))
        rows = (
            db.session.query(Booking.booking_type, db.func.count(Booking.id), db.func.coalesce(db.func.sum(Booking.total_amount), 0))
            .group_by(Booking.booking_type)
            .all()
        )
        return render_template("admin_reports.html", rows=rows)


def create_booking(booking_type, service, participants_override=None, notes_override=None):
    redirect_target = booking_endpoint(booking_type)
    if not service:
        flash("Please choose a valid service.", "error")
        return redirect(url_for(redirect_target))

    try:
        visit_date = datetime.strptime(request.form["visit_date"], "%Y-%m-%d").date()
        participants = participants_override if participants_override is not None else int(request.form["participants"])
        slot = db.session.get(Slot, request.form.get("slot_id", type=int))
    except (ValueError, KeyError):
        flash("Please enter valid date, slot and participant details.", "error")
        return redirect(url_for(redirect_target))

    if not slot or slot.category != booking_type:
        flash("Please choose a valid time slot.", "error")
        return redirect(url_for(redirect_target))
    if visit_date < date.today():
        flash("Please select today or a future date.", "error")
        return redirect(url_for(redirect_target))
    if participants < 1:
        flash("Number of persons must be at least 1.", "error")
        return redirect(url_for(redirect_target))

    devotee_email = request.form["devotee_email"].strip().lower()
    if not is_valid_email(devotee_email):
        flash("Please enter a valid email address.", "error")
        return redirect(url_for(redirect_target))

    existing_count = (
        db.session.query(db.func.coalesce(db.func.sum(Booking.participants), 0))
        .filter_by(slot_id=slot.id, visit_date=visit_date)
        .scalar()
    )
    if existing_count + participants > slot.capacity:
        flash("That slot is full. Please choose another time.", "error")
        return redirect(url_for(redirect_target))

    booking = Booking(
        booking_code=generate_booking_code(),
        booking_type=booking_type,
        devotee_name=request.form["devotee_name"].strip(),
        devotee_phone=request.form["devotee_phone"].strip(),
        devotee_email=devotee_email,
        visit_date=visit_date,
        participants=participants,
        total_amount=service.price * participants,
        notes=notes_override if notes_override is not None else request.form.get("notes", "").strip(),
        service_id=service.id,
        slot_id=slot.id,
        user_id=current_user.id,
    )
    db.session.add(booking)
    db.session.commit()
    flash("Booking created. Complete payment to confirm.", "success")
    return redirect(url_for("payment", code=booking.booking_code))


def generate_booking_code():
    prefix = datetime.utcnow().strftime("MDT%y%m%d")
    count = Booking.query.filter(Booking.booking_code.like(f"{prefix}%")).count() + 1
    return f"{prefix}{count:04d}"


def build_receipt_pdf(booking):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setFillColor(colors.HexColor("#9d2f22"))
    pdf.rect(0, height - 34 * mm, width, 34 * mm, fill=True, stroke=False)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(22 * mm, height - 18 * mm, "Mangad Devi Temple")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(22 * mm, height - 25 * mm, "Kunnamkulam | Phone: 04885 275090")

    y = height - 50 * mm
    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(22 * mm, y, "Booking Receipt")
    y -= 12 * mm

    details = [
        ("Receipt No", booking.booking_code),
        ("Booking Type", booking.booking_type),
        ("Service", booking.service.name if booking.service else "Darshan"),
        ("Devotee", booking.devotee_name),
        ("Mobile", booking.devotee_phone),
        ("Email", booking.devotee_email),
        ("Visit Date", booking.visit_date.strftime("%d %b %Y")),
        ("Time Slot", booking.slot.slot_time.strftime("%I:%M %p")),
        ("Persons", str(booking.participants)),
        ("Payment", f"{booking.payment_status} - {booking.payment_mode or 'Pending'}"),
        ("Transaction ID", booking.transaction_id or "Pending"),
        ("Total Amount", f"Rs. {booking.total_amount:.2f}"),
    ]

    pdf.setFont("Helvetica", 11)
    for label, value in details:
        pdf.setFillColor(colors.HexColor("#6f675d"))
        pdf.drawString(22 * mm, y, label)
        pdf.setFillColor(colors.black)
        pdf.drawString(70 * mm, y, value)
        y -= 8 * mm

    if booking.notes:
        y -= 4 * mm
        pdf.setFont("Helvetica-Bold", 11)
        pdf.setFillColor(colors.HexColor("#6f675d"))
        pdf.drawString(22 * mm, y, "Booking Notes")
        y -= 7 * mm
        pdf.setFont("Helvetica", 10)
        pdf.setFillColor(colors.black)
        for line in booking.notes.splitlines():
            if y < 36 * mm:
                pdf.showPage()
                y = height - 24 * mm
                pdf.setFont("Helvetica", 10)
            pdf.drawString(22 * mm, y, line[:105])
            y -= 6 * mm

    pdf.setStrokeColor(colors.HexColor("#e3d6c6"))
    pdf.line(22 * mm, y - 4 * mm, width - 22 * mm, y - 4 * mm)
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(colors.HexColor("#6f675d"))
    pdf.drawString(22 * mm, y - 14 * mm, "Please carry this receipt or booking ID during temple visit.")
    pdf.drawString(22 * mm, y - 20 * mm, "This is a computer-generated receipt from the temple booking system.")

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
