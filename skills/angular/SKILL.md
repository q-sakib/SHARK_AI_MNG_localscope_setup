---
name: angular
description: "Angular 17.x development and error debugging. Covers NgModule architecture, constructor DI, template patterns (*ngIf/*ngFor / @if/@for), RxJS 7, UI5 Web Components, and mandatory subscription teardown. Includes a comprehensive error catalog: compile/build (NG####, TS####), NgModule/import, template/render, runtime (NG0xxx), DI, routing, RxJS/HTTP, and change-detection errors — each with cause and fix. Use whenever generating Angular code or debugging ANY Angular/TypeScript error."
---

# Angular

Assistant for **Angular 17.x** apps — **NgModule-based**, **zone.js** change detection. Generate code that matches the codebase, and **diagnose every class of Angular/TS error**. Given an error: match the catalog, state the one-line cause, give the fix.

## Architecture reality — match it

Read `package.json` (`@angular/core` version) before emitting any API. Follow what is actually in the repo:

- **NgModule architecture** — feature modules under `src/app/modules/<kebab-case>/`, lazy-loaded via a `*-routing.module.ts`. Do **not** generate `standalone: true` unless the existing code uses it.
- **Constructor DI** — `constructor(private router: Router, private authService: AuthService) {}`. Prefer constructor DI over `inject()` unless the project uses `inject()` heavily.
- **Separate template/style files** — `templateUrl: './x.component.html'`, `styleUrl: './x.component.css'`. Inline templates only where the project already does it.
- **Templates use `*ngIf` / `*ngFor`** as the dominant style; `@if`/`@for` control flow is valid in v17 and both styles coexist. Match whichever the file already uses.
- **No signals** — state is plain class fields; async via RxJS `Observable` + `async` pipe or `.subscribe()`.
- **`strictTemplates: true`** — templates are type-checked; a mistyped binding is a **build error**.
- **UI5 Web Components** (`@ui5/webcomponents*`) — custom elements (`<ui5-button>`, etc.). The declaring module **must** add `schemas: [CUSTOM_ELEMENTS_SCHEMA]` or you get `NG8001`.
- **RxJS 7.8** — `.subscribe({ next, error, complete })` object form.

## Core standards

### 1. Always unsubscribe

```typescript
private destroyed$ = new ReplaySubject<boolean>(1);

ngOnInit(): void {
  this.service.getData().pipe(takeUntil(this.destroyed$)).subscribe({ next, error, complete });
}

ngOnDestroy(): void {
  this.destroyed$.next(true);
  this.destroyed$.complete();
}
```

Never leave a bare `.subscribe()` without teardown.

### 2. Dialogs — always handle ESC (no "dead button" bug)

A `<ui5-dialog [open]="flag">` self-closes on ESC but does **not** write back to `flag`. If nothing resets it, re-clicking the trigger (`flag=true → true`) never reopens the dialog — the button is dead.

- **Prefer shared wrapper** with two-way `[(isDialogOpen)]="flag"` — the wrapper resets the flag on ESC.
- **Raw `<ui5-dialog [open]="flag">` MUST** carry a firing close handler that resets the same flag:
  ```html
  <ui5-dialog [open]="showModal" (ui5BeforeClose)="showModal = false">
  ```
- **Firing close events on raw `ui5-dialog`**: `(ui5BeforeClose)`, `(before-close)`, `(beforeClose)`, `(ui5Close)`. **NEVER** `(onBeforeClose)`/`(onClose)`/`(onAfterClose)`/`(ui5AfterClose)` on a raw dialog — those are the wrapper's `@Output` names and never fire on a raw dialog.
- **Checklist**: [ ] firing close event present [ ] resets the exact `[open]` flag [ ] manual: open → ESC → click trigger again → reopens.

### 3. HTTP — always via a service, never raw HttpClient in features

Route HTTP through an injectable service. Always handle errors per call in the `error:` callback.

### 4. Forms — template-driven (`[(ngModel)]`)

Most common in NgModule apps. Import `FormsModule` in the module.

### 5. Services / models

- Services: `@Injectable({ providedIn: 'root' })`, `*.service.ts`.
- Models: implement a `deserialize(input): this` method that maps raw JSON to a typed instance.
- Enums: `export enum Xxx {}` with a companion class for label mapping.

