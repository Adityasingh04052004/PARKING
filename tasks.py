# tasks.py

from celery_app import celery
from backend.models import User, Reservation
from datetime import datetime, timedelta
from mail_helper import send_email
import csv
import os
from sqlalchemy import func


# ======================
# 1️⃣ DAILY REMINDER JOB
# ======================
@celery.task
def send_daily_reminders():
    """
    Send email reminder to users who have no parking in the last 7 days.
    """

    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    users = User.query.all()
    inactive_users = []

    for user in users:

        # Find most recent completed reservation
        last_reservation = Reservation.query.filter_by(user_id=user.id)\
            .order_by(Reservation.leaving_timestamp.desc())\
            .first()

        # If user never booked -> reminder
        if last_reservation is None:
            inactive_users.append(user)
            continue

        # If last booking too old -> reminder
        if last_reservation.leaving_timestamp is None or \
           last_reservation.leaving_timestamp < seven_days_ago:
            inactive_users.append(user)

    count = 0
    for user in inactive_users:
        if user.email:
            subject = "Reminder: Need to Park Today?"
            body = f"""
Hi {user.username},

We haven't seen you parking lately 🚗
Book a parking spot anytime easily from your Park With Ease dashboard!
"""
            send_email(user.email, subject, body)
            count += 1

    return f"Daily reminders sent to {count} inactive users!"

# ======================
# 2️⃣ CSV EXPORT JOB (Already in your project — improved version)
# ======================
@celery.task
def export_user_history_csv(user_id):
    """
    Export user's reservation history to CSV and notify via email.
    """

    from backend.models import User

    folder = "exports"
    os.makedirs(folder, exist_ok=True)

    filename = f"user_{user_id}_history.csv"
    path = os.path.join(folder, filename)

    reservations = Reservation.query.filter_by(user_id=user_id).all()

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Lot", "Spot", "Start", "End", "Cost"])
        for r in reservations:
            writer.writerow([
                r.id,
                r.spot.lot.prime_location_name,
                r.spot_id,
                r.parking_timestamp,
                r.leaving_timestamp,
                r.total_cost,
            ])

    # Notify user when export is ready
    user = User.query.get(user_id)
    if user and user.email:
        download_url = f"http://localhost:5000/download/{filename}"
        subject = "Your Parking History Export is Ready!"
        message = f"""
Hi {user.username},

Your CSV export is ready 🎉
You can download it using the link below:

{download_url}
"""

        send_email(user.email, subject, message)

    return {"filename": filename, "path": path}
