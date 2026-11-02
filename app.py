
import os
import hashlib
import secrets
import smtplib
import ssl

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)

from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db_connection, init_db


# APP CONFIGURATION


app = Flask(__name__)

app.secret_key = os.environ.get(
    "STREET_BITES_SECRET_KEY",
    "street-bites-change-this-secret-key"
)

# Allow templates to display the current year.
app.jinja_env.globals["now"] = datetime.now

ADMIN_EMAIL = os.environ.get(
    "STREET_BITES_ADMIN_EMAIL",
    "admin@gmail.com"
).strip().lower()

BUSINESS_PHONE = "+27 60 301 7938"
BUSINESS_WHATSAPP = "27603017938"
ORDER_STATUSES = (
    "Pending",
    "Approved",
    "Preparing",
    "Ready",
    "Out for Delivery",
    "Completed",
    "Cancelled",
)
DELIVERY_AREAS = (
    "Amanzimtoti",
    "KwaMakhutha",
    "Adams Mission",
    "Illovo",
    "Umlazi",
    "Isipingo",
    "Umgababa",
    "Umbumbulu",
)


@app.context_processor
def inject_admin_email():
    return {
        "ADMIN_EMAIL": ADMIN_EMAIL,
        "BUSINESS_PHONE": BUSINESS_PHONE,
        "BUSINESS_WHATSAPP": BUSINESS_WHATSAPP,
        "DELIVERY_AREAS": DELIVERY_AREAS,
        "mail_configured": bool(MAIL_USERNAME and MAIL_APP_PASSWORD),
    }



# DATABASE INITIALIZATION


init_db()


def init_password_reset_table():
    connection = get_db_connection()

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        connection.commit()

    finally:
        connection.close()


init_password_reset_table()



# EMAIL CONFIGURATION


MAIL_USERNAME = os.environ.get("MAIL_USERNAME", ADMIN_EMAIL).strip()

MAIL_APP_PASSWORD = os.environ.get(
    "MAIL_APP_PASSWORD", ""
).replace(" ", "")

MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com").strip()
MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
MAIL_TIMEOUT_SECONDS = 20

RESET_TOKEN_MAX_AGE_MINUTES = 30
RESET_BASE_URL = os.environ.get(
    "STREET_BITES_BASE_URL",
    "",
).strip().rstrip("/")


def send_reset_email(recipient, reset_url):
    """Send a password reset email using an authenticated STARTTLS server."""

    if not MAIL_USERNAME or not MAIL_APP_PASSWORD:
        raise RuntimeError(
            "Email configuration is missing. "
            "Set MAIL_APP_PASSWORD and, if needed, MAIL_USERNAME."
        )
    if not MAIL_SERVER or not 1 <= MAIL_PORT <= 65535:
        raise RuntimeError("The configured mail server or port is invalid.")

    message = EmailMessage()

    message["Subject"] = "Reset your Street Bites password"
    message["From"] = f"Street Bites <{MAIL_USERNAME}>"
    message["To"] = recipient

    message.set_content(
        "We received a request to reset your Street Bites password.\n\n"
        f"Use this link within {RESET_TOKEN_MAX_AGE_MINUTES} minutes:\n"
        f"{reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )

    with smtplib.SMTP(
        MAIL_SERVER,
        MAIL_PORT,
        timeout=MAIL_TIMEOUT_SECONDS,
    ) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(MAIL_USERNAME, MAIL_APP_PASSWORD)
        refused_recipients = smtp.send_message(message)
        if refused_recipients:
            raise smtplib.SMTPRecipientsRefused(refused_recipients)



# PRODUCTS


PRODUCTS = {
    "1": {"name": "Classic Burger", "price": 55.00},
    "2": {"name": "Cheese Burger", "price": 65.00},
    "3": {"name": "Double Beef Burger", "price": 85.00},
    "4": {"name": "Crispy Chicken", "price": 60.00},
    "5": {"name": "Chicken & Chips", "price": 75.00},
    "6": {"name": "Chicken Wrap", "price": 50.00},
    "7": {"name": "Regular Chips", "price": 25.00},
    "8": {"name": "Soft Drink", "price": 18.00},
    "9": {"name": "Loaded Chips", "price": 45.00},
}


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return render_template("index.html")


# SIGNUP


@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("Please fill in all fields.")
            return render_template("signup.html")

        if len(name) > 100 or len(email) > 254:
            flash("Your name or email address is too long.")
            return render_template("signup.html")

        if len(password) < 8:
            flash("Your password must be at least 8 characters.")
            return render_template("signup.html")

        connection = get_db_connection()

        try:
            connection.execute(
                """
                INSERT INTO users (name, email, password_hash)
                VALUES (?, ?, ?)
                """,
                (name, email, generate_password_hash(password)),
            )

            connection.commit()

            flash("Account created successfully. You can now log in!")
            return redirect(url_for("login"))

        except Exception as error:
            if "UNIQUE constraint failed" in str(error):
                flash("That email address is already registered.")
            else:
                app.logger.exception("Signup failed.")
                flash("Something went wrong. Please try again.")

        finally:
            connection.close()

    return render_template("signup.html")



# LOGIN


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        connection = get_db_connection()

        try:
            user = connection.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,),
            ).fetchone()

        finally:
            connection.close()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"].lower()

            flash("Welcome back!")
            return redirect(url_for("home"))

        flash("Invalid email or password.")

    return render_template("login.html")



# LOGOUT


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("home"))


# FIND US


@app.route("/where-to-find-us")
def where_to_find_us():
    return render_template("where_to_find_us.html")



# CONTACT US


@app.route("/contact-us", methods=["GET", "POST"])
def contact_us():

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()

        if not all([name, email, subject, message]):
            flash("Please complete all fields.")
            return render_template("contact_us.html")

        if (
            len(name) > 100
            or len(email) > 254
            or len(subject) > 150
            or len(message) > 3000
        ):
            flash("One or more fields exceed the allowed length.")
            return render_template("contact_us.html")

        flash("Thanks for contacting Street Bites! Your form was submitted.")
        return redirect(url_for("contact_us"))

    return render_template("contact_us.html")


