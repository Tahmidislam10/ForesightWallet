import os
from flask import Flask, render_template, session
from dotenv import load_dotenv
from extensions import bcrypt

from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.spending import spending_bp
from routes.budget import budget_bp

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

bcrypt.init_app(app)

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(spending_bp)
app.register_blueprint(budget_bp)


@app.route("/")
def landing():
    return render_template("landing.html")


if __name__ == "__main__":
    app.run(debug=True)