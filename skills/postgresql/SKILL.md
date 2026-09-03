---
name: postgresql
description: "PostgreSQL schema design, query tuning, and comprehensive SQLSTATE error debugging via Laravel 11 migrations and Eloquent. Covers B-tree/GIN/partial indexing, JSON/JSONB, EXPLAIN ANALYZE, transactions, sequences, and MySQL→Postgres portability gotchas. Full error catalog: connection (08006/28P01/3D000), missing table/column (42P01/42703), integrity/FK (23505/23503/23502), data/type (22P02/22001/22003), transaction/lock (40P01/40001/55P03/25P02), and migration/privilege errors — each with cause and fix."
---

# PostgreSQL

Assistant for **PostgreSQL** managed via **Laravel 11 migrations** and Eloquent. Use for schema design, query tuning, and diagnosing any PostgreSQL/SQLSTATE error.

## Core rules

- **Access via Eloquent / query builder.** Raw SQL only when necessary; always parameter-bind (`DB::select('… where id = ?', [$id])`).
- **Case-folding** — unquoted identifiers fold to **lower case**. Laravel's schema builder handles this; avoid hand-written mixed-case quoted identifiers.
- **Sequences** back `id()` (`bigserial`/identity) — after a manual insert with explicit id you may need to reset the sequence.
- **Migrations** define schema; FKs `unsignedBigInteger` ↔ `id()`.
- **Tests hit a real DB** by default.

## Connection config

```php
'pgsql' => [
    'driver'      => 'pgsql',
    'host'        => env('DB_HOST', '127.0.0.1'),
    'port'        => env('DB_PORT', '5432'),
    'database'    => env('DB_DATABASE'),
    'charset'     => 'utf8',
    'search_path' => 'public',
    'sslmode'     => 'prefer',
],
```
Set `DB_CONNECTION=pgsql`, then `php artisan config:clear`.

## MySQL → PostgreSQL portability gotchas

- **No `ENGINE`/`utf8mb4`** — ignore those; no `Schema::defaultStringLength(191)` / `1071` key-length issue.
- **Booleans are real `boolean`**, not `tinyint(1)`. Don't compare to `1`/`0` in raw SQL.
- **Case-sensitive string comparison** by default. Use `ILIKE` for case-insensitive, or `LOWER()` + index.
- **`GROUP BY` is strict** — every non-aggregated selected column must appear in `GROUP BY`.
- **`||` is string concat**, not OR. **Double quotes** = identifiers, **single quotes** = string literals.
- **`RETURNING`** is available (Laravel uses it for inserts to fetch the id).
- **JSON → prefer `jsonb`** (indexable, deduped) over `json`.

## Best practices

1. **Index filters/joins/sorts** via migration. Postgres extras: **partial** (`WHERE active`), **expression** (`LOWER(email)`), **GIN** for `jsonb`/full-text/arrays.
2. **`EXPLAIN (ANALYZE, BUFFERS)`** to profile; watch `Seq Scan` on big tables and bad row estimates (`ANALYZE` the table to refresh stats).
3. **Transactions**: `DB::transaction(fn () => …)`. Postgres aborts the whole transaction on the first error — must roll back before continuing (see `25P02`).
4. **`jsonb`** for semi-structured data; query with `->` / `->>` / `@>`; GIN-index it.
5. **`decimal`/`numeric`** for money/quantities, never `float`.
6. **Chunk large reads** — `chunkById` / `cursor()`.
7. **Kill N+1** — `with()`; `preventLazyLoading()` in dev.

## Migration snippet

```php
Schema::create('machines', function (Blueprint $table) {
    $table->id();
    $table->string('name');
    $table->foreignId('hall_id')->constrained()->cascadeOnDelete();
    $table->decimal('capacity', 10, 2)->default(0);
    $table->jsonb('meta')->nullable();
    $table->boolean('active')->default(true);
    $table->timestamps();
    $table->index(['hall_id', 'name']);
});
// GIN index on jsonb (raw in a migration):
DB::statement('CREATE INDEX machines_meta_gin ON machines USING gin (meta)');
```

---

# ERROR CATALOG (SQLSTATE)

Surfaces as `Illuminate\Database\QueryException`. 5-char Postgres SQLSTATE. Format: **Symptom → Cause → Fix**.

## 1. Connection / auth

