from flask import Flask, render_template, request, redirect, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import requests
import re
import urllib.parse  # for safe URL encoding

app = Flask(__name__)
app.secret_key = "SmartPantry"

# ---------------- SENDGRID CONFIG ----------------
SENDGRID_API_KEY = "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"
SENDER_EMAIL = "smartpantry28@gmail.com"  # verified sender email

# ---------------- PIXABAY CONFIG ----------------
PIXABAY_API_KEY = "53925676-923ada41045b5b093107c781b"  # replace with your Pixabay API key

# ---------------- DATABASE ----------------
client = MongoClient("mongodb://localhost:27017")
db = client.smart_pantry
users = db.users
items = db.items

# ---------------- SEND EMAIL FUNCTION ----------------
def send_email(to_email, subject, content):
    try:
        message = Mail(
            from_email=SENDER_EMAIL,
            to_emails=to_email,
            subject=subject,
            plain_text_content=content
        )
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
    except Exception as e:
        print("Email error:", e)

# ---------------- GET FOOD IMAGE ----------------
def get_food_image(food_name):
    try:
        food_name_encoded = urllib.parse.quote(food_name)
        url = f"https://pixabay.com/api/?key={PIXABAY_API_KEY}&q={food_name_encoded}&image_type=photo&per_page=3"
        response = requests.get(url, timeout=5)
        data = response.json()
        if data.get('hits'):
            return data['hits'][0]['webformatURL']
        else:
            return "/static/food.png"  # fallback image
    except Exception as e:
        print("Pixabay error:", e)
        return "/static/food.png"

# ---------------- HOME ----------------
@app.route("/")
def index():
    return render_template("index.html")

# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        if not username or not email or not password:
            return "All fields required"

        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return "Invalid email"

        if users.find_one({"username": username}):
            return "User already exists"

        users.insert_one({
            "username": username,
            "email": email,
            "password": generate_password_hash(password)
        })

        send_email(
            email,
            "Welcome to Smart Pantry",
            "Your Smart Pantry account has been created successfully 🌱"
        )

        return redirect("/login")

    return render_template("signup.html")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = users.find_one({"username": username})
        if not user or not check_password_hash(user["password"], password):
            return render_template("login.html", error="Invalid credentials")

        session["user"] = username
        return redirect("/pantry")

    return render_template("login.html")

# ---------------- PANTRY ----------------
@app.route("/pantry")
def pantry():
    if "user" not in session:
        return redirect("/login")

    today = datetime.today().date()
    user = users.find_one({"username": session["user"]})
    user_items = list(items.find({"user": session["user"]}))

    for item in user_items:
        expiry = datetime.strptime(item["expiry"], "%Y-%m-%d").date()

        # delete expired
        if expiry < today:
            items.delete_one({"_id": item["_id"]})
            continue

        # reminder 7 days
        if expiry == today + timedelta(days=7):
            send_email(
                user["email"],
                "Expiry Reminder ⏰",
                f"{item['name']} expires in 7 days."
            )

        # reminder 1 day
        if expiry == today + timedelta(days=1):
            send_email(
                user["email"],
                "Urgent Expiry Alert ⚠️",
                f"{item['name']} expires tomorrow!"
            )

    # Fetch updated items
    user_items = list(items.find({"user": session["user"]}))

    # Ensure each item has an image
    for item in user_items:
        if "image" not in item:
            item["image"] = get_food_image(item["name"])

    return render_template("pantry.html", items=user_items, today=today)

# ---------------- ADD ITEM ----------------
@app.route("/add", methods=["POST"])
def add_item():
    if "user" in session:
        food_name = request.form.get("name")
        expiry_date = request.form.get("expiry")
        image_url = get_food_image(food_name)
        items.insert_one({
            "user": session["user"],
            "name": food_name,
            "expiry": expiry_date,
            "image": image_url
        })
    return redirect("/pantry")

# ---------------- DELETE ITEM ----------------
@app.route("/delete/<item_id>")
def delete_item(item_id):
    if "user" in session:
        items.delete_one({"_id": ObjectId(item_id)})
    return redirect("/pantry")

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)

