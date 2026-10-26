from app.services.billing_exceptions import SettlementReconciliationRequired


def test_reconciliation_required_exception_is_value_error_compatible():
    error = SettlementReconciliationRequired(
        "Actual cost exceeds reserved amount"
    )

    assert isinstance(error, ValueError)
    assert str(error) == "Actual cost exceeds reserved amount"
