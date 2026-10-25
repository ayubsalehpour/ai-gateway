# AI Gateway — Batch 01

## Included
- Persisted gateway request state in `gateway_requests`.
- Idempotency fingerprinting: same key + same payload replays the stored successful response; same key + different payload is rejected.
- Request statuses: `processing`, `succeeded`, `failed`, `reconciliation_required`.
- Provider request ID is stored when available.
- Pricing and gateway request indexes are created during application startup.
- Claude `system` messages are now forwarded as Anthropic's `system` parameter instead of being silently discarded.
- Gateway API maps ambiguous/in-progress requests to HTTP 409 and provider failures to HTTP 502.
- Unit tests updated/added for saved response replay and different-payload reuse.

## Apply
Extract the archive into the backend directory, preserving folders and allowing overwrite of the listed files.

Before applying, commit or copy your current working tree so you can roll back.

## Verify on Windows PowerShell
Run from `E:\work\Python-Learning\FAZ4\ai-gateway\backend` with `.venv` activated:

```powershell
python -m compileall -q .\app .\tests
python -m pytest -q
```

The current environment used to prepare this patch did not have the project's Python dependencies installed, so the complete pytest suite has **not** been executed here. Syntax compilation succeeded. Run the full tests locally before committing.

## Important operational note
A request in `reconciliation_required` is deliberately not retried automatically. A provider timeout can occur after the provider has accepted or billed a request. These reservations need a future reconciliation/admin workflow before they can be safely released.
