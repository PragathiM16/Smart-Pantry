from flask import Flask, render_template, request, redirect, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import requests
import urllib.parse
import os

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "SmartPantry")

# ---------------- CONFIG (ENV VARIABLES) ----------------
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# ---------------- DATABASE ----------------
try:
    client = MongoClient(MONGO_URI)
    db = client.smart_pantry
    users = db.users
    items = db.items
except Exception as e:
    print("MongoDB connection error:", e)

# ---------------- EMAIL ----------------
def send_email(to_email, subject, content):
    if not SENDGRID_API_KEY or not SENDER_EMAIL:
        return
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        message = Mail(
            from_email=SENDER_EMAIL,
            to_emails=to_email,
            subject=subject,
            plain_text_content=content
        )
        sg.send(message)
    except Exception as e:
        print("Email error:", e)

# ---------------- IMAGE ----------------
def get_food_image(food_name):
    if not PIXABAY_API_KEY:
        return "/static/food.png"
    try:
        q = urllib.parse.quote(food_name)
        url = f"https://pixabay.com/api/?key={PIXABAY_API_KEY}&q={q}&image_type=photo&per_page=3"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data.get("hits"):
            return data["hits"][0]["webformatURL"]
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
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        if users.find_one({"username": username}):
            return "User already exists"

        users.insert_one({
            "username": username,
            "email": email,
            "password": generate_password_hash(password)
        })

        send_email(email, "Welcome to Smart Pantry", "Account created successfully 🌱")
        return redirect("/login")

    return render_template("signup.html")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = users.find_one({"username": request.form["username"]})
        if not user or not check_password_hash(user["password"], request.form["password"]):
            return render_template("login.html", error="Invalid credentials")

        session["user"] = user["username"]
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

    stats = {"total": 0, "soon": 0, "safe": 0}
    updated_items = []

    for item in user_items:
        try:
            expiry = datetime.strptime(item["expiry"], "%Y-%m-%d").date()
        except:
            continue

        days_left = (expiry - today).days

        if expiry < today:
            items.delete_one({"_id": item["_id"]})
            continue

        if days_left <= 7:
            stats["soon"] += 1
        else:
            stats["safe"] += 1

        stats["total"] += 1

        item["days_left"] = days_left
        item["image"] = item.get("image") or get_food_image(item["name"])
        updated_items.append(item)

        if days_left == 7:
            send_email(user["email"], "Expiry Reminder ⏰", f"{item['name']} expires in 7 days")
        if days_left == 1:
            send_email(user["email"], "Urgent Alert ⚠️", f"{item['name']} expires tomorrow")

    return render_template(
        "pantry.html",
        items=updated_items,
        stats=stats,
        today=today
    )

# ---------------- ADD ITEM ----------------
@app.route("/add", methods=["POST"])
def add_item():
    if "user" not in session:
        return redirect("/login")

    items.insert_one({
        "user": session["user"],
        "name": request.form["name"],
        "expiry": request.form["expiry"],
        "image": get_food_image(request.form["name"]),
        "added_on": datetime.today().strftime("%Y-%m-%d")
    })
    return redirect("/pantry")

# ---------------- DELETE ITEM ----------------
@app.route("/delete/<id>")
def delete_item(id):
    if "user" in session:
        try:
            items.delete_one({"_id": ObjectId(id)})
        except:
            pass
    return redirect("/pantry")

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ---------------- RUN (Render safe) ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