# FORGOT PASSWORD


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        generic_message = (
            "If an account exists for that email, "
            "a password-reset link will be sent."
        )

        if not MAIL_USERNAME or not MAIL_APP_PASSWORD:
            app.logger.error(
                "Password-reset email is unavailable because mail credentials "
                "are not configured."
            )
            flash(
                "Password reset emails are temporarily unavailable. "
                "Please contact Street Bites support."
            )
            return redirect(url_for("forgot_password"))

        if not email or len(email) > 254:
            flash(generic_message)
            return redirect(url_for("forgot_password"))

        connection = get_db_connection()

        try:
            user = connection.execute(
                "SELECT id, email FROM users WHERE email = ?",
                (email,),
            ).fetchone()

            if user:
                raw_token = secrets.token_urlsafe(32)

                token_hash = hashlib.sha256(
                    raw_token.encode("utf-8")
                ).hexdigest()

                expires_at = (
                    datetime.now(timezone.utc)
                    + timedelta(minutes=RESET_TOKEN_MAX_AGE_MINUTES)
                ).isoformat()

                connection.execute(
                    """
                    DELETE FROM password_reset_tokens
                    WHERE user_id = ? AND used_at IS NULL
                    """,
                    (user["id"],),
                )

                connection.execute(
                    """
                    INSERT INTO password_reset_tokens
                    (user_id, token_hash, expires_at)
                    VALUES (?, ?, ?)
                    """,
                    (user["id"], token_hash, expires_at),
                )

                connection.commit()

                reset_path = url_for("reset_password", token=raw_token)
                reset_url = (
                    f"{RESET_BASE_URL}{reset_path}"
                    if RESET_BASE_URL
                    else url_for(
                        "reset_password",
                        token=raw_token,
                        _external=True,
                    )
                )

                try:
                    send_reset_email(user["email"], reset_url)

                except (RuntimeError, OSError, smtplib.SMTPException):
                    connection.execute(
                        """
                        DELETE FROM password_reset_tokens
                        WHERE token_hash = ?
                        """,
                        (token_hash,),
                    )

                    connection.commit()

                    app.logger.exception(
                        "Could not send password-reset email."
                    )

            flash(generic_message)

        except Exception:
            connection.rollback()
            app.logger.exception("Password-reset request failed.")
            flash(generic_message)

        finally:
            connection.close()

        return redirect(url_for("forgot_password"))

    return render_template("forgot_password.html")


