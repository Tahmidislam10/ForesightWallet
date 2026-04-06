import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, r2_score
import joblib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(os.path.join(BASE_DIR, "Personal_Finance_Dataset.csv"))

# ── Clean ──
df.columns = df.columns.str.strip()
df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df = df.dropna(subset=["Date", "Amount", "Type", "Category"])
df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
df = df.dropna(subset=["Amount"])
df["Year"] = df["Date"].dt.year
df["Month"] = df["Date"].dt.month

# ── Engineer monthly features ──
monthly = df.groupby(["Year", "Month"]).apply(lambda g: pd.Series({
    "total_expenses": g[g["Type"] == "Expense"]["Amount"].sum(),
    "total_income": g[g["Type"] == "Income"]["Amount"].sum(),
    "food_drink": g[(g["Type"] == "Expense") & (g["Category"] == "Food & Drink")]["Amount"].sum(),
    "rent": g[(g["Type"] == "Expense") & (g["Category"] == "Rent")]["Amount"].sum(),
    "entertainment": g[(g["Type"] == "Expense") & (g["Category"] == "Entertainment")]["Amount"].sum(),
    "shopping": g[(g["Type"] == "Expense") & (g["Category"] == "Shopping")]["Amount"].sum(),
    "health_fitness": g[(g["Type"] == "Expense") & (g["Category"] == "Health & Fitness")]["Amount"].sum(),
    "travel": g[(g["Type"] == "Expense") & (g["Category"] == "Travel")]["Amount"].sum(),
    "utilities": g[(g["Type"] == "Expense") & (g["Category"] == "Utilities")]["Amount"].sum(),
    "num_transactions": len(g[g["Type"] == "Expense"]),
    "expense_ratio": g[g["Type"] == "Expense"]["Amount"].sum() / g[g["Type"] == "Income"]["Amount"].sum()
        if g[g["Type"] == "Income"]["Amount"].sum() > 0 else 0,
}), include_groups=False).reset_index()

# ── Sort chronologically — critical for time series ──
monthly = monthly.sort_values(["Year", "Month"]).reset_index(drop=True)

# ── Add richer features ──
# Lag features
monthly["lag_1"] = monthly["total_expenses"].shift(1)
monthly["lag_2"] = monthly["total_expenses"].shift(2)

# Rolling 3-month average expenses
monthly["rolling_3m_expenses"] = monthly["total_expenses"].rolling(window=3, min_periods=1).mean()

# Spending trend — difference between this month and 3 months ago
monthly["spending_trend"] = monthly["total_expenses"] - monthly["total_expenses"].shift(3).fillna(monthly["total_expenses"].mean())

# Month number — captures seasonality
monthly["month_num"] = monthly["Month"]

# Income trend
monthly["income_trend"] = monthly["total_income"] - monthly["total_income"].shift(3).fillna(monthly["total_income"].mean())

# Expense to income ratio trend
monthly["ratio_trend"] = monthly["expense_ratio"] - monthly["expense_ratio"].shift(3).fillna(monthly["expense_ratio"].mean())

# ── Target: spending change ratio ──
monthly["next_month_expenses"] = monthly["total_expenses"].shift(-1)
monthly["spending_ratio"] = monthly["next_month_expenses"] / monthly["total_expenses"]

# ── Remove unstable ratios ──
monthly = monthly[
    (monthly["spending_ratio"] >= 0.5) &
    (monthly["spending_ratio"] <= 2.0) &
    (monthly["total_expenses"] > 100)
].dropna(subset=["spending_ratio"])

print(f"Total monthly records after cleaning: {len(monthly)}")
print(f"Spending ratio range: {monthly['spending_ratio'].min():.3f} — {monthly['spending_ratio'].max():.3f}")
print(f"Mean ratio: {monthly['spending_ratio'].mean():.3f}")
print(f"Std ratio: {monthly['spending_ratio'].std():.3f}")

