from flask import Blueprint, render_template, session, redirect, request
from datetime import datetime
from collections import defaultdict
from extensions import spending_collection, budget_collection
from helpers import normalize_section
import calendar

risk_bp = Blueprint("risk", __name__)

@risk_bp.route("/risk")
def risk():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    now = datetime.utcnow()

    selected_year = int(request.args.get("year", now.year))
    selected_month = int(request.args.get("month", now.month))
    analysed = request.args.get("analysed", "false") == "true"

    years = [now.year - 1, now.year, now.year + 1]
    month_options = [{"value": i, "label": calendar.month_name[i]} for i in range(1, 13)]

    risk_data = {}
    factors = []

    if analysed:
        month_start = datetime(selected_year, selected_month, 1)
        next_month_start = datetime(selected_year + 1, 1, 1) if selected_month == 12 else datetime(selected_year, selected_month + 1, 1)

        transactions = list(spending_collection.find({
            "user_id": user_id,
            "date": {"$gte": month_start, "$lt": next_month_start}
        }))

        # Previous month
        if selected_month == 1:
            prev_year, prev_month = selected_year - 1, 12
        else:
            prev_year, prev_month = selected_year, selected_month - 1

        prev_start = datetime(prev_year, prev_month, 1)
        prev_end = datetime(prev_year + 1, 1, 1) if prev_month == 12 else datetime(prev_year, prev_month + 1, 1)

        prev_transactions = list(spending_collection.find({
            "user_id": user_id,
            "date": {"$gte": prev_start, "$lt": prev_end}
        }))

        budget_doc = budget_collection.find_one({
            "user_id": user_id, "year": selected_year, "month": selected_month
        }) or {}

        spending_limit = float(budget_doc.get("spending_limit", 0))
        monthly_income = float(budget_doc.get("monthly_income", 0))
        account_balance = float(budget_doc.get("account_balance", 0))
        savings = normalize_section(budget_doc.get("savings", {}))
        bills = normalize_section(budget_doc.get("bills", {}))
        debts = normalize_section(budget_doc.get("debts", {}))

        savings_total = round(sum(savings.values()), 2)
        bills_total = round(sum(bills.values()), 2)
        debts_total = round(sum(debts.values()), 2)
        planned_deductions = round(savings_total + bills_total + debts_total, 2)

        current_by_cat = defaultdict(float)
        for t in transactions:
            if t.get("type") == "expense":
                current_by_cat[t["category"]] += t["amount"]

        prev_by_cat = defaultdict(float)
        for t in prev_transactions:
            if t.get("type") == "expense":
                prev_by_cat[t["category"]] += t["amount"]

        total_expenses = round(sum(current_by_cat.values()), 2)
        prev_total = round(sum(prev_by_cat.values()), 2)

        budget_usage_pct = round((total_expenses / spending_limit) * 100, 1) if spending_limit > 0 else 0
        savings_rate = round((savings_total / monthly_income) * 100, 1) if monthly_income > 0 else 0
        debt_ratio = round((debts_total / monthly_income) * 100, 1) if monthly_income > 0 else 0
        bills_ratio = round((bills_total / monthly_income) * 100, 1) if monthly_income > 0 else 0
        deductions_ratio = round((planned_deductions / monthly_income) * 100, 1) if monthly_income > 0 else 0
        mom_change = round(((total_expenses - prev_total) / prev_total) * 100, 1) if prev_total > 0 else 0

        # ── SCORING SYSTEM (total 100 points, lower = higher risk) ──
        score = 100

        # Factor 1: Budget usage (max penalty 30)
        if spending_limit > 0:
            if budget_usage_pct >= 100:
                score -= 30
                factors.append({"label": "Budget Usage", "value": f"{budget_usage_pct}%", "impact": "high", "deducted": 30, "note": "Spending limit exceeded"})
            elif budget_usage_pct >= 85:
                score -= 20
                factors.append({"label": "Budget Usage", "value": f"{budget_usage_pct}%", "impact": "high", "deducted": 20, "note": "Near spending limit"})
            elif budget_usage_pct >= 60:
                score -= 10
                factors.append({"label": "Budget Usage", "value": f"{budget_usage_pct}%", "impact": "medium", "deducted": 10, "note": "Moderate budget usage"})
            else:
                factors.append({"label": "Budget Usage", "value": f"{budget_usage_pct}%", "impact": "low", "deducted": 0, "note": "Within safe range"})
        else:
            score -= 10
            factors.append({"label": "Budget Usage", "value": "No limit set", "impact": "medium", "deducted": 10, "note": "Set a spending limit to track usage"})

        # Factor 2: Savings rate (max penalty 25)
        if savings_total == 0:
            score -= 25
            factors.append({"label": "Savings Rate", "value": "0%", "impact": "high", "deducted": 25, "note": "No savings allocated this month"})
        elif savings_rate < 10:
            score -= 15
            factors.append({"label": "Savings Rate", "value": f"{savings_rate}%", "impact": "medium", "deducted": 15, "note": "Below recommended 10–20%"})
        elif savings_rate >= 20:
            factors.append({"label": "Savings Rate", "value": f"{savings_rate}%", "impact": "low", "deducted": 0, "note": "Above recommended threshold"})
        else:
            score -= 5
            factors.append({"label": "Savings Rate", "value": f"{savings_rate}%", "impact": "low", "deducted": 5, "note": "Within healthy range"})

        # Factor 3: Debt ratio (max penalty 20)
        if debt_ratio > 20:
            score -= 20
            factors.append({"label": "Debt Repayments", "value": f"{debt_ratio}%", "impact": "high", "deducted": 20, "note": "Above recommended 20% of income"})
        elif debt_ratio > 10:
            score -= 10
            factors.append({"label": "Debt Repayments", "value": f"{debt_ratio}%", "impact": "medium", "deducted": 10, "note": "Manageable but worth monitoring"})
        elif debts_total > 0:
            factors.append({"label": "Debt Repayments", "value": f"{debt_ratio}%", "impact": "low", "deducted": 0, "note": "Within safe range"})
        else:
            factors.append({"label": "Debt Repayments", "value": "None", "impact": "low", "deducted": 0, "note": "No debt repayments this month"})

        # Factor 4: Month-on-month spending change (max penalty 15)
        if prev_total > 0:
            if mom_change >= 25:
                score -= 15
                factors.append({"label": "Spending Trend", "value": f"+{mom_change}%", "impact": "high", "deducted": 15, "note": "Large increase vs last month"})
            elif mom_change >= 10:
                score -= 8
                factors.append({"label": "Spending Trend", "value": f"+{mom_change}%", "impact": "medium", "deducted": 8, "note": "Moderate increase vs last month"})
            elif mom_change <= -10:
                factors.append({"label": "Spending Trend", "value": f"{mom_change}%", "impact": "low", "deducted": 0, "note": "Spending decreased vs last month"})
            else:
                factors.append({"label": "Spending Trend", "value": f"{mom_change:+.1f}%", "impact": "low", "deducted": 0, "note": "Stable spending vs last month"})
        else:
            factors.append({"label": "Spending Trend", "value": "N/A", "impact": "low", "deducted": 0, "note": "No prior month data available"})

        # Factor 5: Bills ratio (max penalty 10)
        if bills_ratio > 30:
            score -= 10
            factors.append({"label": "Bills Burden", "value": f"{bills_ratio}%", "impact": "high", "deducted": 10, "note": "High fixed bills relative to income"})
        elif bills_ratio > 15:
            score -= 5
            factors.append({"label": "Bills Burden", "value": f"{bills_ratio}%", "impact": "medium", "deducted": 5, "note": "Moderate bills burden"})
        else:
            factors.append({"label": "Bills Burden", "value": f"{bills_ratio}%" if bills_total > 0 else "None", "impact": "low", "deducted": 0, "note": "Bills within manageable range"})

        # Clamp score
        score = max(0, min(100, score))

        # Determine risk level
        if score >= 75:
            risk_level = "Low"
            risk_colour = "success"
            risk_description = "Your financial position appears stable. Continue maintaining good saving and spending habits."
        elif score >= 50:
            risk_level = "Medium"
            risk_colour = "warning"
            risk_description = "There are some areas of concern in your finances. Review the factors below and consider adjustments."
        else:
            risk_level = "High"
            risk_colour = "danger"
            risk_description = "Your financial indicators suggest elevated risk. Immediate attention to spending and savings is recommended."

        risk_data = {
            "score": score,
            "risk_level": risk_level,
            "risk_colour": risk_colour,
            "risk_description": risk_description,
            "total_expenses": total_expenses,
            "budget_usage_pct": budget_usage_pct,
            "savings_rate": savings_rate,
            "debt_ratio": debt_ratio,
            "monthly_income": monthly_income,
            "spending_limit": spending_limit,
            "planned_deductions": planned_deductions,
        }

    return render_template("risk.html",
        risk_data=risk_data,
        factors=factors,
        analysed=analysed,
        selected_year=selected_year,
        selected_month=selected_month,
        years=years,
        month_options=month_options,
        month_name=calendar.month_name[selected_month],
        active_page="risk",
    )