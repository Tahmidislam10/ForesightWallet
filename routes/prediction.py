from flask import Blueprint, render_template, session, redirect, request
from datetime import datetime
from collections import defaultdict
from extensions import spending_collection, budget_collection
from helpers import normalize_section
import joblib
import os
import numpy as np
import calendar

prediction_bp = Blueprint("insights", __name__)

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


def get_daily_totals(transactions, year, month):
    days_in_month = calendar.monthrange(year, month)[1]
    daily = defaultdict(float)
    for t in transactions:
        if t.get("type") == "expense":
            daily[t["date"].day] += t["amount"]
    return {d: round(daily.get(d, 0), 2) for d in range(1, days_in_month + 1)}


def get_prev_month(year, month, steps=1):
    for _ in range(steps):
        if month == 1:
            month, year = 12, year - 1
        else:
            month -= 1
    return year, month


def get_next_month(year, month):
    if month == 12:
        return year + 1, 1
    return year, month + 1


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
    """Build feature vector from user's MongoDB data matching training features."""
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
    }, total_expenses, lag_1, lag_2, lag_3


def check_data_availability(user_id, year, month):
    """Check how many of the last 3 months have spending data."""
    months_with_data = 0
    for i in range(1, 4):
        h_year, h_month = get_prev_month(year, month, i)
        total = get_month_total_expenses(user_id, h_year, h_month)
        if total > 0:
            months_with_data += 1
    return months_with_data


@prediction_bp.route("/insights")
def insights():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    now = datetime.now()
    today = now.date()

    active_feature = request.args.get("feature", "")
    forecast_scope = int(request.args.get("scope", 1))
    forecast_analysed = request.args.get("forecast_analysed", "false") == "true"

    prediction_data = {}

    if forecast_analysed:
        cur_year = now.year
        cur_month = now.month
        today_day = now.day

        months_available = check_data_availability(user_id, cur_year, cur_month)
        history_warning = None

        if months_available == 0:
            history_warning = "No historical spending data found. Using dataset average as fallback."
        elif months_available < forecast_scope:
            history_warning = (
                f"Only {months_available} month(s) of history found but you selected "
                f"{forecast_scope} month(s) as scope. Pattern will be based on available data only."
            )

        feat_year, feat_month = get_prev_month(cur_year, cur_month, 1)
        features, current_total, lag_1, lag_2, lag_3 = build_user_features(
            user_id, feat_year, feat_month
        )

        if current_total > 0:
            X = np.array([[features[col] for col in forecast_feature_cols]])
            predicted_ratio = float(np.clip(forecast_model.predict(X)[0], 0.5, 2.0))
        else:
            predicted_ratio = kaggle_avg_ratio
            history_warning = "No spending data found for this month. Using dataset average as fallback."

        scope_base_totals = []
        for i in range(1, forecast_scope + 1):
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

        predicted_total = round(base_total * predicted_ratio, 2)

        budget_doc = budget_collection.find_one({
            "user_id": user_id, "year": cur_year, "month": cur_month
        }) or {}
        spending_limit = float(budget_doc.get("spending_limit", 0))
        will_exceed = spending_limit > 0 and predicted_total > spending_limit
        spending_limit_pct = round((predicted_total / spending_limit) * 100, 1) if spending_limit > 0 else 0

        # Build daily pattern from scope months
        scope_patterns = []
        for i in range(1, forecast_scope + 1):
            h_year, h_month = get_prev_month(cur_year, cur_month, i)
            h_transactions = get_month_transactions(user_id, h_year, h_month)
            h_daily = get_daily_totals(h_transactions, h_year, h_month)
            h_total = sum(h_daily.values())
            days_in_h = calendar.monthrange(h_year, h_month)[1]
            if h_total > 0:
                h_pattern = {d: h_daily[d] / h_total for d in range(1, days_in_h + 1)}
                scope_patterns.append((h_pattern, days_in_h))

        if scope_patterns:
            avg_pattern = {}
            for day_pos in range(1, 32):
                vals = [p.get(day_pos, 0) for p, days in scope_patterns if day_pos <= days]
                avg_pattern[day_pos] = sum(vals) / len(vals) if vals else 0
            total_pat = sum(avg_pattern.values())
            if total_pat > 0:
                avg_pattern = {d: v / total_pat for d, v in avg_pattern.items()}
        else:
            avg_pattern = {d: 1 / 30 for d in range(1, 31)}

        cur_transactions = get_month_transactions(user_id, cur_year, cur_month)
        cur_daily = get_daily_totals(cur_transactions, cur_year, cur_month)
        actual_total_so_far = sum(cur_daily[d] for d in range(1, today_day + 1))

        actual_labels = []
        actual_values = []
        for d in range(1, today_day + 1):
            actual_labels.append(f"{cur_year}-{cur_month:02d}-{d:02d}")
            actual_values.append(cur_daily.get(d, 0))

        from datetime import date, timedelta
        start_pred = date(cur_year, cur_month, today_day) + timedelta(days=1)
        pred_dates = [start_pred + timedelta(days=i) for i in range(30)]

        remaining_total = max(predicted_total - actual_total_so_far, 0)

        day_positions = [d.day for d in pred_dates]
        pattern_sum = sum(avg_pattern.get(pos, 0) for pos in day_positions)

        predicted_labels = []
        predicted_values = []
        for i, d in enumerate(pred_dates):
            predicted_labels.append(d.strftime("%Y-%m-%d"))
            pos = d.day
            if pattern_sum > 0:
                daily_pred = round(remaining_total * (avg_pattern.get(pos, 0) / pattern_sum), 2)
            else:
                daily_pred = round(remaining_total / len(pred_dates), 2)
            predicted_values.append(daily_pred)

        end_date = pred_dates[-1] if pred_dates else start_pred
        end_date_label = end_date.strftime("%d %b %Y")

        prediction_data = {
            "actual_labels": actual_labels,
            "actual_values": actual_values,
            "predicted_labels": predicted_labels,
            "predicted_values": predicted_values,
            "predicted_total": predicted_total,
            "predicted_ratio": round(predicted_ratio, 4),
            "current_total": current_total,
            "spending_limit": spending_limit,
            "spending_limit_pct": spending_limit_pct,
            "will_exceed": will_exceed,
            "scope": forecast_scope,
            "months_available": months_available,
            "history_warning": history_warning,
            "end_date_label": end_date_label,
            "today_label": today.strftime("%d %b %Y"),
            "cv_r2": 0.0964,
            "cv_mae": 0.3120,
            "test_r2": 0.1274,
        }

    return render_template("prediction.html",
        active_feature=active_feature,
        prediction_data=prediction_data,
        forecast_analysed=forecast_analysed,
        forecast_scope=forecast_scope,
    )