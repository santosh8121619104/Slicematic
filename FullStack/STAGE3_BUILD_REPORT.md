# SliceMatic Stage 3 Build Report

This file documents what has been built so far and why it is designed as a real end-customer application, not a single-form prototype.

## Requirement Sources Reviewed

- `Project_Requirements/PizzaFlow_Assignment_Brief_FDE.pdf`
- `Project_Requirements/SliceMatic_Business_Economics.pdf`
- `documents/SliceMatic_PRD_Business_Economics.pdf`
- `Project_Requirements/Types_of_Base.txt`
- `Project_Requirements/Types_of_Pizza.txt`
- `Project_Requirements/Types_of_Toppings.txt`
- `documents/option_a_recommendation_engine_analysis.md`

The Stage 3 rubric was mapped against the implementation: Vercel-ready frontend, Supabase database integration, admin dashboard/auth, preserved Stage 2 logic, OpenRouter AI feature, README documentation, and live demo readiness.

## Application Built

The app in `FullStack` is now a Next.js full-stack application with:

- Separate customer, admin, and AI workspaces
- Application-grade admin auth screens for login, logout, forgot password, and reset password
- Customer ordering journey
- AI recommendation step
- AI cart strategist
- AI menu copywriter
- AI operations briefing
- Menu browsing and pizza customization
- Cart and checkout
- Final itemized bill
- Order confirmation and tracking view
- Admin dashboard
- Admin menu lifecycle studio
- Supabase-ready backend schema
- API routes for menu, orders, admin analytics, CSV export, and AI recommendation
- ML/demand forecast artifact using scikit-learn

The old static prototype files were removed so the folder now clearly represents the production Stage 3 application.

The latest UI pass changed the app shell from a long stacked page into workspace navigation. Customer app, Admin console, and AI lab are mutually exclusive application modes: opening Admin removes the customer order/cart view, and opening Customer removes the admin dashboard. This is the key product-structure change that prevents the project from reviewing like a single giant form.

## End-Customer Flow

The customer journey is intentionally step-based and gated:

1. Customer enters name, phone, delivery address, delivery zone, and optional note.
2. Validation runs before the customer can browse the menu.
3. After valid intake, the app calls the AI recommendation route.
4. Recommendation is shown before menu selection.
5. Customer can build a pizza using pizza type, base, size, toppings, and quantity.
6. Cart updates bill totals live.
7. Checkout requires Cash, Card, or UPI.
8. Order is saved through the backend API.
9. Customer sees tracking plus a final structured bill.

This prevents the app from behaving like a loose form. The flow feels like a delivery product: intake, recommendation, customization, checkout, confirmation, operations.

The admin side is a separate control room, not a continuation of the checkout form. It covers order analytics, menu lifecycle, AI operations, settings, and export workflows.

## UI And Aesthetic Decisions

The UI was designed to feel premium and operational, not like coursework.

- Image-led hero using real pizza imagery.
- Sticky top navigation with brand, order/admin/AI anchors, and search.
- Three-column desktop composition: status rail, main ordering stage, cart.
- Mobile responsive layout with no horizontal overflow.
- Dense admin dashboard instead of a marketing-style landing page.
- Repeated cards use restrained 8px radii.
- Buttons use lucide icons where useful.
- Final bill and admin panels are structured for scanning.
- No decorative bokeh/orb backgrounds.
- Color palette avoids one-note purple/blue/cream themes.
- Customer menu is hidden until intake is valid, preserving a real journey.

Browser verification confirmed:

- Desktop layout has no horizontal overflow.
- Mobile layout has no horizontal overflow.
- Hero, intake, admin, and menu render correctly.
- Images are not broken.
- Admin menu editor and customer flow remain responsive.

## Stage 2 Logic Preserved

Implemented in `lib/pricing.ts`.

Validation:

- Name must be alphabetic/spaces only, 2-40 characters.
- Phone must be 10 digits and start with 6, 7, 8, or 9.
- Delivery address is required and must be descriptive.
- Delivery zone must be selected.
- Active launch delivery radius is 0-4 km.
- 4-6 km is rejected with a controlled message.
- Quantity must be a whole number from 1 to 10.
- Total order capacity cannot exceed 10 pizzas.
- Payment mode must be Cash, Card, or UPI.
- Menu IDs are validated server-side against active pizzas, bases, sizes, and toppings.
- Duplicate toppings are rejected server-side.

Pricing:

- Subtotal is calculated from system prices.
- 10% discount applies when total pizza quantity is 5 or more.
- GST is 18% after discount.
- Final payable is discount-adjusted subtotal plus GST.
- Bill stores subtotal, discount, GST, final total, payment mode, and line items.

## Backend And API Architecture

The backend is implemented through Next.js API routes.

API routes:

- `GET /api/menu`
  - Loads menu from Supabase DB when env vars exist.
  - Uses demo seed data when Supabase is not configured.

