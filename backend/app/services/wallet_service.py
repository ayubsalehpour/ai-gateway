
from bson import ObjectId

from app.repositories.wallet_repository import WalletRepository


class WalletService:
    def __init__(self):
        self.repository = WalletRepository()

    def create_wallet(self, user_id: str, session=None):
        if not ObjectId.is_valid(user_id):
            raise ValueError("Invalid user ID")

        wallet = self.repository.create_wallet(
            user_id,
            session=session,
        )

        if wallet is None:
            raise RuntimeError("Failed to create or retrieve wallet")

        wallet["id"] = str(wallet.pop("_id"))
        return wallet

    def get_wallet(self, user_id: str):
        if not ObjectId.is_valid(user_id):
            raise ValueError("Invalid user ID")

        wallet = self.repository.get_by_user_id(user_id)

        if wallet is None:
            return None

        wallet["id"] = str(wallet.pop("_id"))
        return wallet

    
    def get_transactions(
        self,
        user_id: str,
        limit: int = 20,
        skip: int = 0,
    ):
        if not ObjectId.is_valid(user_id):
            raise ValueError("Invalid user ID")

        transactions = self.repository.get_transactions(
            user_id=user_id,
            limit=limit,
            skip=skip,
        )

        for transaction in transactions:
            transaction["id"] = str(transaction.pop("_id"))

        return transactions


    def credit_wallet(
        self,
        user_id: str,
        amount_toman: int,
        description: str,
        admin_id: str,
        idempotency_key: str,
        reference: str | None = None,
    ):
        if not ObjectId.is_valid(user_id):
            raise ValueError("Invalid user ID")

        if not ObjectId.is_valid(admin_id):
            raise ValueError("Invalid admin ID")

        if isinstance(amount_toman, bool) or not isinstance(amount_toman, int):
            raise ValueError("Amount must be an integer")

        if amount_toman <= 0:
            raise ValueError("Amount must be greater than zero")

        if not description or not description.strip():
            raise ValueError("Description is required")

        if not idempotency_key or not idempotency_key.strip():
            raise ValueError("Idempotency key is required")

        description = description.strip()
        idempotency_key = idempotency_key.strip()

        result = self.repository.credit_wallet_transaction(
            user_id=user_id,
            amount_toman=amount_toman,
            description=description,
            admin_id=admin_id,
            idempotency_key=idempotency_key,
            reference=reference,
        )

        if result is None:
            raise LookupError("Wallet not found")

        if result.get("duplicate"):
            transaction = result["transaction"]

            same_request = (
                transaction.get("user_id") == user_id
                and transaction.get("amount_toman") == amount_toman
                and transaction.get("description") == description
                and transaction.get("admin_id") == admin_id
                and transaction.get("reference") == reference
            )

            if not same_request:
                raise ValueError(
                    "Idempotency key has already been used "
                    "for a different request"
                )

            wallet = self.repository.get_by_user_id(user_id)

            if wallet is None:
                raise LookupError("Wallet not found")

            wallet["id"] = str(wallet.pop("_id"))
            transaction["id"] = str(transaction.pop("_id"))

            return {
                "wallet": wallet,
                "transaction": transaction,
            }

        return result
