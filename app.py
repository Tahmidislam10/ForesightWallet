from flask import Flask, render_template, request, redirect, session, jsonify
from pymongo import MongoClient
from flask_bcrypt import Bcrypt
from datetime import datetime
from bson.objectid import ObjectId
from collections import defaultdict
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "supersecretkey"

bcrypt = Bcrypt(app)

# ==========================
# MONGODB CONNECTION
# ==========================

client = MongoClient(
    "mongodb+srv://foresightUser:iu62PSaj9C4n7L1P@cluster0.feed1o0.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
)

db = client["foresight_wallet"]

users_collection = db["users"]
spending_collection = db["spending"]



# ==========================
# ROUTES
# ==========================

@app.route("/")
def landing():
    return render_template("landing.html")


# ==========================
# REGISTER
# ==========================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        existing_user = users_collection.find_one(
            {"email": request.form["email"]}
        )

        if existing_user:
            return "User already exists"

        hashed_pw = bcrypt.generate_password_hash(
            request.form["password"]
        ).decode("utf-8")

        new_user = {
            "first_name": request.form["first_name"],
            "last_name": request.form["last_name"],
            "email": request.form["email"],
            "password": hashed_pw
        }

        result = users_collection.insert_one(new_user)

        session["user_id"] = str(result.inserted_id)

        return redirect("/dashboard")

    return render_template("register.html")


# ==========================
# LOGIN
# ==========================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = users_collection.find_one(
            {"email": request.form["email"]}
        )

        if user and bcrypt.check_password_hash(
            user["password"],
            request.form["password"]
        ):
            session["user_id"] = str(user["_id"])
            return redirect("/dashboard")

        return "Invalid email or password"

    return render_template("login.html")


# ==========================
# DASHBOARD
# ==========================

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    user_spending = list(
        spending_collection.find(
            {"user_id": session["user_id"]}
        )
    )

    if len(user_spending) == 0:
        return render_template("dashboard.html", empty=True)

    total_income = sum(
        s["amount"] for s in user_spending if s["type"] == "income"
    )

    total_expense = sum(
        s["amount"] for s in user_spending if s["type"] == "expense"
    )

    savings = total_income - total_expense

    return render_template(
        "dashboard.html",
        empty=False,
        total_income=total_income,
        total_expense=total_expense,
        savings=savings,
        transactions=user_spending
    )


# ==========================
# delete transaction
# ==========================

@app.route("/delete-transaction/<id>")
def delete_transaction(id):
    if "user_id" not in session:
        return redirect("/login")

    spending_collection.delete_one({
        "_id": ObjectId(id),
        "user_id": session["user_id"]
    })

    return redirect("/spending-log")


# ==========================
# update transaction
# ==========================

@app.route("/update-transaction/<id>", methods=["POST"])
def update_transaction(id):
    if "user_id" not in session:
        return redirect("/login")

    category = request.form["category"]
    if category == "Other":
        category = request.form.get("custom_category")

    spending_collection.update_one(
        {"_id": ObjectId(id), "user_id": session["user_id"]},
        {"$set": {
            "date": datetime.strptime(request.form["date"], "%Y-%m-%d"),
            "category": category,
            "description": request.form["description"],
            "amount": float(request.form["amount"]),
            "type": request.form["type"]
        }}
    )

    return redirect("/spending-log")

# ==========================
# SPENDING LOG
# ==========================

PREMADE_CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Entertainment",
    "Shopping",
    "Health",
    "Education",
    "Salary",
    "Investments"
]

@app.route("/spending-log", methods=["GET", "POST"])
def spending_log():

    if "user_id" not in session:
        return redirect("/login")

    # ------------------------
    # HANDLE POST (ADD ENTRY)
    # ------------------------
    if request.method == "POST":

        category = request.form["category"]
        if category == "Other":
            category = request.form.get("custom_category")

        new_entry = {
            "user_id": session["user_id"],
            "date": datetime.strptime(request.form["date"], "%Y-%m-%d"),
            "category": category,
            "description": request.form["description"],
            "amount": float(request.form["amount"]),
            "type": request.form["type"],
            "created_at": datetime.utcnow()
        }

        spending_collection.insert_one(new_entry)
        return redirect("/spending-log")

    # ------------------------
    # HANDLE FILTERS
    # ------------------------

    filter_option = request.args.get("filter", "all")
    month_option = request.args.get("month")

    query = {"user_id": session["user_id"]}

    # 🔹 7 / 30 / 90 filters
    if filter_option == "7":
        cutoff = datetime.utcnow() - timedelta(days=7)
        query["date"] = {"$gte": cutoff}

    elif filter_option == "30":
        cutoff = datetime.utcnow() - timedelta(days=30)
        query["date"] = {"$gte": cutoff}

    elif filter_option == "90":
        cutoff = datetime.utcnow() - timedelta(days=90)
        query["date"] = {"$gte": cutoff}

    # 🔹 MONTH FILTER (overrides date filter if selected)
    if month_option:
        month_option = int(month_option)
        query["$expr"] = {
            "$eq": [{"$month": "$date"}, month_option]
        }

    # ------------------------
    # FETCH TRANSACTIONS
    # ------------------------

    transactions = list(
        spending_collection.find(query).sort("date", -1)
    )

    # ------------------------
    # BUILD CHART DATA
    # ------------------------

    category_totals = defaultdict(float)

    for t in transactions:
        if t["type"] == "expense":
            category_totals[t["category"]] += t["amount"]

    chart_labels = list(category_totals.keys())
    chart_values = list(category_totals.values())

    if request.args.get("format") == "json":
        serialized_transactions = []
        for t in transactions:
            serialized_transactions.append({
                "id": str(t["_id"]),
                "date": t["date"].strftime("%d %b %Y"),
                "category": t["category"],
                "description": t["description"],
                "type": t["type"],
                "amount": t["amount"]
            })

        return jsonify({
            "transactions": serialized_transactions,
            "chart_labels": chart_labels,
            "chart_values": chart_values,
            "active_filter": filter_option,
            "active_month": month_option
        })

    return render_template(
        "spending_log.html",
        transactions=transactions,
        categories=PREMADE_CATEGORIES,
        chart_labels=chart_labels,
        chart_values=chart_values,
        active_filter=filter_option,
        active_month=month_option
    )

# ==========================
# LOGOUT
# ==========================

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)
