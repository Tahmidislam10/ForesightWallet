from flask import Blueprint, render_template, request, redirect, session
from datetime import datetime, timedelta
from collections import defaultdict
from extensions import spending_collection, budget_collection
from helpers import calculate_month_summary, normalize_section
import calendar

dashboard_bp = Blueprint("dashboard", __name__)

CATEGORY_ICONS = {
    "Food": "🍔",
    "Transport": "🚗",
    "Shopping": "🛍️",
    "Entertainment": "🎬",
    "Health": "💊",
    "Education": "📚",
    "Bills": "📄",
    "Investments": "📈",
    "Salary": "💼",
    "Other": "💳",
}

MOTIVATIONAL_QUOTES = [
    {"quote": "A budget is telling your money where to go instead of wondering where it went.", "author": "Dave Ramsey"},
    {"quote": "Do not save what is left after spending, but spend what is left after saving.", "author": "Warren Buffett"},
    {"quote": "The habit of saving is itself an education.", "author": "T.T. Munger"},
    {"quote": "Financial freedom is available to those who learn about it and work for it.", "author": "Robert Kiyosaki"},
    {"quote": "It's not your salary that makes you rich, it's your spending habits.", "author": "Charles A. Jaffe"},
    {"quote": "Beware of little expenses; a small leak will sink a great ship.", "author": "Benjamin Franklin"},
    {"quote": "The secret to wealth is simple: spend less than you earn.", "author": "Thomas J. Stanley"},
    {"quote": "Money is a terrible master but an excellent servant.", "author": "P.T. Barnum"},
    {"quote": "Rich people stay rich by living like they're broke. Broke people stay broke by living like they're rich.", "author": "Unknown"},
    {"quote": "An investment in knowledge pays the best interest.", "author": "Benjamin Franklin"},
    {"quote": "Never spend your money before you have it.", "author": "Thomas Jefferson"},
    {"quote": "Wealth consists not in having great possessions, but in having few wants.", "author": "Epictetus"},
    {"quote": "The art is not in making money, but in keeping it.", "author": "Proverb"},
    {"quote": "Saving must become a priority, not just a thought.", "author": "Dave Ramsey"},
    {"quote": "A penny saved is a penny earned.", "author": "Benjamin Franklin"},
    {"quote": "Don't tell me what you value, show me your budget, and I'll tell you what you value.", "author": "Joe Biden"},
    {"quote": "Too many people spend money they haven't earned to buy things they don't want.", "author": "Will Rogers"},
    {"quote": "The more you learn, the more you earn.", "author": "Warren Buffett"},
    {"quote": "Spend less than you make, save the rest, give generously.", "author": "Unknown"},
    {"quote": "Financial peace isn't the acquisition of stuff. It's learning to live on less than you make.", "author": "Dave Ramsey"},
    {"quote": "Money looks better in the bank than on your feet.", "author": "Sophia Amoruso"},
    {"quote": "Budgeting is the process of deciding how to spend money you don't have.", "author": "Unknown"},
    {"quote": "The goal isn't more money. The goal is living life on your terms.", "author": "Chris Brogan"},
    {"quote": "Saving is a habit, not an event.", "author": "Unknown"},
    {"quote": "You must gain control over your money or the lack of it will forever control you.", "author": "Dave Ramsey"},
    {"quote": "Opportunity is missed by most people because it is dressed in overalls and looks like work.", "author": "Thomas Edison"},
    {"quote": "Cut your coat according to your cloth.", "author": "Proverb"},
    {"quote": "Wealth is not about having a lot of money; it's about having a lot of options.", "author": "Chris Rock"},
    {"quote": "Live beneath your means but above your fears.", "author": "Unknown"},
    {"quote": "The question is not whether you can afford it, the question is whether you can afford not to.", "author": "Unknown"},
    {"quote": "Small steps every day lead to big financial results.", "author": "Unknown"},
]