# RESET PASSWORD


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):

    token_hash = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

    connection = get_db_connection()

    try:
        reset_record = connection.execute(
            """
            SELECT id, user_id, expires_at, used_at
            FROM password_reset_tokens
            WHERE token_hash = ?
            """,
            (token_hash,),
        ).fetchone()

        if reset_record is None or reset_record["used_at"] is not None:
            flash("This reset link is invalid or has already been used.")
            return redirect(url_for("forgot_password"))

        expiry = datetime.fromisoformat(reset_record["expires_at"])

        if datetime.now(timezone.utc) >= expiry:
            connection.execute(
                "DELETE FROM password_reset_tokens WHERE id = ?",
                (reset_record["id"],),
            )

            connection.commit()

            flash("This reset link has expired. Please request a new one.")
            return redirect(url_for("forgot_password"))

        if request.method == "POST":
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")

            if len(password) < 8:
                flash("Your password must be at least 8 characters.")
                return render_template("reset_password.html")

            if password != confirm_password:
                flash("The passwords do not match.")
                return render_template("reset_password.html")

            connection.execute(
                """
                UPDATE users
                SET password_hash = ?
                WHERE id = ?
                """,
                (
                    generate_password_hash(password),
                    reset_record["user_id"],
                ),
            )

            connection.execute(
                """
                UPDATE password_reset_tokens
                SET used_at = ?
                WHERE id = ?
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    reset_record["id"],
                ),
            )

            connection.execute(
                """
                DELETE FROM password_reset_tokens
                WHERE user_id = ? AND id != ?
                """,
                (reset_record["user_id"], reset_record["id"]),
            )

            connection.commit()

            flash("Your password has been reset. Please log in.")
            return redirect(url_for("login"))

        return render_template("reset_password.html")

    except Exception:
        connection.rollback()
        app.logger.exception("Password-reset operation failed.")
        flash("Something went wrong. Please request a new reset link.")
        return redirect(url_for("forgot_password"))

    finally:
        connection.close()


# MENU


@app.route("/menu")
def menu():
    return render_template("menu.html")



# CART HELPERS


def build_cart():

    cart_items = []
    subtotal = 0.0
    cart_data = session.get("cart", {})

    if not isinstance(cart_data, dict):
        return [], 0.0

    for product_id, quantity in cart_data.items():
        product = PRODUCTS.get(product_id)

        if (
            product
            and isinstance(quantity, int)
            and not isinstance(quantity, bool)
            and 1 <= quantity <= 99
        ):
            item_total = round(product["price"] * quantity, 2)

            cart_items.append({
                "id": product_id,
                "name": product["name"],
                "price": product["price"],
                "quantity": quantity,
                "total": item_total,
            })

            subtotal += item_total

    return cart_items, round(subtotal, 2)


# VIEW CART


@app.route("/cart")
def cart():
    cart_items, subtotal = build_cart()

    return render_template(
        "cart.html",
        cart_items=cart_items,
        subtotal=subtotal,
    )


# ADD TO CART


@app.route("/add-to-cart/<product_id>", methods=["POST"])
def add_to_cart(product_id):

    if product_id not in PRODUCTS:
        flash("That product could not be found.")
        return redirect(url_for("menu"))

    cart_data = session.get("cart", {})

    if not isinstance(cart_data, dict):
        cart_data = {}

    current_quantity = cart_data.get(product_id, 0)

    if (
        not isinstance(current_quantity, int)
        or isinstance(current_quantity, bool)
    ):
        current_quantity = 0

    if current_quantity >= 99:
        flash("You can order up to 99 of one item.")
        return redirect(url_for("menu"))

    cart_data[product_id] = current_quantity + 1

    session["cart"] = cart_data
    session.modified = True

    flash(f'{PRODUCTS[product_id]["name"]} added to your cart.')
    return redirect(url_for("menu"))


# UPDATE CART


@app.route("/update-cart/<product_id>", methods=["POST"])
def update_cart(product_id):

    cart_data = session.get("cart", {})

    if not isinstance(cart_data, dict):
        session.pop("cart", None)
        return redirect(url_for("cart"))

    if product_id not in PRODUCTS or product_id not in cart_data:
        return redirect(url_for("cart"))

    try:
        quantity = int(request.form.get("quantity", "1"))

    except (ValueError, TypeError):
        flash("Please enter a valid quantity.")
        return redirect(url_for("cart"))

    if quantity <= 0:
        cart_data.pop(product_id, None)

    elif quantity <= 99:
        cart_data[product_id] = quantity

    else:
        flash("You can order up to 99 of one item.")
        return redirect(url_for("cart"))

    session["cart"] = cart_data
    session.modified = True

    return redirect(url_for("cart"))


# REMOVE FROM CART


@app.route("/remove-from-cart/<product_id>", methods=["POST"])
def remove_from_cart(product_id):

    cart_data = session.get("cart", {})

    if isinstance(cart_data, dict):
        cart_data.pop(product_id, None)
        session["cart"] = cart_data
        session.modified = True

    flash("Item removed from your cart.")
    return redirect(url_for("cart"))



# CHECKOUT


@app.route("/checkout", methods=["GET", "POST"])
def checkout():

    if "user_id" not in session:
        flash("Please log in before checking out.")
        return redirect(url_for("login"))

    cart_items, subtotal = build_cart()

    if not cart_items:
        flash("Your cart is empty. Add some food before checking out.")
        return redirect(url_for("menu"))

    if request.method == "POST":
        customer_name = request.form.get(
            "customer_name", ""
        ).strip()

        phone = request.form.get("phone", "").strip()
        fulfillment = request.form.get("fulfillment", "")

        address = request.form.get(
            "delivery_address", ""
        ).strip()

        payment_method = request.form.get(
            "payment_method", ""
        )

        if not customer_name or not phone:
            flash("Please enter your name and phone number.")

        elif len(customer_name) > 100 or len(phone) > 30:
            flash("Your name or phone number is too long.")

        elif fulfillment not in ("Delivery", "Collection"):
            flash("Please choose delivery or collection.")

        elif fulfillment == "Delivery" and not address:
            flash("Please enter your delivery address.")

        elif len(address) > 500:
            flash("Your delivery address is too long.")

        elif (
            fulfillment == "Delivery"
            and payment_method != "Cash on Delivery"
        ):
            flash("Choose Cash on Delivery for delivery orders.")

        elif (
            fulfillment == "Collection"
            and payment_method != "Pay on Collection"
        ):
            flash("Choose Pay on Collection for collection orders.")

        else:
            connection = get_db_connection()

            try:
                cursor = connection.execute(
                    """
                    INSERT INTO orders (
                        user_id,
                        customer_name,
                        phone,
                        fulfillment,
                        delivery_address,
                        payment_method,
                        total
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session["user_id"],
                        customer_name,
                        phone,
                        fulfillment,
                        address if fulfillment == "Delivery" else None,
                        payment_method,
                        subtotal,
                    ),
                )

                order_id = cursor.lastrowid

                for item in cart_items:
                    connection.execute(
                        """
                        INSERT INTO order_items (
                            order_id,
                            product_id,
                            product_name,
                            price,
                            quantity,
                            line_total
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            order_id,
                            item["id"],
                            item["name"],
                            item["price"],
                            item["quantity"],
                            item["total"],
                        ),
                    )

                connection.commit()
                session.pop("cart", None)

                return redirect(
                    url_for("order_confirmation", order_id=order_id)
                )

            except Exception:
                connection.rollback()
                app.logger.exception("Could not save checkout order.")
                flash("We couldn't place your order. Please try again.")

            finally:
                connection.close()

    return render_template(
        "checkout.html",
        cart_items=cart_items,
        subtotal=subtotal,
        customer_name=session.get("user_name", ""),
    )



# ORDER CONFIRMATION


@app.route("/order-confirmation/<int:order_id>")
def order_confirmation(order_id):

    if "user_id" not in session:
        flash("Please log in to view your order.")
        return redirect(url_for("login"))

    connection = get_db_connection()

    try:
        order = connection.execute(
            """
            SELECT *
            FROM orders
            WHERE id = ? AND user_id = ?
            """,
            (order_id, session["user_id"]),
        ).fetchone()

        if order is None:
            flash("That order could not be found.")
            return redirect(url_for("home"))

        items = connection.execute(
            """
            SELECT *
            FROM order_items
            WHERE order_id = ?
            """,
            (order_id,),
        ).fetchall()

        return render_template(
            "order_confirmation.html",
            order=order,
            items=items,
        )

    finally:
        connection.close()


#ADMIN ACCESS

def admin_required(view_function):

    @wraps(view_function)
    def wrapped_view(*args, **kwargs):

        if not session.get("user_id"):
            flash("Please log in to access the admin area.")
            return redirect(url_for("login"))

        user_email = session.get("user_email", "").lower()

        if not ADMIN_EMAIL or user_email != ADMIN_EMAIL:
            flash("You are not authorized to access that page.")
            return redirect(url_for("home"))

        return view_function(*args, **kwargs)

    return wrapped_view


def valid_admin_csrf():
    token = session.get("admin_csrf_token")
    submitted_token = request.form.get("csrf_token", "")
    return (
        isinstance(token, str)
        and bool(token)
        and secrets.compare_digest(token, submitted_token)
    )



# ADMIN ORDERS


@app.route("/admin/orders")
@admin_required
def admin_orders():
    selected_status = request.args.get("status", "")
    if selected_status not in ORDER_STATUSES:
        selected_status = ""
    csrf_token = session.setdefault(
        "admin_csrf_token",
        secrets.token_urlsafe(32),
    )

    connection = get_db_connection()

    try:
        status_counts = {status: 0 for status in ORDER_STATUSES}
        status_rows = connection.execute(
            """
            SELECT status, COUNT(*) AS order_count
            FROM orders
            GROUP BY status
            """
        ).fetchall()
        for row in status_rows:
            status_counts[row["status"]] = row["order_count"]

        order_query = """
            SELECT
                orders.*,
                users.email AS account_email
            FROM orders
            JOIN users ON users.id = orders.user_id
        """
        parameters = ()
        if selected_status:
            order_query += " WHERE orders.status = ?"
            parameters = (selected_status,)
        order_query += " ORDER BY orders.id DESC"

        orders = connection.execute(
            order_query,
            parameters,
        ).fetchall()

        items_by_order = {}
        if orders:
            order_ids = [order["id"] for order in orders]
            placeholders = ",".join("?" for _ in order_ids)
            order_items = connection.execute(
                f"""
                SELECT *
                FROM order_items
                WHERE order_id IN ({placeholders})
                ORDER BY order_id DESC, id
                """,
                order_ids,
            ).fetchall()

            for item in order_items:
                items_by_order.setdefault(item["order_id"], []).append(item)

        order_list = [
            {
                "order": order,
                "items": items_by_order.get(order["id"], []),
            }
            for order in orders
        ]

        return render_template(
            "admin_orders.html",
            order_list=order_list,
            statuses=ORDER_STATUSES,
            status_counts=status_counts,
            selected_status=selected_status,
            csrf_token=csrf_token,
        )

    finally:
        connection.close()


@app.route(
    "/admin/orders/<int:order_id>/approve",
    methods=["POST"],
)
@admin_required
def approve_order(order_id):
    if not valid_admin_csrf():
        flash("Your admin session expired. Refresh the dashboard and try again.")
        return redirect(url_for("admin_orders"))

    connection = get_db_connection()

    try:
        cursor = connection.execute(
            """
            UPDATE orders
            SET status = 'Approved'
            WHERE id = ? AND status = 'Pending'
            """,
            (order_id,),
        )
        connection.commit()

        if cursor.rowcount == 0:
            flash("Order could not be approved. It may no longer be pending.")
        else:
            flash(f"Order #{order_id} approved.")

    except Exception:
        connection.rollback()
        app.logger.exception("Could not approve order #%s.", order_id)
        flash("Could not approve the order. Please try again.")

    finally:
        connection.close()

    return redirect(url_for("admin_orders"))



# UPDATE ORDER STATUS


@app.route(
    "/admin/orders/<int:order_id>/status",
    methods=["POST"],
)
@admin_required
def update_order_status(order_id):
    if not valid_admin_csrf():
        flash("Your admin session expired. Refresh the dashboard and try again.")
        return redirect(url_for("admin_orders"))

    new_status = request.form.get("status", "")

    if new_status not in ORDER_STATUSES:
        flash("Invalid order status.")
        return redirect(url_for("admin_orders"))

    connection = get_db_connection()

    try:
        cursor = connection.execute(
            """
            UPDATE orders
            SET status = ?
            WHERE id = ?
            """,
            (new_status, order_id),
        )

        connection.commit()

        if cursor.rowcount == 0:
            flash("Order not found.")
        else:
            flash("Order status updated successfully.")

    except Exception:
        connection.rollback()
        app.logger.exception("Could not update order status.")
        flash("Could not update the order status.")

    finally:
        connection.close()

    return redirect(url_for("admin_orders"))


import os
import hashlib
import secrets
import smtplib

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)

from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db_connection, init_db



# APP CONFIGURATION


app = Flask(__name__)

app.secret_key = os.environ.get(
    "STREET_BITES_SECRET_KEY",
    "street-bites-change-this-secret-key"
)

# Allow templates to display the current year.
app.jinja_env.globals["now"] = datetime.now

ADMIN_EMAIL = os.environ.get(
    "STREET_BITES_ADMIN_EMAIL",
    "admin@gmail.com"
).strip().lower()


@app.context_processor
def inject_admin_email():
    return {
        "ADMIN_EMAIL": ADMIN_EMAIL,
        "BUSINESS_PHONE": BUSINESS_PHONE,
        "BUSINESS_WHATSAPP": BUSINESS_WHATSAPP,
        "DELIVERY_AREAS": DELIVERY_AREAS,
        "mail_configured": bool(MAIL_USERNAME and MAIL_APP_PASSWORD),
    }



# DATABASE INITIALIZATION


init_db()


def init_password_reset_table():
    connection = get_db_connection()

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        connection.commit()

    finally:
        connection.close()


init_password_reset_table()



# EMAIL CONFIGURATION


MAIL_USERNAME = os.environ.get("MAIL_USERNAME", ADMIN_EMAIL).strip()

MAIL_APP_PASSWORD = os.environ.get(
    "MAIL_APP_PASSWORD", ""
).replace(" ", "")

MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com").strip()
MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
MAIL_TIMEOUT_SECONDS = 20

RESET_TOKEN_MAX_AGE_MINUTES = 30


def send_reset_email(recipient, reset_url):
    """Send a password reset email using an authenticated STARTTLS server."""

    if not MAIL_USERNAME or not MAIL_APP_PASSWORD:
        raise RuntimeError(
            "Email configuration is missing. "
            "Set MAIL_APP_PASSWORD and, if needed, MAIL_USERNAME."
        )
    if not MAIL_SERVER or not 1 <= MAIL_PORT <= 65535:
        raise RuntimeError("The configured mail server or port is invalid.")

    message = EmailMessage()

    message["Subject"] = "Reset your Street Bites password"
    message["From"] = f"Street Bites <{MAIL_USERNAME}>"
    message["To"] = recipient

    message.set_content(
        "We received a request to reset your Street Bites password.\n\n"
        f"Use this link within {RESET_TOKEN_MAX_AGE_MINUTES} minutes:\n"
        f"{reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )

    with smtplib.SMTP(
        MAIL_SERVER,
        MAIL_PORT,
        timeout=MAIL_TIMEOUT_SECONDS,
    ) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(MAIL_USERNAME, MAIL_APP_PASSWORD)
        refused_recipients = smtp.send_message(message)
        if refused_recipients:
            raise smtplib.SMTPRecipientsRefused(refused_recipients)



# PRODUCTS


PRODUCTS = {
    "1": {"name": "Classic Burger", "price": 55.00},
    "2": {"name": "Cheese Burger", "price": 65.00},
    "3": {"name": "Double Beef Burger", "price": 85.00},
    "4": {"name": "Crispy Chicken", "price": 60.00},
    "5": {"name": "Chicken & Chips", "price": 75.00},
    "6": {"name": "Chicken Wrap", "price": 50.00},
    "7": {"name": "Regular Chips", "price": 25.00},
    "8": {"name": "Soft Drink", "price": 18.00},
    "9": {"name": "Loaded Chips", "price": 45.00},
}



# HOME


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    payload = request.get_json(silent=True)
    raw_message = payload.get("message") if isinstance(payload, dict) else None

    if not isinstance(raw_message, str):
        return jsonify({"error": "Please enter a text message."}), 400

    message = raw_message.strip()
    if not message or len(message) > 300:
        return jsonify({
            "error": "Please enter a message of 1 to 300 characters."
        }), 400

    normalized_message = message.lower()
    first_word = normalized_message.split(maxsplit=1)[0].strip(".,!?")
    links = []

    def add_link(label, endpoint):
        links.append({"label": label, "url": url_for(endpoint)})

    product_match = next(
        (
            product
            for product in PRODUCTS.values()
            if product["name"].lower() in normalized_message
        ),
        None,
    )

    if product_match:
        reply = (
            f'{product_match["name"]} is R{product_match["price"]:.2f}. '
            "You can add it to your order from our menu."
        )
        add_link("Browse the menu", "menu")
    elif any(word in normalized_message for word in ("menu", "price", "prices", "food", "eat")):
        items = ", ".join(
            f'{product["name"]} (R{product["price"]:.2f})'
            for product in PRODUCTS.values()
        )
        reply = f"Here is our menu: {items}."
        add_link("Browse the menu", "menu")
    elif any(
        word in normalized_message
        for word in ("track", "order status", "where is my order")
    ):
        reply = (
            "You can check your latest order status in My Orders. "
            "Statuses include Pending, Preparing, Ready, Out for Delivery, Completed, and Cancelled."
        )
        if session.get("user_id"):
            add_link("View my orders", "my_orders")
        else:
            reply += " Sign in to view your orders."
            add_link("Sign in", "login")
    elif any(
        word in normalized_message
        for word in ("location", "where", "address", "directions", "find us")
    ):
        reply = "Street Bites is in the Sewula Area, Amanzimtoti, KwaZulu-Natal, South Africa."
        add_link("Get directions", "where_to_find_us")
    elif any(
        word in normalized_message
        for word in ("hour", "open", "closing", "close", "when")
    ):
        reply = (
            "We’re open Monday to Friday, 08:00–19:00, and Saturday to Sunday, "
            "08:00–18:00."
        )
        links.append({
            "label": "Call us",
            "url": f"tel:{BUSINESS_PHONE.replace(' ', '')}",
        })
        links.append({
            "label": "WhatsApp us",
            "url": f"https://wa.me/{BUSINESS_WHATSAPP}",
        })
    elif any(
        word in normalized_message
        for word in ("delivery", "deliver", "collection", "pickup", "pick up")
    ):
        reply = (
            "We deliver to Amanzimtoti, KwaMakhutha, Adams Mission, Illovo, "
            "Umlazi, Isipingo, Umgababa, and Umbumbulu. Delivery is R50 within "
            "5 km and R80 beyond 5 km. The fee is confirmed before fulfillment. "
            "Delivery is paid cash on delivery; collection is paid on collection."
        )
        add_link("View your cart", "cart")
        add_link("Sign in", "login")
        links.append({
            "label": "WhatsApp us",
            "url": f"https://wa.me/{BUSINESS_WHATSAPP}",
        })
    elif any(word in normalized_message for word in ("order", "checkout", "buy", "cart")):
        reply = (
            "Add items to your cart, sign in, then continue to checkout. "
            "You can choose delivery or collection there."
        )
        add_link("Browse the menu", "menu")
        add_link("View your cart", "cart")
    elif any(
        word in normalized_message
        for word in ("password", "account", "login", "sign in", "forgot")
    ):
        reply = "You can sign in or create an account. If you forgot your password, use the reset link on the sign-in page."
        add_link("Sign in", "login")
        add_link("Create an account", "signup")
    elif first_word in ("hello", "hi", "hey", "help"):
        reply = "Hi! I can help with menu prices, orders, delivery, or finding us. What would you like to know?"
    else:
        reply = "I’m not sure about that yet. Send us a message and the Street Bites team can help."
        add_link("Contact us", "contact_us")

    return jsonify({"reply": reply, "links": links})



# SIGNUP


@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("Please fill in all fields.")
            return render_template("signup.html")

        if len(name) > 100 or len(email) > 254:
            flash("Your name or email address is too long.")
            return render_template("signup.html")

        if len(password) < 8:
            flash("Your password must be at least 8 characters.")
            return render_template("signup.html")

        connection = get_db_connection()

        try:
            connection.execute(
                """
                INSERT INTO users (name, email, password_hash)
                VALUES (?, ?, ?)
                """,
                (name, email, generate_password_hash(password)),
            )

            connection.commit()

            flash("Account created successfully. You can now log in!")
            return redirect(url_for("login"))

        except Exception as error:
            if "UNIQUE constraint failed" in str(error):
                flash("That email address is already registered.")
            else:
                app.logger.exception("Signup failed.")
                flash("Something went wrong. Please try again.")

        finally:
            connection.close()

    return render_template("signup.html")



# LOGIN


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        connection = get_db_connection()

        try:
            user = connection.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,),
            ).fetchone()

        finally:
            connection.close()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"].lower()

            flash("Welcome back!")
            return redirect(url_for("home"))

        flash("Invalid email or password.")

    return render_template("login.html")



# LOGOUT


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("home"))



# FIND US


@app.route("/where-to-find-us")
def where_to_find_us():
    return render_template("where_to_find_us.html")



# CONTACT US


@app.route("/contact-us", methods=["GET", "POST"])
def contact_us():

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()

        if not all([name, email, subject, message]):
            flash("Please complete all fields.")
            return render_template("contact_us.html")

        if (
            len(name) > 100
            or len(email) > 254
            or len(subject) > 150
            or len(message) > 3000
        ):
            flash("One or more fields exceed the allowed length.")
            return render_template("contact_us.html")

        flash("Thanks for contacting Street Bites! Your form was submitted.")
        return redirect(url_for("contact_us"))

    return render_template("contact_us.html")



# FORGOT PASSWORD


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        generic_message = (
            "If an account exists for that email, "
            "a password-reset link will be sent."
        )

        if not MAIL_USERNAME or not MAIL_APP_PASSWORD:
            app.logger.error(
                "Password-reset email is unavailable because mail credentials "
                "are not configured."
            )
            flash(
                "Password reset emails are temporarily unavailable. "
                "Please contact Street Bites support."
            )
            return redirect(url_for("forgot_password"))

        if not email or len(email) > 254:
            flash(generic_message)
            return redirect(url_for("forgot_password"))

        connection = get_db_connection()

        try:
            user = connection.execute(
                "SELECT id, email FROM users WHERE email = ?",
                (email,),
            ).fetchone()

            if user:
                raw_token = secrets.token_urlsafe(32)

                token_hash = hashlib.sha256(
                    raw_token.encode("utf-8")
                ).hexdigest()

                expires_at = (
                    datetime.now(timezone.utc)
                    + timedelta(minutes=RESET_TOKEN_MAX_AGE_MINUTES)
                ).isoformat()

                connection.execute(
                    """
                    DELETE FROM password_reset_tokens
                    WHERE user_id = ? AND used_at IS NULL
                    """,
                    (user["id"],),
                )

                connection.execute(
                    """
                    INSERT INTO password_reset_tokens
                    (user_id, token_hash, expires_at)
                    VALUES (?, ?, ?)
                    """,
                    (user["id"], token_hash, expires_at),
                )

                connection.commit()

                reset_path = url_for("reset_password", token=raw_token)
                reset_url = (
                    f"{RESET_BASE_URL}{reset_path}"
                    if RESET_BASE_URL
                    else url_for(
                        "reset_password",
                        token=raw_token,
                        _external=True,
                    )
                )

                try:
                    send_reset_email(user["email"], reset_url)

                except (
                    RuntimeError,
                    OSError,
                    ValueError,
                    smtplib.SMTPException,
                ):
                    connection.execute(
                        """
                        DELETE FROM password_reset_tokens
                        WHERE token_hash = ?
                        """,
                        (token_hash,),
                    )

                    connection.commit()

                    app.logger.exception(
                        "Could not send password-reset email."
                    )

            flash(generic_message)

        except Exception:
            connection.rollback()
            app.logger.exception("Password-reset request failed.")
            flash(generic_message)

        finally:
            connection.close()

        return redirect(url_for("forgot_password"))

    return render_template("forgot_password.html")



# RESET PASSWORD


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):

    token_hash = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

    connection = get_db_connection()

    try:
        reset_record = connection.execute(
            """
            SELECT id, user_id, expires_at, used_at
            FROM password_reset_tokens
            WHERE token_hash = ?
            """,
            (token_hash,),
        ).fetchone()

        if reset_record is None or reset_record["used_at"] is not None:
            flash("This reset link is invalid or has already been used.")
            return redirect(url_for("forgot_password"))

        expiry = datetime.fromisoformat(reset_record["expires_at"])

        if datetime.now(timezone.utc) >= expiry:
            connection.execute(
                "DELETE FROM password_reset_tokens WHERE id = ?",
                (reset_record["id"],),
            )

            connection.commit()

            flash("This reset link has expired. Please request a new one.")
            return redirect(url_for("forgot_password"))

        if request.method == "POST":
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")

            if len(password) < 8:
                flash("Your password must be at least 8 characters.")
                return render_template("reset_password.html")

            if password != confirm_password:
                flash("The passwords do not match.")
                return render_template("reset_password.html")

            connection.execute(
                """
                UPDATE users
                SET password_hash = ?
                WHERE id = ?
                """,
                (
                    generate_password_hash(password),
                    reset_record["user_id"],
                ),
            )

            connection.execute(
                """
                UPDATE password_reset_tokens
                SET used_at = ?
                WHERE id = ?
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    reset_record["id"],
                ),
            )

            connection.execute(
                """
                DELETE FROM password_reset_tokens
                WHERE user_id = ? AND id != ?
                """,
                (reset_record["user_id"], reset_record["id"]),
            )

            connection.commit()

            flash("Your password has been reset. Please log in.")
            return redirect(url_for("login"))

        return render_template("reset_password.html")

    except Exception:
        connection.rollback()
        app.logger.exception("Password-reset operation failed.")
        flash("Something went wrong. Please request a new reset link.")
        return redirect(url_for("forgot_password"))

    finally:
        connection.close()



