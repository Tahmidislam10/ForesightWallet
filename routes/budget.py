from flask import Blueprint, render_template, request, redirect, session
from datetime import datetime
import calendar
from extensions import spending_collection, budget_collection
from helpers import parse_float, normalize_section, get_prev_month_template

budget_bp = Blueprint("budget", __name__)


@budget_bp.route("/budget-tracker", methods=["GET", "POST"])
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

        elif action in ("save_savings", "save_bills", "save_debts"):
            field = {"save_savings": "savings", "save_bills": "bills", "save_debts": "debts"}[action]
            prefix = {"save_savings": "savings", "save_bills": "bills", "save_debts": "debts"}[action]

            keys = request.form.getlist(f"{prefix}_key")
            vals = request.form.getlist(f"{prefix}_val")

            new_dict = {}
            for k, v in zip(keys, vals):
                if k.strip():
                    new_dict[k.strip()] = parse_float(v)

            budget_collection.update_one(
                base_query,
                {"$set": {field: new_dict, "updated_at": datetime.utcnow()}},
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

    raw_savings = budget_doc.get("savings")
    raw_bills = budget_doc.get("bills")
    raw_debts = budget_doc.get("debts")

    default_savings = {"Emergency Fund": 0.0, "House Downpayment": 0.0, "Vacation Fund": 0.0}
    default_bills = {"Electricity": 0.0, "Water": 0.0, "Gas": 0.0, "Internet": 0.0, "Cellphone": 0.0}
    default_debts = {"Student Loan": 0.0, "Amex": 0.0}

    savings_data = normalize_section(raw_savings) if raw_savings is not None else get_prev_month_template(
        session["user_id"], selected_year_int, selected_month_int, "savings", default_savings
    )
    bills_data = normalize_section(raw_bills) if raw_bills is not None else get_prev_month_template(
        session["user_id"], selected_year_int, selected_month_int, "bills", default_bills
    )
    debts_data = normalize_section(raw_debts) if raw_debts is not None else get_prev_month_template(
        session["user_id"], selected_year_int, selected_month_int, "debts", default_debts
    )

    month_start = datetime(selected_year_int, selected_month_int, 1)
    next_month_start = datetime(selected_year_int + 1, 1, 1) if selected_month_int == 12 else datetime(selected_year_int, selected_month_int + 1, 1)

    month_transactions = list(spending_collection.find({
        "user_id": session["user_id"],
        "date": {"$gte": month_start, "$lt": next_month_start}
    }))

    month_income_total = round(sum(t["amount"] for t in month_transactions if t.get("type") == "income"), 2)
    month_expense_total = round(sum(t["amount"] for t in month_transactions if t.get("type") == "expense"), 2)

    savings_total = round(sum(savings_data.values()), 2)
    bills_total = round(sum(bills_data.values()), 2)
    debts_total = round(sum(debts_data.values()), 2)
    planned_deductions = round(savings_total + bills_total + debts_total, 2)

    starting_budget = round(monthly_income, 2)
    net_spending_log = round(month_income_total - month_expense_total, 2)
    current_budget = round(starting_budget - planned_deductions + net_spending_log, 2)
    spending_limit_spent = round(month_expense_total, 2)
    spending_limit_remaining = round(spending_limit - spending_limit_spent, 2)
    spending_limit_used_pct = round((spending_limit_spent / spending_limit) * 100, 1) if spending_limit > 0 else 0.0

    years = [now.year - 1, now.year, now.year + 1]
    month_options = [{"value": i, "label": calendar.month_name[i]} for i in range(1, 13)]

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