@dashboard_bp.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    now = datetime.utcnow()

    kpi_month = int(request.args.get("kpi_month", now.month))
    kpi_year = now.year

    totals_month = int(request.args.get("totals_month", now.month))
    totals_year = now.year

    summary = calculate_month_summary(user_id, kpi_year, kpi_month)

    if totals_month == 12:
        totals_anchor = datetime(totals_year + 1, 1, 1)
    else:
        totals_anchor = datetime(totals_year, totals_month + 1, 1)
    totals_start = datetime(totals_year, totals_month, 1)

    totals_transactions = list(spending_collection.find({
        "user_id": user_id,
        "date": {"$gte": totals_start, "$lt": totals_anchor}
    }))
    income_total = round(sum(t["amount"] for t in totals_transactions if t.get("type") == "income"), 2)
    expense_total = round(sum(t["amount"] for t in totals_transactions if t.get("type") == "expense"), 2)
    net_total = round(income_total - expense_total, 2)

    if kpi_month == 12:
        kpi_anchor = datetime(kpi_year + 1, 1, 1)
    else:
        kpi_anchor = datetime(kpi_year, kpi_month + 1, 1)
    kpi_start = datetime(kpi_year, kpi_month, 1)

    kpi_transactions = list(spending_collection.find({
        "user_id": user_id,
        "date": {"$gte": kpi_start, "$lt": kpi_anchor}
    }))

    cat_totals = defaultdict(float)
    for t in kpi_transactions:
        if t.get("type") == "expense":
            cat_totals[t["category"]] += t["amount"]

    sorted_cats = sorted(cat_totals.items(), key=lambda x: -x[1])
    top_categories = []
    for i, (cat, amt) in enumerate(sorted_cats[:3]):
        top_categories.append({
            "category": cat,
            "amount": round(amt, 2),
            "icon": CATEGORY_ICONS.get(cat, "💳"),
            "rank": i + 1,
            "label": ["Most spent category", "2nd highest", "3rd highest"][i]
        })

    budget_doc = budget_collection.find_one({
        "user_id": user_id, "year": kpi_year, "month": kpi_month
    }) or {}
    savings = normalize_section(budget_doc.get("savings", {}))
    bills = normalize_section(budget_doc.get("bills", {}))
    debts = normalize_section(budget_doc.get("debts", {}))
    savings_total = round(sum(savings.values()), 2)
    bills_total = round(sum(bills.values()), 2)
    debts_total = round(sum(debts.values()), 2)

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
        m_transactions = list(spending_collection.find({"user_id": user_id, "date": {"$gte": m_start, "$lt": m_end}}))
        m_income = round(sum(t["amount"] for t in m_transactions if t.get("type") == "income"), 2)
        m_expense = round(sum(t["amount"] for t in m_transactions if t.get("type") == "expense"), 2)
        bar_labels.append(calendar.month_abbr[month_offset])
        bar_income.append(m_income)
        bar_expenses.append(m_expense)

    day_of_year = now.timetuple().tm_yday
    daily_quote = MOTIVATIONAL_QUOTES[day_of_year % len(MOTIVATIONAL_QUOTES)]

    hour = now.hour
    if hour < 12:
        greeting = "Good Morning"
    elif hour < 17:
        greeting = "Good Afternoon"
    else:
        greeting = "Good Evening"

    month_names = list(calendar.month_name)[1:]

    return render_template(
        "dashboard.html",
        summary=summary,
        kpi_month=kpi_month,
        kpi_year=kpi_year,
        income_total=income_total,
        expense_total=expense_total,
        net_total=net_total,
        totals_month=totals_month,
        totals_year=totals_year,
        top_categories=top_categories,
        savings_total=savings_total,
        bills_total=bills_total,
        debts_total=debts_total,
        bar_labels=bar_labels,
        bar_income=bar_income,
        bar_expenses=bar_expenses,
        daily_quote=daily_quote,
        greeting=greeting,
        month_names=month_names,
        today=now.strftime("%A, %d %B %Y"),
    )