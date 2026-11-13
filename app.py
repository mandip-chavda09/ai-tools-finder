import os
import re
from datetime import datetime, timezone

from flask import Flask, session, request, render_template, redirect, url_for, flash
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
from werkzeug.security import generate_password_hash, check_password_hash
import certifi

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("Set the FLASK_SECRET_KEY environment variable.")

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("Set the MONGO_URI environment variable.")

# Reuse the client between serverless invocations where possible.
client = MongoClient(
    MONGO_URI,
    tls=True,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=20000
)
db = client["ai_tools_db"]
tools_collection = db["ai_tools"]
users_collection = db["users"]

# Unique indexes prevent duplicate accounts.
users_collection.create_index([("email", ASCENDING)], unique=True)
users_collection.create_index([("username", ASCENDING)], unique=True)

TOOLS_PER_PAGE = 9

CATEGORY_ICONS = {
    "Coding": ("/static/coding.png", "#dbeafe"),
    "Developer": ("/static/dev.png", "#dbeafe"),
    "Writing": ("/static/writing.png", "#fce7f3"),
    "Productivity": ("/static/cal.png", "#e0f2fe"),
    "Search": ("/static/search.png", "#f0fdf4"),
    "Chatbot": ("/static/chatbot.png", "#d1fae5"),
    "Marketing": ("/static/marketing.png", "#fef3c7"),
    "SEO": ("/static/seo.png", "#dcfce7"),
    "Translation": ("/static/translation.png", "#e0e7ff"),
    "Voice": ("/static/voice.png", "#ede9fe"),
    "Audio": ("/static/audio.png", "#f0f9ff"),
    "Music": ("/static/music.png", "#ecfeff"),
    "Image Generation": ("/static/imagegen.png", "#ede9fe"),
    "Design": ("/static/design.png", "#fdf4ff"),
    "Video Generation": ("/static/videogen.png", "#fee2e2"),
    "Animation": ("/static/animation.png", "#fef9c3"),
}

def is_logged_in():
    return bool(session.get("logged_in"))

def enrich(tools):
    for tool in tools:
        icon, bg = CATEGORY_ICONS.get(
            tool.get("category", ""),
            ("/static/coding.png", "#f1f5f9")
        )
        tool["icon"] = icon
        tool["icon_bg"] = bg
        tool["pricing"] = tool.get("pricing") or "Free"
        tool["logo"] = tool.get("logo") or "default.png"
        tool["description"] = tool.get("description") or ""
        tool["tags"] = tool.get("tags") or ""
    return tools

def get_all_categories():
    pipeline = [
        {"$group": {"_id": "$category", "tool_count": {"$sum": 1}}},
        {"$sort": {"tool_count": -1}}
    ]
    rows = []
    for item in tools_collection.aggregate(pipeline):
        category_name = item.get("_id") or "Other"
        icon, bg = CATEGORY_ICONS.get(
            category_name, ("/static/coding.png", "#f1f5f9")
        )
        rows.append({
            "category": category_name,
            "tool_count": item["tool_count"],
            "icon": icon,
            "icon_bg": bg
        })
    return rows

