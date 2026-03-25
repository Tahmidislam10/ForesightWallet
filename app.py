from flask import Flask, render_template, request, redirect, session, jsonify
from pymongo import MongoClient
from flask_bcrypt import Bcrypt
from datetime import datetime
from bson.objectid import ObjectId
from collections import defaultdict
from datetime import datetime, timedelta
import calendar

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
budget_collection = db["budgets"]

def calculate_month_summary(user_id, year, month):
    month_start = datetime(year, month, 1)

    if month == 12:
        next_month_start = datetime(year + 1, 1, 1)
    else:
        next_month_start = datetime(year, month + 1, 1)

    # --------------------------
    # GET TRANSACTIONS
    # --------------------------
    transactions = list(spending_collection.find({
        "user_id": user_id,
        "date": {"$gte": month_start, "$lt": next_month_start}
    }))

    income_total = sum(
        t["amount"] for t in transactions if t.get("type") == "income"
    )

    expense_total = sum(
        t["amount"] for t in transactions if t.get("type") == "expense"
    )

    # --------------------------
    # GET BUDGET DOCUMENT
    # --------------------------
    budget_doc = budget_collection.find_one({
        "user_id": user_id,
        "year": year,
        "month": month
    }) or {}

    monthly_income = float(budget_doc.get("monthly_income", 0))
    spending_limit = float(budget_doc.get("spending_limit", 0))

    savings = budget_doc.get("savings", {})
    bills = budget_doc.get("bills", {})
    debts = budget_doc.get("debts", {})

    savings_total = sum(float(v or 0) for v in savings.values())
    bills_total = sum(float(v or 0) for v in bills.values())
    debts_total = sum(float(v or 0) for v in debts.values())

    planned_deductions = savings_total + bills_total + debts_total

    starting_budget = monthly_income
    net_spending_log = income_total - expense_total
    current_budget = starting_budget - planned_deductions + net_spending_log

    # --------------------------
    # BURN RATE + PROJECTION
    # --------------------------
    today = datetime.utcnow()

    if today.month == month and today.year == year:
        days_passed = today.day
    else:
        days_passed = calendar.monthrange(year, month)[1]

    total_days = calendar.monthrange(year, month)[1]

    if days_passed > 0:
        burn_rate = expense_total / days_passed
    else:
        burn_rate = 0

    projected_expense = burn_rate * total_days
    projected_end_balance = starting_budget - planned_deductions - projected_expense + income_total

    if spending_limit > 0:
        budget_usage_pct = (expense_total / spending_limit) * 100
    else:
        budget_usage_pct = 0

    return {
        "income_total": round(income_total, 2),
        "expense_total": round(expense_total, 2),
        "net_total": round(income_total - expense_total, 2),
        "savings_total": round(savings_total, 2),
        "bills_total": round(bills_total, 2),
        "debts_total": round(debts_total, 2),
        "planned_deductions": round(planned_deductions, 2),
        "current_budget": round(current_budget, 2),
        "burn_rate": round(burn_rate, 2),
        "projected_expense": round(projected_expense, 2),
        "projected_end_balance": round(projected_end_balance, 2),
        "budget_usage_pct": round(budget_usage_pct, 1)
    }


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

    user_id = session["user_id"]
    now = datetime.utcnow()
   

    # -------------------------
    # FILTER PARAMETERS
    # -------------------------
    range_option = request.args.get("range", "30")
    month_option = request.args.get("month", str(now.month))
    compare = request.args.get("compare", "false")
    
    # -------------------------
    # BUILD ANCHOR DATE
    # -------------------------
    if month_option:
        selected_month = int(month_option)
        selected_year = now.year

        # Anchor at END of selected month
        if selected_month == 12:
            anchor_date = datetime(selected_year + 1, 1, 1)
        else:
            anchor_date = datetime(selected_year, selected_month + 1, 1)
    else:
        anchor_date = now
    
    # -------------------------
    # MONTH FOR FINANCIAL ENGINE
    # -------------------------
    if month_option:
        try:
            selected_month = int(month_option)
        except ValueError:
            selected_month = now.month
    else:
        selected_month = now.month

    summary = calculate_month_summary(
        user_id,
        now.year,
        selected_month
    )
    

   

    # -------------------------
    # DATE RANGE FILTER (ANCHOR BASED)
    # -------------------------
    if range_option == "7":
        # If viewing current month, use today as anchor, otherwise use end of selected month
        if selected_month == now.month and selected_year == now.year:
            start_date = now - timedelta(days=7)
            anchor_date = now
        else:
            start_date = anchor_date - timedelta(days=7)

    elif range_option == "30":
        if month_option:
            # Full selected month
            start_date = datetime(selected_year, selected_month, 1)
        else:
            start_date = anchor_date - timedelta(days=30)

    elif range_option == "90":
        start_date = anchor_date - timedelta(days=90)

    else:
        start_date = anchor_date - timedelta(days=30)


    query = {
        "user_id": user_id,
        "date": {"$gte": start_date, "$lt": anchor_date}
    }

    transactions = list(spending_collection.find(query).sort("date", 1))
    income_total = round(
        sum(t["amount"] for t in transactions if t.get("type") == "income"),
        2
    )
    expense_total = round(
        sum(t["amount"] for t in transactions if t.get("type") == "expense"),
        2
    )
    net_total = round(income_total - expense_total, 2)

    # -------------------------
    # DAILY AGGREGATION (CONTINUOUS)
    # -------------------------
    daily_totals = defaultdict(float)

    for t in transactions:
        if t["type"] == "expense":
            date_key = t["date"].strftime("%Y-%m-%d")
            daily_totals[date_key] += t["amount"]

    labels = []
    values = []
    current_date = start_date.date()
    end_date = (anchor_date - timedelta(days=1)).date()

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        labels.append(date_str)
        values.append(round(daily_totals.get(date_str, 0), 2))
        current_date += timedelta(days=1)

    # -------------------------
    # COMPARISON LOGIC
    # -------------------------
    comparison_values = []

    if compare == "true":

        previous_daily = defaultdict(float)

        if month_option:
            # Current selected month
            selected_month = int(month_option)
            selected_year = now.year

            # Previous month logic
            if selected_month == 1:
                prev_month = 12
                prev_year = selected_year - 1
            else:
                prev_month = selected_month - 1
                prev_year = selected_year

            prev_start = datetime(prev_year, prev_month, 1)

            if prev_month == 12:
                prev_end = datetime(prev_year + 1, 1, 1)
            else:
                prev_end = datetime(prev_year, prev_month + 1, 1)

            previous_transactions = list(spending_collection.find({
                "user_id": user_id,
                "date": {"$gte": prev_start, "$lt": prev_end}
            }))

            # Align by day number (1–31)
            for t in previous_transactions:
                if t["type"] == "expense":
                    day_number = t["date"].day
                    previous_daily[day_number] += t["amount"]

            # Build comparison aligned to current month labels
            comparison_values = []

            for label in labels:
                day_number = int(label.split("-")[-1])
                comparison_values.append(round(previous_daily.get(day_number, 0), 2))

        else:
            # fallback for 7/30/90 logic
            period_length = (anchor_date - start_date).days
            previous_start = start_date - timedelta(days=period_length)
            previous_end = start_date

            previous_transactions = list(spending_collection.find({
                "user_id": user_id,
                "date": {"$gte": previous_start, "$lt": previous_end}
            }))

            previous_daily = defaultdict(float)

            for t in previous_transactions:
                if t["type"] == "expense":
                    key = t["date"].strftime("%Y-%m-%d")
                    previous_daily[key] += t["amount"]

            comparison_values = [
                round(previous_daily.get(d, 0), 2) for d in labels
            ]

    return render_template(
        "dashboard.html",
        labels=labels,
        values=values,
        comparison_values=comparison_values,
        compare=compare,
        range_option=range_option,
        month_option=month_option,
        income_total=income_total,
        expense_total=expense_total,
        net_total=net_total,
        summary=summary
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


def parse_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@app.route("/budget-tracker", methods=["GET", "POST"])
def budget_tracker():
    if "user_id" not in session:
        return redirect("/login")

    now = datetime.utcnow()
    selected_year = request.args.get("year", str(now.year))
    selected_month = request.args.get("month", str(now.month))

    try:
        selected_year_int = int(selected_year)
    except ValueError:
        selected_year_int = now.year

    try:
        selected_month_int = int(selected_month)
        if selected_month_int < 1 or selected_month_int > 12:
            selected_month_int = now.month
    except ValueError:
        selected_month_int = now.month

    if request.method == "POST":
        form_year = request.form.get("year", str(selected_year_int))
        form_month = request.form.get("month", str(selected_month_int))
        action = request.form.get("action", "")

        try:
            form_year_int = int(form_year)
        except ValueError:
            form_year_int = selected_year_int

        try:
            form_month_int = int(form_month)
            if form_month_int < 1 or form_month_int > 12:
                form_month_int = selected_month_int
        except ValueError:
            form_month_int = selected_month_int

        base_query = {
            "user_id": session["user_id"],
            "year": form_year_int,
            "month": form_month_int
        }

        if action == "save_overview":
            budget_collection.update_one(
                base_query,
                {"$set": {
                    "spending_limit": parse_float(request.form.get("spending_limit")),
                    "monthly_income": parse_float(request.form.get("monthly_income")),
                    "updated_at": datetime.utcnow()
                }},
                upsert=True
            )
        elif action == "reset_overview":
            budget_collection.update_one(
                base_query,
                {"$set": {
                    "spending_limit": 0.0,
                    "monthly_income": 0.0,
                    "updated_at": datetime.utcnow()
                }},
                upsert=True
            )
        elif action == "save_savings":
            budget_collection.update_one(
                base_query,
                {"$set": {
                    "savings.emergency_fund": parse_float(request.form.get("emergency_fund")),
                    "savings.house_downpayment": parse_float(request.form.get("house_downpayment")),
                    "savings.vacation_fund": parse_float(request.form.get("vacation_fund")),
                    "updated_at": datetime.utcnow()
                }},
                upsert=True
            )
        elif action == "save_bills":
            budget_collection.update_one(
                base_query,
                {"$set": {
                    "bills.electricity": parse_float(request.form.get("electricity")),
                    "bills.water": parse_float(request.form.get("water")),
                    "bills.gas": parse_float(request.form.get("gas")),
                    "bills.internet": parse_float(request.form.get("internet")),
                    "bills.cellphone": parse_float(request.form.get("cellphone")),
                    "updated_at": datetime.utcnow()
                }},
                upsert=True
            )
        elif action == "save_debts":
            budget_collection.update_one(
                base_query,
                {"$set": {
                    "debts.student_loan": parse_float(request.form.get("student_loan")),
                    "debts.amex": parse_float(request.form.get("amex")),
                    "updated_at": datetime.utcnow()
                }},
                upsert=True
            )

        return redirect(f"/budget-tracker?year={form_year_int}&month={form_month_int}")

    budget_doc = budget_collection.find_one({
        "user_id": session["user_id"],
        "year": selected_year_int,
        "month": selected_month_int
    }) or {}

    spending_limit = parse_float(budget_doc.get("spending_limit"))
    monthly_income = parse_float(budget_doc.get("monthly_income"))

    savings = budget_doc.get("savings", {})
    bills = budget_doc.get("bills", {})
    debts = budget_doc.get("debts", {})

    savings_data = {
        "emergency_fund": parse_float(savings.get("emergency_fund")),
        "house_downpayment": parse_float(savings.get("house_downpayment")),
        "vacation_fund": parse_float(savings.get("vacation_fund"))
    }
    bills_data = {
        "electricity": parse_float(bills.get("electricity")),
        "water": parse_float(bills.get("water")),
        "gas": parse_float(bills.get("gas")),
        "internet": parse_float(bills.get("internet")),
        "cellphone": parse_float(bills.get("cellphone"))
    }
    debts_data = {
        "student_loan": parse_float(debts.get("student_loan")),
        "amex": parse_float(debts.get("amex"))
    }

    month_start = datetime(selected_year_int, selected_month_int, 1)
    if selected_month_int == 12:
        next_month_start = datetime(selected_year_int + 1, 1, 1)
    else:
        next_month_start = datetime(selected_year_int, selected_month_int + 1, 1)

    month_transactions = list(spending_collection.find({
        "user_id": session["user_id"],
        "date": {"$gte": month_start, "$lt": next_month_start}
    }))

    month_income_total = round(
        sum(t["amount"] for t in month_transactions if t.get("type") == "income"),
        2
    )
    month_expense_total = round(
        sum(t["amount"] for t in month_transactions if t.get("type") == "expense"),
        2
    )

    savings_total = round(sum(savings_data.values()), 2)
    bills_total = round(sum(bills_data.values()), 2)
    debts_total = round(sum(debts_data.values()), 2)
    planned_deductions = round(savings_total + bills_total + debts_total, 2)

    starting_budget = round(monthly_income, 2)
    net_spending_log = round(month_income_total - month_expense_total, 2)
    current_budget = round(starting_budget - planned_deductions + net_spending_log, 2)
    spending_limit_spent = round(month_expense_total, 2)
    spending_limit_remaining = round(spending_limit - spending_limit_spent, 2)
    if spending_limit > 0:
        spending_limit_used_pct = round((spending_limit_spent / spending_limit) * 100, 1)
    else:
        spending_limit_used_pct = 0.0

    years = [now.year - 1, now.year, now.year + 1]
    month_options = [
        {"value": i, "label": calendar.month_name[i]}
        for i in range(1, 13)
    ]

    return render_template(
        "budget_tracker.html",
        selected_year=selected_year_int,
        selected_month=selected_month_int,
        years=years,
        month_options=month_options,
        spending_limit=spending_limit,
        monthly_income=monthly_income,
        savings_data=savings_data,
        bills_data=bills_data,
        debts_data=debts_data,
        month_income_total=month_income_total,
        month_expense_total=month_expense_total,
        savings_total=savings_total,
        bills_total=bills_total,
        debts_total=debts_total,
        planned_deductions=planned_deductions,
        starting_budget=starting_budget,
        net_spending_log=net_spending_log,
        current_budget=current_budget,
        spending_limit_spent=spending_limit_spent,
        spending_limit_remaining=spending_limit_remaining,
        spending_limit_used_pct=spending_limit_used_pct
    )

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
