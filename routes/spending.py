from flask import Blueprint, render_template, request, redirect, session, jsonify
from datetime import datetime, timedelta
from collections import defaultdict
from bson.objectid import ObjectId
from extensions import spending_collection

spending_bp = Blueprint("spending", __name__)

PREMADE_CATEGORIES = [
    "Food", "Transport", "Bills", "Entertainment",
    "Shopping", "Health", "Education", "Salary", "Investments"
]


@spending_bp.route("/spending-log", methods=["GET", "POST"])
def spending_log():
    if "user_id" not in session:
        return redirect("/login")

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

    filter_option = request.args.get("filter", "all")
    month_option = request.args.get("month")
    query = {"user_id": session["user_id"]}

    if filter_option == "7":
        query["date"] = {"$gte": datetime.utcnow() - timedelta(days=7)}
    elif filter_option == "30":
        query["date"] = {"$gte": datetime.utcnow() - timedelta(days=30)}
    elif filter_option == "90":
        query["date"] = {"$gte": datetime.utcnow() - timedelta(days=90)}

    if month_option:
        month_option = int(month_option)
        query["$expr"] = {"$eq": [{"$month": "$date"}, month_option]}

    transactions = list(spending_collection.find(query).sort("date", -1))

    category_totals = defaultdict(float)
    for t in transactions:
        if t["type"] == "expense":
            category_totals[t["category"]] += t["amount"]

    chart_labels = list(category_totals.keys())
    chart_values = list(category_totals.values())

    if request.args.get("format") == "json":
        return jsonify({
            "transactions": [{
                "id": str(t["_id"]),
                "date": t["date"].strftime("%d %b %Y"),
                "category": t["category"],
                "description": t["description"],
                "type": t["type"],
                "amount": t["amount"]
            } for t in transactions],
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


@spending_bp.route("/delete-transaction/<id>")
def delete_transaction(id):
    if "user_id" not in session:
        return redirect("/login")
    spending_collection.delete_one({"_id": ObjectId(id), "user_id": session["user_id"]})
    return redirect("/spending-log")


@spending_bp.route("/update-transaction/<id>", methods=["POST"])
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