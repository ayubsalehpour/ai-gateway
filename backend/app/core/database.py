from pymongo import MongoClient

from app.core.config import settings


client = MongoClient(settings.mongodb_url)

database = client[settings.mongodb_database]

users_collection = database["users"]
wallets_collection = database["wallets"]
wallet_transactions_collection = database["wallet_transactions"]