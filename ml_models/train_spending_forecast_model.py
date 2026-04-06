import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, r2_score
import joblib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(os.path.join(BASE_DIR, "budgetwise_finance_dataset.csv"))

print(f"Raw dataset shape: {df.shape}")
print(f"Columns: {df.columns.tolist()}")

# ── Clean column names ──
df.columns = df.columns.str.strip().str.lower()

# ── Keep only needed columns ──
df = df[["user_id", "date", "transaction_type", "category", "amount"]]

# ── Clean transaction_type ──
df["transaction_type"] = df["transaction_type"].str.strip().str.title()
df = df[df["transaction_type"].isin(["Income", "Expense"])]

# ── Clean amount ──
df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
df = df.dropna(subset=["amount"])
df = df[(df["amount"] > 0) & (df["amount"] < 500000)]

# ── Parse dates — handle multiple formats ──
df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=False)
df = df.dropna(subset=["date"])
df["year"] = df["date"].dt.year
df["month"] = df["date"].dt.month

# ── Standardise categories ──
category_map = {
    # Food variants
    "food": "Food", "foods": "Food", "fod": "Food",
    "food & drink": "Food", "food and drink": "Food",
    "foodd": "Food", "foood": "Food",
    # Rent variants
    "rent": "Rent", "rentt": "Rent", "rент": "Rent",
    # Entertainment variants
    "entertainment": "Entertainment",
    # Shopping variants
    "shopping": "Shopping",
    # Health variants
    "health": "Health", "healthcare": "Health",
    "health & fitness": "Health", "health and fitness": "Health",
    # Travel variants
    "travel": "Travel", "transport": "Travel",
    # Utilities variants
    "utilities": "Utilities", "utility": "Utilities",
    # Education variants
    "education": "Education",
    # Income types
    "salary": "Salary", "freelance": "Freelance",
    "others": "Others", "other": "Others",
    "investment": "Investment", "investments": "Investment",
}

df["category"] = df["category"].str.strip().str.lower().map(
    lambda x: category_map.get(x, x.title()) if isinstance(x, str) else "Other"
)

print(f"\nAfter cleaning: {df.shape}")
print(f"Date range: {df['date'].min()} — {df['date'].max()}")
print(f"Unique users: {df['user_id'].nunique()}")
print(f"Transaction types:\n{df['transaction_type'].value_counts()}")
print(f"\nTop categories:\n{df['category'].value_counts().head(10)}")

# ── Engineer monthly features per user ──
def get_category_sum(g, cat):
    return g[(g["transaction_type"] == "Expense") & (g["category"] == cat)]["amount"].sum()

records = []
for (user_id, year, month), g in df.groupby(["user_id", "year", "month"]):
    total_expenses = g[g["transaction_type"] == "Expense"]["amount"].sum()
    total_income = g[g["transaction_type"] == "Income"]["amount"].sum()

    if total_expenses == 0:
        continue

    records.append({
        "user_id": user_id,
        "year": year,
        "month": month,
        "total_expenses": total_expenses,
        "total_income": total_income,
        "food": get_category_sum(g, "Food"),
        "rent": get_category_sum(g, "Rent"),
        "entertainment": get_category_sum(g, "Entertainment"),
        "shopping": get_category_sum(g, "Shopping"),
        "health": get_category_sum(g, "Health"),
        "travel": get_category_sum(g, "Travel"),
        "utilities": get_category_sum(g, "Utilities"),
        "education": get_category_sum(g, "Education"),
        "num_transactions": len(g[g["transaction_type"] == "Expense"]),
        "expense_ratio": total_expenses / total_income if total_income > 0 else 0,
        "month_num": month,
    })

monthly = pd.DataFrame(records)
monthly = monthly.sort_values(["user_id", "year", "month"]).reset_index(drop=True)

print(f"\nTotal user-month records: {len(monthly)}")
print(f"Unique users with data: {monthly['user_id'].nunique()}")

# ── Add lag and rolling features per user ──
monthly["lag_1"] = monthly.groupby("user_id")["total_expenses"].shift(1)
monthly["lag_2"] = monthly.groupby("user_id")["total_expenses"].shift(2)
monthly["rolling_3m"] = monthly.groupby("user_id")["total_expenses"].transform(
    lambda x: x.shift(1).rolling(3, min_periods=1).mean()
)
monthly["spending_trend"] = monthly.groupby("user_id")["total_expenses"].transform(
    lambda x: x - x.shift(3).fillna(x.mean())
)
monthly["income_trend"] = monthly.groupby("user_id")["total_income"].transform(
    lambda x: x - x.shift(3).fillna(x.mean())
)

