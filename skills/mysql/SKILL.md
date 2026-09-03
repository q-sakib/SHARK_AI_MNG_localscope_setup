---
name: mysql
description: "MySQL schema design, query tuning, and comprehensive SQLSTATE error debugging via Laravel 11 migrations and Eloquent. Covers InnoDB/utf8mb4 conventions, indexing, transactions, N+1 patterns, and a full error catalog: connection (1045/2002/1049), missing table/column (1146/1054), integrity/FK (1062/1452/1048), data (1406/1264/1366), locking/deadlock (1213/1205), and migration errors — each with cause and fix."
---

# MySQL

Assistant for **MySQL** databases managed via **Laravel 11 migrations** and Eloquent. Use for schema design, query tuning, and diagnosing any MySQL/SQLSTATE error.

## Core rules

- **Access via Eloquent / query builder**. Raw SQL only for what the builder can't express; always parameter-bind (`DB::select('… where id = ?', [$id])`) — never interpolate.
- **InnoDB + utf8mb4** defaults. Model names singular (`Machine` → `machines`); `id()` gives `BIGINT UNSIGNED AUTO_INCREMENT` PK.
- **Migrations** define schema (`database/migrations/`). FKs reference `unsignedBigInteger` ↔ `id()`.
- **Tests hit a real DB** by default — verify DB_DATABASE before destructive ops.

## Connection config

```php
// config/database.php → connections.mysql
'mysql' => [
    'driver'    => 'mysql',
    'host'      => env('DB_HOST', '127.0.0.1'),
    'port'      => env('DB_PORT', '3306'),
    'database'  => env('DB_DATABASE'),
    'charset'   => 'utf8mb4',
    'collation' => 'utf8mb4_unicode_ci',
    'engine'    => 'InnoDB',
],
```
After changing `.env`: `php artisan config:clear` (cached config ignores `.env`).

## Best practices

1. **Index columns you filter/join/sort on** — FKs, `where`, `order by`. Add via migration: `$table->index('machine_id')`, composite `$table->index(['hall_id', 'created_at'])`.
2. **Kill N+1** — `Model::with('relation')`; enable `Model::preventLazyLoading()` in dev.
3. **Transactions** for multi-write consistency: `DB::transaction(fn () => …)` — auto rollback on exception.
4. **Chunk large reads** — `->chunkById(1000, fn ($rows) => …)` / `cursor()`; never `->get()` millions of rows.
5. **`updateOrCreate` / `upsert`** instead of catching duplicate-key errors.
6. **Tight column types** — `unsignedBigInteger` for FKs, `decimal` for money/quantities (never `float`), `timestamp`/`datetime` deliberately.
7. **utf8mb4 index length** — legacy MySQL (<5.7.7) caps indexed varchar; use `Schema::defaultStringLength(191)` only if you hit `1071`.
8. **`EXPLAIN`** a slow query before adding indexes; look for `type: ALL` (full scan) and `Using filesort`.
9. **Avoid `SELECT *`** on wide tables in hot paths.

## Migration snippet

```php
Schema::create('machines', function (Blueprint $table) {
    $table->id();
    $table->string('name');
    $table->foreignId('hall_id')->constrained()->cascadeOnDelete();
    $table->decimal('capacity', 10, 2)->default(0);
    $table->timestamps();
    $table->index(['hall_id', 'name']);
});
```

---

# ERROR CATALOG (SQLSTATE)

Surfaces as `Illuminate\Database\QueryException`. Format: **Symptom → Cause → Fix**.

## 1. Connection / auth

- **`[1045] Access denied for user`** → wrong username/password. Fix: `.env` `DB_USERNAME`/`DB_PASSWORD`; `config:clear`.
- **`[2002] Connection refused / Can't connect`** → server down, wrong `DB_HOST` or port. Fix: start MySQL; verify host/port; in Docker use service name, not `127.0.0.1`.
- **`[1049] Unknown database 'X'`** → `DB_DATABASE` not created / wrong name. Fix: create it or correct name; `config:clear`.
- **`MySQL server has gone away`** → connection timeout or packet too large. Fix: reconnect; raise `max_allowed_packet`; smaller batches.
- **`Too many connections (1040)`** → pool exhausted. Fix: close/queue work; raise `max_connections`.

