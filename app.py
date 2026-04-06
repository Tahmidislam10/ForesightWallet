import os
from flask import Flask, render_template, session
from dotenv import load_dotenv
from extensions import bcrypt, users_collection
from flask import session
from bson.objectid import ObjectId

from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.spending import spending_bp
from routes.budget import budget_bp
from routes.feedback import feedback_bp
from routes.risk import risk_bp
from routes.prediction import prediction_bp

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

bcrypt.init_app(app)

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(spending_bp)
app.register_blueprint(budget_bp)
app.register_blueprint(feedback_bp)
app.register_blueprint(risk_bp)
app.register_blueprint(prediction_bp)

@app.context_processor
def inject_user():
    if "user_id" in session:
        user = users_collection.find_one({"_id": ObjectId(session["user_id"])})
        if user:
            return {"user": user}
    return {"user": None}


@app.route("/")
def landing():
    return render_template("landing.html")


if __name__ == "__main__":
    app.run(debug=True)