# MENU


@app.route("/menu")
def menu():
    return render_template("menu.html")



# CART HELPERS


def build_cart():

    cart_items = []
    subtotal = 0.0
    cart_data = session.get("cart", {})

    if not isinstance(cart_data, dict):
        return [], 0.0

    for product_id, quantity in cart_data.items():
        product = PRODUCTS.get(product_id)

        if (
            product
            and isinstance(quantity, int)
            and not isinstance(quantity, bool)
            and 1 <= quantity <= 99
        ):
            item_total = round(product["price"] * quantity, 2)

            cart_items.append({
                "id": product_id,
                "name": product["name"],
                "price": product["price"],
                "quantity": quantity,
                "total": item_total,
            })

            subtotal += item_total

    return cart_items, round(subtotal, 2)



# VIEW CART


@app.route("/cart")
def cart():
    cart_items, subtotal = build_cart()

    return render_template(
        "cart.html",
        cart_items=cart_items,
        subtotal=subtotal,
    )



# ADD TO CART


@app.route("/add-to-cart/<product_id>", methods=["POST"])
def add_to_cart(product_id):

    if product_id not in PRODUCTS:
        flash("That product could not be found.")
        return redirect(url_for("menu"))

    cart_data = session.get("cart", {})

    if not isinstance(cart_data, dict):
        cart_data = {}

    current_quantity = cart_data.get(product_id, 0)

    if (
        not isinstance(current_quantity, int)
        or isinstance(current_quantity, bool)
    ):
        current_quantity = 0

    if current_quantity >= 99:
        flash("You can order up to 99 of one item.")
        return redirect(url_for("menu"))

    cart_data[product_id] = current_quantity + 1

    session["cart"] = cart_data
    session.modified = True

    flash(f'{PRODUCTS[product_id]["name"]} added to your cart.')
    return redirect(url_for("menu"))



