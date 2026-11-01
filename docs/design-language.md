# Design language

Ported from **MetricsGo v2** at Kavin's request, so the two apps feel like one
family. MetricsGo is Next.js; this is Vite. The token layer transfers
unchanged — both are Tailwind v4, CSS-first, with no `tailwind.config.js`.

Source of truth: `frontend/src/index.css` (tokens) and
`frontend/src/components/ui/styles.ts` (class constants).

## Tokens

Colours are CSS variables on `:root`, overridden on `[data-theme="dark"]`, then
aliased into Tailwind utilities through `@theme inline`. Because every utility
resolves through a variable, **no `dark:` class appears anywhere in the app** —
dark mode flips the variables, not the markup.

Semantic aliases, used instead of `neutral-*` / `gray-*`:

| utility | meaning |
|---|---|
| `bg-app-bg` | page background — a warm off-white, `#f6f4f1`, not gray |
| `bg-card` | surfaces |
| `border-line` | every separator |
| `bg-hoverfill` | hover fill, muted chip background |
| `text-ink` / `text-ink-2` | primary / secondary ink |
| `bg-brand` `text-brand` | accent |
| `bg-darkbtn` | inverting secondary CTA |
| `green` `red` `amber` (+ `-bg` tints) | status |

Opacity modifiers work on all of them and are used freely: `border-line/60`,
`text-ink-2/70`, `bg-red-bg/40`.

**The one deliberate divergence:** MetricsGo's brand orange `#f26522` is its own
identity. Excel Engineers uses a deep industrial blue, `#1e5eb8` (lightened to
`#4b8ee0` in dark mode, where the darker blue fails contrast). Rebranding the
entire app is two lines in `index.css`.

## Theme switching

A blocking inline script in `index.html` reads `localStorage["ee-theme"]`
(`light` | `dark` | `system`, default `system`) and stamps
`document.documentElement.dataset.theme` **before first paint**, so there is no
flash of the wrong theme. `frontend/src/lib/theme.ts` handles later changes and
re-applies on OS change while the preference is `system`.

## Rules

- **Borders, not shadows.** `border border-line` separates everything. Shadows
  appear only on popovers (`shadow-sm`), the mobile drawer (`shadow-xl`) and the
  toast (`shadow-lg`). There is no elevation system.
- **Two radii.** `rounded-xl` (12px) for cards, panels and tables; `rounded-lg`
  (8px) for buttons, inputs, dropdowns and nav items. `rounded-md` for items
  nested inside a `rounded-lg` container; `rounded-full` for chips and avatars.
- **Dense type, almost all under 14px.** `text-[13px]` is the workhorse — body,
  table cells, buttons, inputs, nav. `text-xl font-semibold tracking-tight` for
  the page heading, `text-xs` for table headers, `text-[11px]` for chips,
  `text-[10px] uppercase tracking-wide` for eyebrow labels.
- **`tabular-nums` on every number** in a column or a stat tile. Stock counts
  that jitter as they change are unreadable.
- **Active state is a border, not a fill.** Sidebar items go
  `border-line bg-app-bg` when active, `border-transparent` otherwise.
- **Focus turns the border brand-coloured** (`outline-none focus:border-brand`).
  No focus rings.
- **`transition-colors` and nothing else.** No transforms, no scale, no motion,
  except the sidebar's `transition-[width]`.
- **Numbers are Indian-formatted** — `toLocaleString("en-IN")`, and money is
  rendered from integer paise by one shared helper.

## Honesty in states

Taken directly from MetricsGo, and it matters more here because these numbers
are stock and money:

- **Error, loading and empty are three different states** and are never
  conflated. An empty table says "no products match this filter", a failed load
  says what failed and offers a retry.
- Missing data renders `—`, never a fabricated `0`.
- Truncation is announced ("showing the first 200 of 1,340").
- Loading is the word `Loading…`. No skeletons, no spinners.

## Buttons

Three levels, and picking the wrong one is the most common way a screen starts
looking off:

1. `primaryBtnCls` — brand fill. One per screen: the thing you came to do.
2. `darkBtnCls` — inverting dark. A strong secondary action.
3. `ghostBtnCls` — bordered. Everything else.
4. `dangerBtnCls` — red fill. Destructive only, and never the default focus.

## Icons

MetricsGo hand-rolls inline SVG at `strokeWidth="1.8"` and `17px`. That weight
is part of the look — lucide's default 2px at 24px reads noticeably heavier. We
use the same approach: a local path map rendered by one small `<Icon>`.

## What we did NOT port

MetricsGo's auth pages use a separate marketing style — orange gradients,
hard-coded hex, `rounded-3xl`, no tokens, no dark mode. That split exists there
for good reason (a public signup funnel). This app has one login screen for one
company, so it uses the same tokens as the rest of the app.
