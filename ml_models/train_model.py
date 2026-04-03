import pandas as pd
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, classification_report
import joblib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(os.path.join(BASE_DIR, "Personal_Finance_Dataset.csv"))

# Clean data
df.columns = df.columns.str.strip()
df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df = df.dropna(subset=["Date", "Amount", "Type", "Category"])
df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
df = df.dropna(subset=["Amount"])
df["Year"] = df["Date"].dt.year
df["Month"] = df["Date"].dt.month

# Engineer monthly features
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
}), include_groups=False).reset_index()

# Target: above median total expenses = "high spending month" (naturally balanced)
median_expenses = monthly["total_expenses"].median()
monthly["exceeded_budget"] = (monthly["total_expenses"] > median_expenses).astype(int)
monthly["expense_ratio"] = monthly["total_expenses"] / monthly["total_income"].replace(0, np.nan)
monthly = monthly.dropna(subset=["expense_ratio"])

print(f"Median monthly expenses: £{median_expenses:.2f}")
print(f"Class distribution:\n{monthly['exceeded_budget'].value_counts()}")
print(f"Total monthly records: {len(monthly)}")

feature_cols = [
    "total_expenses", "total_income", "food_drink", "rent",
    "entertainment", "shopping", "health_fitness", "travel",
    "utilities", "num_transactions", "expense_ratio"
]

X = monthly[feature_cols]
y = monthly["exceeded_budget"]

# Train/test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# Decision Tree
dt_model = DecisionTreeClassifier(
    max_depth=3,
    min_samples_leaf=3,
    class_weight="balanced",
    random_state=42
)
dt_model.fit(X_train, y_train)
dt_pred = dt_model.predict(X_test)

# Evaluation
test_accuracy = accuracy_score(y_test, dt_pred)
cv_scores = cross_val_score(dt_model, X, y, cv=5)
cv_accuracy = cv_scores.mean()

print(f"\nDecision Tree Test Accuracy: {test_accuracy:.2%}")
print(f"Cross-Validation Accuracy: {cv_accuracy:.2%} (+/- {cv_scores.std():.2%})")
print(f"\nClassification Report:")
print(classification_report(y_test, dt_pred))

# Feature importances
print("Feature Importances:")
for feat, imp in sorted(zip(feature_cols, dt_model.feature_importances_), key=lambda x: -x[1]):
    if imp > 0:
        print(f"  {feat}: {imp:.3f}")

# Save
joblib.dump(dt_model, os.path.join(BASE_DIR, "decision_tree_model.pkl"))
joblib.dump(feature_cols, os.path.join(BASE_DIR, "feature_cols.pkl"))
joblib.dump(median_expenses, os.path.join(BASE_DIR, "median_expenses.pkl"))

print(f"\nModel saved to ml_models/")
print(f"Final CV Accuracy: {cv_accuracy:.2%}")