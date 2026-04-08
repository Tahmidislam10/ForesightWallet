import os
import json
from flask import Blueprint, request, jsonify, session
from datetime import datetime
from extensions import spending_collection, budget_collection, users_collection
from helpers import normalize_section
from bson.objectid import ObjectId
from google import genai
from google.genai import types

walletwise_bp = Blueprint("walletwise", __name__)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def get_user_financial_context(user_id):
    now = datetime.utcnow()
    year, month = now.year, now.month

    budget_doc = budget_collection.find_one({
        "user_id": user_id, "year": year, "month": month
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

    month_start = datetime(year, month, 1)
    month_end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    transactions = list(spending_collection.find({
        "user_id": user_id,
        "date": {"$gte": month_start, "$lt": month_end}
    }))

    total_expenses = round(sum(t["amount"] for t in transactions if t.get("type") == "expense"), 2)
    total_income_logged = round(sum(t["amount"] for t in transactions if t.get("type") == "income"), 2)
    spending_remaining = round(spending_limit - total_expenses, 2) if spending_limit > 0 else None

    recent_transactions = sorted(
        [t for t in transactions],
        key=lambda x: x.get("date", datetime.min),
        reverse=True
    )[:5]

    recent_list = [
        f"{t.get('category', 'Unknown')} - £{t.get('amount', 0):.2f} ({t.get('type', 'expense')})"
        for t in recent_transactions
    ]

    return {
        "month": datetime(year, month, 1).strftime("%B %Y"),
        "monthly_income": monthly_income,
        "account_balance": account_balance,
        "spending_limit": spending_limit,
        "total_expenses_this_month": total_expenses,
        "spending_remaining": spending_remaining,
        "planned_deductions": planned_deductions,
        "savings_total": savings_total,
        "bills_total": bills_total,
        "debts_total": debts_total,
        "recent_transactions": recent_list,
    }


@walletwise_bp.route("/api/walletwise", methods=["POST"])
def walletwise_chat():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json()
    user_message = data.get("message", "").strip()
    chat_history = data.get("history", [])

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    user_id = session["user_id"]
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    first_name = user.get("first_name", "there") if user else "there"

    ctx = get_user_financial_context(user_id)

    system_prompt = f"""You are WalletWise, a friendly and knowledgeable personal finance assistant built into Foresight Wallet.
You are chatting with {first_name}. Be warm, concise, and genuinely helpful.

Here is {first_name}'s current financial snapshot for {ctx['month']}:
- Monthly Income: £{ctx['monthly_income']:.2f}
- Account Balance: £{ctx['account_balance']:.2f}
- Spending Limit this month: £{ctx['spending_limit']:.2f}
- Total Spent this month: £{ctx['total_expenses_this_month']:.2f}
- Spending Remaining: {'£' + str(ctx['spending_remaining']) if ctx['spending_remaining'] is not None else 'No limit set'}
- Planned Deductions (savings + bills + debts): £{ctx['planned_deductions']:.2f}
  - Savings: £{ctx['savings_total']:.2f}
  - Bills: £{ctx['bills_total']:.2f}
  - Debts: £{ctx['debts_total']:.2f}
- Recent transactions: {', '.join(ctx['recent_transactions']) if ctx['recent_transactions'] else 'None logged yet'}

Guidelines:
- Always use £ (GBP) for currency
- When asked if someone can afford something, check their spending remaining and account balance
- If they ask about a product price, search the web for the current UK price
- Keep responses concise — 2-4 sentences usually enough
- Be encouraging but honest about their finances
- Never make up financial data — only use what's provided above
- If asked something outside finance, gently redirect to financial topics
"""

    try:
        contents = []
        for msg in chat_history[-10:]:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
        contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[types.Tool(google_search=types.GoogleSearch())],
            )
        )
        reply = response.text

        return jsonify({"reply": reply})

    except Exception as e:
        print(f"WalletWise error: {str(e)}")
        return jsonify({"reply": f"Sorry, I'm having trouble right now. Please try again in a moment. Error: {str(e)}"})