---
name: laravel
description: "Laravel 11 development and error debugging. Covers slim-controller/service/form-request/API-resource architecture, Eloquent models, migrations, Sanctum auth, queued Jobs, Events/Listeners, spatie packages (permission, auditing, medialibrary), and Laravel Pint. Includes a comprehensive error catalog: PHP fatal/compile, runtime exceptions, Blade, Composer/autoload, Eloquent/DB (SQLSTATE), migration, HTTP 419/403/404/405/500, validation, queue/job failures, and env/config cache errors — each with cause and fix. Use whenever generating Laravel backend code or debugging ANY Laravel/PHP error."
---

# Laravel

Assistant for **Laravel 11** backends. Generate idiomatic code and **diagnose every class of Laravel/PHP error**. Given an error: match the catalog, state the cause, give the fix.

## Architecture standards

**Slim controllers → Services.** Controllers HTTP-handle; Services hold business logic.

- **Controllers** — constructor-inject services via property promotion: `public function __construct(private readonly FooService $fooService) {}`. Return API Resources or a shared envelope. No query/business logic in the controller.
- **Services** — `app/Services/`, constructor-injected. Wrap multi-write operations in `DB::transaction(fn () => …)`.
- **Form Requests** — `php artisan make:request` — `authorize(): bool`, `rules(): array`. Use `$request->validate()` only for tiny endpoints.
- **Models** — `extends Model`; `$guarded = []` or explicit `$fillable`. Cast dates/bools/JSON via `$casts`. Relationships explicit with return-type hints (`: BelongsTo`, `: HasMany`). Eager-load in queries with `with([...])`, not `$with`. Never lazy-load in loops.
- **Enums** — PHP native backed enums in `app/Enums/`. `enum X: string { case A = 'A'; }`.
- **Jobs** — `implements ShouldQueue`, `use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;`, `handle()`. Only serializable data in the constructor.
- **Events / Broadcasting** — `implements ShouldBroadcast`, public props, `broadcastOn()`, `broadcastAs()`, `broadcastWith()`. Wire in `EventServiceProvider::$listen`.
- **Migrations** — anonymous class, `up()`/`down()`. FKs: `foreignIdFor(Model::class)->constrained()`. Index filtered/joined columns. Never hand-edit the DB.
- **Routing** — group with `Route::controller()->prefix()->middleware()->group()`. Kebab-case URL prefixes.
- **Auth** — Sanctum SPA cookie + bearer. Spatie/permission for roles (`hasPermissionTo`/`can`/`hasRole`).

## Core rules

1. **Eloquent** models with `$fillable`/`$guarded` set — avoids mass-assignment errors.
2. **Migrations** for schema; never alter DB by hand.
3. **Form Requests** for validation.
4. **Route model binding** over manual `find()`.
5. `config()` not `env()` outside `config/` — `env()` returns null when config is cached.
6. **Eager load** to avoid N+1 (`with()`).
7. **Queue** slow work; jobs implement `ShouldQueue`.
8. **Service classes** hold logic; controllers stay thin.
9. **Parameterized queries only** — no raw string interpolation.
10. **Secrets in `.env`** — never committed; cache config/routes in prod (`php artisan optimize`).

## Controller → Service template

```php
// app/Http/Controllers/MachineController.php
class MachineController extends Controller
{
    public function __construct(private readonly MachineService $machines) {}

    public function store(StoreMachineRequest $request)
    {
        $machine = $this->machines->create($request->validated());
        return MachineResource::make($machine);
    }
}
```

```php
// app/Http/Requests/StoreMachineRequest.php
class StoreMachineRequest extends FormRequest
{
    public function authorize(): bool { return true; }

    public function rules(): array
    {
        return [
            'name'    => ['required', 'string', 'max:255'],
            'hall_id' => ['required', 'integer', Rule::exists('halls', 'id')],
        ];
    }
}
```

```php
// app/Services/MachineService.php
public function create(array $data): Machine
{
    return DB::transaction(fn () => Machine::create($data));
}
```

## Commands

```bash
php artisan make:model Post -m          # model + migration
php artisan make:request StorePostRequest
php artisan make:job ProcessImport
php artisan queue:work
php artisan migrate
php artisan config:clear                # always after .env changes
php artisan optimize:clear              # after deploy to clear all caches
php artisan route:list                  # debug routing
php -l app/Services/FooService.php      # syntax check without reformatting
vendor/bin/pint                         # PSR-12 lint/format
vendor/bin/phpunit
```

---

# ERROR CATALOG

Format: **Symptom → Cause → Fix**.

## 1. PHP fatal / compile / import errors

- **`Parse error: syntax error, unexpected …`** → missing `;`/`}` or bad token. Fix: the reported line and the one above.
- **`Fatal error: Class "App\Models\X" not found`** → wrong namespace, missing `use`, or stale autoload. Fix: correct `namespace`/`use`; `composer dump-autoload`.
- **`Call to undefined method App\Models\X::y()`** → method/relationship undefined. Fix: define it; use `X::query()->y()`.
- **`Call to a member function X() on null`** → relationship/lookup returned null. Fix: `$m?->x()`, `optional()`, eager load, or `findOrFail`.
- **`Typed property must not be accessed before initialization`** → typed prop unset. Fix: init in constructor or make nullable.
- **`Argument #1 must be of type X, Y given (TypeError)`** → type-hint mismatch. Fix: validate/cast before passing.

