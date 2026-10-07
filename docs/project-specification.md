# AI Gateway — Project Specification

## 1. Project Overview

AI Gateway is an open-source platform that provides a unified interface for accessing multiple AI providers through a single API and web application.

The initial providers are:

- OpenAI
- Anthropic
- Google Gemini

The platform is designed to provide a unified developer experience while handling authentication, provider abstraction, usage tracking, pricing, wallet balance, and billing.

---

## 2. Project Goals

The main goals are:

- Provide a unified API for multiple AI providers.
- Hide provider-specific implementation details behind a common interface.
- Track AI token consumption.
- Calculate usage costs.
- Provide a wallet-based billing system.
- Provide user authentication and authorization.
- Provide a web-based chat interface.
- Provide a public API for developers.
- Build a production-oriented backend architecture.
- Keep the project extensible for future AI providers and features.

---

## 3. MVP Scope

The first MVP will focus on the following capabilities:

### Authentication

- User registration
- User login
- Password hashing
- JWT authentication
- Current-user dependency

### AI Gateway

- Common AI provider interface
- OpenAI provider
- Anthropic provider
- Gemini provider
- Model selection
- Unified chat request/response format

### Usage Tracking

For each AI request, the system should record:

- User
- Provider
- Model
- Input tokens
- Output tokens
- Total tokens
- Request timestamp
- Request status

### Billing

The system should calculate the cost of AI requests based on:

- Provider
- Model
- Input token price
- Output token price
- Exchange rate
- Platform margin

### Wallet

Users should have:

- Wallet balance
- Credit transactions
- Debit transactions
- Transaction history

The system should use a transaction ledger instead of relying only on a mutable balance value.

### API

The MVP API should provide endpoints for:

- Authentication
- User information
- AI chat
- Usage
- Wallet
- Transactions

---

## 4. Non-MVP Features

The following features are intentionally postponed:

- Redis
- Background workers
- Celery
- Docker production deployment
- Kubernetes
- PostgreSQL
- SQLAlchemy
- Smart model routing
- RAG
- AI agents
- Function/tool calling
- File processing
- Vision
- Embeddings
- Team accounts
- Webhooks
- SDKs
- Advanced analytics
- Multi-region deployment

These features may be introduced in later versions.

---

## 5. High-Level Architecture

```text
                    ┌───────────────┐
                    │   Frontend    │
                    │     Vue       │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │    FastAPI    │
                    │   API Layer   │
                    └───────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
          Auth Layer    AI Gateway     Billing
                              │
                  ┌───────────┼───────────┐
                  │           │           │
                  ▼           ▼           ▼
               OpenAI     Anthropic    Gemini
                             
                            │
                            ▼
                       Usage Tracking
                            │
                            ▼
                         MongoDB
```

---

## 6. Backend Architecture

The backend follows a layered architecture:

```text
app/
├── main.py
├── core/
├── api/
├── schemas/
├── services/
├── repositories/
└── models/
```

### main.py

Application entry point.

Responsibilities:

- Create FastAPI application
- Register routers
- Configure application metadata
- Configure middleware

### core/

Application-wide configuration and infrastructure.

Examples:

- Settings
- Security
- Database configuration
- Application constants

### api/

HTTP API layer.

Responsibilities:

- Define routes
- Validate requests
- Return HTTP responses
- Inject dependencies

### schemas/

Pydantic request and response models.

Examples:

- UserCreate
- LoginRequest
- ChatRequest
- ChatResponse
- UsageResponse

### services/

Business logic.

Examples:

- Authentication service
- AI Gateway service
- Billing service
- Wallet service

### repositories/

Database access layer.

Responsibilities:

- Create
- Read
- Update
- Delete
- Query database documents

### models/

Database-related models and data structures.

---

## 7. AI Provider Architecture

The system should not directly couple the application to a specific AI provider.

The intended architecture is:

```text
AIProvider
    │
    ├── OpenAIProvider
    ├── AnthropicProvider
    └── GeminiProvider
```

The application communicates with the common provider interface.

This allows new providers to be added without changing the main business logic.

Future providers can include:

- DeepSeek
- Mistral
- xAI
- Cohere
- Other compatible providers

---

## 8. Unified Chat Interface

The application should expose a common request format.

Conceptually:

```json
{
    "provider": "openai",
    "model": "gpt-model",
    "messages": [
        {
            "role": "user",
            "content": "Hello"
        }
    ]
}
```

The gateway translates this request into the provider-specific API format.

The response should also be normalized into a common structure.

---

## 9. Usage Tracking

Each AI request should generate a usage record.

Conceptual structure:

