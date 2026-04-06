from flask import Blueprint, render_template, session, redirect, request
from datetime import datetime
from collections import defaultdict
from extensions import spending_collection, budget_collection
from helpers import normalize_section
import joblib
import os
import numpy as np
import calendar

category_bp = Blueprint("category_prediction", __name__)

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ml_models")
forecast_model = joblib.load(os.path.join(BASE_DIR, "spending_forecast_model.pkl"))
forecast_feature_cols = joblib.load(os.path.join(BASE_DIR, "forecast_feature_cols.pkl"))
kaggle_avg_ratio = joblib.load(os.path.join(BASE_DIR, "kaggle_avg_ratio.pkl"))
kaggle_avg_total = joblib.load(os.path.join(BASE_DIR, "kaggle_avg_total.pkl"))


def get_month_transactions(user_id, year, month):
    month_start = datetime(year, month, 1)
    next_month_start = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return list(spending_collection.find({
        "user_id": user_id,
        "date": {"$gte": month_start, "$lt": next_month_start}
    }))


def get_prev_month(year, month, steps=1):
    for _ in range(steps):
        if month == 1:
            month, year = 12, year - 1
        else:
            month -= 1
    return year, month


def get_month_total_expenses(user_id, year, month):
    transactions = get_month_transactions(user_id, year, month)
    return round(sum(t["amount"] for t in transactions if t.get("type") == "expense"), 2)


def get_month_total_income(user_id, year, month):
    budget_doc = budget_collection.find_one({
        "user_id": user_id, "year": year, "month": month
    }) or {}
    monthly_income = float(budget_doc.get("monthly_income", 0))
    transactions = get_month_transactions(user_id, year, month)
    income_log = sum(t["amount"] for t in transactions if t.get("type") == "income")
    return round(monthly_income + income_log, 2)


def build_user_features(user_id, year, month):
    """Build ML feature vector from a completed month."""
    transactions = get_month_transactions(user_id, year, month)
    budget_doc = budget_collection.find_one({
        "user_id": user_id, "year": year, "month": month
    }) or {}

    by_cat = defaultdict(float)
    for t in transactions:
        if t.get("type") == "expense":
            by_cat[t["category"]] += t["amount"]

    monthly_income = float(budget_doc.get("monthly_income", 0))
    income_log = sum(t["amount"] for t in transactions if t.get("type") == "income")
    total_income = monthly_income + income_log
    total_expenses = sum(by_cat.values())
    bills = normalize_section(budget_doc.get("bills", {}))
    expense_ratio = total_expenses / total_income if total_income > 0 else 0

    lag1_year, lag1_month = get_prev_month(year, month, 1)
    lag2_year, lag2_month = get_prev_month(year, month, 2)
    lag3_year, lag3_month = get_prev_month(year, month, 3)

    lag_1 = get_month_total_expenses(user_id, lag1_year, lag1_month)
    lag_2 = get_month_total_expenses(user_id, lag2_year, lag2_month)
    lag_3 = get_month_total_expenses(user_id, lag3_year, lag3_month)

    rolling_3m = round((lag_1 + lag_2 + lag_3) / 3, 2) if any([lag_1, lag_2, lag_3]) else total_expenses
    spending_trend = total_expenses - lag_3 if lag_3 > 0 else 0

    lag3_income = get_month_total_income(user_id, lag3_year, lag3_month)
    income_trend = total_income - lag3_income if lag3_income > 0 else 0

    return {
        "total_expenses": total_expenses,
        "total_income": total_income,
        "food": by_cat.get("Food", 0),
        "rent": 0,
        "entertainment": by_cat.get("Entertainment", 0),
        "shopping": by_cat.get("Shopping", 0),
        "health": by_cat.get("Health", 0),
        "travel": by_cat.get("Transport", 0),
        "utilities": sum(bills.values()),
        "education": by_cat.get("Education", 0),
        "num_transactions": len([t for t in transactions if t.get("type") == "expense"]),
        "expense_ratio": expense_ratio,
        "month_num": month,
        "lag_1": lag_1,
        "lag_2": lag_2,
        "rolling_3m": rolling_3m,
        "spending_trend": spending_trend,
        "income_trend": income_trend,
    }, total_expenses


