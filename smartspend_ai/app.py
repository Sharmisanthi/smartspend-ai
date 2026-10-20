from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os
from pathlib import Path
from datetime import date, datetime, timedelta
from statistics import median

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("SMARTSPEND_DB_PATH", str(BASE_DIR / "smartspend.db")))
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "smartspend-dev-key-change-before-deployment")

CATEGORIES = ["Food", "Transport", "Shopping", "Bills", "Education", "Health", "Entertainment", "Housing", "Other"]


def connect_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect_db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL CHECK(kind IN ('income','expense')),
            amount REAL NOT NULL CHECK(amount > 0),
            category TEXT NOT NULL,
            description TEXT DEFAULT '',
            txn_date TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            monthly_budget REAL NOT NULL DEFAULT 10000
        )""")
        conn.execute("INSERT OR IGNORE INTO settings (id, monthly_budget) VALUES (1, 10000)")
        count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        if count == 0:
            # Demo data helps the dashboard look useful on first launch. You can delete it.
            today = date.today()
            demo = [
                ("income", 30000, "Salary", "Monthly salary", today.replace(day=1).isoformat()),
                ("expense", 1800, "Housing", "Room rent contribution", (today - timedelta(days=1)).isoformat()),
                ("expense", 320, "Food", "Groceries", (today - timedelta(days=2)).isoformat()),
                ("expense", 150, "Transport", "Bus and auto", (today - timedelta(days=3)).isoformat()),
                ("expense", 650, "Shopping", "Clothing", (today - timedelta(days=5)).isoformat()),
                ("expense", 240, "Food", "Lunch and snacks", (today - timedelta(days=6)).isoformat()),
                ("expense", 900, "Bills", "Internet and phone", (today - timedelta(days=8)).isoformat()),
                ("expense", 420, "Entertainment", "Movie", (today - timedelta(days=10)).isoformat()),
                ("expense", 280, "Food", "Dinner", (today - timedelta(days=12)).isoformat()),
                ("expense", 1200, "Education", "Course materials", (today - timedelta(days=14)).isoformat()),
                ("expense", 350, "Health", "Pharmacy", (today - timedelta(days=18)).isoformat()),
                ("expense", 500, "Shopping", "Online order", (today - timedelta(days=20)).isoformat()),
            ]
            conn.executemany("INSERT INTO transactions (kind, amount, category, description, txn_date) VALUES (?, ?, ?, ?, ?)", demo)


def get_metrics():
    today = date.today()
    month_start = today.replace(day=1).isoformat()
    next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1).isoformat()
    with connect_db() as conn:
        month_rows = conn.execute("SELECT * FROM transactions WHERE txn_date >= ? AND txn_date < ? ORDER BY txn_date DESC, id DESC", (month_start, next_month)).fetchall()
        all_expenses = conn.execute("SELECT * FROM transactions WHERE kind='expense' ORDER BY txn_date DESC, id DESC").fetchall()
        budget = float(conn.execute("SELECT monthly_budget FROM settings WHERE id=1").fetchone()[0])
        all_rows = conn.execute("SELECT * FROM transactions ORDER BY txn_date DESC, id DESC").fetchall()

    month_income = sum(float(r['amount']) for r in month_rows if r['kind'] == 'income')
    month_expenses = sum(float(r['amount']) for r in month_rows if r['kind'] == 'expense')
    savings = month_income - month_expenses
    remaining_budget = budget - month_expenses

    category_totals = {}
    for r in month_rows:
        if r['kind'] == 'expense':
            category_totals[r['category']] = category_totals.get(r['category'], 0) + float(r['amount'])
    category_labels = list(category_totals.keys())
    category_values = [round(v, 2) for v in category_totals.values()]

    # Current-month daily spend chart, including zero-spend days.
    daily_labels, daily_values = [], []
    daily_map = {}
    for r in month_rows:
        if r['kind'] == 'expense':
            daily_map[r['txn_date']] = daily_map.get(r['txn_date'], 0) + float(r['amount'])
    for day_num in range(1, today.day + 1):
        d = today.replace(day=day_num)
        daily_labels.append(d.strftime('%d %b'))
        daily_values.append(round(daily_map.get(d.isoformat(), 0), 2))

    # Forecast: average daily expenses so far this month multiplied by days in month.
    # This is a simple baseline forecast, not a trained ML model.
    days_in_month = (date(today.year + (today.month == 12), 1 if today.month == 12 else today.month + 1, 1) - timedelta(days=1)).day
    forecast = (month_expenses / max(today.day, 1)) * days_in_month

    # Flag a transaction when it is > 2x the historical median expense (minimum history required).
    history_amounts = [float(r['amount']) for r in all_expenses if r['txn_date'] < today.isoformat()]
    typical = median(history_amounts) if len(history_amounts) >= 4 else None
    alerts = []
    for r in all_expenses:
        amount = float(r['amount'])
        if typical and amount > 2 * typical:
            alerts.append({"date": r['txn_date'], "category": r['category'], "amount": amount, "description": r['description'] or r['category']})
        if len(alerts) >= 3:
            break

    recommendations = []
    if month_expenses == 0:
        recommendations.append("Add your expenses to receive personalized spending insights.")
    else:
        if remaining_budget < 0:
            recommendations.append(f"You are ₹{abs(remaining_budget):,.0f} over your monthly budget. Pause non-essential purchases where possible.")
        elif remaining_budget <= budget * 0.2:
            recommendations.append(f"Only ₹{remaining_budget:,.0f} of your budget remains. Review upcoming bills before spending more.")
        else:
            recommendations.append(f"You have ₹{remaining_budget:,.0f} left in your monthly budget. Keep checking your spending through the month.")
        if category_totals:
            top_category = max(category_totals, key=category_totals.get)
            potential = category_totals[top_category] * 0.10
            recommendations.append(f"Your highest spending category is {top_category} (₹{category_totals[top_category]:,.0f}). Reducing it by 10% could free about ₹{potential:,.0f} this month.")
        if savings > 0:
            recommendations.append(f"Your current monthly balance is ₹{savings:,.0f}. Consider setting aside a realistic part of it as savings after essential expenses.")
        else:
            recommendations.append("Your expenses are at or above your income this month. Prioritize essentials and review flexible spending first.")

    return {
        "today": today.isoformat(), "month_name": today.strftime('%B %Y'),
        "income": month_income, "expenses": month_expenses, "savings": savings,
        "budget": budget, "remaining_budget": remaining_budget, "forecast": forecast,
        "category_labels": category_labels, "category_values": category_values,
        "daily_labels": daily_labels, "daily_values": daily_values,
        "transactions": all_rows[:50], "categories": CATEGORIES,
        "recommendations": recommendations, "alerts": alerts,
        "budget_percent": min(100, (month_expenses / budget * 100)) if budget > 0 else 0,
    }


@app.route('/')
def dashboard():
    return render_template('index.html', **get_metrics())


@app.post('/add')
def add_transaction():
    kind = request.form.get('kind', 'expense')
    category = request.form.get('category', 'Other')
    description = request.form.get('description', '').strip()[:120]
    txn_date = request.form.get('txn_date', date.today().isoformat())
    try:
        amount = float(request.form.get('amount', '0'))
        parsed_date = datetime.strptime(txn_date, '%Y-%m-%d').date()
        if kind not in ('income', 'expense') or amount <= 0:
            raise ValueError
        if kind == 'income':
            category = 'Income'
        elif category not in CATEGORIES:
            category = 'Other'
    except (ValueError, TypeError):
        flash('Please enter a valid date and an amount greater than zero.', 'error')
        return redirect(url_for('dashboard'))
    with connect_db() as conn:
        conn.execute('INSERT INTO transactions (kind, amount, category, description, txn_date) VALUES (?, ?, ?, ?, ?)', (kind, amount, category, description, parsed_date.isoformat()))
    flash('Transaction added successfully.', 'success')
    return redirect(url_for('dashboard'))


@app.post('/delete/<int:transaction_id>')
def delete_transaction(transaction_id):
    with connect_db() as conn:
        conn.execute('DELETE FROM transactions WHERE id = ?', (transaction_id,))
    flash('Transaction deleted.', 'success')
    return redirect(url_for('dashboard'))


@app.post('/budget')
def update_budget():
    try:
        budget = float(request.form.get('monthly_budget', '0'))
        if budget <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Enter a monthly budget greater than zero.', 'error')
        return redirect(url_for('dashboard'))
    with connect_db() as conn:
        conn.execute('UPDATE settings SET monthly_budget = ? WHERE id = 1', (budget,))
    flash('Monthly budget updated.', 'success')
    return redirect(url_for('dashboard'))


@app.post('/reset-demo')
def reset_demo():
    with connect_db() as conn:
        conn.execute('DELETE FROM transactions')
    init_db()
    flash('Demo transactions restored.', 'success')
    return redirect(url_for('dashboard'))


init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '5000')), debug=False)