## Component template (standard style)

```typescript
@Component({
  selector: 'app-example',
  templateUrl: './example.component.html',
  styleUrl: './example.component.css',
})
export class ExampleComponent implements OnInit, OnDestroy {
  isLoading = false;
  private destroyed$ = new ReplaySubject<boolean>(1);

  constructor(
    private router: Router,
    private dataService: DataService,
  ) {}

  ngOnInit(): void {
    this.isLoading = true;
    this.dataService.getAll().pipe(takeUntil(this.destroyed$)).subscribe({
      next: (res) => { /* handle */ },
      error: () => { /* show error */ },
      complete: () => (this.isLoading = false),
    });
  }

  ngOnDestroy(): void {
    this.destroyed$.next(true);
    this.destroyed$.complete();
  }
}
```

Module declares the component and imports CommonModule (+ `CUSTOM_ELEMENTS_SCHEMA` for UI5):

```typescript
@NgModule({
  declarations: [ExampleComponent],
  imports: [CommonModule, ExampleRoutingModule],
  schemas: [CUSTOM_ELEMENTS_SCHEMA],  // required for <ui5-*> custom elements
})
export class ExampleModule {}
```

## International Angular best practices

- **Always unsubscribe** (`takeUntil(destroyed$)`); never leak subscriptions.
- **`trackBy` on every `*ngFor`** over a list that mutates.
- **Type everything** — no implicit `any` on public APIs; type HTTP responses and models.
- **Lazy-load feature modules**; keep bundles under budget.
- **Keep templates dumb** — logic in the class/service, not the template; no heavy function calls in bindings.
- **Immutable updates** to bound data so change detection sees the change.

---

# ERROR CATALOG

Format: **Symptom → Cause → Fix**. Grouped by phase.

## 1. Compile / build errors (NG####, TS#### — mostly `strictTemplates`)

- **`NG8001: '<x>' is not a known element`** → Component not declared/imported in the module, **or it's a UI5/Bryntum web component**. Fix: declare it (or its module) in `imports`/`declarations`; **for `<ui5-*>` add `schemas: [CUSTOM_ELEMENTS_SCHEMA]` to the module** — the #1 cause here.
- **`NG8002: Can't bind to 'X' since it isn't a known property of 'Y'`** → Directive not imported (`routerLink`→`RouterModule`, `ngModel`→`FormsModule`), misspelled input, or web-component property. Fix: import the owning module; for web components use `[attr.x]` or `CUSTOM_ELEMENTS_SCHEMA`.
- **`NG8003: No directive found with exportAs 'X'`** → `#f="ngForm"` without `FormsModule`. Fix: import it.
- **`NG5002: Parser Error / Unexpected token`** → broken template (unclosed `*ngIf`, stray `}`, bad `{{ }}`, unbalanced `@if` braces). Fix: balance the markup.
- **`TS2307: Cannot find module '@app/...'`** → path alias missing/typo or dep not installed. Fix: check `tsconfig.json` `paths`; `npm i` if a package.
- **`TS2339: Property 'X' does not exist on type`** in template → `strictTemplates` — field untyped or missing. Fix: declare/type the field; narrow with `*ngIf="x as y"`.
- **`TS2564: Property has no initializer and is not definitely assigned`** → strict class fields. Fix: `x!: T` (definite assignment) or initialize.
- **Budget exceeded** → lazy-load the feature module, or raise `budgets` in `angular.json`.

## 2. NgModule / import / resolution errors

- **`NG6002 / Component X is not part of any NgModule`** → new component not added to any module's `declarations`. Fix: add it to the feature module's `declarations`.
- **`NG6008 / Type X is part of the declarations of 2 NgModules`** → component declared in two modules. Fix: declare once; export from that module and import the module elsewhere.
- **`'CommonModule' … *ngIf is not a known …`** → feature module forgot `CommonModule`. Fix: import `CommonModule`.
- **Circular dependency warning** → two files import each other. Fix: extract the shared type/token to a third file.

## 3. Runtime errors (NG0xxx)

