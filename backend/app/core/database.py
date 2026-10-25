from pymongo import MongoClient

from app.core.config import settings


client = MongoClient(settings.mongodb_url)

database = client[settings.mongodb_database]

users_collection = database["users"]
wallets_collection = database["wallets"]
wallet_transactions_collection = database["wallet_transactions"]

usage_records_collection = database["usage_records"]

wallet_reservations_collection = database["wallet_reservations"]
gateway_requests_collection = database["gateway_requests"]
