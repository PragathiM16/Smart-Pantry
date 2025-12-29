from flask import Flask, render_template, request, redirect, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from bson.objectid import ObjectId
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import requests
import urllib.parse
import os

app = Flask(__name__)
app.secret_key = "SmartPantry"

# ---------------- CONFIG ----------------
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDER_EMAIL = "smartpantry28@gmail.com"
MONGO_URI = "mongodb://localhost:27017/"
PIXABAY_API_KEY = "53925676-923ada41045b5b093107c781b"

# ---------------- DATABASE ----------------
client = MongoClient(MONGO_URI)
db = client.smart_pantry
users = db.users
items = db.items

# ---------------- EMAIL ----------------
def send_email(to_email, subject, content):
    if not SENDGRID_API_KEY:
        raise RuntimeError("SENDGRID_API_KEY not set")

    sg = SendGridAPIClient(SENDGRID_API_KEY)
    message = Mail(
        from_email=SENDER_EMAIL,
        to_emails=to_email,
        subject=subject,
        plain_text_content=content
    )
    sg.send(message)

# ---------------- IMAGE FETCH (PIXABAY) ----------------
def get_food_image(food_name):
    if not PIXABAY_API_KEY:
        return "/static/food.png"

    query = urllib.parse.quote(food_name)
    url = "https://pixabay.com/api/"
    params = {
        "key": PIXABAY_API_KEY,
        "q": query,
        "image_type": "photo",
        "category": "food",
        "per_page": 3
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if data.get("hits"):
            return data["hits"][0]["webformatURL"]
    except Exception as e:
        print("Pixabay Error:", e)

    return "/static/food.png"

# ---------------- WELCOME PAGE ----------------
@app.route("/")
def welcome():
    return render_template("welcome.html")

# ---------------- HOME PAGE ----------------
@app.route("/index")
def index():
    return render_template("index.html")

# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        if users.find_one({"username": request.form["username"]}):
            return "User already exists"

        users.insert_one({
            "username": request.form["username"],
            "email": request.form["email"],
            "password": generate_password_hash(request.form["password"])
        })

        send_email(
            request.form["email"],
            "Welcome to Smart Pantry",
            "Account created successfully 🌱"
        )
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
        expiry = datetime.strptime(item["expiry"], "%Y-%m-%d").date()
        days_left = (expiry - today).days

        if days_left < 0:
            items.delete_one({"_id": item["_id"]})
            continue

        stats["total"] += 1
        if days_left <= 7:
            stats["soon"] += 1
        else:
            stats["safe"] += 1

        if not item.get("image"):
            item["image"] = get_food_image(item["name"])
            items.update_one(
                {"_id": item["_id"]},
                {"$set": {"image": item["image"]}}
            )

        item["days_left"] = days_left
        updated_items.append(item)

        if days_left == 7:
            send_email(user["email"], "Expiry Reminder ⏰", f"{item['name']} expires in 7 days")
        if days_left == 1:
            send_email(user["email"], "Urgent Alert ⚠️", f"{item['name']} expires tomorrow")

    return render_template("pantry.html", items=updated_items, stats=stats)

# ---------------- ADD ITEM ----------------
@app.route("/add", methods=["POST"])
def add_item():
    if "user" not in session:
        return redirect("/login")

    food_name = request.form["name"]

    items.insert_one({
        "user": session["user"],
        "name": food_name,
        "expiry": request.form["expiry"],
        "image": get_food_image(food_name),
        "added_on": datetime.today().strftime("%Y-%m-%d")
    })

    return redirect("/pantry")

# ---------------- DELETE ----------------
@app.route("/delete/<id>")
def delete_item(id):
    if "user" in session:
        items.delete_one({"_id": ObjectId(id)})
    return redirect("/pantry")

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)

    