@app.route("/")
def default():
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if is_logged_in():
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("register"))
        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "danger")
            return redirect(url_for("register"))
        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for("register"))

        if users_collection.find_one({"email": email}, {"_id": 1}):
            flash("An account with that email already exists.", "danger")
            return redirect(url_for("register"))
        if users_collection.find_one({"username": username}, {"_id": 1}):
            flash("That username is already taken.", "danger")
            return redirect(url_for("register"))

        try:
            users_collection.insert_one({
                "username": username,
                "email": email,
                "password": generate_password_hash(password),
                "created_at": datetime.now(timezone.utc)
            })
        except DuplicateKeyError:
            flash("That username or email is already registered.", "danger")
            return redirect(url_for("register"))

        flash("Account created! You can now sign in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if is_logged_in():
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = users_collection.find_one({"username": username})

        valid = False
        if user:
            stored_password = user.get("password", "")
            try:
                valid = check_password_hash(stored_password, password)
            except (ValueError, TypeError):
                valid = False

            # Support imported legacy plaintext passwords once, then hash them.
            if not valid and stored_password == password:
                valid = True
                users_collection.update_one(
                    {"_id": user["_id"]},
                    {"$set": {"password": generate_password_hash(password)}}
                )

        if user and valid:
            session["logged_in"] = True
            session["username"] = user["username"]
            flash(f"Welcome back, {user['username']}! 👋", "success")
            return redirect(url_for("index"))

        return render_template("login.html", error="Invalid username or password.")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You've been signed out.", "info")
    return redirect(url_for("login"))

@app.route("/index")
def index():
    if not is_logged_in():
        return redirect(url_for("login"))

    total_tools = tools_collection.count_documents({})
    free_count = tools_collection.count_documents({
        "$or": [
            {"pricing": {"$regex": "Free", "$options": "i"}},
            {"pricing": None},
            {"pricing": ""}
        ]
    })

    all_categories = get_all_categories()
    top_categories = all_categories[:5]

    featured_names = ["chatgpt", "claude", "gemini", "replit ai", "cursor"]
    recent_tools = list(tools_collection.find(
        {"name": {"$in": [
            re.compile("^" + re.escape(name) + "$", re.IGNORECASE)
            for name in featured_names
        ]}},
        {
            "_id": 0, "name": 1, "description": 1, "category": 1,
            "url": 1, "pricing": 1, "logo": 1
        }
    ).limit(8))

    return render_template(
        "index.html",
        username=session.get("username"),
        total_tools=total_tools,
        free_count=free_count,
        total_categories=len(all_categories),
        all_categories=all_categories,
        top_categories=top_categories,
        recent_tools=enrich(recent_tools)
    )

@app.route("/category")
def category():
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template(
        "category.html",
        username=session.get("username"),
        categories=get_all_categories()
    )

@app.route("/search")
def search():
    if not is_logged_in():
        return redirect(url_for("login"))

    query = request.args.get("query", "").strip()
    active_category = request.args.get("category", "").strip()
    active_pricing = request.args.get("pricing", "").strip()
    active_sort = request.args.get("sort", "newest").strip()

    try:
        current_page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        current_page = 1

    filters = []
    if query:
        regex = {"$regex": re.escape(query), "$options": "i"}
        filters.append({"$or": [
            {"name": regex}, {"description": regex},
            {"tags": regex}, {"category": regex}
        ]})

    if active_category:
        filters.append({"category": active_category})

    if active_pricing == "Free":
        filters.append({"$or": [
            {"pricing": {"$regex": "Free", "$options": "i"}},
            {"pricing": None},
            {"pricing": ""}
        ]})
    elif active_pricing == "Paid":
        filters.append({"pricing": {"$nin": [None, ""] , "$not": {"$regex": "Free", "$options": "i"}}})

    mongo_filter = {"$and": filters} if filters else {}

    sort_map = {
        "newest": [("created_at", DESCENDING)],
        "oldest": [("created_at", ASCENDING)],
        "name": [("name", ASCENDING)]
    }
    sort_order = sort_map.get(active_sort, sort_map["newest"])

    total_results = tools_collection.count_documents(mongo_filter)
    total_pages = max(1, (total_results + TOOLS_PER_PAGE - 1) // TOOLS_PER_PAGE)
    current_page = min(current_page, total_pages)
    offset = (current_page - 1) * TOOLS_PER_PAGE

    results = list(tools_collection.find(
        mongo_filter,
        {
            "_id": 0, "name": 1, "description": 1, "category": 1,
            "url": 1, "tags": 1, "pricing": 1, "created_at": 1, "logo": 1
        }
    ).sort(sort_order).skip(offset).limit(TOOLS_PER_PAGE))

    all_categories = sorted(
        [item.get("_id") for item in tools_collection.aggregate([
            {"$group": {"_id": "$category"}},
            {"$match": {"_id": {"$ne": None}}}
        ])]
    )

    return render_template(
        "search.html",
        username=session.get("username"),
        query=query,
        results=enrich(results),
        active_category=active_category,
        active_pricing=active_pricing,
        active_sort=active_sort,
        current_page=current_page,
        total_pages=total_pages,
        total_results=total_results,
        all_categories=all_categories,
        categories=all_categories
    )

@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

if __name__ == "__main__":
    app.run(debug=True)
