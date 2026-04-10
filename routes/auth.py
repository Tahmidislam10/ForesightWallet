from flask import Blueprint, render_template, request, redirect, session, url_for
from extensions import users_collection, bcrypt
from requests_oauthlib import OAuth2Session
import os

auth_bp = Blueprint("auth", __name__)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"]


# Register new user with email and password
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


# Log in existing user with email and password
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = users_collection.find_one({"email": request.form["email"]})
        if user and user.get("password") and bcrypt.check_password_hash(user["password"], request.form["password"]):
            session["user_id"] = str(user["_id"])
            return redirect("/dashboard")
        return render_template("login.html", error="Invalid email or password")
    return render_template("login.html")


# Start Google OAuth login flow
@auth_bp.route("/google-login")
def google_login():
    redirect_uri = url_for("auth.google_callback", _external=True)
    oauth = OAuth2Session(GOOGLE_CLIENT_ID, redirect_uri=redirect_uri, scope=SCOPES)
    authorization_url, state = oauth.authorization_url(GOOGLE_AUTH_URL, access_type="offline")
    session["oauth_state"] = state
    return redirect(authorization_url)



# Handle Google OAuth callback and create/update user
@auth_bp.route("/google/callback")
def google_callback():
    try:
        redirect_uri = url_for("auth.google_callback", _external=True)
        oauth = OAuth2Session(GOOGLE_CLIENT_ID, redirect_uri=redirect_uri, state=session.get("oauth_state"))
        token = oauth.fetch_token(GOOGLE_TOKEN_URL, client_secret=GOOGLE_CLIENT_SECRET, authorization_response=request.url)
        userinfo = oauth.get(GOOGLE_USERINFO_URL).json()
        email = userinfo.get("email")
        first_name = userinfo.get("given_name", "")
        last_name = userinfo.get("family_name", "")
        user = users_collection.find_one({"email": email})
        profile_picture = userinfo.get("picture", None)
        if not user:
            result = users_collection.insert_one({
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "password": None,
                "google_auth": True,
                "profile_picture": profile_picture
            })
            session["user_id"] = str(result.inserted_id)
        else:
            # Update profile picture every login in case it changed
            users_collection.update_one(
                {"_id": user["_id"]},
                {"$set": {"profile_picture": profile_picture}}
            )
            session["user_id"] = str(user["_id"])
        return redirect("/dashboard")
    except Exception as e:
        print(f"Google auth error: {e}")
        return redirect("/login")

# Log out user and clear session
@auth_bp.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect("/")