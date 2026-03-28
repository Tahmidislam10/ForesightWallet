import os
from pymongo import MongoClient
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))

db = client["foresight_wallet"]

users_collection = db["users"]
spending_collection = db["spending"]
budget_collection = db["budgets"]

bcrypt = Bcrypt()