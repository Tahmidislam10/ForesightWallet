import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import joblib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(os.path.join(BASE_DIR, "budgetwise_finance_dataset.csv"))

print(f"Raw dataset shape: {df.shape}")

# Clean column names
df.columns = df.columns.str.strip().str.lower()
df = df[["user_id", "date", "transaction_type", "category", "amount"]]
df["transaction_type"] = df["transaction_type"].str.strip().str.title()
df = df[df["transaction_type"].isin(["Income", "Expense"])]
df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
df = df.dropna(subset=["amount"])
df = df[(df["amount"] > 0) & (df["amount"] < 500000)]
df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=False)
df = df.dropna(subset=["date"])
df["year"] = df["date"].dt.year
df["month"] = df["date"].dt.month

# Standardise categories
category_map = {
    "food": "Food", "foods": "Food", "fod": "Food",
    "food & drink": "Food", "food and drink": "Food",
    "foodd": "Food", "foood": "Food",
    "rent": "Rent", "rentt": "Rent",
    "entertainment": "Entertainment",
    "shopping": "Shopping",
    "health": "Health", "healthcare": "Health",
    "health & fitness": "Health", "health and fitness": "Health",
    "travel": "Travel", "transport": "Travel",
    "utilities": "Utilities", "utility": "Utilities",
    "education": "Education",
    "salary": "Salary", "freelance": "Freelance",
    "others": "Others", "other": "Others",
    "investment": "Investment", "investments": "Investment",
}
df["category"] = df["category"].str.strip().str.lower().map(
    lambda x: category_map.get(x, x.title()) if isinstance(x, str) else "Other"
)

# Build user-level features ──
# For clustering we aggregate across ALL months per user
# to get their overall spending profile
records = []
for user_id, g in df.groupby("user_id"):
    expenses = g[g["transaction_type"] == "Expense"]
    income = g[g["transaction_type"] == "Income"]

    total_expenses = expenses["amount"].sum()
    total_income = income["amount"].sum()

    if total_expenses == 0:
        continue

    def cat_pct(cat):
        return expenses[expenses["category"] == cat]["amount"].sum() / total_expenses

    expense_ratio = total_expenses / total_income if total_income > 0 else 0
    savings_pct = 1 - expense_ratio if expense_ratio < 1 else 0

    records.append({
        "user_id": user_id,
        "food_pct": cat_pct("Food"),
        "rent_pct": cat_pct("Rent"),
        "entertainment_pct": cat_pct("Entertainment"),
        "shopping_pct": cat_pct("Shopping"),
        "health_pct": cat_pct("Health"),
        "travel_pct": cat_pct("Travel"),
        "utilities_pct": cat_pct("Utilities"),
        "education_pct": cat_pct("Education"),
        "expense_ratio": expense_ratio,
        "savings_pct": savings_pct,
    })

user_profiles = pd.DataFrame(records)
print(f"\nUser profiles built: {len(user_profiles)}")

# Features for clustering 
feature_cols = [
    "food_pct", "rent_pct", "entertainment_pct", "shopping_pct",
    "health_pct", "travel_pct", "utilities_pct", "education_pct",
    "expense_ratio", "savings_pct"
]

X = user_profiles[feature_cols].fillna(0)

# Scale features 
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Elbow method — find optimal K 
from sklearn.metrics import silhouette_score

inertias = []
silhouette_scores = []
K_range = range(2, 8)

for k in K_range:
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    km.fit(X_scaled)
    inertias.append(km.inertia_)
    silhouette_scores.append(silhouette_score(X_scaled, km.labels_))

print("\nElbow Method (Inertia):")
for k, inertia in zip(K_range, inertias):
    print(f"  K={k}: {inertia:.2f}")

print("\nSilhouette Scores:")
for k, score in zip(K_range, silhouette_scores):
    print(f"  K={k}: {score:.4f}")

best_k = K_range[silhouette_scores.index(max(silhouette_scores))]
print(f"\nBest K by silhouette: {best_k}")
print(f"Chosen K=3 for interpretability (Saver / Balanced / Leisure-Heavy)")

#  K-Means with 3 clusters 
kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
kmeans.fit(X_scaled)
user_profiles["cluster"] = kmeans.labels_

#  Final silhouette score for K=3 
final_silhouette = silhouette_score(X_scaled, kmeans.labels_)
print(f"\nFinal Silhouette Score (K=3): {final_silhouette:.4f}")
print("(Score closer to 1.0 = well-separated clusters, >0.3 = acceptable)")

#  Analyse clusters to assign labels
cluster_summary = user_profiles.groupby("cluster")[feature_cols].mean()
print("\nCluster centres:")
print(cluster_summary.round(3))

# Assign meaningful labels based on expense_ratio and entertainment+shopping %
# Saver = low expense_ratio, Balanced = medium, Leisure-Heavy = high entertainment/shopping
cluster_expense_ratio = cluster_summary["expense_ratio"]
cluster_leisure = cluster_summary["entertainment_pct"] + cluster_summary["shopping_pct"]

sorted_by_expense = cluster_expense_ratio.sort_values()
sorted_by_leisure = cluster_leisure.sort_values(ascending=False)

cluster_labels = {}
assigned = set()

# Saver = lowest expense ratio
saver_cluster = sorted_by_expense.index[0]
cluster_labels[saver_cluster] = "Saver"
assigned.add(saver_cluster)

# Leisure-Heavy = highest leisure %
for idx in sorted_by_leisure.index:
    if idx not in assigned:
        cluster_labels[idx] = "Leisure-Heavy"
        assigned.add(idx)
        break

# Balanced = remaining
for idx in range(3):
    if idx not in assigned:
        cluster_labels[idx] = "Balanced"
        assigned.add(idx)

print(f"\nCluster label assignments: {cluster_labels}")

cluster_counts = user_profiles["cluster"].value_counts()
for c, label in cluster_labels.items():
    print(f"  Cluster {c} ({label}): {cluster_counts[c]} users")

# Save
joblib.dump(kmeans, os.path.join(BASE_DIR, "kmeans_model.pkl"))
joblib.dump(scaler, os.path.join(BASE_DIR, "kmeans_scaler.pkl"))
joblib.dump(feature_cols, os.path.join(BASE_DIR, "kmeans_feature_cols.pkl"))
joblib.dump(cluster_labels, os.path.join(BASE_DIR, "kmeans_cluster_labels.pkl"))
joblib.dump(final_silhouette, os.path.join(BASE_DIR, "kmeans_silhouette.pkl"))

print(f"\nAll K-Means models saved to ml_models/")
print(f"Cluster labels: {cluster_labels}")
print(f"Silhouette Score: {final_silhouette:.4f}")