# UPDATE CART


@app.route("/update-cart/<product_id>", methods=["POST"])
def update_cart(product_id):

    cart_data = session.get("cart", {})

    if not isinstance(cart_data, dict):
        session.pop("cart", None)
        return redirect(url_for("cart"))

    if product_id not in PRODUCTS or product_id not in cart_data:
        return redirect(url_for("cart"))

    try:
        quantity = int(request.form.get("quantity", "1"))

    except (ValueError, TypeError):
        flash("Please enter a valid quantity.")
        return redirect(url_for("cart"))

    if quantity <= 0:
        cart_data.pop(product_id, None)

    elif quantity <= 99:
        cart_data[product_id] = quantity

    else:
        flash("You can order up to 99 of one item.")
        return redirect(url_for("cart"))

    session["cart"] = cart_data
    session.modified = True

    return redirect(url_for("cart"))



# REMOVE ITEMS FROM THE CART


@app.route("/remove-from-cart/<product_id>", methods=["POST"])
def remove_from_cart(product_id):

    cart_data = session.get("cart", {})

    if isinstance(cart_data, dict):
        cart_data.pop(product_id, None)
        session["cart"] = cart_data
        session.modified = True

    flash("Item removed from your cart.")
    return redirect(url_for("cart"))



# CHECKOUT


