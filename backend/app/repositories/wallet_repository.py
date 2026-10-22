from datetime import datetime, timezone

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.database import (
    client,
    wallets_collection,
    wallet_transactions_collection,
)


class WalletRepository:
    def create_wallet(self, user_id: str, session=None):
        now = datetime.now(timezone.utc)

        wallet = {
            "user_id": user_id,
            "balance_toman": 0,
            "created_at": now,
            "updated_at": now,
        }

        try:
            wallets_collection.insert_one(wallet, session=session)
        except DuplicateKeyError:
            pass

        return wallets_collection.find_one(
            {"user_id": user_id},
            session=session,
        )


    def get_by_user_id(self, user_id: str):
        return wallets_collection.find_one({"user_id": user_id})

    def create_transaction(self, transaction_data: dict):
        result = wallet_transactions_collection.insert_one(transaction_data)
        return wallet_transactions_collection.find_one(
            {"_id": result.inserted_id}
        )

    def get_transactions(
        self,
        user_id: str,
        limit: int = 20,
        skip: int = 0,
    ):
        return list(
            wallet_transactions_collection.find({"user_id": user_id})
            .sort([
                ("created_at", -1),
                ("_id", -1),
            ])
            .skip(skip)
            .limit(limit)
        )


    def create_indexes(self):
        wallets_collection.create_index("user_id", unique=True)

        wallet_transactions_collection.create_index(
        [
            ("user_id", 1),
            ("created_at", -1),
            ("_id", -1),
        ]
        )

        wallet_transactions_collection.create_index(
            "idempotency_key",
            unique=True,
            partialFilterExpression={"idempotency_key": {"$type": "string"}},
        )

      

    def credit_balance(self, user_id: str, amount_toman: int):
        now = datetime.now(timezone.utc)

        return wallets_collection.find_one_and_update(
            {
                "user_id": user_id,
                "balance_toman": {"$gte": 0},
            },
            {
                "$inc": {"balance_toman": amount_toman},
                "$set": {"updated_at": now},
            },
            return_document=ReturnDocument.AFTER,
        )


    def debit_balance(self, user_id: str, amount_toman: int):
        if isinstance(amount_toman, bool) or not isinstance(amount_toman, int):
            raise ValueError("Amount must be an integer")

        if amount_toman <= 0:
            raise ValueError("Amount must be greater than zero")

        now = datetime.now(timezone.utc)

        return wallets_collection.find_one_and_update(
            {
                "user_id": user_id,
                "balance_toman": {"$gte": amount_toman},
            },
            {
                "$inc": {"balance_toman": -amount_toman},
                "$set": {"updated_at": now},
            },
            return_document=ReturnDocument.AFTER,
        )


    def debit_wallet_transaction(
        self,
        user_id: str,
        amount_toman: int,
        description: str,
        idempotency_key: str,
        reference: str | None = None,
    ):
        if isinstance(amount_toman, bool) or not isinstance(amount_toman, int):
            raise ValueError("Amount must be an integer")

        if amount_toman <= 0:
            raise ValueError("Amount must be greater than zero")

        now = datetime.now(timezone.utc)

        try:
            with client.start_session() as session:
                with session.start_transaction():
                    existing_transaction = wallet_transactions_collection.find_one(
                        {"idempotency_key": idempotency_key},
                        session=session,
                    )

                    if existing_transaction is not None:
                        return {
                            "duplicate": True,
                            "transaction": existing_transaction,
                        }

                    wallet = wallets_collection.find_one_and_update(
                        {
                            "user_id": user_id,
                            "balance_toman": {"$gte": amount_toman},
                        },
                        {
                            "$inc": {"balance_toman": -amount_toman},
                            "$set": {"updated_at": now},
                        },
                        return_document=ReturnDocument.AFTER,
                        session=session,
                    )

                    if wallet is None:
                        return None

                    transaction_data = {
                        "wallet_id": str(wallet["_id"]),
                        "user_id": user_id,
                        "type": "debit",
                        "amount_toman": amount_toman,
                        "balance_after": wallet["balance_toman"],
                        "description": description,
                        "reference": reference,
                        "idempotency_key": idempotency_key,
                        "created_at": now,
                    }

                    result = wallet_transactions_collection.insert_one(
                        transaction_data,
                        session=session,
                    )

                    transaction_data["id"] = str(result.inserted_id)
                    wallet["id"] = str(wallet.pop("_id"))

                    return {
                        "duplicate": False,
                        "wallet": wallet,
                        "transaction": transaction_data,
                    }

        except DuplicateKeyError:
            # A duplicate idempotency key aborts the transaction.
            existing_transaction = wallet_transactions_collection.find_one(
                {"idempotency_key": idempotency_key}
            )

            if existing_transaction is None:
                raise

            return {
                "duplicate": True,
                "transaction": existing_transaction,
            }


    def credit_wallet_transaction(
        self,
        user_id: str,
        amount_toman: int,
        description: str,
        admin_id: str,
        idempotency_key: str,
        reference: str | None = None,
    ):
        if isinstance(amount_toman, bool) or not isinstance(amount_toman, int):
            raise ValueError("Amount must be an integer")

        if amount_toman <= 0:
            raise ValueError("Amount must be greater than zero")

        now = datetime.now(timezone.utc)

        try:
            with client.start_session() as session:
                with session.start_transaction():
                    existing_transaction = wallet_transactions_collection.find_one(
                        {"idempotency_key": idempotency_key},
                        session=session,
                    )

                    if existing_transaction is not None:
                        return {
                            "duplicate": True,
                            "transaction": existing_transaction,
                        }

                    wallet = wallets_collection.find_one_and_update(
                        {
                            "user_id": user_id,
                            "balance_toman": {"$gte": 0},
                        },
                        {
                            "$inc": {"balance_toman": amount_toman},
                            "$set": {"updated_at": now},
                        },
                        return_document=ReturnDocument.AFTER,
                        session=session,
                    )

                    if wallet is None:
                        return None

                    transaction_data = {
                        "wallet_id": str(wallet["_id"]),
                        "user_id": user_id,
                        "type": "credit",
                        "amount_toman": amount_toman,
                        "balance_after": wallet["balance_toman"],
                        "description": description,
                        "reference": reference,
                        "admin_id": admin_id,
                        "idempotency_key": idempotency_key,
                        "created_at": now,
                    }

                    result = wallet_transactions_collection.insert_one(
                        transaction_data,
                        session=session,
                    )

                    transaction_data["id"] = str(result.inserted_id)
                    wallet["id"] = str(wallet.pop("_id"))

                    return {
                        "duplicate": False,
                        "wallet": wallet,
                        "transaction": transaction_data,
                    }

        except DuplicateKeyError:
            # The transaction has been aborted before this lookup.
            existing_transaction = wallet_transactions_collection.find_one(
                {"idempotency_key": idempotency_key}
            )

            if existing_transaction is None:
                raise

            return {
                "duplicate": True,
                "transaction": existing_transaction,
            }
