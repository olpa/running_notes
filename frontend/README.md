# Frontend maintenance guide

The frontend is a Vite-built single-page application written in strict
TypeScript. It uses native custom elements rather than a UI framework.
Production assets are built in a Node container stage and served by Nginx.

This document describes architectural rules and conventions that should remain
useful as components are added, removed, or reorganized.

## Architecture

- `src/main.ts` owns application startup, authentication state, and top-level
  coordination.
- `src/api.ts` is the frontend boundary for backend HTTP calls.
- `src/contracts.ts` defines the frontend's typed assumptions about backend
  requests and responses.
- Shared, application-independent DOM behavior belongs in small modules under
  `src/`.
- Feature-specific markup and behavior belong together under
  `src/components/`.
- Component HTML templates live beside their TypeScript modules and are
  imported using Vite's `?raw` suffix.
- Components currently use the light DOM and shared global CSS. They do not use
  Shadow DOM.
- A small client-side router maps top-level browser paths to tabs and supports
  direct message links. Browser routes and backend APIs use separate
  namespaces.

Avoid introducing a framework, global state library, routing library, or Shadow DOM
solely for consistency with other projects. Add one only when an application
requirement justifies its cost.

## Authentication and API access

Authentication uses a server-managed session cookie. The frontend must not
store access tokens or authentication credentials in browser storage.

Components should receive or import the shared API client instead of
implementing their own `fetch` behavior. Common response handling, including
session expiry, belongs in the API and application layers.

JSON, upload, and media endpoints live under `/api`. Browser authentication
flows remain under `/auth`. Do not reuse a browser route as an API path.

An authenticated request returning `401` transitions the entire application to
its anonymous state. Components should not attempt to maintain an independent
authentication state.

Interfaces in `src/contracts.ts` provide compile-time contracts; they do not
validate server responses at runtime. Keep the interfaces synchronized with
backend response shapes. Introduce runtime validation only if response drift or
untrusted external APIs make it necessary.

## Component conventions

Custom element names use the `rn-` prefix. Register every element in
`src/custom-elements.d.ts` so DOM APIs infer its concrete TypeScript class.

Prefer explicit, typed component interfaces:

- Properties and methods provide data and commands to a component.
- Bubbling `CustomEvent` instances communicate user intent to the application
  shell.
- `activate()` and `deactivate()` represent tab visibility changes.
- `reset()` clears session-specific or sensitive state.

Changing an element's `hidden` state does not disconnect it from the document,
so native `connectedCallback()` and `disconnectedCallback()` do not represent
tab activation. Use the explicit activation methods for that purpose.

Tab changes should navigate through `src/router.ts`, preserving browser
history, direct links, and authentication return paths. Nginx explicitly lists
the supported browser routes instead of applying a site-wide SPA fallback.

Components that start asynchronous work must cancel it or ignore stale results
after reset, logout, or a newer request. Components that own media streams,
playback, timers, or other resources must release them when the session ends.

Insert backend-derived and user-derived text with `textContent`. Do not
interpolate untrusted values into imported HTML templates or `innerHTML`.

## Adding a component

1. Create adjacent `.html` and `.ts` files under an appropriate directory in
   `src/components/`.
2. Extend `HTMLElement` and register an `rn-*` custom element name.
3. Add the element to `HTMLElementTagNameMap` in `src/custom-elements.d.ts`.
4. Define typed properties, methods, events, and backend contracts.
5. Keep authentication and common HTTP behavior outside the component.
6. Add cleanup for requests, timers, media resources, and sensitive data.
7. Add focused tests for behavior and lifecycle boundaries.
8. Run the typecheck, tests, and production build.

## Development and verification

Run commands from `frontend/`:

```console
npm run dev
npm run check
npm test
npm run build
```

`npm run build` performs a strict TypeScript check before invoking Vite.
Generated assets are written to `frontend/dist/` and are not committed.

From the repository root, rebuild the frontend image and replace only the
frontend container in the running development Compose application with:

```console
./frontend/update_app.sh
```

The script itself is self-locating, so an absolute or otherwise valid path to
it can be invoked from any directory. It rebuilds and force-recreates the
`nginx` service without restarting its dependencies.

The application footer displays the UTC build timestamp and short Git commit.
Docker exposes only the minimal Git reference data needed to the build stage;
the final Nginx image does not contain Git metadata.
