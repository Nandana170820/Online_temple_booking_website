# Mangad Devi Temple Online Booking System

A complete Flask-based booking website for Mangad Devi Temple, Kunnamkulam, styled as a temple online services portal. It supports service listings, temple history, devotee registration/login, darshan and vazhipadu booking, payment-mode selection, booking confirmation IDs, slot capacity validation, PDF receipts, a devotee dashboard, and an admin dashboard.

## Features

- Python Flask backend
- SQLite database with automatic setup
- Devotee registration and login
- Temple history page for Mangad Devi Temple, Kunnamkulam
- Public portal with notices, timings, online service shortcuts, and gallery
- Book darshan and vazhipadu services
- Slot capacity checking
- Payment record flow with UPI, card, net banking, wallet, and counter payment options
- Razorpay Checkout support when gateway keys are configured
- Booking confirmation receipt with PDF download
- Devotee dashboard
- Admin dashboard with booking and revenue summary
- Responsive frontend using HTML, CSS, and a small JavaScript helper

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
flask --app app run --debug
```

Open `http://127.0.0.1:5000`.

## Sample admin login

```text
Email: admin@temple.local
Password: admin123
```

## Project structure

```text
app/
  __init__.py          Flask app, models, routes, seed data
  templates/           HTML pages
  static/css/          Styling
  static/js/           Date helper
  static/images/       Temple image
app.py                 Local entry point
wsgi.py                Production entry point
requirements.txt       Python dependencies
Procfile               Render/Railway/Heroku style process file
```

## Hosting

You can host this on Render, Railway, PythonAnywhere, or any VPS.

The public website does not require a secret key for visitors. `SECRET_KEY` is only a private Flask server
environment variable used to protect sessions. Anyone can open the deployed URL, view the public pages, register,
and book available darshan or vazhipadu slots.

### Render free demo settings

The included `render.yaml` creates a free Python web service for demo/recruiter review.

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn wsgi:app --bind 0.0.0.0:$PORT`
- Plan: `free`
- Optional payment variables: `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`

SQLite is fine for local review and free demo hosting. Demo data can reset on redeploys or service restarts. For
production, use PostgreSQL and set `DATABASE_URL` to your database connection string.

See `DEPLOYMENT.md` for Render and Razorpay setup notes.

## Project highlights

Project highlights:

- It is built from scratch in Python.
- The database initializes automatically.
- The UI is not only a form; it has a full visitor journey.
- There is basic authentication and admin reporting.
- The deployment entry point is included.
