from flask import Blueprint, render_template, session, redirect, request
from datetime import datetime
from collections import defaultdict
from extensions import spending_collection, budget_collection
from helpers import normalize_section
import calendar

feedback_bp = Blueprint("feedback", __name__)

@feedback_bp.route("/feedback")
def feedback():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    now = datetime.utcnow()

    selected_year = int(request.args.get("year", now.year))
    selected_month = int(request.args.get("month", now.month))
    analysed = request.args.get("analysed", "false") == "true"

    years = [now.year - 1, now.year, now.year + 1]
    month_options = [{"value": i, "label": calendar.month_name[i]} for i in range(1, 13)]

    tips = []
    summary_stats = {}

    if analysed:
        month_start = datetime(selected_year, selected_month, 1)
        next_month_start = datetime(selected_year + 1, 1, 1) if selected_month == 12 else datetime(selected_year, selected_month + 1, 1)

        transactions = list(spending_collection.find({
            "user_id": user_id,
            "date": {"$gte": month_start, "$lt": next_month_start}
        }))

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
        savings = normalize_section(budget_doc.get("savings", {}))
        bills = normalize_section(budget_doc.get("bills", {}))
        debts = normalize_section(budget_doc.get("debts", {}))
        savings_total = round(sum(savings.values()), 2)
        debts_total = round(sum(debts.values()), 2)

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
        mom_change = round(((total_expenses - prev_total) / prev_total) * 100, 1) if prev_total > 0 else None
        top_cat = max(current_by_cat, key=current_by_cat.get) if current_by_cat else None
        top_cat_amount = round(current_by_cat[top_cat], 2) if top_cat else 0
        savings_rate = round((savings_total / monthly_income) * 100, 1) if monthly_income > 0 else 0

        summary_stats = {
            "total_expenses": total_expenses,
            "top_cat": top_cat or "N/A",
            "top_cat_amount": top_cat_amount,
            "mom_change": mom_change,
            "prev_month_name": calendar.month_abbr[prev_month],
        }

        if not transactions:
            tips.append({
                "severity": "warning",
                "category": "Data",
                "title": "No Transactions Found",
                "message": f"No spending data found for {calendar.month_name[selected_month]} {selected_year}. Log your transactions in the Spending Log to receive personalised feedback."
            })
        else:
            # RULE 1: Month-on-month category changes — core of feedback
            for cat, amount in sorted(current_by_cat.items(), key=lambda x: -x[1]):
                prev_amount = prev_by_cat.get(cat, 0)
                if prev_amount > 0:
                    pct_change = round(((amount - prev_amount) / prev_amount) * 100, 1)
                    if pct_change >= 50:
                        tips.append({
                            "severity": "danger",
                            "category": cat,
                            "title": f"{cat} Up {pct_change}% This Month",
                            "message": f"You spent £{amount:.2f} on {cat} compared to £{prev_amount:.2f} last month — a {pct_change}% increase. Consider whether this is a recurring pattern and whether it can be reduced."
                        })
                    elif pct_change >= 25:
                        tips.append({
                            "severity": "warning",
                            "category": cat,
                            "title": f"{cat} Spending Rose {pct_change}%",
                            "message": f"{cat} costs increased from £{prev_amount:.2f} to £{amount:.2f} this month. Review whether this spending is necessary."
                        })
                    elif pct_change <= -25:
                        tips.append({
                            "severity": "success",
                            "category": cat,
                            "title": f"{cat} Spending Down {abs(pct_change)}%",
                            "message": f"Good progress — {cat} spending reduced from £{prev_amount:.2f} to £{amount:.2f} this month. Keep this up."
                        })
                elif prev_amount == 0 and amount > 0:
                    tips.append({
                        "severity": "warning",
                        "category": cat,
                        "title": f"New Spending Category: {cat}",
                        "message": f"You spent £{amount:.2f} on {cat} this month with no prior spending in this category. Ensure this fits within your budget."
                    })

            # RULE 2: Food spending advice
            food = current_by_cat.get("Food", 0)
            if monthly_income > 0 and food > 0:
                food_pct = round((food / monthly_income) * 100, 1)
                if food_pct > 20:
                    tips.append({
                        "severity": "warning",
                        "category": "Food",
                        "title": "High Food Spending",
                        "message": f"Food spending of £{food:.2f} represents {food_pct}% of your monthly income. Meal planning and home cooking can significantly reduce this cost."
                    })
                elif food_pct <= 10:
                    tips.append({
                        "severity": "success",
                        "category": "Food",
                        "title": "Food Spending Well Managed",
                        "message": f"Food costs of £{food:.2f} ({food_pct}% of income) are within a healthy range. Good budgeting on essentials."
                    })

            # RULE 3: Transport advice
            transport = current_by_cat.get("Transport", 0)
            if monthly_income > 0 and transport > 0:
                transport_pct = round((transport / monthly_income) * 100, 1)
                if transport_pct > 15:
                    tips.append({
                        "severity": "warning",
                        "category": "Transport",
                        "title": "High Transport Costs",
                        "message": f"Transport costs of £{transport:.2f} represent {transport_pct}% of your income. Using public transport or carpooling where possible may help reduce this."
                    })

            # RULE 4: Entertainment and Shopping advice
            entertainment = current_by_cat.get("Entertainment", 0)
            shopping = current_by_cat.get("Shopping", 0)
            leisure = entertainment + shopping
            if monthly_income > 0 and leisure > 0:
                leisure_pct = round((leisure / monthly_income) * 100, 1)
                if leisure_pct > 30:
                    tips.append({
                        "severity": "danger",
                        "category": "Leisure",
                        "title": "Leisure Spending Too High",
                        "message": f"Entertainment (£{entertainment:.2f}) and Shopping (£{shopping:.2f}) total £{leisure:.2f} — {leisure_pct}% of income. Financial guidelines recommend keeping leisure spending under 30% of monthly income."
                    })
                elif leisure_pct > 15:
                    tips.append({
                        "severity": "warning",
                        "category": "Leisure",
                        "title": "Moderate Leisure Spending",
                        "message": f"Entertainment and Shopping total £{leisure:.2f} ({leisure_pct}% of income). This is manageable but worth monitoring to avoid overspend."
                    })

            # RULE 5: Savings advice
            if savings_total == 0:
                tips.append({
                    "severity": "danger",
                    "category": "Savings",
                    "title": "No Savings Allocated This Month",
                    "message": "No savings have been set in the Budget Tracker for this month. Consistent saving, even in small amounts, is key to long-term financial stability."
                })
            elif monthly_income > 0:
                if savings_rate < 10:
                    tips.append({
                        "severity": "warning",
                        "category": "Savings",
                        "title": f"Low Savings Rate ({savings_rate}%)",
                        "message": f"You are saving £{savings_total:.2f} ({savings_rate}% of income). Financial guidance recommends saving at least 10–20% of monthly income. Consider increasing your savings allocation next month."
                    })
                elif savings_rate >= 20:
                    tips.append({
                        "severity": "success",
                        "category": "Savings",
                        "title": f"Excellent Savings Rate ({savings_rate}%)",
                        "message": f"You are saving £{savings_total:.2f} ({savings_rate}% of income), exceeding the recommended 20% threshold. Excellent financial discipline."
                    })
                else:
                    tips.append({
                        "severity": "success",
                        "category": "Savings",
                        "title": f"Good Savings Rate ({savings_rate}%)",
                        "message": f"You are saving £{savings_total:.2f} ({savings_rate}% of income), within the recommended 10–20% range."
                    })

            # RULE 6: Debt advice
            if debts_total > 0 and monthly_income > 0:
                debt_pct = round((debts_total / monthly_income) * 100, 1)
                if debt_pct > 20:
                    tips.append({
                        "severity": "danger",
                        "category": "Debt",
                        "title": "High Debt Repayments",
                        "message": f"Debt repayments of £{debts_total:.2f} represent {debt_pct}% of your income, above the recommended 20%. A structured repayment plan could help reduce this burden over time."
                    })
                else:
                    tips.append({
                        "severity": "success",
                        "category": "Debt",
                        "title": "Debt Repayments Manageable",
                        "message": f"Debt repayments of £{debts_total:.2f} ({debt_pct}% of income) are within a manageable range. Stay consistent to clear balances sooner."
                    })

            # RULE 7: Top category dominance
            if top_cat:
                top_cat_pct = round((top_cat_amount / total_expenses) * 100, 1) if total_expenses > 0 else 0
                if top_cat_pct >= 40:
                    tips.append({
                        "severity": "warning",
                        "category": "Category",
                        "title": f"{top_cat} Dominates Your Spending",
                        "message": f"{top_cat} accounts for {top_cat_pct}% of your total spending at £{top_cat_amount:.2f}. If this is discretionary spending, consider setting a monthly category limit."
                    })

    return render_template("feedback.html",
        tips=tips,
        summary_stats=summary_stats,
        analysed=analysed,
        selected_year=selected_year,
        selected_month=selected_month,
        years=years,
        month_options=month_options,
        month_name=calendar.month_name[selected_month],
    )