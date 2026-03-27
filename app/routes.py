from functools import wraps

from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
    current_app,
)
from flask_mail import Message
from datetime import datetime, timedelta
import random
import string

from . import db, mail
from sqlalchemy import or_
from .models import ActivityHistory, StoredItem, User, ResetToken


main_bp = Blueprint("main", __name__)


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(**kwargs):
        if "user_id" not in session:
            flash("Please log in to see this page.")
            return redirect(url_for("main.login"))
        return view_func(**kwargs)

    return wrapped_view


@main_bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")
    g.user = User.query.get(user_id) if user_id else None


def log_activity(user: User, description: str) -> None:
    if not user:
        return
    activity = ActivityHistory(
        user_id=user.id, activity_description=description)
    db.session.add(activity)


def generate_otp():
    return ''.join(random.choices(string.digits, k=6))


@main_bp.route("/")
def index():
    if g.user:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("main.login"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    items = StoredItem.query.filter_by(user_id=g.user.id).all()
    activities = (
        ActivityHistory.query.filter_by(user_id=g.user.id)
        .order_by(ActivityHistory.timestamp.desc())
        .limit(10)
        .all()
    )
    return render_template(
        "dashboard.html",
        user=g.user,
        items=items,
        activities=activities,
    )


@main_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm", "").strip()

        error = None

        if not username:
            error = "Username is required."
        elif not email:
            error = "Email is required."
        elif not password:
            error = "Password is required."
        elif password != confirm:
            error = "Passwords do not match."
        elif User.query.filter_by(username=username).first():
            error = "Username is already taken."
        elif User.query.filter_by(email=email).first():
            error = "Email is already used."

        if error is None:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("Registration successful. Please log in.")
            return redirect(url_for("main.login"))

        flash(error)

    return render_template("register.html")


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        error = None
        user = User.query.filter_by(username=username).first()

        if user is None:
            error = "Incorrect username."
        elif not user.check_password(password):
            error = "Incorrect password."

        if error is None:
            session.clear()
            session["user_id"] = user.id
            log_activity(user, "User logged in")
            db.session.commit()
            flash("You are now logged in.")
            return redirect(url_for("main.dashboard"))

        flash(error)

    return render_template("login.html")


@main_bp.route("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("main.login"))


@main_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        error = None

        if not identifier:
            error = "Email or username is required."
        else:
            user = User.query.filter(
                or_(User.email == identifier, User.username == identifier)
            ).first()
            if user:
                # Generate OTP
                otp = generate_otp()
                expires_at = datetime.utcnow() + timedelta(minutes=10)

                # Delete old tokens
                ResetToken.query.filter_by(user_id=user.id).delete()

                # Create new token
                token = ResetToken(user_id=user.id, otp=otp,
                                   expires_at=expires_at)
                db.session.add(token)
                db.session.commit()

                # Send email
                msg = Message(
                    subject="Password Reset OTP",
                    recipients=[user.email],
                    body=f"Your password reset OTP is: {otp}\nIt expires in 10 minutes.",
                    sender=current_app.config['MAIL_USERNAME']
                )
                try:
                    mail.send(msg)
                    flash("6-digit OTP sent to your email. Check inbox/spam.")
                except Exception as e:
                    flash("Email sending failed. Please try again.")
                    db.session.rollback()
            else:
                error = "No account found with that email or username."

        if error:
            flash(error)

    return render_template("forgot_password.html")


@main_bp.route("/reset-password/<int:token_id>", methods=["GET", "POST"])
def reset_password(token_id):
    token = ResetToken.query.filter_by(id=token_id).filter(
        ResetToken.expires_at > datetime.utcnow()).first_or_404()

    if request.method == "POST":
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm", "").strip()
        error = None

        if not password:
            error = "Password is required."
        elif password != confirm:
            error = "Passwords do not match."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."

        if error is None:
            token.user.set_password(password)
            db.session.delete(token)
            db.session.commit()
            flash("Password reset successful. Please log in.")
            log_activity(token.user, "Password reset via OTP")
            return redirect(url_for("main.login"))

        flash(error)

    return render_template("reset_password.html", token_id=token_id, username=token.user.username)


@main_bp.route("/items/new", methods=["GET", "POST"])
@login_required
def create_item():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()

        if not title or not content:
            flash("Title and content are required.")
            return render_template("item_form.html", action="Create")

        item = StoredItem(title=title, content=content, user_id=g.user.id)
        db.session.add(item)
        log_activity(g.user, f"Created item: '{title}'")
        db.session.commit()
        flash("Item created.")
        return redirect(url_for("main.dashboard"))

    return render_template("item_form.html", action="Create")


@main_bp.route("/items/<int:item_id>")
@login_required
def view_item(item_id):
    item = StoredItem.query.filter_by(
        id=item_id, user_id=g.user.id).first_or_404()
    return render_template("item_detail.html", item=item)


@main_bp.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def update_item(item_id):
    item = StoredItem.query.filter_by(
        id=item_id, user_id=g.user.id).first_or_404()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()

        if not title or not content:
            flash("Title and content are required.")
            return render_template("item_form.html", action="Update", item=item)

        old_title = item.title
        item.title = title
        item.content = content
        log_activity(g.user, f"Updated item: '{old_title}' to '{title}'")
        db.session.commit()
        flash("Item updated.")
        return redirect(url_for("main.view_item", item_id=item.id))

    return render_template("item_form.html", action="Update", item=item)


@main_bp.route("/items/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_item(item_id):
    item = StoredItem.query.filter_by(
        id=item_id, user_id=g.user.id).first_or_404()
    title = item.title
    db.session.delete(item)
    log_activity(g.user, f"Deleted item: '{title}'")
    db.session.commit()
    flash("Item deleted.")
    return redirect(url_for("main.dashboard"))