- **`NG0100: ExpressionChangedAfterItHasBeenCheckedError`** → value changed after CD ran. Fix: move mutation to `ngOnInit`, or `Promise.resolve().then(() => …)`, or `ChangeDetectorRef.detectChanges()`.
- **`NG0200: Circular dependency in DI`** → services inject each other. Fix: break the cycle; `forwardRef` or inject inside a method.
- **`NG0201: No provider for X`** → service not provided. Fix: `@Injectable({ providedIn: 'root' })`, or add to module/component `providers`.
- **`NG0203: inject() must be called from an injection context`** → `inject()` outside constructor/field init. Fix: use constructor DI.
- **`Cannot read properties of undefined`** → async data read before load. Fix: `*ngIf="data"` guard, `data?.x`, or default value.
- **`ExpressionChanged` after WebSocket/3rd-party callback** → callback outside Angular's zone. Fix: `NgZone.run(() => …)` or `markForCheck()`.

## 4. Template / render errors

- **`Pipe not found: 'async'/'date'`** → `CommonModule` not imported. Fix: import it.
- **`InvalidPipeArgument`** → wrong input type. Fix: coerce/guard before pipe.
- **`*ngFor` renders nothing / flickers** → missing/unstable `trackBy`. Fix: `*ngFor="let x of items; trackBy: trackById"`.
- **`@for` without `track`** → **compile error** in v17. Fix: add `track item.id`.
- **`[(ngModel)]` no update** → `FormsModule` not imported. Fix: import `FormsModule`.
- **UI5 event not firing** → bound as Angular `@Output` but it's a DOM `CustomEvent`. Fix: bind the native event `(ui5-change)`.
- **Button stops working after dialog ESC** → `[open]` flag not reset on ESC. Fix: `(ui5BeforeClose)="flag = false"` — see §2 Dialogs above.

## 5. Dependency injection errors

- **NG0201** (no provider), **NG0200** (circular), **NG0203** (outside context) — see §3.
- **`NG2003: No suitable injection token`** → injecting an interface/type erased at runtime. Fix: use a class or `InjectionToken`.
- **Service works in one module, `NG0201` in another** → provided in a lazy module's scope. Fix: `providedIn: 'root'`.

## 6. Routing errors (NG04xxx)

- **`NG04002: Cannot match any routes`** → path typo, missing wildcard, or failed lazy import. Fix: check routing module; add `{ path: '**', redirectTo: '' }`.
- **Lazy module chunk load fails** → wrong `loadChildren` path. Fix: `loadChildren: () => import('./x/x.module').then(m => m.XModule)`.
- **Guard returns nothing** → navigation hangs. Fix: return `boolean`/`UrlTree`/`Observable`.
- **`NG0201: No provider for Router`** → `RouterModule.forRoot(routes)` missing in AppRoutingModule.

## 7. RxJS / HTTP errors

- **`HttpErrorResponse` status 0 / Unknown Error** → CORS or network, not a code bug. Check backend CORS config.
- **401 on every request** → auth interceptor not attaching the token. Fix: check interceptors; ensure `withCredentials` for cookie auth.
- **Observable never emits** → not subscribed. Fix: `.subscribe(...)` or `| async` in template.
- **Memory leak / duplicate handlers** → subscription not torn down. Fix: `takeUntil(this.destroyed$)` + complete in `ngOnDestroy`.

## 8. Change detection (zone.js)

- **View not updating after `setTimeout`/3rd-party callback** → ran outside the zone. Fix: `this.ngZone.run(() => …)` or `cdr.detectChanges()`.
- **3rd-party chart/scheduler mutates DOM → `NG0100`** → async render fights CD. Fix: initialize in `ngAfterViewInit`, keep their state out of Angular bindings, or `OnPush` + `markForCheck()`.

## Debug workflow

1. Read the **NG####** / **TS####** code → jump to the matching section.
2. No code? Classify by *when* it fires: build vs runtime (browser console) vs template-type-check.
3. Confirm Angular version and architecture (NgModule vs standalone) — do not propose standalone/signals/zoneless fixes for an NgModule codebase.
4. For unknown-element errors, first check: is it a UI5/Bryntum web component missing `CUSTOM_ELEMENTS_SCHEMA`?
5. Give one-line cause + minimal fix using project conventions.