def get_predicted_total(user_id, cur_year, cur_month, scope):
    """Use ML model + scope base to get predicted total — same logic as forecast."""
    feat_year, feat_month = get_prev_month(cur_year, cur_month, 1)
    features, current_total = build_user_features(user_id, feat_year, feat_month)

    if current_total > 0:
        X = np.array([[features[col] for col in forecast_feature_cols]])
        predicted_ratio = float(np.clip(forecast_model.predict(X)[0], 0.5, 2.0))
    else:
        predicted_ratio = kaggle_avg_ratio

    scope_base_totals = []
    for i in range(1, scope + 1):
        s_year, s_month = get_prev_month(cur_year, cur_month, i)
        s_total = get_month_total_expenses(user_id, s_year, s_month)
        if s_total > 0:
            scope_base_totals.append(s_total)

    if scope_base_totals:
        base_total = sum(scope_base_totals) / len(scope_base_totals)
    elif current_total > 0:
        base_total = current_total
    else:
        base_total = kaggle_avg_total

    return round(base_total * predicted_ratio, 2), round(predicted_ratio, 4)


def build_category_prediction(user_id, cur_year, cur_month, scope, predicted_total):
    """
    For each scope month, calculate what % of total expenses each category was.
    Average those percentages across months.
    Apply to predicted_total to get predicted £ per category.
    Returns top 3 categories sorted by predicted %.
    """
    category_month_pcts = defaultdict(list)
    months_used = 0

    for i in range(1, scope + 1):
        h_year, h_month = get_prev_month(cur_year, cur_month, i)
        transactions = get_month_transactions(user_id, h_year, h_month)

        by_cat = defaultdict(float)
        for t in transactions:
            if t.get("type") == "expense":
                by_cat[t["category"]] += t["amount"]

        total = sum(by_cat.values())
        if total == 0:
            continue

        for cat, amt in by_cat.items():
            category_month_pcts[cat].append(amt / total)

        months_used += 1

    if months_used == 0:
        return [], 0

    avg_pcts = {}
    for cat, pcts in category_month_pcts.items():
        avg_pcts[cat] = sum(pcts) / months_used

    total_pct = sum(avg_pcts.values())
    if total_pct > 0:
        avg_pcts = {cat: pct / total_pct for cat, pct in avg_pcts.items()}

    sorted_cats = sorted(avg_pcts.items(), key=lambda x: -x[1])

    results = []
    for cat, pct in sorted_cats[:3]:
        results.append({
            "category": cat,
            "predicted_pct": round(pct * 100, 1),
            "predicted_amount": round(predicted_total * pct, 2),
        })

    return results, months_used


@category_bp.route("/insights/category")
def category_prediction():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    now = datetime.now()

    scope = int(request.args.get("scope", 1))
    analysed = request.args.get("analysed", "false") == "true"

    category_data = {}

    if analysed:
        cur_year = now.year
        cur_month = now.month

        # Get predicted total from ML model automatically
        predicted_total, predicted_ratio = get_predicted_total(
            user_id, cur_year, cur_month, scope
        )

        top_categories, months_used = build_category_prediction(
            user_id, cur_year, cur_month, scope, predicted_total
        )

        history_warning = None
        if months_used == 0:
            history_warning = "No historical spending data found. Cannot predict top categories."
        elif months_used < scope:
            history_warning = (
                f"Only {months_used} month(s) of history found but you selected "
                f"{scope} month(s) as scope. Prediction based on available data only."
            )

        category_data = {
            "top_categories": top_categories,
            "months_used": months_used,
            "scope": scope,
            "predicted_total": predicted_total,
            "predicted_ratio": predicted_ratio,
            "history_warning": history_warning,
        }

    return render_template("prediction.html",
        active_feature="category",
        category_data=category_data,
        category_analysed=analysed,
        category_scope=scope,
        prediction_data={},
        forecast_analysed=False,
        forecast_scope=1,
    )