# ── Target: next month spending ratio per user ──
monthly["next_month_expenses"] = monthly.groupby("user_id")["total_expenses"].shift(-1)
monthly["spending_ratio"] = monthly["next_month_expenses"] / monthly["total_expenses"]

# ── Remove unstable ratios ──
monthly = monthly[
    (monthly["spending_ratio"] >= 0.5) &
    (monthly["spending_ratio"] <= 2.0) &
    (monthly["total_expenses"] > 10)
].dropna(subset=["spending_ratio", "lag_1", "lag_2"])

print(f"\nRecords after cleaning: {len(monthly)}")
print(f"Spending ratio range: {monthly['spending_ratio'].min():.3f} — {monthly['spending_ratio'].max():.3f}")
print(f"Mean ratio: {monthly['spending_ratio'].mean():.3f}")
print(f"Std ratio: {monthly['spending_ratio'].std():.3f}")

# ── Save fallback values ──
kaggle_avg_ratio = round(monthly["spending_ratio"].mean(), 4)
kaggle_avg_total = round(monthly["total_expenses"].mean(), 2)
print(f"\nFallback avg ratio: {kaggle_avg_ratio:.4f}")
print(f"Fallback avg total: £{kaggle_avg_total:.2f}")

# ── Features ──
feature_cols = [
    "total_expenses", "total_income",
    "food", "rent", "entertainment", "shopping",
    "health", "travel", "utilities", "education",
    "num_transactions", "expense_ratio", "month_num",
    "lag_1", "lag_2", "rolling_3m",
    "spending_trend", "income_trend"
]

X = monthly[feature_cols]
y = monthly["spending_ratio"]

# ── Time-based split ──
split_idx = int(len(monthly) * 0.8)
X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

print(f"\nTraining on {len(X_train)} records, testing on {len(X_test)} records")

# ── Random Forest Regressor ──
model = RandomForestRegressor(
    n_estimators=200,
    max_depth=6,
    min_samples_leaf=2,
    random_state=42
)
model.fit(X_train, y_train)
y_pred = np.clip(model.predict(X_test), 0.5, 2.0)

# ── Evaluation ──
mae = mean_absolute_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)
print(f"\nRandom Forest — Time-Based Split:")
print(f"Test MAE: {mae:.4f} (ratio units)")
print(f"Test R²: {r2:.4f}")

# ── Time Series CV ──
tscv = TimeSeriesSplit(n_splits=5)
cv_r2_scores = []
cv_mae_scores = []

for train_idx, test_idx in tscv.split(X):
    X_cv_train, X_cv_test = X.iloc[train_idx], X.iloc[test_idx]
    y_cv_train, y_cv_test = y.iloc[train_idx], y.iloc[test_idx]

    m = RandomForestRegressor(
        n_estimators=200, max_depth=6,
        min_samples_leaf=2, random_state=42
    )
    m.fit(X_cv_train, y_cv_train)
    y_cv_pred = np.clip(m.predict(X_cv_test), 0.5, 2.0)
    cv_r2_scores.append(r2_score(y_cv_test, y_cv_pred))
    cv_mae_scores.append(mean_absolute_error(y_cv_test, y_cv_pred))

cv_r2 = np.mean(cv_r2_scores)
cv_mae = np.mean(cv_mae_scores)

print(f"\nTime Series CV (5 folds):")
print(f"CV R²: {cv_r2:.4f} (+/- {np.std(cv_r2_scores):.4f})")
print(f"CV MAE: {cv_mae:.4f}")

# ── Feature importances ──
print("\nFeature Importances:")
for feat, imp in sorted(zip(feature_cols, model.feature_importances_), key=lambda x: -x[1]):
    if imp > 0.01:
        print(f"  {feat}: {imp:.3f}")

# ── Save ──
joblib.dump(model, os.path.join(BASE_DIR, "spending_forecast_model.pkl"))
joblib.dump(feature_cols, os.path.join(BASE_DIR, "forecast_feature_cols.pkl"))
joblib.dump(kaggle_avg_ratio, os.path.join(BASE_DIR, "kaggle_avg_ratio.pkl"))
joblib.dump(kaggle_avg_total, os.path.join(BASE_DIR, "kaggle_avg_total.pkl"))

print(f"\nAll models saved to ml_models/")
print(f"Final CV R²: {cv_r2:.4f}")
print(f"Final CV MAE: {cv_mae:.4f}")