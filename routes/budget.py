from flask import Blueprint, render_template, request, redirect, session
from datetime import datetime
import calendar
from extensions import spending_collection, budget_collection
from helpers import parse_float, normalize_section, get_prev_month_template, deduplicate_section

budget_bp = Blueprint("budget", __name__)


# API endpoint returns previous month's end balance for carry forward button
@budget_bp.route("/api/prev-month-balance")
def prev_month_balance():
    from flask import jsonify
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    from helpers import calculate_month_summary
    year = int(request.args.get("year"))
    month = int(request.args.get("month"))

    # Get previous month
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    summary = calculate_month_summary(session["user_id"], prev_year, prev_month)
    return jsonify({"end_balance": summary["real_balance"]})

# Main budget tracker handles viewing and saving spending limits income savings, bills and debts
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
            monthly_income_val = parse_float(request.form.get("monthly_income"))
            income_date_str = request.form.get("income_date", "").strip()

            budget_collection.update_one(
                base_query,
                {"$set": {
                    "spending_limit": parse_float(request.form.get("spending_limit")),
                    "monthly_income": monthly_income_val,
                    "account_balance": parse_float(request.form.get("account_balance")),
                    "updated_at": datetime.utcnow()
                }},
                upsert=True
            )

            # Log monthly income as a spending log transaction if amount > 0 and date provided
            if monthly_income_val > 0 and income_date_str:
                try:
                    income_date = datetime.strptime(income_date_str, "%Y-%m-%d")
                    # Remove any existing monthly income transaction for this month
                    spending_collection.delete_one({
                        "user_id": session["user_id"],
                        "type": "income",
                        "category": "Salary",
                        "description": "Monthly Income",
                        "date": {
                            "$gte": datetime(form_year_int, form_month_int, 1),
                            "$lt": datetime(form_year_int + 1, 1, 1) if form_month_int == 12 else datetime(form_year_int, form_month_int + 1, 1)
                        }
                    })
                    # Insert fresh transaction
                    spending_collection.insert_one({
                        "user_id": session["user_id"],
                        "date": income_date,
                        "category": "Salary",
                        "description": "Monthly Income",
                        "amount": monthly_income_val,
                        "type": "income",
                        "created_at": datetime.utcnow()
                    })
                except ValueError:
                    pass
            
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
            # Also delete the auto-logged monthly income transaction
            spending_collection.delete_one({
                "user_id": session["user_id"],
                "type": "income",
                "category": "Salary",
                "description": "Monthly Income",
                "date": {
                    "$gte": datetime(form_year_int, form_month_int, 1),
                    "$lt": datetime(form_year_int + 1, 1, 1) if form_month_int == 12 else datetime(form_year_int, form_month_int + 1, 1)
                }
            })

        elif action in ("save_savings", "save_bills", "save_debts"):
            field = {"save_savings": "savings", "save_bills": "bills", "save_debts": "debts"}[action]
            prefix = {"save_savings": "savings", "save_bills": "bills", "save_debts": "debts"}[action]

            keys = request.form.getlist(f"{prefix}_key")
            vals = request.form.getlist(f"{prefix}_val")

            new_dict = deduplicate_section(keys, vals)
            
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
    account_balance = parse_float(budget_doc.get("account_balance"))

    # Find existing monthly income transaction date for this month
    month_start_check = datetime(selected_year_int, selected_month_int, 1)
    month_end_check = datetime(selected_year_int + 1, 1, 1) if selected_month_int == 12 else datetime(selected_year_int, selected_month_int + 1, 1)
    existing_income_tx = spending_collection.find_one({
        "user_id": session["user_id"],
        "type": "income",
        "category": "Salary",
        "description": "Monthly Income",
        "date": {"$gte": month_start_check, "$lt": month_end_check}
    })
    income_date = existing_income_tx["date"].strftime("%Y-%m-%d") if existing_income_tx else f"{selected_year_int}-{str(selected_month_int).zfill(2)}-01"

    # Carry forward balance from previous month if not set
    if account_balance == 0.0:
        if selected_month_int == 1:
            prev_year, prev_month = selected_year_int - 1, 12
        else:
            prev_year, prev_month = selected_year_int, selected_month_int - 1

        prev_doc = budget_collection.find_one({
            "user_id": session["user_id"],
            "year": prev_year,
            "month": prev_month
        }) or {}

        prev_balance = parse_float(prev_doc.get("account_balance"))
        prev_income = parse_float(prev_doc.get("monthly_income"))
        prev_savings = sum(normalize_section(prev_doc.get("savings", {})).values())
        prev_bills = sum(normalize_section(prev_doc.get("bills", {})).values())
        prev_debts = sum(normalize_section(prev_doc.get("debts", {})).values())
        prev_deductions = prev_savings + prev_bills + prev_debts

        from datetime import datetime as dt
        prev_month_start = dt(prev_year, prev_month, 1)
        if prev_month == 12:
            prev_month_end = dt(prev_year + 1, 1, 1)
        else:
            prev_month_end = dt(prev_year, prev_month + 1, 1)

        prev_transactions = list(spending_collection.find({
            "user_id": session["user_id"],
            "date": {"$gte": prev_month_start, "$lt": prev_month_end}
        }))

        prev_income_log = sum(t["amount"] for t in prev_transactions if t.get("type") == "income" and not (t.get("category") == "Salary" and t.get("description") == "Monthly Income"))
        prev_expense_log = sum(t["amount"] for t in prev_transactions if t.get("type") == "expense")

        account_balance = round(
            prev_balance + prev_income_log - prev_expense_log, 2
        )

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
    current_budget = round(net_spending_log - planned_deductions, 2)
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
        account_balance=account_balance,
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
        spending_limit_used_pct=spending_limit_used_pct,
        income_date=income_date,
        active_page="budget"
    )
    
    