from flask import Blueprint, render_template, request, redirect, session
from datetime import datetime, timedelta
from collections import defaultdict
from extensions import spending_collection
import calendar

income_trends_bp = Blueprint("income_trends", __name__)


@income_trends_bp.route("/income-trends")
def income_trends():
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
        selected_month = now.month
        selected_year = now.year

    try:
        selected_month = int(month_option)
    except (ValueError, TypeError):
        selected_month = now.month

    if range_option == "7":
        if selected_month == now.month and selected_year == now.year:
            start_date = now - timedelta(days=7)
            anchor_date = now
        else:
            start_date = anchor_date - timedelta(days=7)
    elif range_option == "30":
        start_date = datetime(selected_year, selected_month, 1)
    elif range_option == "90":
        start_date = anchor_date - timedelta(days=90)
    else:
        start_date = datetime(selected_year, selected_month, 1)

    query = {"user_id": user_id, "date": {"$gte": start_date, "$lt": anchor_date}}
    transactions = list(spending_collection.find(query).sort("date", 1))

    income_total = round(sum(t["amount"] for t in transactions if t.get("type") == "income"), 2)

    daily_totals = defaultdict(float)
    for t in transactions:
        if t.get("type") == "income":
            daily_totals[t["date"].strftime("%Y-%m-%d")] += t["amount"]

    labels = []
    values = []
    current_date = start_date.date()
    end_date = (anchor_date - timedelta(days=1)).date()
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        labels.append(date_str)
        values.append(round(daily_totals.get(date_str, 0), 2))
        current_date += timedelta(days=1)

    comparison_values = []
    if compare == "true":
        previous_daily = defaultdict(float)
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
            if t.get("type") == "income":
                previous_daily[t["date"].day] += t["amount"]
        comparison_values = [round(previous_daily.get(int(l.split("-")[-1]), 0), 2) for l in labels]

    # Year overview — last 12 months
    year_labels = []
    year_income = []
    for i in range(12, 0, -1):
        total_months = now.year * 12 + now.month - 1 - i
        year_offset = total_months // 12
        month_offset = total_months % 12 + 1
        m_start = datetime(year_offset, month_offset, 1)
        m_end = datetime(year_offset + 1, 1, 1) if month_offset == 12 else datetime(year_offset, month_offset + 1, 1)
        m_transactions = list(spending_collection.find({"user_id": user_id, "date": {"$gte": m_start, "$lt": m_end}}))
        m_income = round(sum(t["amount"] for t in m_transactions if t.get("type") == "income"), 2)
        year_labels.append(f"{calendar.month_abbr[month_offset]} {str(year_offset)[2:]}")
        year_income.append(m_income)

    months_with_data = [e for e in year_income if e > 0]
    year_monthly_avg = round(sum(months_with_data) / len(months_with_data), 2) if months_with_data else 0

    # Current year — Jan to Dec
    current_year_labels = []
    current_year_income = []
    for month_num in range(1, 13):
        m_start = datetime(now.year, month_num, 1)
        m_end = datetime(now.year + 1, 1, 1) if month_num == 12 else datetime(now.year, month_num + 1, 1)
        m_transactions = list(spending_collection.find({"user_id": user_id, "date": {"$gte": m_start, "$lt": m_end}}))
        m_income = round(sum(t["amount"] for t in m_transactions if t.get("type") == "income"), 2)
        current_year_labels.append(calendar.month_abbr[month_num])
        current_year_income.append(m_income)

    current_year_months_with_data = [e for e in current_year_income if e > 0]
    current_year_avg = round(sum(current_year_months_with_data) / len(current_year_months_with_data), 2) if current_year_months_with_data else 0

    return render_template(
        "income_trends.html",
        labels=labels,
        values=values,
        comparison_values=comparison_values,
        compare=compare,
        range_option=range_option,
        month_option=str(selected_month),
        income_total=income_total,
        year_labels=year_labels,
        year_income=year_income,
        year_monthly_avg=year_monthly_avg,
        current_year_labels=current_year_labels,
        current_year_income=current_year_income,
        current_year_avg=current_year_avg,
    )