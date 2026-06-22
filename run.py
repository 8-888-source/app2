import json
import os
import sqlite3
from datetime import date
import urllib.error
import urllib.parse
import urllib.request

from flask import Flask, Response, redirect, render_template, request, session, url_for
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

from config.config import Config
from web.db import db


app = Flask(__name__)

app.config.from_object(Config)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

os.makedirs(app.instance_path, exist_ok=True)
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

db.init_app(app)


class Users(db.Model):

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(140), nullable=False)

    email = db.Column(db.String(120), unique=True, nullable=False)

    password = db.Column("pasword", db.String(160), nullable=False)

    premium = db.Column(db.Boolean, nullable=False, default=False)


def _ensure_user_schema():
    db_path = os.path.join(app.instance_path, "notes.db")

    if not os.path.exists(db_path):
        return

    with sqlite3.connect(db_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}

        if "premium" not in columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN premium INTEGER NOT NULL DEFAULT 0"
            )
            connection.commit()


def _normalize_email(email):
    return email.strip().lower()


def _stripe_request(method, path, payload=None):
    if not Config.STRIPE_SECRET_KEY:
        raise RuntimeError("STRIPE_SECRET_KEY не задан. Добавь его в .env или переменные окружения.")

    url = f"https://api.stripe.com/v1{path}"
    headers = {
        "Authorization": f"Bearer {Config.STRIPE_SECRET_KEY}",
    }
    data = None

    if payload is not None:
        data = urllib.parse.urlencode(payload).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    request_obj = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(request_obj, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(detail or f"Stripe API error ({exc.code})")


def _create_premium_checkout(email):
    success_url = f"{url_for('premium_success', _external=True)}?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = url_for("premium_cancel", _external=True)

    payload = [
        ("mode", "payment"),
        ("customer_email", email),
        ("client_reference_id", email),
        ("metadata[email]", email),
        ("success_url", success_url),
        ("cancel_url", cancel_url),
        ("line_items[0][quantity]", "1"),
        ("line_items[0][price_data][currency]", Config.STRIPE_CURRENCY),
        ("line_items[0][price_data][unit_amount]", str(Config.PREMIUM_PRICE_CENTS)),
        ("line_items[0][price_data][product_data][name]", Config.PREMIUM_PRODUCT_NAME),
        (
            "line_items[0][price_data][product_data][description]",
            Config.PREMIUM_PRODUCT_DESCRIPTION,
        ),
    ]

    return _stripe_request("POST", "/checkout/sessions", payload)


def _fetch_checkout_session(session_id):
    return _stripe_request("GET", f"/checkout/sessions/{session_id}")


def _activate_premium(email):
    user = Users.query.filter(func.lower(Users.email) == email.lower()).first()

    if not user:
        return False

    user.premium = True
    db.session.commit()
    return True


@app.route("/robots.txt")
def robots_txt():
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /login",
        "Disallow: /register",
        "Disallow: /notes",
        "Disallow: /profile",
        "Disallow: /pasword",
        f"Sitemap: {url_for('sitemap_xml', _external=True)}",
    ]

    return Response("\n".join(lines) + "\n", mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    today = date.today().isoformat()
    pages = [
        {
            "loc": url_for("main", _external=True),
            "lastmod": today,
            "changefreq": "daily",
            "priority": "1.0",
        },
        {
            "loc": url_for("category", _external=True),
            "lastmod": today,
            "changefreq": "weekly",
            "priority": "0.8",
        },
        {
            "loc": url_for("videos", _external=True),
            "lastmod": today,
            "changefreq": "weekly",
            "priority": "0.8",
        },
        {
            "loc": url_for("video", _external=True),
            "lastmod": today,
            "changefreq": "weekly",
            "priority": "0.7",
        },
        {
            "loc": url_for("premium", _external=True),
            "lastmod": today,
            "changefreq": "monthly",
            "priority": "0.6",
        },
    ]

    return Response(render_template("sitemap.xml", pages=pages), mimetype="application/xml")

with app.app_context():
    db.create_all()
    _ensure_user_schema()


@app.route("/")
def main():
    return render_template('index.html')

@app.route("/profile")
def profile():
    return render_template('index.html')

@app.route("/notes")
def notes():
    return render_template('index.html')



@app.route("/login" ,methods=['POST', 'GET'])
def login():

    if request.method == "POST":

        email = _normalize_email(request.form["email"])
        password = request.form["password"]

        user = Users.query.filter(func.lower(Users.email) == email).first()

        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            session["username"] = user.username
            session["email"] = user.email
            return redirect("/notes")

        return "❌ Неверный email или пароль"


    return render_template('login.html')



@app.route("/register" ,methods=['POST', 'GET'])
def register():
    if request.method == "POST":
        username = request.form['username'].strip()
        email = _normalize_email(request.form['email'])
        password = request.form['password']
        user_exists = Users.query.filter(func.lower(Users.email) == email).first()

        if user_exists:
            return "❌ Этот email уже зарегистрирован"

        hashed_password = generate_password_hash(password)

        new_user = Users(
            username=username,
            email=email,
            password=hashed_password
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect("/login")
    return render_template('register.html')

@app.route("/pasword" ,methods=['POST', 'GET'])
def password():
    return render_template('password.html')


@app.route("/premium", methods=["GET", "POST"])
def premium():
    email = session.get("email", "")
    message = ""
    status = ""
    price_text = f"{Config.PREMIUM_PRICE_CENTS / 100:.2f} {Config.STRIPE_CURRENCY.upper()}"

    if request.method == "POST":
        email = _normalize_email(request.form.get("email", ""))

        if not email:
            status = "error"
            message = "Укажи email, чтобы привязать оплату к аккаунту."
        elif not Config.STRIPE_SECRET_KEY:
            status = "error"
            message = "Stripe не настроен. Добавь STRIPE_SECRET_KEY в .env и повтори."
        else:
            try:
                checkout_session = _create_premium_checkout(email)
                return redirect(checkout_session["url"])
            except Exception as exc:
                status = "error"
                message = f"Не удалось создать платёж: {exc}"

    return render_template(
        "categoryes/premium.html",
        email=email,
        message=message,
        status=status,
        price_text=price_text,
    )


@app.route("/premium/success")
def premium_success():
    session_id = request.args.get("session_id", "").strip()

    if not session_id:
        return render_template(
            "categoryes/premium.html",
            status="error",
            message="Не найден идентификатор платежа.",
            email="",
            price_text=f"{Config.PREMIUM_PRICE_CENTS / 100:.2f} {Config.STRIPE_CURRENCY.upper()}",
        )

    try:
        checkout_session = _fetch_checkout_session(session_id)
    except Exception as exc:
        return render_template(
            "categoryes/premium.html",
            status="error",
            message=f"Не удалось проверить оплату: {exc}",
            email="",
            price_text=f"{Config.PREMIUM_PRICE_CENTS / 100:.2f} {Config.STRIPE_CURRENCY.upper()}",
        )

    if checkout_session.get("payment_status") != "paid":
        return render_template(
            "categoryes/premium.html",
            status="error",
            message="Платёж ещё не подтверждён.",
            email="",
            price_text=f"{Config.PREMIUM_PRICE_CENTS / 100:.2f} {Config.STRIPE_CURRENCY.upper()}",
        )

    email = checkout_session.get("customer_email") or checkout_session.get("metadata", {}).get("email", "")
    activated = False

    if email:
        activated = _activate_premium(email)

    return render_template(
        "categoryes/premium.html",
        status="success",
        message="Оплата прошла успешно.",
        email=email,
        activated=activated,
        price_text=f"{Config.PREMIUM_PRICE_CENTS / 100:.2f} {Config.STRIPE_CURRENCY.upper()}",
    )


@app.route("/premium/cancel")
def premium_cancel():
    return render_template(
        "categoryes/premium.html",
        status="cancel",
        message="Оплата отменена.",
        email="",
        price_text=f"{Config.PREMIUM_PRICE_CENTS / 100:.2f} {Config.STRIPE_CURRENCY.upper()}",
    )

@app.route("/videos")
def videos():
    return render_template('videos.html')

@app.route("/category")
def category():
    return render_template('category.html')

@app.route("/video")
def video():
    return render_template('video.html')






if __name__ == '__main__':
    app.run(debug=True)