## 2. Composer / dependency errors

- **`Your requirements could not be resolved`** → version conflict. Fix: check `php -v` vs `require.php`; `composer why-not`.
- **`Failed opening required 'vendor/autoload.php'`** → deps not installed. Fix: `composer install`.
- **`Class not found` only in production** → `--no-dev` dropped a dep used in prod. Fix: move to `require`.

## 3. Runtime exceptions

- **`BindingResolutionException: Target class [X] does not exist`** → wrong namespace or unbound interface. Fix: correct FQCN; bind in a service provider.
- **`MassAssignmentException: Add [field] to fillable`** → assigning a non-fillable attribute. Fix: add to `$fillable`.
- **`ModelNotFoundException`** → `findOrFail`/route binding found nothing → **404**. Catch inline or customize in `Handler.php`.
- **`QueryException`** → wraps a DB/SQLSTATE error → see the `mysql`/`postgresql` skills.
- **`Serialization of 'Closure' is not allowed`** → queuing a job carrying a closure. Fix: pass only serializable data.

## 4. Blade / render / view errors

- **`View [x] not found`** → missing file / wrong dotted path. Fix: `resources/views/x.blade.php`; `view('folder.x')`.
- **`Undefined variable $x` in Blade** → not passed from controller. Fix: `view('x', compact('x'))`.
- **Compiled view stale** → `php artisan view:clear`.

## 5. Database / Eloquent errors (SQLSTATE)

- **`[1045] / 28P01 Access denied`** → wrong credentials. Fix: `.env`; `config:clear`.
- **`[2002] / 08006 Connection refused`** → DB down / wrong host/port. Fix: start DB; verify.
- **`[1049] / 3D000 Unknown database`** → wrong `DB_DATABASE`. Fix: create it or correct name; `config:clear`.
- **`[1146] / 42P01 Table not found`** → migrations not run. Fix: `php artisan migrate`.
- **`[1054] / 42703 Column not found`** → column typo or migration pending. Fix: add migration; fix name.
- **`23000 / 23505 Integrity constraint`**: duplicate → `updateOrCreate`/validate `unique`; FK fails → create parent first; null → provide value / nullable column.
- **N+1 (no error, slow)** → `with('relation')`; `preventLazyLoading()` in dev.
- Deeper DB diagnostics → `mysql` / `postgresql` skills.

## 6. Migration errors

- **`Nothing to migrate`** → already run or wrong DB active.
- **`Table already exists (1050 / 42P07)`** → partial prior run. Fix (dev): `migrate:fresh` — **drops data**.
- **`1071 key too long`** (old MySQL utf8mb4) → `Schema::defaultStringLength(191)` in a provider.
- **`Cannot add foreign key (1215/1005)`** → column type mismatch or referenced table not yet created. Fix: match `unsignedBigInteger` ↔ `id()`; order migrations.

## 7. HTTP status errors

- **419 Page Expired** → missing/expired CSRF token or Sanctum session issue. Fix: `@csrf` for web; for SPA ensure `X-XSRF-TOKEN` cookie + `withCredentials`; check `SANCTUM_STATEFUL_DOMAINS`.
- **403 Forbidden** → policy/gate or spatie/permission denied. Fix: check role/permission, `can` middleware, `authorize()`.
- **404 Not Found** → route undefined, `ModelNotFoundException`, or stale route cache. Fix: `route:list`; `route:clear`.
- **405 Method Not Allowed** → wrong HTTP verb. Fix: match verb.
- **500 Internal Server Error** → uncaught exception. Fix: read `storage/logs/laravel.log`; `APP_DEBUG=true` locally.
- **429 Too Many Requests** → rate limiter. Fix: adjust `throttle` middleware.
- **CORS blocked** → `config/cors.php` `allowed_origins`.

## 8. Validation errors

- **422 Unprocessable Entity** → validation failed (expected for APIs); errors in JSON `errors`. Not a bug.
- **Rule not applied** → misspelled rule. Fix: check `nullable`/`sometimes`/`exists:table,col`/`unique:table,col`.

## 9. Queue / job errors

- **Jobs never run** → no worker. Fix: `php artisan queue:work`; check `QUEUE_CONNECTION` (tests often use `sync`).
- **`failed_jobs` filling up** → job throws. Fix: read exception; `php artisan queue:retry all`.
- **`Job attempted too many times`** → `$tries`/`$timeout` exceeded. Fix: raise them, fix root cause.
- **Stale worker after deploy** → `php artisan queue:restart`.

## 10. Config / env / cache errors

- **`.env` changes ignored** → config cached. Fix: `php artisan config:clear`; don't call `env()` outside `config/`.
- **`No application encryption key`** → missing `APP_KEY`. Fix: `php artisan key:generate`.
- **500 right after deploy** → stale caches. Fix: `php artisan optimize:clear`.
- **`Permission denied` (storage/bootstrap)** → wrong perms. Fix: `chmod -R 775 storage bootstrap/cache`.
- **Route closures + `route:cache` error** → closures aren't cacheable. Fix: use controller classes.

## Debug workflow

1. Read `storage/logs/laravel.log` first (or browser with `APP_DEBUG=true`).
2. Classify: PHP-fatal / exception class / SQLSTATE / HTTP code / queue → jump to the section.
3. One-line cause + minimal fix. For DB internals defer to the `mysql`/`postgresql` skills. Cache-related → `php artisan optimize:clear`.
