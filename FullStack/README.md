# SliceMatic Stage 3

SliceMatic is a full-stack PizzaFlow delivery application built for the Stage 3 live demo. It includes a customer ordering flow, Supabase-backed menu/orders schema, admin dashboard, CSV export, and an OpenRouter-powered recommendation engine.

## Architecture

```mermaid
flowchart LR
  Customer["Customer UI (Next.js on Vercel)"] --> MenuAPI["/api/menu"]
  Customer --> RecommendAPI["/api/recommend"]
  Customer --> OrdersAPI["/api/orders"]
  Admin["Admin Dashboard + Supabase Auth"] --> AdminAPI["/api/admin/orders"]
  Admin --> MenuAdminAPI["/api/admin/menu"]
  MenuAPI --> Supabase["Supabase PostgreSQL"]
  OrdersAPI --> Supabase
  AdminAPI --> Supabase
  MenuAdminAPI --> Supabase
  RecommendAPI --> Supabase
  RecommendAPI --> OpenRouter["OpenRouter Chat Completions"]
  Supabase --> Tables["pizza_types, pizza_bases, toppings, pizza_sizes, customer, orders, order_item, order_item_topping, recommendation_event"]
```

## Application Workspaces

SliceMatic is structured as a real product with separate workspaces, not one giant form:

- Customer app: intake, AI recommendation, menu browsing, pizza builder, cart, checkout, tracking, and final bill.
- Admin console: login, logout, forgot password, reset password, authenticated operations dashboard, filters, revenue metrics, CSV export, order table, forecast, settings, and menu lifecycle tools.
- AI lab: admin-facing AI explanations, recommendation strategy, cart strategist, menu copywriter, and operations briefing.

The customer workspace does not render the admin console below the order flow. The admin workspace does not render the customer cart or ordering stage. This keeps the live demo focused and makes the application feel like a complete delivery platform.

## Stage 3 Rubric Coverage

| Requirement | Implementation |
| --- | --- |
| Frontend on Vercel, Next.js/React recommended | Next.js App Router app in this folder. Vercel-ready with `npm run build`. |
| Full ordering flow | Customer intake, AI recommendation, menu customization, cart, checkout, bill totals, and tracking confirmation. |
| Supabase backend and database | `supabase/schema.sql` creates separate menu, orders, and line-item tables. API routes use Supabase JS. |
| Menu from DB tables | `/api/menu` reads `slicematic.pizza_types`, `pizza_bases`, `toppings`, and `pizza_sizes`; demo seed fallback is only for local no-key runs. |
| Orders saved in PostgreSQL | `/api/orders` inserts customer, order, order item, item topping, totals, payment method, address, and recommendation status. |
| Admin login | Admin screen signs in with Supabase Auth when Supabase env keys exist; local demo credentials are available for development. |
| Admin dashboard | Revenue, order count, AOV, top-selling pizza, busiest hour, payment mix, order filters, CSV export, menu controls, and forecast panel. |
| Preserve Stage 2 logic | Name, phone, quantity, payment, discount, GST, and bill calculation rules live in `lib/pricing.ts`. |
| AI/ML integration | OpenRouter recommendation engine, AI cart strategist, AI menu copywriter, AI operations briefing, recommendation logging, and demand forecast dashboard. |

## Stage 2 Business Rules Preserved

- Name: alphabets and spaces only, 2-40 characters.
- Phone: exactly 10 digits and starts with 6, 7, 8, or 9.
- Delivery radius: active launch radius is 0-4 km; 4-6 km is rejected with a controlled message.
- Total quantity: 1-10 pizzas per order.
- Discount: 10% when total pizza quantity is 5 or more.
- GST: 18% after discount.
- Payment modes: Cash, Card, UPI only.
- Bill: itemized line total, subtotal, discount, GST, final payable amount.

The source of truth is `lib/pricing.ts`.

## Menu Lifecycle

Admin users can add new sellable catalogue items from the Menu tab:

- New pizza type: code, name, price, badge, prep time, tags, image path, description.
- New crust/base: code, name, price, description.
- New topping: code, name, price.

When Supabase is configured and the admin is signed in, `POST /api/admin/menu` creates a real database row in the correct menu table. During local demo mode, the item is added to the in-memory menu so the workflow can still be shown without credentials.

New available pizzas appear in the customer menu immediately. New bases and toppings appear inside the pizza builder immediately.

## Admin Authentication

The admin console is built like a secure application workspace:

- Login screen with validated email and password.
- Logout action from the signed-in admin shell.
- Forgot password screen using Supabase `resetPasswordForEmail` when env keys are configured.
- Reset password screen using Supabase `updateUser` during a recovery session.
- Local demo fallback that can reset the demo password for the current browser session.
- Admin APIs remain protected with bearer-token checks when Supabase admin env keys exist.

## Local Setup

```bash
cd FullStack
npm install
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000`.

Without environment keys the app runs with demo menu/orders so the UI can be reviewed immediately. With Supabase keys it becomes fully persistent.

## Environment Variables

