# Responsive check (Requirements 34.1-34.4)

## Method

- `npm run build`, then `npx vite preview --port 4173`.
- Headless Microsoft Edge driven by `playwright-core`, installed in a temp directory outside the repo (no change to `package.json` or `package-lock.json`).
- API calls were intercepted and answered with mock JSON. Every text field (names, addresses, emails, order references) held a 144-character unbroken string to stress overflow. Auth was simulated through localStorage (role CUSTOMER, RESTAURANT_OWNER or DELIVERY_PARTNER). The cart held one item.
- Each route was loaded at 320, 480, 768, 1280 and 1920 px wide (height 900). Pass means `document.documentElement.scrollWidth <= window.innerWidth`.

## Results

| Route | 320 | 480 | 768 | 1280 | 1920 |
|---|---|---|---|---|---|
| /login | pass | pass | pass | pass | pass |
| /register | pass | pass | pass | pass | pass |
| /restaurants | pass | pass | pass | pass | pass |
| /dishes | pass | pass | pass | pass | pass |
| /restaurants/1 | pass | pass | pass | pass | pass |
| /cart | pass | pass | pass | pass | pass |
| /customer/dashboard | pass | pass | pass | pass | pass |
| /orders/1 | pass | pass | pass | pass | pass |
| /insights | pass | pass | pass | pass | pass |
| /owner/dashboard | pass | pass | pass | pass | pass |
| /owner/menu | pass | pass | pass | pass | pass |
| /owner/orders | pass | pass | pass | pass | pass |
| /partner/dashboard | pass | pass | pass | pass | pass |
| /partner/history | pass | pass | pass | pass | pass |
| /nope (404) | pass | pass | pass | pass | pass |

## Fixes made

Before the fixes, `/restaurants/1`, `/orders/1` and `/partner/dashboard` overflowed horizontally (up to 1587 px at 768 px wide) when given long unbroken text.

- `base.css`: `.container { overflow-wrap: anywhere }`; at 768 px and below, `--control-height` is 2.75rem (44 px) and `.btn-sm` gets 44 px minimum height.
- `components.css`: at 768 px and below, the hamburger toggle is 44x44 and nav links have a 44 px minimum height.
- `PartnerDashboard.css`: grid column minimum is `min(280px, 100%)`.

Already in place: hamburger Navbar at 768 px and below, grids with fewer columns at 768 px and single-column at 480 px, full-width forms at 480 px, all tables inside `.table-wrap` (scrolls inside the wrapper), images with `max-width: 100%`.

## Limitations

- Data came from mocks, so real backend payloads were not exercised. Pages with modals (review, return) were measured closed.
- Only Chromium (Edge) was used.