```text
Usage
├── user_id
├── provider
├── model
├── input_tokens
├── output_tokens
├── total_tokens
├── cost
├── request_id
└── created_at
```

The request ID will allow individual requests to be traced through the system.

---

## 10. Pricing Engine

The pricing engine will separate provider pricing from user billing.

Conceptually:

```text
Provider Model Price
        │
        ▼
Token Usage
        │
        ▼
Cost Calculation
        │
        ▼
Exchange Rate
        │
        ▼
Platform Margin
        │
        ▼
Final User Cost
```

Pricing must be configurable rather than hard-coded inside provider implementations.

---

## 11. Wallet Architecture

The wallet system should maintain a financial ledger.

Conceptually:

```text
Wallet
  │
  ├── Credit
  ├── Debit
  └── Transaction History
```

Transactions should contain information such as:

```text
Transaction
├── user_id
├── type
├── amount
├── balance_before
├── balance_after
├── reference
├── description
└── created_at
```

The transaction history should provide an auditable record of wallet changes.

---

## 12. Security Requirements

The application should follow these principles:

- Passwords must never be stored as plaintext.
- Provider API keys must never be exposed to users.
- Secrets must be stored in environment variables or a secret manager.
- User API keys should be stored securely.
- JWT secrets must not be committed to Git.
- API endpoints must enforce authentication where required.
- Rate limiting should be introduced.
- Spending limits should be supported.
- API keys should be revocable.
- Sensitive information must not be written to logs.
- Production traffic must use HTTPS.

---

## 13. Database Strategy

### MVP

MongoDB will be used for rapid development and flexible document modeling.

### Later

The project may migrate selected or all financial and relational workloads to PostgreSQL.

Potential future stack:

```text
PostgreSQL
+
SQLAlchemy
+
Alembic
```

The repository/service separation should make this transition easier.

---

## 14. Version Roadmap

### V0.0.1

Project Foundation

- Repository
- Git workflow
- Environment configuration
- Backend structure

### V0.1.0

FastAPI Core

- Application configuration
- Routers
- Error handling
- Health checks
- API structure

### V0.2.0

Authentication

- Registration
- Login
- Password hashing
- JWT
- Protected routes

### V0.3.0

AI Provider Architecture

- Provider interface
- Provider registry
- Unified request model

### V0.4.0

First AI Chat

- First provider integration
- Unified chat endpoint
- Basic response normalization

### V0.5.0

Multi-Provider AI

- OpenAI
- Anthropic
- Gemini

### V0.6.0

Usage Tracking

- Token tracking
- Request tracking
- Usage history

### V0.7.0

Billing Engine

- Model pricing
- Cost calculation
- Exchange rate
- Platform margin

### V0.8.0

Wallet

- Wallet balance
- Credit
- Debit
- Transaction ledger

### V0.9.0

Payments

- Payment gateway
- Callback verification
- Wallet recharge

### V1.0.0

Public API

- API keys
- Usage limits
- Rate limiting
- Developer documentation

### V1.1.0

Vue Dashboard

- Login
- Chat
- Wallet
- Usage
- API keys

### V1.2.0

Admin Panel

- Users
- Providers
- Models
- Pricing
- Payments
- Usage

### V1.3.0

Security & Hardening

- Rate limiting
- Audit logs
- Security improvements

### V1.4.0

Production Database

- PostgreSQL
- SQLAlchemy
- Alembic

### V1.5.0

Infrastructure

- Docker
- Redis
- Background workers
- Nginx

### V1.6.0

Quality & Delivery

- Pytest
- Integration tests
- CI/CD
- Automated checks

### V1.7.0

Observability

- Structured logging
- Metrics
- Error tracking
- Monitoring

### V2.0.0

Smart AI Gateway

- Intelligent model routing
- Cost optimization
- Fallback providers
- Availability-aware routing

---

## 15. Development Principles

The project will follow these principles:

1. Keep business logic independent from HTTP.
2. Keep provider integrations isolated.
3. Keep database access inside repositories.
4. Keep business rules inside services.
5. Validate external input with Pydantic.
6. Never commit secrets.
7. Prefer small, focused commits.
8. Use conventional commit messages.
9. Write tests for important business logic.
10. Build the MVP before adding advanced infrastructure.

---

## 16. Current Status

Current version:

```text
V0.0.1 — Project Foundation
```

Completed:

- GitHub repository
- Git configuration
- Project structure
- Python virtual environment
- FastAPI
- Uvicorn
- Pydantic Settings
- Environment configuration
- Health endpoint
- Initial backend commit

Next target:

```text
V0.1.0 — FastAPI Core
```