from flask import Blueprint, render_template, redirect, session
from datetime import datetime
from helpers import (
    build_budget_doc_lookup,
    get_planned_deductions_history_from_lookup,
    get_deductions_summary_from_lookup,
)

planned_deductions_bp = Blueprint("planned_deductions", __name__)


@planned_deductions_bp.route("/planned-deductions")
def planned_deductions():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    now = datetime.utcnow()

    # Last 6 months
    deductions_6m_months = []
    for i in range(5, -1, -1):
        total_months = now.year * 12 + now.month - 1 - i
        y = total_months // 12
        m = total_months % 12 + 1
        deductions_6m_months.append((y, m))

    # Last 12 months
    deductions_12m_months = []
    for i in range(11, -1, -1):
        total_months = now.year * 12 + now.month - 1 - i
        y = total_months // 12
        m = total_months % 12 + 1
        deductions_12m_months.append((y, m))

    all_months = deductions_6m_months + deductions_12m_months
    for yr in [now.year - 1, now.year, now.year + 1]:
        all_months.extend((yr, m) for m in range(1, 13))

    budget_docs = build_budget_doc_lookup(user_id, all_months)

    deductions_6m = get_planned_deductions_history_from_lookup(deductions_6m_months, budget_docs)
    deductions_12m = get_planned_deductions_history_from_lookup(deductions_12m_months, budget_docs)

    deductions_by_year = {}
    summary_by_year = {}
    for yr in [now.year - 1, now.year, now.year + 1]:
        yr_months = [(yr, m) for m in range(1, 13)]
        deductions_by_year[str(yr)] = get_planned_deductions_history_from_lookup(yr_months, budget_docs)
        summary_by_year[str(yr)] = get_deductions_summary_from_lookup(yr_months, budget_docs)

    summary_6m = get_deductions_summary_from_lookup(deductions_6m_months, budget_docs)
    summary_12m = get_deductions_summary_from_lookup(deductions_12m_months, budget_docs)

    return render_template(
        "planned_deductions.html",
        deductions_6m=deductions_6m,
        deductions_12m=deductions_12m,
        deductions_by_year=deductions_by_year,
        summary_6m=summary_6m,
        summary_12m=summary_12m,
        summary_by_year=summary_by_year,
    )
