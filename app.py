from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/spending-log")
def spending_log():
    return render_template("spending_log.html")

@app.route("/insights")
def insights():
    return render_template("insights.html")

@app.route("/budget-tracker")
def budget_tracker():
    return render_template("budget_tracker.html")

@app.route("/feedback")
def feedback():
    return render_template("feedback.html")

if __name__ == "__main__":
    app.run(debug=True)