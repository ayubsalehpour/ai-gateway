
import time
from datetime import datetime, timezone

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.core.database import (
    client,
    wallets_collection,
    wallet_reservations_collection,
    wallet_transactions_collection,
    usage_records_collection,
)
from app.services.billing_exceptions import SettlementReconciliationRequired


class BillingRepository:
    def create_indexes(self) -> None:
        wallet_reservations_collection.create_index(
            "idempotency_key",
            unique=True,
        )
        wallet_reservations_collection.create_index(
            "request_id",
            unique=True,
        )
        wallet_reservations_collection.create_index(
            [("user_id", 1), ("status", 1), ("created_at", -1)]
        )
        usage_records_collection.create_index(
            "request_id",
            unique=True,
        )

    @staticmethod
    def _serialize(document: dict | None) -> dict | None:
        if document is None:
            return None

        result = dict(document)
        if "_id" in result:
            result["id"] = str(result.pop("_id"))
        return result


    
    def get_by_idempotency_key(self, idempotency_key: str) -> dict | None:
        reservation = wallet_reservations_collection.find_one(
            {"idempotency_key": idempotency_key}
        )
        return self._serialize(reservation)



    @staticmethod
    def _validate_idempotency_key(
        existing: dict,
        user_id: str,
        amount_toman: int,
        request_id: str,
    ) -> None:
        if (
            existing.get("user_id") != user_id
            or existing.get("request_id") != request_id
            or existing.get("amount_toman") != amount_toman
        ):
            raise ValueError(
                "Idempotency key has already been used "
                "for a different reservation"
            )

    def reserve(
        self,
        user_id: str,
        amount_toman: int,
        idempotency_key: str,
        request_id: str,
        metadata: dict | None = None,
    ) -> dict | None:
        if isinstance(amount_toman, bool) or not isinstance(amount_toman, int):
            raise ValueError("Reservation amount must be an integer")
        if amount_toman <= 0:
            raise ValueError("Reservation amount must be greater than zero")
        if not user_id or not idempotency_key or not request_id:
            raise ValueError(
                "User ID, idempotency key and request ID are required"
            )

        max_attempts = 3

        for attempt in range(max_attempts):
            now = datetime.now(timezone.utc)

            try:
                with client.start_session() as session:
                    with session.start_transaction():
                        existing = wallet_reservations_collection.find_one(
                            {"idempotency_key": idempotency_key},
                            session=session,
                        )

                        if existing is not None:
                            self._validate_idempotency_key(
                                existing,
                                user_id,
                                amount_toman,
                                request_id,
                            )
                            wallet = wallets_collection.find_one(
                                {"user_id": user_id},
                                session=session,
                            )
                            return {
                                "reservation": self._serialize(existing),
                                "wallet": self._serialize(wallet),
                                "duplicate": True,
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

                        reservation = {
                            "user_id": user_id,
                            "wallet_id": str(wallet["_id"]),
                            "request_id": request_id,
                            "idempotency_key": idempotency_key,
                            "amount_toman": amount_toman,
                            "status": "reserved",
                            "metadata": metadata or {},
                            "created_at": now,
                            "updated_at": now,
                        }

                        result = wallet_reservations_collection.insert_one(
                            reservation,
                            session=session,
                        )
                        reservation["_id"] = result.inserted_id

                        wallet_transactions_collection.insert_one(
                            {
                                "wallet_id": str(wallet["_id"]),
                                "user_id": user_id,
                                "type": "debit",
                                "amount_toman": amount_toman,
                                "balance_after": wallet["balance_toman"],
                                "description": "AI API credit reservation",
                                "reference": request_id,
                                "idempotency_key": (
                                    f"billing-reserve:{request_id}"
                                ),
                                "created_at": now,
                            },
                            session=session,
                        )

                        return {
                            "reservation": self._serialize(reservation),
                            "wallet": self._serialize(wallet),
                            "duplicate": False,
                        }

            except DuplicateKeyError:
                # A concurrent request may already have committed this key.
                existing = wallet_reservations_collection.find_one(
                    {"idempotency_key": idempotency_key}
                )

                if existing is None:
                    # A conflicting request_id or ledger key is not success.
                    raise

                self._validate_idempotency_key(
                    existing,
                    user_id,
                    amount_toman,
                    request_id,
                )
                wallet = wallets_collection.find_one({"user_id": user_id})
                return {
                    "reservation": self._serialize(existing),
                    "wallet": self._serialize(wallet),
                    "duplicate": True,
                }

            except PyMongoError as exc:
                is_transient = (
                    exc.has_error_label("TransientTransactionError")
                    or getattr(exc, "code", None) == 112
                )

                if not is_transient or attempt == max_attempts - 1:
                    raise

                # Retry the whole transaction, never just one write.
                time.sleep(0.05 * (2 ** attempt))

        raise RuntimeError("Reservation retry loop exited unexpectedly")

    def settle(
        self,
        idempotency_key: str,
        actual_cost_toman: int,
        usage_data: dict,
    ) -> dict:
        if (
            isinstance(actual_cost_toman, bool)
            or not isinstance(actual_cost_toman, int)
            or actual_cost_toman < 0
        ):
            raise ValueError(
                "Actual cost must be a non-negative integer"
            )

        if not isinstance(usage_data, dict):
            raise ValueError("Usage data must be a dictionary")

        request_id = usage_data.get("request_id")
        user_id = usage_data.get("user_id")

        if not isinstance(request_id, str) or not request_id.strip():
            raise ValueError("Usage request_id is required")
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("Usage user_id is required")

        now = datetime.now(timezone.utc)

        with client.start_session() as session:
            with session.start_transaction():
                reservation = wallet_reservations_collection.find_one(
                    {"idempotency_key": idempotency_key},
                    session=session,
                )

                if reservation is None:
                    raise LookupError("Reservation not found")

                if (
                    reservation.get("user_id") != user_id
                    or reservation.get("request_id") != request_id
                ):
                    raise ValueError(
                        "Usage data does not match the reservation"
                    )

                if reservation["status"] == "settled":
                    if (
                        reservation.get("actual_cost_toman")
                        != actual_cost_toman
                    ):
                        raise ValueError(
                            "Reservation was settled with a different cost"
                        )

                    existing_usage = usage_records_collection.find_one(
                        {"request_id": request_id},
                        session=session,
                    )
                    wallet = wallets_collection.find_one(
                        {"user_id": user_id},
                        session=session,
                    )

                    return {
                        "reservation": self._serialize(reservation),
                        "wallet": self._serialize(wallet),
                        "usage": self._serialize(existing_usage),
                        "duplicate": True,
                    }

                if reservation["status"] != "reserved":
                    raise ValueError(
                        "Only reserved requests can be settled"
                    )

                reserved_amount = reservation["amount_toman"]

                if actual_cost_toman > reserved_amount:
                    raise SettlementReconciliationRequired(
                        "Actual cost exceeds reserved amount"
                    )

                refund_amount = reserved_amount - actual_cost_toman

                wallet = wallets_collection.find_one(
                    {"user_id": user_id},
                    session=session,
                )
                if wallet is None:
                    raise LookupError("Wallet not found")

                if refund_amount > 0:
                    wallet = wallets_collection.find_one_and_update(
                        {"user_id": user_id},
                        {
                            "$inc": {"balance_toman": refund_amount},
                            "$set": {"updated_at": now},
                        },
                        return_document=ReturnDocument.AFTER,
                        session=session,
                    )
                    if wallet is None:
                        raise LookupError("Wallet not found")

                    wallet_transactions_collection.insert_one(
                        {
                            "wallet_id": str(wallet["_id"]),
                            "user_id": user_id,
                            "type": "credit",
                            "amount_toman": refund_amount,
                            "balance_after": wallet["balance_toman"],
                            "description": "AI API unused reservation refund",
                            "reference": request_id,
                            "idempotency_key": (
                                f"billing-refund:{request_id}"
                            ),
                            "created_at": now,
                        },
                        session=session,
                    )

                usage_record = {
                    **usage_data,
                    "request_id": request_id,
                    "user_id": user_id,
                    "total_cost_toman": actual_cost_toman,
                    "created_at": now,
                }

                usage_result = usage_records_collection.insert_one(
                    usage_record,
                    session=session,
                )
                usage_record["_id"] = usage_result.inserted_id

                updated_reservation = (
                    wallet_reservations_collection.find_one_and_update(
                        {
                            "_id": reservation["_id"],
                            "status": "reserved",
                        },
                        {
                            "$set": {
                                "status": "settled",
                                "actual_cost_toman": actual_cost_toman,
                                "refund_amount_toman": refund_amount,
                                "usage_record_id": str(
                                    usage_result.inserted_id
                                ),
                                "settled_at": now,
                                "updated_at": now,
                            }
                        },
                        return_document=ReturnDocument.AFTER,
                        session=session,
                    )
                )

                if updated_reservation is None:
                    raise RuntimeError("Failed to settle reservation")

                return {
                    "reservation": self._serialize(updated_reservation),
                    "wallet": self._serialize(wallet),
                    "usage": self._serialize(usage_record),
                    "duplicate": False,
                }

    def release(self, idempotency_key: str) -> dict:
        now = datetime.now(timezone.utc)

        with client.start_session() as session:
            with session.start_transaction():
                reservation = wallet_reservations_collection.find_one(
                    {"idempotency_key": idempotency_key},
                    session=session,
                )

                if reservation is None:
                    raise LookupError("Reservation not found")

                if reservation["status"] == "released":
                    wallet = wallets_collection.find_one(
                        {"user_id": reservation["user_id"]},
                        session=session,
                    )
                    return {
                        "reservation": self._serialize(reservation),
                        "wallet": self._serialize(wallet),
                        "duplicate": True,
                    }

                if reservation["status"] != "reserved":
                    raise ValueError(
                        "Only reserved requests can be released"
                    )

                user_id = reservation["user_id"]
                request_id = reservation["request_id"]
                amount = reservation["amount_toman"]

                updated_reservation = (
                    wallet_reservations_collection.find_one_and_update(
                        {
                            "_id": reservation["_id"],
                            "status": "reserved",
                        },
                        {
                            "$set": {
                                "status": "released",
                                "released_at": now,
                                "updated_at": now,
                            }
                        },
                        return_document=ReturnDocument.AFTER,
                        session=session,
                    )
                )

                if updated_reservation is None:
                    raise RuntimeError("Failed to release reservation")

                wallet = wallets_collection.find_one_and_update(
                    {"user_id": user_id},
                    {
                        "$inc": {"balance_toman": amount},
                        "$set": {"updated_at": now},
                    },
                    return_document=ReturnDocument.AFTER,
                    session=session,
                )

                if wallet is None:
                    raise LookupError("Wallet not found")

                wallet_transactions_collection.insert_one(
                    {
                        "wallet_id": str(wallet["_id"]),
                        "user_id": user_id,
                        "type": "credit",
                        "amount_toman": amount,
                        "balance_after": wallet["balance_toman"],
                        "description": "AI API reservation released",
                        "reference": request_id,
                        "idempotency_key": f"billing-refund:{request_id}",
                        "created_at": now,
                    },
                    session=session,
                )

                return {
                    "reservation": self._serialize(updated_reservation),
                    "wallet": self._serialize(wallet),
                    "duplicate": False,
                }
