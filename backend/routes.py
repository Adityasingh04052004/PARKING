from flask import Blueprint, request, jsonify, render_template, current_app, send_from_directory
from functools import wraps
from datetime import datetime, timedelta
import jwt
import re
from celery.result import AsyncResult
from app_factory import db, cache
from backend.models import User, ParkingLot, ParkingSpot, Reservation

bp = Blueprint("app_routes", __name__)

# --------------------
# JWT HELPERS
# --------------------
def create_token(user):
    payload = {
        "user_id": user.id,
        "role": user.role,
        "exp": datetime.utcnow() + timedelta(hours=6)
    }
    token = jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")
    # PyJWT>=2 returns str, older returns bytes
    return token if isinstance(token, str) else token.decode("utf-8")

def is_valid_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(pattern, email) is not None

def token_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        token = auth.split(" ")[1] if " " in auth else None

        if not token:
            return jsonify({"error": "Token missing"}), 401

        try:
            data = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
            current_user = User.query.get(data["user_id"])
            if not current_user:
                return jsonify({"error": "Invalid user"}), 401
        except Exception:
            return jsonify({"error": "Invalid or expired token"}), 401

        return f(current_user, *args, **kwargs)
    return decorator


def admin_required(f):
    @wraps(f)
    def wrapper(current_user, *args, **kwargs):
        if current_user.role != "admin":
            return jsonify({"error": "Admin required"}), 403
        return f(current_user, *args, **kwargs)
    return wrapper


# --------------------
# AUTO-CREATE ADMIN
# --------------------
admin_initialized = False

@bp.before_app_request
def create_admin():
    """
    Ensure DB tables exist and a default admin user is present.
    """
    global admin_initialized
    if admin_initialized:
        return

    db.create_all()

    if not User.query.filter_by(role="admin").first():
        admin = User(username="admin", email="admin@parking.com", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()

    admin_initialized = True


# ----------------------------------------------------------
# AUTH ROUTES
# ----------------------------------------------------------
@bp.route("/api/register", methods=["POST"])
def register():
    data = request.json or {}

    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "")

    # ✅ Basic missing fields check
    if not username or not email or not password:
        return jsonify({"error": "Missing fields"}), 400

    # ✅ Email validation
    if not is_valid_email(email):
        return jsonify({"error": "Invalid email format"}), 400

    # ✅ password min length (optional but recommended)
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    # ✅ Check duplicates
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username exists"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email exists"}), 400

    # ✅ Create user
    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "Registered"}), 201


@bp.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    user = User.query.filter_by(username=data.get("username")).first()
    if not user or not user.check_password(data.get("password")):
        return jsonify({"error": "Invalid credentials"}), 401

    return jsonify({"token": create_token(user), "role": user.role})


# ----------------------------------------------------------
# ADMIN DASHBOARD ROUTES
# ----------------------------------------------------------
@bp.route("/api/admin/dashboard_summary", methods=["GET"])
@token_required
@admin_required
def admin_dashboard_summary(current_user):
    return jsonify({
        "total_lots": ParkingLot.query.count(),
        "total_spots": ParkingSpot.query.count(),
        "available_spots": ParkingSpot.query.filter_by(status="A").count(),
        "occupied_spots": ParkingSpot.query.filter_by(status="O").count(),
        "registered_users": User.query.filter_by(role="user").count()
    })


@bp.route("/api/admin/spots", methods=["GET"])
@token_required
@admin_required
def admin_spots(current_user):
    spots = ParkingSpot.query.all()
    return jsonify([
        {
            "id": s.id,
            "lot_name": s.lot.prime_location_name,
            "status": s.status
        } for s in spots
    ])


@bp.route("/api/admin/spot-details/<int:spot_id>", methods=["GET"])
@token_required
@admin_required
def spot_details(current_user, spot_id):
    spot = ParkingSpot.query.get_or_404(spot_id)

    # If spot marked available or no active reservation => treat as free
    active_res = Reservation.query.filter_by(
        spot_id=spot.id,
        leaving_timestamp=None
    ).order_by(Reservation.parking_timestamp.desc()).first()

    if not active_res or spot.status == "A":
        return jsonify({"status": "Available"})

    user = active_res.user
    duration_hours = round(
        (datetime.utcnow() - active_res.parking_timestamp).total_seconds() / 3600, 2
    )

    return jsonify({
        "status": "Occupied",
        "user": {
            "username": user.username,
            "email": user.email
        },
        "reservation": {
            "start_time": active_res.parking_timestamp.isoformat(),
            "duration_hours": duration_hours
        }
    })