```bash
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
OPENROUTER_API_KEY=
OPENROUTER_MODEL=openai/gpt-oss-20b
NEXT_PUBLIC_DEMO_ADMIN_EMAIL=admin@slicematic.in
NEXT_PUBLIC_DEMO_ADMIN_PASSWORD=slicematic-demo
```

Keep `SUPABASE_SERVICE_ROLE_KEY` only in server environments such as Vercel project settings. Never expose it in browser code.

## Supabase Setup

1. Create a Supabase project.
2. Open SQL Editor.
3. Run `supabase/schema.sql`.
4. In Authentication, create the admin user used for the demo.
5. Add the environment variables to `.env.local` and to Vercel.
6. For marking, create a read-only Supabase user or invite the evaluator with read-only access.

The required core tables are:

- `slicematic.pizza_types`
- `slicematic.pizza_bases`
- `slicematic.toppings`
- `slicematic.pizza_sizes`
- `slicematic.customer`
- `slicematic.orders`
- `slicematic.order_item`
- `slicematic.order_item_topping`
- `slicematic.recommendation_event`

## AI Features

The application includes multiple AI features for Stage 3 and bonus coverage:

1. AI Recommendation Engine
   - Trigger point: after name and phone, before menu browsing.
   - Data used: customer phone, past Supabase order history, current menu IDs, toppings, and popularity fallback.
   - Feature profile: favourite pizza, favourite topping, order count, average quantity, average spend, vegetarian lean, spicy lean, and recency.
   - Menu signals: available menu IDs, local favourites, and high-value topping signals so recommendations improve fit and AOV.
   - Output: one pizza ID, one topping ID, reason, and confidence.
   - Guardrail: the server validates that returned IDs exist in the current available menu.
   - Persistence: every shown recommendation is written to `recommendation_event`; if purchased, `/api/orders` marks it as `Purchased`.

2. AI Cart Strategist
   - Trigger point: customer cart panel.
   - Data used: current cart, totals, discount threshold, menu, and delivery context.
   - Output: one concise cart improvement, discount cue, pairing, or checkout reassurance.
   - Business value: improves conversion and AOV without pushing random upsells.

3. AI Menu Copywriter
   - Trigger point: admin menu lifecycle studio.
   - Data used: new item type, name, price, and draft tags.
   - Output: customer-facing description, badge, tags, prep time, and merchandising note.
   - Business value: helps launch new menu items consistently.

4. AI Operations Briefing
   - Trigger point: admin overview.
   - Data used: revenue, AOV, top pizza, busiest hour, payment mix, hourly demand, and forecast.
   - Output: shift briefing, staffing cue, prep list, revenue watch, and prioritized actions.
   - Business value: turns order data into kitchen/rider decisions.

All AI endpoints have deterministic fallbacks so the app continues working if OpenRouter is unavailable.

### OpenRouter System Prompt

```text
You are SliceMatic's in-app pizza recommendation assistant for a single outlet in Delhi.
Recommend exactly one pizza and one topping the customer is likely to enjoy.
Hard rules:
- Only choose from the menu IDs provided. Never invent menu items.
- Return strict JSON only.
- If history exists, personalize using favourite pizza, topping, spend, veg/non-veg lean, spicy lean, quantity pattern, and recency.
- If the customer is new, recommend a popular crowd-pleaser and say it is a safe first pick.
- Prefer combinations that improve customer fit and contribution margin without pushing unnecessary discounts.
- Keep the reason under 20 words, friendly, and without emojis.
```

### Model Choice

Default model: `openai/gpt-oss-20b` via OpenRouter.

Reason: the task needs low-latency structured JSON, light personalization, and reliable instruction following. The model is strong enough for grounded menu recommendations while staying cost-conscious for a student demo. The model can be changed by editing `OPENROUTER_MODEL`.

## Demand Forecast ML

The admin forecast panel estimates upcoming peak demand from historical hourly orders. For the live app, the API computes a lightweight forecast from Supabase order history with a demo fallback. The included `scripts/forecast_model.py` can be used to present a scikit-learn training workflow during Q&A.

```bash
python -m pip install -r requirements-ml.txt
python scripts/forecast_model.py
```

## Deployment

```bash
npm run build
```

Deploy the `FullStack` directory to Vercel and set all environment variables in Vercel Project Settings.

Submission checklist:

- Public Vercel URL.
- GitHub repository URL.
- Supabase read-only access for evaluator.
- Loom walkthrough link.
- README with architecture, setup, AI feature, system prompt, and model rationale.
- Live demo ready to show one code modification, such as changing the discount trigger in `lib/pricing.ts` from 5 pizzas to 3.

## Demo Flow

1. Enter a valid name, phone, and delivery address.
2. Show AI recommendation and explain OpenRouter plus Supabase history lookup.
3. Build a pizza with base, size, toppings, and quantity.
4. Place order with UPI, Card, or Cash.
5. Open admin dashboard, show filters, CSV export, top pizza, busiest hour, and revenue summary.
6. Explain schema tables and how `orders` and `order_item` separate header vs line data.
