# Café Counter Points-and-Tiers Loyalty System ☕

A financial-grade points-and-tiers loyalty POS application for café counter terminals.

The core guarantee: **The balance is always exactly right.** No drift from double-counted purchases, half-applied redemptions, or race conditions when two terminals touch the same member simultaneously.

---

## Key Guarantees & Technical Principles

1. **Single Source of Truth (Append-Only Ledger)**:
   - `Transaction` table (`PURCHASE` or `REDEMPTION`) is the single source of truth.
   - `MemberBalanceCache` is a derived, transactionally-consistent copy updated in the **same atomic database transaction** as writing the ledger row.
2. **Strict Financial Atomicity**:
   - Single DB transaction boundary (`BEGIN IMMEDIATE`) for ledger writes and balance cache updates. If any step fails, everything rolls back.
3. **Client-Generated Idempotency Keys**:
   - Every purchase or redemption includes a unique client-side `idempotency_key`. Retried requests return the exact stored response without duplicate point calculations or ledger rows.
4. **Server-Side Live Balance Validation**:
   - Redemptions re-verify available points **inside the write lock** on the server, preventing stale client balance overdrawing.
5. **Concurrency Protection**:
   - SQLite Write-Ahead Logging (WAL) mode with row-level write serialization. Verified by multi-threaded race condition tests (`tests/test_redemption_race_conditions.py`).
6. **Tier Progression & Snapshots**:
   - Points earned = `floor(amount_spent × tier_multiplier)`.
   - Tier is determined by cumulative **Lifetime Earned Points** (Base: 1.0x, Silver: 1.25x @ 500 pts, Gold: 1.5x @ 1500 pts).
   - Each transaction snapshots `tier_at_time`.

---

## Project Structure

```
cafe-rewards/
├── README.md
├── docs/
│   └── design-decisions.md         # Rounding rules, tier metrics, concurrency guarantees
├── src/
│   ├── domain/                     # Pure business logic (No DB/Framework dependencies)
│   │   ├── member.py               # Member domain entity & phone normalization
│   │   ├── tier.py                 # Tier thresholds, multipliers, upgrade logic
│   │   ├── points.py               # Points calculation + floor rounding rule
│   │   └── ledger.py               # Transaction types & ledger data structures
│   ├── services/                   # Orchestrates domain & storage (owns transactions)
│   │   ├── purchase_service.py     # record_purchase()
│   │   ├── redemption_service.py   # redeem_reward()
│   │   ├── lookup_service.py       # find_by_phone(), search(), get_ledger_history()
│   │   └── reconcile_service.py    # Reconstructs balance from ledger replay
│   ├── storage/
│   │   ├── models.py               # SQLite dataclasses (Member, Transaction, RewardItem, BalanceCache)
│   │   ├── database.py             # SQLite WAL connection management & schemas
│   │   └── repository.py           # Atomic writes, row locking, idempotency store
│   ├── api/                        # REST API Layer (FastAPI)
│   │   ├── routes_member.py        # POST /api/members
│   │   ├── routes_purchase.py      # POST /api/purchases
│   │   ├── routes_redeem.py        # POST /api/redemptions, GET /api/redemptions/rewards
│   │   └── routes_lookup.py        # GET /api/members/search, GET /api/members/phone/{phone}
│   ├── ui/                         # Modern Counter Web UI
│   │   ├── index.html              # Responsive glassmorphism counter interface
│   │   ├── app.js                  # Frontend event handling & real-time search
│   │   └── styles.css              # Custom POS design system & animations
│   ├── main.py                     # FastAPI app entry point
│   └── reconcile.py                # Standalone CLI reconciliation tool
└── tests/
    ├── test_points_calculation.py         # Unit tests for rounding math
    ├── test_tier_upgrades.py              # Unit tests for tier boundaries
    ├── test_idempotency.py                # Idempotency duplicate key test
    ├── test_redemption_race_conditions.py  # Concurrency & race condition test
    └── test_ledger_replay_matches_cache.py # Verification proof test (ledger replay == cache)
```

---

## Quick Start & Installation

### 1. Run Application Server

Launch the web application on `http://localhost:8000`:

```bash
python -m src.main
```
Or with Uvicorn:
```bash
uvicorn src.main:app --port 8000 --reload
```

Then open your browser to **`http://localhost:8000`** to access the Artisan Café Counter UI.

---

## Running Test Suite

Execute all automated unit, concurrency, idempotency, and correctness tests:

```bash
python -m pytest tests/
```

Expected output:
```text
tests/test_idempotency.py ..                                             [ 16%]
tests/test_ledger_replay_matches_cache.py .                              [ 25%]
tests/test_points_calculation.py ....                                    [ 58%]
tests/test_redemption_race_conditions.py .                               [ 66%]
tests/test_tier_upgrades.py ....                                         [100%]
============================= 12 passed in 0.19s ==============================
```

---

## Ledger Reconciliation CLI Tool

Run the standalone audit tool to replay all transaction logs and verify zero balance drift across all members:

```bash
python -m src.reconcile --all
```

Or for a specific member ID:
```bash
python -m src.reconcile --member-id mem_12345678
```

---

## API Documentation

Interactive Swagger API documentation is available at **`http://localhost:8000/docs`** when the server is running.

### Core Endpoints:
- `POST /api/members`: Register a new member.
- `GET /api/members/search?query=...`: Fast indexed phone/name lookup.
- `GET /api/members/phone/{phone}`: Get live member balance & tier progress.
- `POST /api/purchases`: Record purchase and earn points (`amount_spent`, `idempotency_key`).
- `POST /api/redemptions`: Redeem reward item (`reward_id`, `idempotency_key`).
- `GET /api/members/{member_id}/ledger`: Get member transaction audit trail.
- `GET /api/members/{member_id}/reconcile`: Run live ledger replay audit.