## 2. Missing object

- **`[1146] Base table or view not found`** → migration not run. Fix: `php artisan migrate`.
- **`[1054] Unknown column 'X'`** → column typo, migration pending, or wrong `$fillable`. Fix: add migration / fix the name.
- **`[1305] FUNCTION does not exist`** → MySQL-specific function name or missing parens. Fix: use the correct MySQL function.

## 3. Integrity / constraint (23000)

- **`[1062] Duplicate entry`** → unique/PK collision. Fix: `updateOrCreate`, `upsert`, or validate `unique:table,col`.
- **`[1452] Cannot add child row: FK constraint fails`** → parent row missing. Fix: create parent first; verify FK value exists.
- **`[1451] Cannot delete parent row: FK constraint fails`** → children still reference it. Fix: cascade, delete children first, or `nullOnDelete`.
- **`[1048] Column cannot be null`** → required column got null. Fix: provide a value or make nullable.
- **`[1364] Field doesn't have a default value`** → NOT NULL column not provided. Fix: pass it, add `->default(...)`, or nullable.

## 4. Data / type

- **`[1406] Data too long for column`** → value exceeds column size. Fix: enlarge or validate `max:`.
- **`[1264] Out of range value`** → number exceeds type range. Fix: use `bigInteger`/`unsignedBigInteger`.
- **`[1366] Incorrect string/integer value`** → charset mismatch or wrong type. Fix: ensure utf8mb4 end-to-end; cast the value.
- **`[1292] Truncated incorrect DOUBLE/DATE value`** → bad date/number string. Fix: normalize input before insert.

## 5. Locking / concurrency

- **`[1213] Deadlock found`** → two transactions locked rows in opposite order. Fix: wrap in `DB::transaction()`, consistent lock ordering, short transactions.
- **`[1205] Lock wait timeout exceeded`** → another transaction holds a lock. Fix: shorten transactions; commit sooner; raise `innodb_lock_wait_timeout` as last resort.

## 6. Migration-time

- **`[1050] Table already exists`** → partial prior migration. Fix (dev): `migrate:rollback` / `migrate:fresh` — **drops data**.
- **`[1071] Key too long`** → utf8mb4 index on long varchar (old MySQL). Fix: `Schema::defaultStringLength(191)` in `AppServiceProvider::boot()`, or upgrade MySQL.
- **`[1215] Cannot add foreign key` / `[1005]`** → column type/signedness mismatch. Fix: match `unsignedBigInteger` to `id()`; order migrations so referenced table exists first.
- **`[3730] Cannot drop table referenced by FK`** → drop FK/child first, or `Schema::disableForeignKeyConstraints()`.

## 7. Privilege / grants

- **`[1142] command denied` / `[1044] Access denied to database`** → missing grant. Fix: `GRANT` the privilege; common when a new DB wasn't granted to the app user.

## 8. Performance (no error, just slow)

- **Full table scan** → `EXPLAIN` shows `type: ALL`. Fix: add index on filtered column.
- **`Using filesort` / `Using temporary`** → unindexed `ORDER BY`/`GROUP BY`. Fix: composite index matching the sort.
- **N+1** → lazy load in loop. Fix: eager `with()`.
- **Large `OFFSET` pagination** → deep offset scans rows. Fix: keyset/`whereId('>', $last)` or `chunkById`.

## Debug workflow

1. Read the SQLSTATE + driver code from the `QueryException` / `storage/logs/laravel.log`.
2. Map the bracketed code to the section above.
3. `EXPLAIN` for slow queries; add indexes via migration — never alter schema by hand.
