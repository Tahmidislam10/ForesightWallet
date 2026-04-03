import calendar
from datetime import datetime
from collections import defaultdict
from extensions import budget_collection, spending_collection


def parse_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_section(raw):
    result = {}
    for k, v in raw.items():
        if isinstance(v, dict):
            result[k] = parse_float(v.get("amount", 0.0))
        else:
            result[k] = parse_float(v)
    return result


def deduplicate_section(keys, vals):
    new_dict = {}
    seen_keys = {}
    for k, v in zip(keys, vals):
        clean_key = k.strip()
        if not clean_key:
            continue
        lower_key = clean_key.lower()
        if lower_key in seen_keys:
            existing_key = seen_keys[lower_key]
            new_dict[existing_key] = round(new_dict[existing_key] + parse_float(v), 2)
        else:
            seen_keys[lower_key] = clean_key
            new_dict[clean_key] = parse_float(v)
    return new_dict


def get_prev_month_template(user_id, year, month, field, default):
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    prev_doc = budget_collection.find_one({
        "user_id": user_id,
        "year": prev_year,
        "month": prev_month
    }) or {}

    prev_data = prev_doc.get(field)
    if prev_data:
        normalized = normalize_section(prev_data)
        return {k: 0.0 for k in normalized.keys()}
    return default


def get_planned_deductions_history(user_id, months):
    result = []
    for year, month in months:
        budget_doc = budget_collection.find_one({
            "user_id": user_id,
            "year": year,
            "month": month
        }) or {}

        savings = normalize_section(budget_doc.get("savings", {}))
        bills = normalize_section(budget_doc.get("bills", {}))
        debts = normalize_section(budget_doc.get("debts", {}))

        result.append({
            "label": f"{calendar.month_abbr[month]} {str(year)[2:]}",
            "savings": round(sum(savings.values()), 2),
            "bills": round(sum(bills.values()), 2),
            "debts": round(sum(debts.values()), 2),
        })
    return result

def get_deductions_summary(user_id, months):
    """
    Returns aggregated totals for each individual savings item,
    plus total bills and total debts across the given months.
    """
    savings_totals = defaultdict(float)
    bills_total = 0.0
    debts_total = 0.0

    for year, month in months:
        budget_doc = budget_collection.find_one({
            "user_id": user_id,
            "year": year,
            "month": month
        }) or {}

        savings = normalize_section(budget_doc.get("savings", {}))
        bills = normalize_section(budget_doc.get("bills", {}))
        debts = normalize_section(budget_doc.get("debts", {}))

        for k, v in savings.items():
            # Normalise key to lowercase for deduplication, but preserve first seen casing
            lower_k = k.strip().lower()
            matched_key = next((existing for existing in savings_totals if existing.lower() == lower_k), None)
            if matched_key:
                savings_totals[matched_key] += v
            else:
                savings_totals[k.strip()] += v

        bills_total += sum(bills.values())
        debts_total += sum(debts.values())

    return {
        "savings": {k: round(v, 2) for k, v in savings_totals.items()},
        "bills_total": round(bills_total, 2),
        "debts_total": round(debts_total, 2)
    }


def calculate_month_summary(user_id, year, month):
    month_start = datetime(year, month, 1)
    if month == 12:
        next_month_start = datetime(year + 1, 1, 1)
    else:
        next_month_start = datetime(year, month + 1, 1)

    transactions = list(spending_collection.find({
        "user_id": user_id,
        "date": {"$gte": month_start, "$lt": next_month_start}
    }))

    income_total = sum(t["amount"] for t in transactions if t.get("type") == "income")
    expense_total = sum(t["amount"] for t in transactions if t.get("type") == "expense")

    budget_doc = budget_collection.find_one({
        "user_id": user_id,
        "year": year,
        "month": month
    }) or {}

    monthly_income = float(budget_doc.get("monthly_income", 0))
    spending_limit = float(budget_doc.get("spending_limit", 0))
    account_balance = float(budget_doc.get("account_balance", 0))

    savings = normalize_section(budget_doc.get("savings", {}))
    bills = normalize_section(budget_doc.get("bills", {}))
    debts = normalize_section(budget_doc.get("debts", {}))

    savings_total = round(sum(savings.values()), 2)
    bills_total = round(sum(bills.values()), 2)
    debts_total = round(sum(debts.values()), 2)
    planned_deductions = savings_total + bills_total + debts_total

    starting_budget = monthly_income
    net_spending_log = income_total - expense_total
    current_budget = starting_budget - planned_deductions + net_spending_log

    # Real balance calculation
    real_balance = round(account_balance + monthly_income + income_total - expense_total - planned_deductions, 2)

    today = datetime.utcnow()
    days_passed = today.day if (today.month == month and today.year == year) else calendar.monthrange(year, month)[1]
    total_days = calendar.monthrange(year, month)[1]
    burn_rate = expense_total / days_passed if days_passed > 0 else 0
    projected_expense = burn_rate * total_days
    projected_end_balance = account_balance + monthly_income + income_total - planned_deductions - projected_expense
    budget_usage_pct = (expense_total / spending_limit) * 100 if spending_limit > 0 else 0

    spending_limit_remaining = round(spending_limit - expense_total, 2)

    return {
        "income_total": round(income_total, 2),
        "expense_total": round(expense_total, 2),
        "net_total": round(income_total - expense_total, 2),
        "savings_total": round(savings_total, 2),
        "bills_total": round(bills_total, 2),
        "debts_total": round(debts_total, 2),
        "planned_deductions": round(planned_deductions, 2),
        "current_budget": round(current_budget, 2),
        "spending_limit_remaining": spending_limit_remaining,
        "spending_limit": round(spending_limit, 2),
        "real_balance": real_balance,
        "account_balance": round(account_balance, 2),
        "burn_rate": round(burn_rate, 2),
        "projected_expense": round(projected_expense, 2),
        "projected_end_balance": round(projected_end_balance, 2),
        "budget_usage_pct": round(budget_usage_pct, 1)
    }