- **`08006` / could not connect to server** → server down, wrong `DB_HOST`/`DB_PORT` (default 5432). Fix: start Postgres; verify; in Docker use service name.
- **`28P01` password authentication failed** → wrong credentials. Fix: `.env` `DB_USERNAME`/`DB_PASSWORD`; `config:clear`.
- **`28000` no pg_hba.conf entry** → server rejects client host/SSL. Fix: add `pg_hba.conf` rule; set `sslmode` appropriately.
- **`3D000` database does not exist** → wrong/absent `DB_DATABASE`. Fix: create it or correct the name; `config:clear`.
- **`53300` too many connections** → pool exhausted. Fix: reduce concurrency; raise `max_connections`; use PgBouncer.

## 2. Missing object

- **`42P01` relation does not exist** → migration not run, wrong `search_path`, or wrong DB. Fix: `php artisan migrate`; check `search_path=public`.
- **`42703` column does not exist** → column typo, pending migration, or case-folding issue (mixed-case quoted name created lower-case). Fix: fix the name/migration.
- **`42883` function does not exist** → wrong function name or no matching argument types. Fix: cast args or use the correct function.
- **`42P07` relation already exists** → duplicate create (partial prior migration). Fix (dev): `migrate:fresh` — **drops data**.

## 3. Integrity / constraint

- **`23505` duplicate key violates unique constraint** → unique/PK collision. Fix: `updateOrCreate`/`upsert`. **After manual-id inserts**, reset sequence: `SELECT setval(pg_get_serial_sequence('machines','id'), MAX(id)) FROM machines;`
- **`23503` foreign key violation** → inserting/deleting breaks an FK. Fix: create parent first / cascade / delete children first.
- **`23502` null value violates not-null constraint** → required column got null. Fix: provide a value or `->nullable()`.
- **`23514` check constraint violated** → value fails a CHECK. Fix: satisfy or amend the constraint.

## 4. Data / type

- **`22P02` invalid input syntax for type X** → wrong string for a typed column (e.g. `'abc'` into integer). Fix: cast/validate before insert; Postgres won't silently coerce like MySQL.
- **`22001` value too long for character varying(n)** → exceeds varchar length. Fix: enlarge or validate `max`.
- **`22003` numeric value out of range** → number exceeds type. Fix: use `bigInteger`/wider `numeric`.
- **`42804` column is of type boolean but expression is of type integer** → comparing/assigning `1`/`0` to a real boolean. Fix: use `true`/`false`.

## 5. Transaction / locking

- **`40P01` deadlock detected** → transactions locked rows in opposite order. Fix: `DB::transaction()` with retry; consistent lock ordering; short transactions.
- **`40001` serialization failure** → serializable/repeatable-read conflict. Fix: retry the transaction.
- **`55P03` lock not available / nowait** → `FOR UPDATE NOWAIT` couldn't lock. Fix: retry, or drop `NOWAIT`.
- **`25P02` current transaction is aborted** → an earlier statement in the transaction errored; Postgres blocks the rest. Fix: **roll back** (Laravel does on exception in `DB::transaction`); never swallow the first error and keep issuing queries.
- **`25006` cannot execute in a read-only transaction** → write against a replica. Fix: target the primary connection.

## 6. Migration / privilege

- **`42P07` / `42710` duplicate object** → partial migration. Fix (dev): `migrate:fresh`.
- **`2BP01` cannot drop because other objects depend on it** → dependent FK/view. Fix: drop dependents first.
- **`42501` permission denied for table/schema/sequence** → role lacks privilege. Fix: `GRANT` the privilege (don't forget sequences for inserts).
- **`0A000` feature not supported** → unsupported ALTER on populated column. Fix: multi-step migration (add col, backfill, swap).

## 7. Performance (no error, just slow)

- **`Seq Scan` on large table** → missing index. Fix: add B-tree / partial / expression index.
- **Bad row estimates** → stale stats. Fix: `ANALYZE table;`.
- **`ILIKE '%x%'` slow** → leading wildcard can't use B-tree. Fix: `pg_trgm` GIN index.
- **`jsonb` filter slow** → no GIN index. Fix: `CREATE INDEX ... USING gin (col)`.
- **Deep `OFFSET` pagination** → fix: keyset pagination.
- **Table bloat** → dead tuples. Fix: `VACUUM` / autovacuum tuning.

## Debug workflow

1. Read the 5-char SQLSTATE from `QueryException` / `storage/logs/laravel.log`.
2. Map it to the section above (Postgres codes differ from MySQL numeric ones).
3. On mid-transaction failure, remember `25P02` — transaction is poisoned until rollback.
4. `EXPLAIN (ANALYZE, BUFFERS)` slow queries; add indexes via migration.
