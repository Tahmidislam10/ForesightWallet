from flask import Blueprint, render_template, request, redirect, session
from extensions import users_collection, bcrypt

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        existing_user = users_collection.find_one({"email": request.form["email"]})
        if existing_user:
            return "User already exists"

        hashed_pw = bcrypt.generate_password_hash(request.form["password"]).decode("utf-8")
        new_user = {
            "first_name": request.form["first_name"],
            "last_name": request.form["last_name"],
            "email": request.form["email"],
            "password": hashed_pw
        }
        result = users_collection.insert_one(new_user)
        session["user_id"] = str(result.inserted_id)
        return redirect("/dashboard")

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = users_collection.find_one({"email": request.form["email"]})
        if user and bcrypt.check_password_hash(user["password"], request.form["password"]):
            session["user_id"] = str(user["_id"])
            return redirect("/dashboard")
        return "Invalid email or password"

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect("/")