# Design Decisions & Correctness Guarantees

This document outlines the architectural decisions and mathematical rules governing the **Café Counter Points-and-Tiers Loyalty System**.

---

## 1. Single Source of Truth: Append-Only Ledger

In financial accounting and balance-critical systems, updating a balance directly via `UPDATE members SET points = points + x` causes drift, lost updates, double-counting, and audit untraceability.

- **Ledger Model**: Every point modification is represented as an **immutable row** in the `transactions` table.
- **`MemberBalanceCache`**: The `member_balance_cache` table is a **derived, non-authoritative cache**. It is written inside the **exact same database transaction** as the ledger insertion.
- **Reconstructibility**: A member's current and lifetime balance can be rebuilt at any time by executing:
  ```sql
  SELECT SUM(points_delta) FROM transactions WHERE member_id = ?;
  ```
  This is formally verified by `tests/test_ledger_replay_matches_cache.py`.

---

## 2. Points Calculation & Rounding Rule

- **Formula**: `points_earned = floor(amount_spent * tier_multiplier)`
- **Rule Choice**: **Floor (round down to nearest integer point)**.
  - *Rationale*: Rounding down guarantees that members never receive fractional or unearned points. It provides predictable, deterministic arithmetic across currency amounts (e.g. `$10.99` at `1.25x` = `13.7375` -> `13` points).
- **Redemption**: Point redemptions map 1-to-1 with reward `points_cost` and produce a negative `points_delta`.

---

## 3. Tier Qualification Metric & Multipliers

- **Qualifying Metric**: **Cumulative Lifetime Earned Points**.
  - *Rationale*: Lifetime points earned is monotonic and append-only. Unlike net current points (which decrease upon redemption) or rolling spend (which decays over time), lifetime points earned provides an audited, transparent record of customer loyalty.
- **Tier Definitions**:
  - **BASE**: 0–499 lifetime points | **1.0×** multiplier
  - **SILVER**: 500–1,499 lifetime points | **1.25×** multiplier
  - **GOLD**: 1,500+ lifetime points | **1.5×** multiplier
- **Tier Snapshotting**: Every transaction records `tier_at_time`. If a purchase pushes a member over a tier threshold, points for *that* purchase are calculated using the multiplier at the start of the transaction, and subsequent purchases use the upgraded tier multiplier.

---

## 4. Concurrency Safety & Atomicity

- **Isolation**: SQLite is configured in **Write-Ahead Logging (WAL)** mode.
- **Exclusive Locking**: Transaction operations acquire an immediate write lock (`BEGIN IMMEDIATE;`). This prevents two counter terminals from reading a stale balance and simultaneously performing conflicting redemptions.
- **Server-Side Re-validation**: Redemption balance checks are performed **inside the write lock** on the server side, ignoring any balance cached on the counter UI client.
- **Test Proof**: `tests/test_redemption_race_conditions.py` spawns concurrent worker threads attempting simultaneous redemptions against a limited balance; exactly one succeeds and the second fails cleanly with `InsufficientPointsError`.

---

## 5. Idempotency Key Handling

- Every POST request (`/api/purchases`, `/api/redemptions`) includes a client-generated `idempotency_key` header/body parameter.
- The server records the original response payload in `idempotency_records` within the atomic transaction.
- If a network blip or double-tap occurs, the server catches the duplicate key and returns the identical cached response without re-processing ledger updates or modifying points.
- Test Proof: `tests/test_idempotency.py`.
