
from flask import Flask, render_template, request, redirect, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import requests
import re
import urllib.parse

app = Flask(__name__)
app.secret_key = "SmartPantry"

# ---------------- CONFIG ----------------
SENDGRID_API_KEY = "SG.xxxxxx"
SENDER_EMAIL = "smartpantry28@gmail.com"
PIXABAY_API_KEY = "53925676-923ada41045b5b093107c781b"

# ---------------- DATABASE ----------------
client = MongoClient("mongodb+srv://SmartPantry:<db_password>@cluster0.0yreptr.mongodb.net/?appName=Cluster0")
db = client.smart_pantry
users = db.users
items = db.items

# ---------------- EMAIL ----------------
def send_email(to_email, subject, content):
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(Mail(SENDER_EMAIL, to_email, subject, content))
    except Exception as e:
        print(e)

# ---------------- IMAGE ----------------
def get_food_image(food_name):
    try:
        q = urllib.parse.quote(food_name)
        url = f"https://pixabay.com/api/?key={PIXABAY_API_KEY}&q={q}&image_type=photo"
        data = requests.get(url, timeout=5).json()
        return data["hits"][0]["webformatURL"] if data.get("hits") else "/static/food.png"
    except:
        return "/static/food.png"

# ---------------- ROUTES ----------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/pantry")
def pantry():
    if "user" not in session:
        return redirect("/login")

    today = datetime.today().date()
    user = users.find_one({"username": session["user"]})
    user_items = list(items.find({"user": session["user"]}))

    stats = {
        "total": 0,
        "expired": 0,
        "expiring_soon": 0,
        "safe": 0
    }

    updated_items = []

    for item in user_items:
        expiry = datetime.strptime(item["expiry"], "%Y-%m-%d").date()
        days_left = (expiry - today).days

        if expiry < today:
            items.delete_one({"_id": item["_id"]})
            stats["expired"] += 1
            continue

        if days_left <= 7:
            stats["expiring_soon"] += 1
        else:
            stats["safe"] += 1

        stats["total"] += 1
        item["days_left"] = days_left
        item["image"] = item.get("image", get_food_image(item["name"]))
        updated_items.append(item)

    return render_template(
        "pantry.html",
        items=updated_items,
        today=today,
        stats=stats
    )

@app.route("/add", methods=["POST"])
def add_item():
    if "user" in session:
        items.insert_one({
            "user": session["user"],
            "name": request.form["name"],
            "expiry": request.form["expiry"],
            "image": get_food_image(request.form["name"]),
            "added_on": datetime.today().strftime("%Y-%m-%d")
        })
    return redirect("/pantry")

@app.route("/delete/<id>")
def delete_item(id):
    items.delete_one({"_id": ObjectId(id)})
    return redirect("/pantry")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run()