@app.route("/checkout", methods=["GET", "POST"])
def checkout():

    if "user_id" not in session:
        flash("Please log in before checking out.")
        return redirect(url_for("login"))

    cart_items, subtotal = build_cart()

    if not cart_items:
        flash("Your cart is empty. Add some food before checking out.")
        return redirect(url_for("menu"))

    if request.method == "POST":
        customer_name = request.form.get(
            "customer_name", ""
        ).strip()

        phone = request.form.get("phone", "").strip()
        fulfillment = request.form.get("fulfillment", "")

        address = request.form.get(
            "delivery_address", ""
        ).strip()

        payment_method = request.form.get(
            "payment_method", ""
        )

        if not customer_name or not phone:
            flash("Please enter your name and phone number.")

        elif len(customer_name) > 100 or len(phone) > 30:
            flash("Your name or phone number is too long.")

        elif fulfillment not in ("Delivery", "Collection"):
            flash("Please choose delivery or collection.")

        elif fulfillment == "Delivery" and not address:
            flash("Please enter your delivery address.")

        elif len(address) > 500:
            flash("Your delivery address is too long.")

        elif (
            fulfillment == "Delivery"
            and payment_method != "Cash on Delivery"
        ):
            flash("Choose Cash on Delivery for delivery orders.")

        elif (
            fulfillment == "Collection"
            and payment_method != "Pay on Collection"
        ):
            flash("Choose Pay on Collection for collection orders.")

        else:
            connection = get_db_connection()

            try:
                cursor = connection.execute(
                    """
                    INSERT INTO orders (
                        user_id,
                        customer_name,
                        phone,
                        fulfillment,
                        delivery_address,
                        payment_method,
                        total
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session["user_id"],
                        customer_name,
                        phone,
                        fulfillment,
                        address if fulfillment == "Delivery" else None,
                        payment_method,
                        subtotal,
                    ),
                )

                order_id = cursor.lastrowid

                for item in cart_items:
                    connection.execute(
                        """
                        INSERT INTO order_items (
                            order_id,
                            product_id,
                            product_name,
                            price,
                            quantity,
                            line_total
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            order_id,
                            item["id"],
                            item["name"],
                            item["price"],
                            item["quantity"],
                            item["total"],
                        ),
                    )

                connection.commit()
                session.pop("cart", None)

                return redirect(
                    url_for("order_confirmation", order_id=order_id)
                )

            except Exception:
                connection.rollback()
                app.logger.exception("Could not save checkout order.")
                flash("We couldn't place your order. Please try again.")

            finally:
                connection.close()

    return render_template(
        "checkout.html",
        cart_items=cart_items,
        subtotal=subtotal,
        customer_name=session.get("user_name", ""),
    )




