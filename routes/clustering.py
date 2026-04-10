from flask import Blueprint, render_template, session, redirect, request
from datetime import datetime
from collections import defaultdict
from extensions import spending_collection, budget_collection
from helpers import normalize_section
import joblib
import os
import numpy as np

clustering_bp = Blueprint("clustering", __name__)

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ml_models")
kmeans_model = joblib.load(os.path.join(BASE_DIR, "kmeans_model.pkl"))
kmeans_scaler = joblib.load(os.path.join(BASE_DIR, "kmeans_scaler.pkl"))
kmeans_feature_cols = joblib.load(os.path.join(BASE_DIR, "kmeans_feature_cols.pkl"))
kmeans_cluster_labels = joblib.load(os.path.join(BASE_DIR, "kmeans_cluster_labels.pkl"))


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


def build_user_cluster_features(user_id, cur_year, cur_month, scope):
    """
    Build user spending profile across scope months for K-Means classification.
    Aggregates category percentages and expense ratio across all scope months.
    """
    all_expenses = defaultdict(float)
    total_income = 0.0
    total_expenses = 0.0
    months_used = 0

    for i in range(1, scope + 1):
        h_year, h_month = get_prev_month(cur_year, cur_month, i)
        transactions = get_month_transactions(user_id, h_year, h_month)
        budget_doc = budget_collection.find_one({
            "user_id": user_id, "year": h_year, "month": h_month
        }) or {}

        for t in transactions:
            if t.get("type") == "expense":
                all_expenses[t["category"]] += t["amount"]
                total_expenses += t["amount"]

        monthly_income = float(budget_doc.get("monthly_income", 0))
        income_log = sum(t["amount"] for t in transactions if t.get("type") == "income")
        total_income += monthly_income + income_log
        months_used += 1

    if total_expenses == 0:
        return None, 0

    def cat_pct(cat):
        return all_expenses.get(cat, 0) / total_expenses

    expense_ratio = total_expenses / total_income if total_income > 0 else 0
    savings_pct = max(1 - expense_ratio, 0)

    features = {
        "food_pct": cat_pct("Food"),
        "rent_pct": 0,
        "entertainment_pct": cat_pct("Entertainment"),
        "shopping_pct": cat_pct("Shopping") + cat_pct("Clothes"),
        "health_pct": cat_pct("Health"),
        "travel_pct": cat_pct("Transport"),
        "utilities_pct": cat_pct("Bills"),
        "education_pct": cat_pct("Education"),
        "expense_ratio": expense_ratio,
        "savings_pct": savings_pct,
    }

    return features, months_used


CLUSTER_DESCRIPTIONS = {
    "Saver": {
        "description": "You consistently spend less than you earn and maintain a healthy savings rate. Your expenses are well controlled across categories.",
        "badge": "bg-success",
        "icon": "💰",
        "tips": [
            "Keep maintaining your low expense ratio.",
            "Consider investing your surplus savings.",
            "You are on track for strong financial stability."
        ]
    },
    "Balanced": {
        "description": "Your spending and income are fairly balanced. You cover essentials well but have room to improve your savings rate.",
        "badge": "bg-primary",
        "icon": "⚖️",
        "tips": [
            "Try to reduce discretionary spending by 10% to boost savings.",
            "Review your bills and subscriptions for any unused services.",
            "Set a monthly savings target to move toward the Saver profile."
        ]
    },
    "Leisure-Heavy": {
        "description": "A significant portion of your spending goes toward entertainment, food, and shopping. Your expense ratio is high relative to income.",
        "badge": "bg-warning text-dark",
        "icon": "🎯",
        "tips": [
            "Consider setting a weekly limit on entertainment and dining out.",
            "Track your shopping spend — small purchases add up quickly.",
            "Redirecting 15% of leisure spend to savings could make a big difference."
        ]
    }
}


@clustering_bp.route("/insights/clustering")
def clustering():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    now = datetime.now()

    scope = int(request.args.get("scope", 1))
    analysed = request.args.get("analysed", "false") == "true"

    clustering_data = {}

    if analysed:
        cur_year = now.year
        cur_month = now.month

        features, months_used = build_user_cluster_features(
            user_id, cur_year, cur_month, scope
        )

        history_warning = None
        if features is None:
            history_warning = "No historical spending data found. Cannot classify spending behaviour."
        elif months_used < scope:
            history_warning = (
                f"Only {months_used} month(s) of history found but you selected "
                f"{scope} month(s) as scope. Classification based on available data only."
            )

        if features is not None:
            X = np.array([[features[col] for col in kmeans_feature_cols]])
            X_scaled = kmeans_scaler.transform(X)
            cluster_id = int(kmeans_model.predict(X_scaled)[0])
            cluster_label = kmeans_cluster_labels[cluster_id]
            cluster_info = CLUSTER_DESCRIPTIONS[cluster_label]

            # Build category breakdown for display
            category_breakdown = []
            display_cats = [
                ("food_pct", "Food"),
                ("entertainment_pct", "Entertainment"),
                ("shopping_pct", "Shopping"),
                ("travel_pct", "Transport"),
                ("utilities_pct", "Bills"),
                ("health_pct", "Health"),
                ("education_pct", "Education"),
            ]
            for feat_key, label in display_cats:
                pct = round(features[feat_key] * 100, 1)
                if pct > 0:
                    category_breakdown.append({
                        "category": label,
                        "pct": pct
                    })

            category_breakdown.sort(key=lambda x: -x["pct"])

            clustering_data = {
                "cluster_label": cluster_label,
                "cluster_id": cluster_id,
                "description": cluster_info["description"],
                "badge": cluster_info["badge"],
                "icon": cluster_info["icon"],
                "tips": cluster_info["tips"],
                "expense_ratio": round(features["expense_ratio"] * 100, 1),
                "savings_pct": round(features["savings_pct"] * 100, 1),
                "category_breakdown": category_breakdown,
                "months_used": months_used,
                "scope": scope,
                "history_warning": history_warning,
            }
        else:
            clustering_data = {
                "cluster_label": None,
                "history_warning": history_warning,
            }

    return render_template("prediction.html",
        active_feature="clustering",
        clustering_data=clustering_data,
        clustering_analysed=analysed,
        clustering_scope=scope,
        prediction_data={},
        forecast_analysed=False,
        forecast_scope=1,
        category_data={},
        category_analysed=False,
        category_scope=1,
        active_page="prediction",
    )