# ── Save Kaggle fallback values ──
kaggle_avg_ratio = round(monthly["spending_ratio"].mean(), 4)
kaggle_avg_total = round(monthly["total_expenses"].mean(), 2)
print(f"\nKaggle average monthly total: £{kaggle_avg_total:.2f}")
print(f"Kaggle average spending ratio (fallback): {kaggle_avg_ratio:.4f}")

# ── Features ──
feature_cols = [
    "total_expenses", "total_income",
    "food_drink", "rent", "entertainment", "shopping",
    "health_fitness", "travel", "utilities",
    "num_transactions", "expense_ratio",
    "rolling_3m_expenses", "spending_trend",
    "month_num", "income_trend", "ratio_trend",
    "lag_1", "lag_2"
]

X = monthly[feature_cols]
y = monthly["spending_ratio"]

# ── Time-based split — train on past, test on future ──
split_idx = int(len(monthly) * 0.8)
X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

print(f"\nTraining on {len(X_train)} months, testing on {len(X_test)} months")
print(f"Train period: up to month index {split_idx}")
print(f"Test period: last {len(X_test)} months")

# ── Random Forest Regressor ──
model = RandomForestRegressor(
    n_estimators=200,
    max_depth=6,
    min_samples_leaf=2,
    random_state=42
)
model.fit(X_train, y_train)
y_pred = model.predict(X_test)
y_pred_clamped = np.clip(y_pred, 0.5, 2.0)

# ── Evaluation ──
mae = mean_absolute_error(y_test, y_pred_clamped)
r2 = r2_score(y_test, y_pred_clamped)

print(f"\nRandom Forest Regressor — Time-Based Split Results:")
print(f"Test MAE: {mae:.4f} (ratio units)")
print(f"Test R²: {r2:.4f}")

# ── Time Series Cross Validation ──
tscv = TimeSeriesSplit(n_splits=5)
cv_r2_scores = []
cv_mae_scores = []

for train_idx, test_idx in tscv.split(X):
    X_cv_train, X_cv_test = X.iloc[train_idx], X.iloc[test_idx]
    y_cv_train, y_cv_test = y.iloc[train_idx], y.iloc[test_idx]

    model_cv = RandomForestRegressor(
        n_estimators=200,
        max_depth=6,
        min_samples_leaf=2,
        random_state=42
    )
    model_cv.fit(X_cv_train, y_cv_train)
    y_cv_pred = np.clip(model_cv.predict(X_cv_test), 0.5, 2.0)

    cv_r2_scores.append(r2_score(y_cv_test, y_cv_pred))
    cv_mae_scores.append(mean_absolute_error(y_cv_test, y_cv_pred))

cv_r2 = np.mean(cv_r2_scores)
cv_mae = np.mean(cv_mae_scores)

print(f"\nTime Series Cross Validation (5 folds):")
print(f"CV R²: {cv_r2:.4f} (+/- {np.std(cv_r2_scores):.4f})")
print(f"CV MAE: {cv_mae:.4f} (ratio units)")

# ── Feature importances ──
print("\nFeature Importances:")
for feat, imp in sorted(zip(feature_cols, model.feature_importances_), key=lambda x: -x[1]):
    if imp > 0.01:
        print(f"  {feat}: {imp:.3f}")

# ── Save ──
joblib.dump(model, os.path.join(BASE_DIR, "spending_forecast_model_old.pkl"))
joblib.dump(feature_cols, os.path.join(BASE_DIR, "forecast_feature_cols_old.pkl"))
joblib.dump(kaggle_avg_ratio, os.path.join(BASE_DIR, "kaggle_avg_ratio_old.pkl"))
joblib.dump(kaggle_avg_total, os.path.join(BASE_DIR, "kaggle_avg_total_old.pkl"))

print(f"\nOld models saved to ml_models/ with _old suffix")
print(f"Final CV R²: {cv_r2:.4f}")
print(f"Final CV MAE: {cv_mae:.4f}")