# ORDER CONFIRMATION


@app.route("/order-confirmation/<int:order_id>")
def order_confirmation(order_id):

    if "user_id" not in session:
        flash("Please log in to view your order.")
        return redirect(url_for("login"))

    connection = get_db_connection()

    try:
        order = connection.execute(
            """
            SELECT *
            FROM orders
            WHERE id = ? AND user_id = ?
            """,
            (order_id, session["user_id"]),
        ).fetchone()

        if order is None:
            flash("That order could not be found.")
            return redirect(url_for("home"))

        items = connection.execute(
            """
            SELECT *
            FROM order_items
            WHERE order_id = ?
            """,
            (order_id,),
        ).fetchall()

        return render_template(
            "order_confirmation.html",
            order=order,
            items=items,
        )

    finally:
        connection.close()


@app.route("/my-orders")
def my_orders():

    if "user_id" not in session:
        flash("Please log in to view your orders.")
        return redirect(url_for("login"))

    connection = get_db_connection()

    try:
        orders = connection.execute(
            """
            SELECT *
            FROM orders
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (session["user_id"],),
        ).fetchall()

        order_items = connection.execute(
            """
            SELECT order_items.*
            FROM order_items
            JOIN orders ON orders.id = order_items.order_id
            WHERE orders.user_id = ?
            ORDER BY order_items.order_id DESC, order_items.id
            """,
            (session["user_id"],),
        ).fetchall()

        items_by_order = {}
        for item in order_items:
            items_by_order.setdefault(item["order_id"], []).append(item)

        return render_template(
            "my_orders.html",
            orders=orders,
            items_by_order=items_by_order,
        )

    finally:
        connection.close()



# ADMIN ACCESS


def admin_required(view_function):

    @wraps(view_function)
    def wrapped_view(*args, **kwargs):

        if not session.get("user_id"):
            flash("Please log in to access the admin area.")
            return redirect(url_for("login"))

        user_email = session.get("user_email", "").lower()

        if not ADMIN_EMAIL or user_email != ADMIN_EMAIL:
            flash("You are not authorized to access that page.")
            return redirect(url_for("home"))

        return view_function(*args, **kwargs)

    return wrapped_view



# ADMIN ORDERS


@app.route("/admin/orders")
@admin_required
def admin_orders():
    selected_status = request.args.get("status", "")
    if selected_status not in ORDER_STATUSES:
        selected_status = ""
    csrf_token = session.setdefault(
        "admin_csrf_token",
        secrets.token_urlsafe(32),
    )

    connection = get_db_connection()

    try:
        status_counts = {status: 0 for status in ORDER_STATUSES}
        status_rows = connection.execute(
            """
            SELECT status, COUNT(*) AS order_count
            FROM orders
            GROUP BY status
            """
        ).fetchall()
        for row in status_rows:
            status_counts[row["status"]] = row["order_count"]

        order_query = """
            SELECT
                orders.*,
                users.email AS account_email
            FROM orders
            JOIN users ON users.id = orders.user_id
        """
        parameters = ()
        if selected_status:
            order_query += " WHERE orders.status = ?"
            parameters = (selected_status,)
        order_query += " ORDER BY orders.id DESC"

        orders = connection.execute(
            order_query,
            parameters,
        ).fetchall()

        items_by_order = {}
        if orders:
            order_ids = [order["id"] for order in orders]
            placeholders = ",".join("?" for _ in order_ids)
            order_items = connection.execute(
                f"""
                SELECT *
                FROM order_items
                WHERE order_id IN ({placeholders})
                ORDER BY order_id DESC, id
                """,
                order_ids,
            ).fetchall()

            for item in order_items:
                items_by_order.setdefault(item["order_id"], []).append(item)

        order_list = [
            {
                "order": order,
                "items": items_by_order.get(order["id"], []),
            }
            for order in orders
        ]

        return render_template(
            "admin_orders.html",
            order_list=order_list,
            statuses=ORDER_STATUSES,
            status_counts=status_counts,
            selected_status=selected_status,
            csrf_token=csrf_token,
        )

    finally:
        connection.close()


@app.route(
    "/admin/orders/<int:order_id>/approve",
    methods=["POST"],
)
@admin_required
def approve_order(order_id):
    connection = get_db_connection()

    try:
        cursor = connection.execute(
            """
            UPDATE orders
            SET status = 'Approved'
            WHERE id = ? AND status = 'Pending'
            """,
            (order_id,),
        )
        connection.commit()

        if cursor.rowcount == 0:
            flash("Order could not be approved. It may no longer be pending.")
        else:
            flash(f"Order #{order_id} approved.")

    except Exception:
        connection.rollback()
        app.logger.exception("Could not approve order #%s.", order_id)
        flash("Could not approve the order. Please try again.")

    finally:
        connection.close()

    return redirect(url_for("admin_orders"))



# UPDATE ORDER STATUS


@app.route(
    "/admin/orders/<int:order_id>/status",
    methods=["POST"],
)
@admin_required
def update_order_status(order_id):

    new_status = request.form.get("status", "")

    if new_status not in ORDER_STATUSES:
        flash("Invalid order status.")
        return redirect(url_for("admin_orders"))

    connection = get_db_connection()

    try:
        cursor = connection.execute(
            """
            UPDATE orders
            SET status = ?
            WHERE id = ?
            """,
            (new_status, order_id),
        )

        connection.commit()

        if cursor.rowcount == 0:
            flash("Order not found.")
        else:
            flash("Order status updated successfully.")

    except Exception:
        connection.rollback()
        app.logger.exception("Could not update order status.")
        flash("Could not update the order status.")

    finally:
        connection.close()

    return redirect(url_for("admin_orders"))



# RUN APPLICATION


if __name__ == "__main__":
    app.run(debug=True)