@bp.route("/api/admin/users", methods=["GET"])
@token_required
@admin_required
def admin_users(current_user):
    users = User.query.filter_by(role="user").all()
    return jsonify([
        {"id": u.id, "username": u.username, "email": u.email}
        for u in users
    ])


# ----------------------------------------------------------
# ADMIN LOT CRUD
# ----------------------------------------------------------
@bp.route("/api/admin/lots", methods=["GET"])
@token_required
@admin_required
def get_lots(current_user):
    lots = ParkingLot.query.all()
    return jsonify([
        {
            "id": l.id,
            "prime_location_name": l.prime_location_name,
            "price_per_hour": float(l.price_per_hour),
            "address": l.address,
            "pincode": l.pincode,
            "number_of_spots": l.number_of_spots
        } for l in lots
    ])


@bp.route("/api/admin/create_lot", methods=["POST"])
@token_required
@admin_required
def create_lot(current_user):
    data = request.json or {}
    required = ["prime_location_name", "price_per_hour", "address", "pincode", "number_of_spots"]
    if any(k not in data or data[k] in ("", None) for k in required):
        return jsonify({"error": "All fields are required"}), 400

    try:
        price = float(data["price_per_hour"])
        spots_count = int(data["number_of_spots"])
    except (TypeError, ValueError):
        return jsonify({"error": "Price and spots must be numeric"}), 400

    if spots_count <= 0:
        return jsonify({"error": "Number of spots must be > 0"}), 400

    lot = ParkingLot(
        prime_location_name=data["prime_location_name"],
        price_per_hour=price,
        address=data["address"],
        pincode=data["pincode"],
        number_of_spots=spots_count
    )
    db.session.add(lot)
    db.session.commit()  # so lot.id is available

    # create spots
    for _ in range(lot.number_of_spots):
        db.session.add(ParkingSpot(lot_id=lot.id, status="A"))
    db.session.commit()

    return jsonify({"message": "Lot created"}), 201


@bp.route("/api/admin/update_lot/<int:lot_id>", methods=["PUT"])
@token_required
@admin_required
def update_lot(current_user, lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)
    data = request.json or {}

    # Update simple fields
    lot.prime_location_name = data.get("prime_location_name", lot.prime_location_name)
    lot.address = data.get("address", lot.address)
    lot.pincode = data.get("pincode", lot.pincode)

    if "price_per_hour" in data and data["price_per_hour"] not in ("", None):
        try:
            lot.price_per_hour = float(data["price_per_hour"])
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid price"}), 400

    # Handle change in total number of spots
    if "number_of_spots" in data and data["number_of_spots"] not in ("", None):
        try:
            new_count = int(data["number_of_spots"])
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid spots value"}), 400

        if new_count <= 0:
            return jsonify({"error": "Number of spots must be > 0"}), 400

        current_spots = ParkingSpot.query.filter_by(lot_id=lot.id).all()
        current_count = len(current_spots)

        if new_count > current_count:
            # add extra spots
            for _ in range(new_count - current_count):
                db.session.add(ParkingSpot(lot_id=lot.id, status="A"))
        elif new_count < current_count:
            # only delete free spots
            removable_needed = current_count - new_count
            removable = ParkingSpot.query.filter_by(lot_id=lot.id, status="A")\
                                         .order_by(ParkingSpot.id.desc())\
                                         .limit(removable_needed).all()
            if len(removable) != removable_needed:
                return jsonify({"error": "Cannot reduce spots while some are occupied"}), 400

            for s in removable:
                db.session.delete(s)

        lot.number_of_spots = new_count

    db.session.commit()
    return jsonify({"message": "Lot updated"})


@bp.route("/api/admin/delete_lot/<int:lot_id>", methods=["DELETE"])
@token_required
@admin_required
def delete_lot(current_user, lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)

    occupied_count = ParkingSpot.query.filter_by(lot_id=lot_id, status="O").count()
    if occupied_count > 0:
        return jsonify({"error": "Cannot delete, some spots are occupied"}), 400

    ParkingSpot.query.filter_by(lot_id=lot_id).delete()
    db.session.delete(lot)
    db.session.commit()

    return jsonify({"message": "Lot deleted"})


