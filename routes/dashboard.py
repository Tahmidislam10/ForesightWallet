from flask import Blueprint, render_template, request, redirect, session
from datetime import datetime, timedelta
from collections import defaultdict
from extensions import spending_collection, budget_collection
from helpers import calculate_month_summary, get_planned_deductions_history, get_deductions_summary, normalize_section
import calendar

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    now = datetime.utcnow()

    range_option = request.args.get("range", "30")
    month_option = request.args.get("month", str(now.month))
    compare = request.args.get("compare", "false")

    if month_option:
        selected_month = int(month_option)
        selected_year = now.year
        if selected_month == 12:
            anchor_date = datetime(selected_year + 1, 1, 1)
        else:
            anchor_date = datetime(selected_year, selected_month + 1, 1)
    else:
        anchor_date = now

    if month_option:
        try:
            selected_month = int(month_option)
        except ValueError:
            selected_month = now.month
    else:
        selected_month = now.month

    summary = calculate_month_summary(user_id, now.year, selected_month)

    if range_option == "7":
        if selected_month == now.month and selected_year == now.year:
            start_date = now - timedelta(days=7)
            anchor_date = now
        else:
            start_date = anchor_date - timedelta(days=7)
    elif range_option == "30":
        if month_option:
            start_date = datetime(selected_year, selected_month, 1)
        else:
            start_date = anchor_date - timedelta(days=30)
    elif range_option == "90":
        start_date = anchor_date - timedelta(days=90)
    else:
        start_date = anchor_date - timedelta(days=30)

    query = {"user_id": user_id, "date": {"$gte": start_date, "$lt": anchor_date}}
    transactions = list(spending_collection.find(query).sort("date", 1))

    income_total = round(sum(t["amount"] for t in transactions if t.get("type") == "income"), 2)
    expense_total = round(sum(t["amount"] for t in transactions if t.get("type") == "expense"), 2)
    net_total = round(income_total - expense_total, 2)

    daily_totals = defaultdict(float)
    for t in transactions:
        if t["type"] == "expense":
            daily_totals[t["date"].strftime("%Y-%m-%d")] += t["amount"]

    daily_income_totals = defaultdict(float)
    for t in transactions:
        if t["type"] == "income":
            daily_income_totals[t["date"].strftime("%Y-%m-%d")] += t["amount"]

    labels = []
    values = []
    income_values = []
    current_date = start_date.date()
    end_date = (anchor_date - timedelta(days=1)).date()
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        labels.append(date_str)
        values.append(round(daily_totals.get(date_str, 0), 2))
        income_values.append(round(daily_income_totals.get(date_str, 0), 2))
        current_date += timedelta(days=1)

    comparison_values = []
    income_comparison_values = []

    if compare == "true":
        previous_daily = defaultdict(float)
        previous_income_daily = defaultdict(float)

        if month_option:
            selected_month = int(month_option)
            selected_year = now.year
            if selected_month == 1:
                prev_month, prev_year = 12, selected_year - 1
            else:
                prev_month, prev_year = selected_month - 1, selected_year
            prev_start = datetime(prev_year, prev_month, 1)
            prev_end = datetime(prev_year + 1, 1, 1) if prev_month == 12 else datetime(prev_year, prev_month + 1, 1)
            previous_transactions = list(spending_collection.find({
                "user_id": user_id,
                "date": {"$gte": prev_start, "$lt": prev_end}
            }))
            for t in previous_transactions:
                if t["type"] == "expense":
                    previous_daily[t["date"].day] += t["amount"]
                if t["type"] == "income":
                    previous_income_daily[t["date"].day] += t["amount"]
            comparison_values = [round(previous_daily.get(int(l.split("-")[-1]), 0), 2) for l in labels]
            income_comparison_values = [round(previous_income_daily.get(int(l.split("-")[-1]), 0), 2) for l in labels]
        else:
            period_length = (anchor_date - start_date).days
            previous_start = start_date - timedelta(days=period_length)
            previous_transactions = list(spending_collection.find({
                "user_id": user_id,
                "date": {"$gte": previous_start, "$lt": start_date}
            }))
            for t in previous_transactions:
                if t["type"] == "expense":
                    previous_daily[t["date"].strftime("%Y-%m-%d")] += t["amount"]
                if t["type"] == "income":
                    previous_income_daily[t["date"].strftime("%Y-%m-%d")] += t["amount"]
            comparison_values = [round(previous_daily.get(d, 0), 2) for d in labels]
            income_comparison_values = [round(previous_income_daily.get(d, 0), 2) for d in labels]

    # -------------------------
    # INCOME VS EXPENSE BAR CHART — Last 6 months
    # -------------------------
    bar_labels = []
    bar_income = []
    bar_expenses = []

    for i in range(5, -1, -1):
        month_offset = now.month - i
        year_offset = now.year
        if month_offset <= 0:
            month_offset += 12
            year_offset -= 1

        m_start = datetime(year_offset, month_offset, 1)
        m_end = datetime(year_offset + 1, 1, 1) if month_offset == 12 else datetime(year_offset, month_offset + 1, 1)

        m_transactions = list(spending_collection.find({
            "user_id": user_id,
            "date": {"$gte": m_start, "$lt": m_end}
        }))

        m_income = round(sum(t["amount"] for t in m_transactions if t.get("type") == "income"), 2)
        m_expense = round(sum(t["amount"] for t in m_transactions if t.get("type") == "expense"), 2)

        bar_labels.append(calendar.month_abbr[month_offset])
        bar_income.append(m_income)
        bar_expenses.append(m_expense)

    # -------------------------
    # YEAR OVERVIEW — Last 12 months
    # -------------------------
    year_labels = []
    year_expenses = []
    year_income = []

    for i in range(12, 0, -1):
        total_months = now.year * 12 + now.month - 1 - i
        year_offset = total_months // 12
        month_offset = total_months % 12 + 1

        m_start = datetime(year_offset, month_offset, 1)
        m_end = datetime(year_offset + 1, 1, 1) if month_offset == 12 else datetime(year_offset, month_offset + 1, 1)

        m_transactions = list(spending_collection.find({
            "user_id": user_id,
            "date": {"$gte": m_start, "$lt": m_end}
        }))

        m_expense = round(sum(t["amount"] for t in m_transactions if t.get("type") == "expense"), 2)
        m_income = round(sum(t["amount"] for t in m_transactions if t.get("type") == "income"), 2)

        year_labels.append(f"{calendar.month_abbr[month_offset]} {str(year_offset)[2:]}")
        year_expenses.append(m_expense)
        year_income.append(m_income)

    months_with_expense_data = [e for e in year_expenses if e > 0]
    year_monthly_avg = round(sum(months_with_expense_data) / len(months_with_expense_data), 2) if months_with_expense_data else 0

    months_with_income_data = [e for e in year_income if e > 0]
    year_income_monthly_avg = round(sum(months_with_income_data) / len(months_with_income_data), 2) if months_with_income_data else 0

    # -------------------------
    # CURRENT YEAR OVERVIEW — Jan to Dec
    # -------------------------
    current_year_labels = []
    current_year_expenses = []
    current_year_income = []

    for month_num in range(1, 13):
        m_start = datetime(now.year, month_num, 1)
        m_end = datetime(now.year + 1, 1, 1) if month_num == 12 else datetime(now.year, month_num + 1, 1)

        m_transactions = list(spending_collection.find({
            "user_id": user_id,
            "date": {"$gte": m_start, "$lt": m_end}
        }))

        m_expense = round(sum(t["amount"] for t in m_transactions if t.get("type") == "expense"), 2)
        m_income = round(sum(t["amount"] for t in m_transactions if t.get("type") == "income"), 2)

        current_year_labels.append(calendar.month_abbr[month_num])
        current_year_expenses.append(m_expense)
        current_year_income.append(m_income)

    current_year_months_with_data = [e for e in current_year_expenses if e > 0]
    current_year_avg = round(sum(current_year_months_with_data) / len(current_year_months_with_data), 2) if current_year_months_with_data else 0

    current_year_income_months_with_data = [e for e in current_year_income if e > 0]
    current_year_income_avg = round(sum(current_year_income_months_with_data) / len(current_year_income_months_with_data), 2) if current_year_income_months_with_data else 0

    # -------------------------
    # PLANNED DEDUCTIONS — Last 6 months (default)
    # -------------------------
    deductions_6m_months = []
    for i in range(5, -1, -1):
        total_months = now.year * 12 + now.month - 1 - i
        y = total_months // 12
        m = total_months % 12 + 1
        deductions_6m_months.append((y, m))

    deductions_6m = get_planned_deductions_history(user_id, deductions_6m_months)

    # -------------------------
    # PLANNED DEDUCTIONS — Last 12 months
    # -------------------------
    deductions_12m_months = []
    for i in range(11, -1, -1):
        total_months = now.year * 12 + now.month - 1 - i
        y = total_months // 12
        m = total_months % 12 + 1
        deductions_12m_months.append((y, m))

    deductions_12m = get_planned_deductions_history(user_id, deductions_12m_months)

    # -------------------------
    # PLANNED DEDUCTIONS — Per year (2025, 2026, 2027)
    # -------------------------
    deductions_by_year = {}
    summary_by_year = {}
    for yr in [now.year - 1, now.year, now.year + 1]:
        yr_months = [(yr, m) for m in range(1, 13)]
        deductions_by_year[str(yr)] = get_planned_deductions_history(user_id, yr_months)
        summary_by_year[str(yr)] = get_deductions_summary(user_id, yr_months)

    summary_6m = get_deductions_summary(user_id, deductions_6m_months)
    summary_12m = get_deductions_summary(user_id, deductions_12m_months)

    return render_template(
        "dashboard.html",
        labels=labels,
        values=values,
        income_values=income_values,
        comparison_values=comparison_values,
        income_comparison_values=income_comparison_values,
        compare=compare,
        range_option=range_option,
        month_option=month_option,
        income_total=income_total,
        expense_total=expense_total,
        net_total=net_total,
        summary=summary,
        bar_labels=bar_labels,
        bar_income=bar_income,
        bar_expenses=bar_expenses,
        year_labels=year_labels,
        year_expenses=year_expenses,
        year_income=year_income,
        year_monthly_avg=year_monthly_avg,
        year_income_monthly_avg=year_income_monthly_avg,
        current_year_labels=current_year_labels,
        current_year_expenses=current_year_expenses,
        current_year_income=current_year_income,
        current_year_avg=current_year_avg,
        current_year_income_avg=current_year_income_avg,
        deductions_6m=deductions_6m,
        deductions_12m=deductions_12m,
        deductions_by_year=deductions_by_year,
        summary_6m=summary_6m,
        summary_12m=summary_12m,
        summary_by_year=summary_by_year,
    )
    