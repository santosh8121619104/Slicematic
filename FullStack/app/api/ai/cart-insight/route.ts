import { NextResponse } from "next/server";
import { callOpenRouterJson } from "../../../../lib/ai";
import { loadMenu } from "../../../../lib/data-service";
import { BULK_DISCOUNT_QTY, calculateBill, getLineUnitPrice } from "../../../../lib/pricing";
import { CartLine, CustomerDetails } from "../../../../lib/types";

export const dynamic = "force-dynamic";

type CartInsightRequest = {
  customer?: CustomerDetails;
  lines: CartLine[];
};

type CartInsight = {
  headline: string;
  message: string;
  nextAction: string;
  suggestedPizzaId?: number;
  suggestedPizzaName?: string;
  suggestedToppingId?: number;
  suggestedToppingName?: string;
  expectedImpact: string;
  confidence: number;
};

const SYSTEM = `You are SliceMatic's AI cart strategist.
Return strict JSON only.
Help the customer make a better pizza order while protecting outlet economics.
Use the current cart, menu, discount threshold, GST rules, and delivery context.
Do not invent menu items. Recommend only provided menu IDs.
Avoid pushy upsells; suggest one useful improvement or reassure the customer if the cart is already strong.
Keep text concise and customer-facing.`;

export async function POST(request: Request) {
  const body = (await request.json()) as CartInsightRequest;
  const menu = await loadMenu();
  const totals = calculateBill(body.lines ?? [], menu);
  const fallback = fallbackInsight(body.lines ?? [], menu);

  const cart = (body.lines ?? []).map((line) => {
    const pizza = menu.pizzas.find((item) => item.id === line.pizzaId);
    const base = menu.bases.find((item) => item.id === line.baseId);
    const toppings = line.toppingIds.map((id) => menu.toppings.find((item) => item.id === id)?.name).filter(Boolean);
    return {
      pizza_id: line.pizzaId,
      pizza: pizza?.name,
      base: base?.name,
      toppings,
      quantity: line.quantity,
      line_total: getLineUnitPrice(line, menu) * line.quantity
    };
  });

  const { data, source } = await callOpenRouterJson<CartInsight>({
    system: SYSTEM,
    user: {
      customer: {
        name: body.customer?.name,
        deliveryZone: body.customer?.deliveryZone
      },
      cart,
      totals,
      discount_threshold_quantity: BULK_DISCOUNT_QTY,
      menu: {
        pizzas: menu.pizzas.filter((item) => item.available).map(({ id, name, price, tags }) => ({ id, name, price, tags })),
        toppings: menu.toppings.filter((item) => item.available).map(({ id, name, price }) => ({ id, name, price }))
      },
      output_schema: {
        headline: "string under 8 words",
        message: "string under 28 words",
        nextAction: "string under 18 words",
        suggestedPizzaId: "number optional",
        suggestedToppingId: "number optional",
        expectedImpact: "string under 18 words",
        confidence: "number 0..1"
      }
    },
    fallback
  });

  return NextResponse.json({ ok: true, insight: normalizeInsight(data, fallback, menu), source });
}

function fallbackInsight(lines: CartLine[], menu: Awaited<ReturnType<typeof loadMenu>>): CartInsight {
  const totals = calculateBill(lines, menu);
  const extraCheese = menu.toppings.find((item) => item.available && item.name.includes("Extra Cheese")) ?? menu.toppings.find((item) => item.available);
  const paneer = menu.pizzas.find((item) => item.available && item.name.includes("Paneer")) ?? menu.pizzas.find((item) => item.available);

  if (!lines.length) {
    return {
      headline: "Start with a bestseller",
      message: `${paneer?.name ?? "Paneer Tikka"} is a reliable first pick for new SliceMatic customers.`,
      nextAction: "Build the suggested combo",
      suggestedPizzaId: paneer?.id,
      suggestedPizzaName: paneer?.name,
      suggestedToppingId: extraCheese?.id,
      suggestedToppingName: extraCheese?.name,
      expectedImpact: "Higher first-order confidence",
      confidence: 0.76
    };
  }

  if (totals.totalQuantity < BULK_DISCOUNT_QTY) {
    return {
      headline: "Group value nearby",
      message: `Add ${BULK_DISCOUNT_QTY - totals.totalQuantity} more pizza${BULK_DISCOUNT_QTY - totals.totalQuantity === 1 ? "" : "s"} to unlock the 10% quantity discount.`,
      nextAction: "Consider one more pizza",
      suggestedPizzaId: paneer?.id,
      suggestedPizzaName: paneer?.name,
      suggestedToppingId: extraCheese?.id,
      suggestedToppingName: extraCheese?.name,
      expectedImpact: "Unlocks quantity discount",
      confidence: 0.82
    };
  }

  return {
    headline: "Cart is discount-ready",
    message: "Your order already unlocks the quantity discount. Extra toppings are optional, not necessary.",
    nextAction: "Proceed to checkout",
    suggestedToppingId: extraCheese?.id,
    suggestedToppingName: extraCheese?.name,
    expectedImpact: "Clear value and faster checkout",
    confidence: 0.86
  };
}

function normalizeInsight(insight: CartInsight, fallback: CartInsight, menu: Awaited<ReturnType<typeof loadMenu>>): CartInsight {
  const pizza = menu.pizzas.find((item) => item.id === Number(insight.suggestedPizzaId) && item.available);
  const topping = menu.toppings.find((item) => item.id === Number(insight.suggestedToppingId) && item.available);
  return {
    headline: String(insight.headline || fallback.headline).slice(0, 80),
    message: String(insight.message || fallback.message).slice(0, 180),
    nextAction: String(insight.nextAction || fallback.nextAction).slice(0, 80),
    suggestedPizzaId: pizza?.id ?? fallback.suggestedPizzaId,
    suggestedPizzaName: pizza?.name ?? fallback.suggestedPizzaName,
    suggestedToppingId: topping?.id ?? fallback.suggestedToppingId,
    suggestedToppingName: topping?.name ?? fallback.suggestedToppingName,
    expectedImpact: String(insight.expectedImpact || fallback.expectedImpact).slice(0, 100),
    confidence: clamp(Number(insight.confidence || fallback.confidence))
  };
}

function clamp(value: number) {
  if (!Number.isFinite(value)) return 0.8;
  return Math.min(0.99, Math.max(0.01, value));
}