# ----------------------------------------------------------
# USER ROUTES
# ----------------------------------------------------------
@bp.route("/api/user/lots", methods=["GET"])
@token_required
def user_lots(current_user):
    lots = ParkingLot.query.all()
    data = []
    for lot in lots:
        free = ParkingSpot.query.filter_by(lot_id=lot.id, status="A").count()
        data.append({
            "id": lot.id,
            "prime_location_name": lot.prime_location_name,
            "price_per_hour": float(lot.price_per_hour),
            "address": lot.address,
            "pincode": lot.pincode,
            "total_spots": lot.number_of_spots,
            "available_spots": free
        })
    return jsonify(data)


@bp.route("/api/user/book/<int:lot_id>", methods=["POST"])
@token_required
def book_spot(current_user, lot_id):
    spot = ParkingSpot.query.filter_by(lot_id=lot_id, status="A").first()
    if not spot:
        return jsonify({"error": "No free spots"}), 400

    res = Reservation(
        spot_id=spot.id,
        user_id=current_user.id,
        parking_timestamp=datetime.utcnow()
    )
    db.session.add(res)
    spot.status = "O"
    db.session.commit()

    return jsonify({"reservation_id": res.id, "spot_id": spot.id})


@bp.route("/api/user/release/<int:reservation_id>", methods=["POST"])
@token_required
def release_spot(current_user, reservation_id):
    res = Reservation.query.filter_by(
        id=reservation_id,
        user_id=current_user.id,
        leaving_timestamp=None
    ).first()

    if not res:
        return jsonify({"error": "No active booking"}), 404

    now = datetime.utcnow()
    hours = (now - res.parking_timestamp).total_seconds() / 3600.0
    cost = round(hours * float(res.spot.lot.price_per_hour), 2)

    res.leaving_timestamp = now
    res.total_cost = cost
    res.spot.status = "A"
    db.session.commit()

    return jsonify({"message": "Released", "total_cost": cost})


@bp.route("/api/user/history", methods=["GET"])
@token_required
def history(current_user):
    reservations = Reservation.query.filter_by(user_id=current_user.id).all()
    return jsonify([
        {
            "reservation_id": r.id,
            "spot_id": r.spot_id,
            "lot_name": r.spot.lot.prime_location_name,
            "parking_timestamp": r.parking_timestamp.isoformat() if r.parking_timestamp else None,
            "leaving_timestamp": r.leaving_timestamp.isoformat() if r.leaving_timestamp else None,
            "total_cost": float(r.total_cost) if r.total_cost is not None else None
        }
        for r in reservations
    ])


@bp.route("/api/user/dashboard_summary", methods=["GET"])
@token_required
def user_summary(current_user):
    total = Reservation.query.filter_by(user_id=current_user.id).count()
    active = Reservation.query.filter_by(user_id=current_user.id, leaving_timestamp=None).count()
    return jsonify({
        "total_bookings": total,
        "active_reservations": active,
        "completed_reservations": total - active
    })


# --------------------
# EXPORT CSV
# --------------------
@bp.route("/api/user/export_csv", methods=["POST"])
@token_required
def export_csv(current_user):
    from tasks import export_user_history_csv
    task = export_user_history_csv.delay(current_user.id)
    return jsonify({"task_id": task.id, "status": "started"})


@bp.route("/api/user/export_status/<task_id>", methods=["GET"])
@token_required
def export_status(current_user, task_id):
    result = AsyncResult(task_id)
    if result.state == "SUCCESS":
        return jsonify({"status": "completed", "filename": result.result["filename"]})
    return jsonify({"status": result.state})


@bp.route("/api/user/download_csv/<task_id>", methods=["GET"])
@token_required
def download_csv(current_user, task_id):
    result = AsyncResult(task_id)
    if result.state != "SUCCESS":
        return jsonify({"status": result.state})

    return jsonify({
        "status": "ready",
        "download": f"/exports/{result.result['filename']}"
    })


@bp.route("/exports/<filename>")
def serve_csv(filename):
    return send_from_directory("exports", filename, as_attachment=True)


# --------------------
# FRONTEND RENDERS
# --------------------
@bp.route("/")
def login_page():
    return render_template("login.html")

@bp.route("/register")
def register_page():
    return render_template("register.html")

@bp.route("/user")
def user_dashboard_page():
    return render_template("user_dashboard.html")

@bp.route("/admin")
def admin_dashboard_page():
    return render_template("admin_dashboard.html")

@bp.route("/admin/lots")
def admin_lots_page():
    return render_template("admin_lots.html")

@bp.route("/user/history")
def user_history_page():
    return render_template("user_history.html")

@bp.route("/user/book")
def user_book_page():
    return render_template("user_book.html")

@bp.route("/user/release")
def user_release_page():
    return render_template("user_release.html")