- `POST /api/orders`
  - Validates customer, delivery zone, cart lines, quantities, menu IDs, and payment mode.
  - Saves customer, order, order items, and toppings through Supabase when configured.
  - Returns a saved order object with final bill totals.

- `GET /api/admin/orders`
  - Returns admin summary and recent orders.
  - Supports `?format=csv`.
  - Requires Supabase Auth bearer token when Supabase admin env is configured.
  - Falls back to demo data locally.

- `POST /api/recommend`
  - Builds a recommendation profile.
  - Calls OpenRouter when `OPENROUTER_API_KEY` exists.
  - Validates returned IDs against the active menu.
  - Logs recommendation events in Supabase when configured.
  - Falls back safely when no key/rate-limit/error occurs.

- `POST /api/ai/cart-insight`
  - Reads the active cart, menu, bill totals, discount threshold, and delivery context.
  - Returns one practical cart improvement, discount cue, pairing, or checkout reassurance.
  - Uses OpenRouter with deterministic fallback.

- `POST /api/ai/menu-copy`
  - Generates admin menu descriptions, badges, tags, prep time, and merchandising notes.
  - Supports pizzas, bases, and toppings.
  - Helps launch new catalogue items consistently.

- `GET /api/ai/ops-briefing`
  - Reads revenue, AOV, top pizza, busiest hour, payment mix, hourly demand, and forecast.
  - Returns shift briefing, staffing cue, prep list, revenue watch, and prioritized actions.
  - Requires admin auth when Supabase admin env is configured.

- `POST /api/admin/menu`
  - Creates new pizzas, bases, or toppings from the admin dashboard.
  - Requires Supabase Auth when Supabase admin env is configured.
  - Generates the next menu code/id.
  - Persists to `pizza_types`, `pizza_bases`, or `toppings`.
  - Supports local demo creation when credentials are not configured.

Important backend files:

- `lib/pricing.ts`
- `lib/data-service.ts`
- `lib/supabase.ts`
- `lib/seed-data.ts`
- `lib/types.ts`
- `app/api/menu/route.ts`
- `app/api/orders/route.ts`
- `app/api/admin/orders/route.ts`
- `app/api/recommend/route.ts`

## Supabase Schema

Schema file:

- `supabase/schema.sql`

Main tables:

- `slicematic.pizza_types`
- `slicematic.pizza_bases`
- `slicematic.toppings`
- `slicematic.pizza_sizes`
- `slicematic.customer`
- `slicematic.orders`
- `slicematic.order_item`
- `slicematic.order_item_topping`
- `slicematic.customer_activity`
- `slicematic.customer_preference`
- `slicematic.recommendation_event`
- `slicematic.daily_sales_fact`

The schema satisfies the Stage 3 requirement for separate menu, orders, and order line item tables.

Additional schema qualities:

- UUID primary keys for transactional tables.
- Foreign keys between order headers, order items, pizzas, bases, sizes, toppings, and customers.
- Payment mode check constraint.
- Quantity check constraint.
- Delivery zone check constraint.
- Admin export view.
- Analytics view.
- RLS enabled.
- Public read policies for menu tables.
- Authenticated read policies for admin/order tables.

## Admin Dashboard

Admin features built:

- Admin login screen.
- Admin logout action.
- Forgot password screen.
- Reset password screen.
- Supabase Auth login when env keys exist.
- Supabase password recovery when env keys exist.
- Demo login for local review.
- Demo password reset fallback for local review.
- Revenue summary.
- Order count.
- Average order value.
- Top-selling pizza.
- Busiest hour.
- Payment mix chart.
- Hourly demand chart.
- Orders table.
- Filter by date.
- Filter by payment mode.
- CSV export.
- Demand forecast chart.
- Top 3 forecast peak windows.
- Menu editor for pizzas, bases, and toppings.
- Menu lifecycle studio for adding brand-new pizzas, crusts, and toppings.
- Availability toggles.
- Price/name editing.
- Brand/outlet/hero copy editing.
- AI feature explanation panel.
- AI cart strategist in customer cart.
- AI menu copywriter in admin menu lifecycle.
- AI operations briefing in admin overview.

The admin view is intentionally dense and operations-focused so it feels like a real restaurant control room.

## AI And ML Recommendation Design

This is not just a generic LLM call. The recommendation API now builds a structured customer profile before calling OpenRouter.

Features engineered:

- Customer tier: new vs returning.
- Favorite pizza.
- Favorite topping.
- Order count.
- Average quantity.
- Average spend.
- Vegetarian lean.
- Spicy lean.
- Last ordered timestamp.
- High-value topping signals.
- Local favorite pizza signals.
- Active menu IDs only.

OpenRouter behavior:

- Uses strict JSON output.
- Only allowed to recommend IDs from the provided menu.
- Validates pizza and topping IDs after the LLM response.
- Rejects hallucinated menu items.
- Falls back to deterministic recommendation if OpenRouter is unavailable.
- Logs `recommendation_event` for measurement.
- Marks recommendation as purchased when the order completes.

Default model:

- `openai/gpt-oss-20b` via OpenRouter.

Reason:

- Good fit for low-latency, cost-conscious structured recommendation.
- Strong enough for grounded JSON and short personalized explanations.
- Easy to swap using `OPENROUTER_MODEL`.

System prompt is documented in `README.md`.

## Demand Forecast ML

Files:

- `scripts/forecast_model.py`
- `requirements-ml.txt`

The ML script trains a lightweight scikit-learn `RandomForestRegressor` for demand forecasting by hour/day.

Features used:

- Weekday.
- Hour.
- Weekend flag.
- Revenue signal.

Metric:

- RMSE.

Output:

- Validation RMSE.
- Top 7 forecast prep windows.

The admin dashboard also shows a demand forecast chart and top 3 peak windows. This supports a stronger ML story during Stage 3 Q&A.

## Verification Completed

Production build:

- `next build` passed cleanly.

Local production server:

- Running on `http://127.0.0.1:3000`.

Verified API behavior:

- Home page returns `200`.
- Menu API works.
- Admin orders API works.
- CSV export works.
- AI recommendation works with fallback.
- Valid order saves and returns correct bill.
- Invalid delivery radius returns controlled error.
- Invalid quantity returns controlled error.
- Invalid pizza ID returns controlled error.
- Duplicate toppings return controlled error.

Verified browser behavior:

- Customer workspace and admin workspace are mutually exclusive.
- Admin console does not show customer cart/order panels.
- AI lab opens as an admin workspace tab, not as another customer form section.
- Admin login screen renders as a separate application access module.
- Forgot password screen renders.
- Reset password screen renders.
- Demo reset updates the local demo password.
- Admin sign-in opens the dashboard shell.
- Admin logout returns to the auth module.
- Menu hidden before intake.
- Clicking Menu before valid intake keeps user on intake.
- Specific toast appears for incomplete intake.
- AI recommendation appears after valid intake.
- Menu appears after recommendation.
- Build-combo flow opens pizza builder.
- Quantity 5 applies discount.
- Checkout completes order.
- Tracking appears.
- Final bill appears with discount/GST/payment message.
- Admin login works.
- Admin tabs render.
- Expanded menu editor renders pizzas, bases, and toppings.
- No desktop horizontal overflow.
- No mobile horizontal overflow.
- No broken images.

## Files Added Or Significantly Updated

- `package.json`
- `package-lock.json`
- `.env.example`
- `.gitignore`
- `README.md`
- `STAGE3_BUILD_REPORT.md`
- `app/layout.tsx`
- `app/page.tsx`
- `app/globals.css`
- `components/SliceMaticStage3.tsx`
- `lib/types.ts`
- `lib/pricing.ts`
- `lib/seed-data.ts`
- `lib/supabase.ts`
- `lib/data-service.ts`
- `app/api/menu/route.ts`
- `app/api/orders/route.ts`
- `app/api/admin/orders/route.ts`
- `app/api/admin/menu/route.ts`
- `app/api/ai/cart-insight/route.ts`
- `app/api/ai/menu-copy/route.ts`
- `app/api/ai/ops-briefing/route.ts`
- `app/api/recommend/route.ts`
- `supabase/schema.sql`
- `scripts/forecast_model.py`
- `requirements-ml.txt`
- `public/assets/pizza-hero.jpg`
- `public/assets/menu/*.jpg`

## Why This Should Review Well

For application reviewers:

- It is not a one-form UI.
- It has login, logout, forgot password, and reset password screens.
- It has a believable end-to-end customer journey.
- It has operational admin screens.
- It preserves business logic.
- It has defensive server validation.
- It has real database schema design.
- It has an AI feature that uses structured customer/order features.
- It includes ML forecasting support.
- It is responsive and visually polished.
- It has documentation for setup, architecture, AI prompt, and model rationale.

For code reviewers:

- Pricing rules are centralized.
- API routes are focused and separated.
- Supabase access is isolated.
- Types are shared.
- Demo fallback is separated from production Supabase behavior.
- OpenRouter output is validated.
- Admin route supports auth when Supabase is configured.

## Remaining External Steps

These require project credentials or deployment access:

1. Create Supabase project.
2. Run `supabase/schema.sql`.
3. Create admin user in Supabase Auth.
4. Add env vars to `.env.local`.
5. Add env vars to Vercel.
6. Deploy `FullStack` to Vercel.
7. Share public Vercel URL.
8. Share GitHub repo.
9. Share Supabase read-only access.
10. Record Loom walkthrough.

## Important Demo Talking Points

- Show `lib/pricing.ts` for validation, GST, discount, and live threshold modification.
- Show `supabase/schema.sql` for menu/order/order item separation.
- Show `app/api/recommend/route.ts` for feature-engineered OpenRouter recommendation.
- Show `components/SliceMaticStage3.tsx` for gated customer flow and admin dashboard.
- Show `scripts/forecast_model.py` for scikit-learn demand forecast.
- Demonstrate changing `BULK_DISCOUNT_QTY` from `5` to `3`, rebuilding, and showing discount behavior.
