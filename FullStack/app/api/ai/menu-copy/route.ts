import { NextResponse } from "next/server";
import { requireAdminSession } from "../../../../lib/admin-auth";
import { callOpenRouterJson } from "../../../../lib/ai";

export const dynamic = "force-dynamic";

type Section = "pizzas" | "bases" | "toppings";

type MenuCopyRequest = {
  section: Section;
  name: string;
  price: number | string;
  tags?: string;
};

type MenuCopy = {
  description: string;
  badge: string;
  tags: string[];
  prepMinutes: number;
  merchandisingNote: string;
};

const SYSTEM = `You are SliceMatic's menu engineering assistant for a single pizza outlet in New Ashok Nagar, Delhi.
Return strict JSON only.
Create premium but concise customer-facing menu copy.
Keep claims realistic for delivery food. Do not mention fake ingredients unless implied by the item name.
For pizzas, produce description, badge, tags, prepMinutes, and merchandisingNote.
For crusts and toppings, produce description, badge, tags, prepMinutes, and merchandisingNote, but keep prepMinutes low.
Tags must be short category words useful for filtering, such as Veg, Chicken, Cheese, Spicy, Mushroom, Classic, Signature.`;

export async function POST(request: Request) {
  const authError = await requireAdminSession(request);
  if (authError) return authError;

  const body = (await request.json()) as MenuCopyRequest;
  if (!body.name?.trim()) {
    return NextResponse.json({ ok: false, errors: { name: "Add an item name before generating AI copy." } }, { status: 400 });
  }

  const fallback = fallbackCopy(body);
  const { data, source } = await callOpenRouterJson<MenuCopy>({
    system: SYSTEM,
    user: {
      section: body.section,
      item_name: body.name,
      price_inr: Number(body.price || 0),
      seed_tags: body.tags,
      output_schema: {
        description: "string under 22 words",
        badge: "string under 3 words",
        tags: "array of 3-5 strings",
        prepMinutes: "number",
        merchandisingNote: "string under 18 words"
      }
    },
    fallback
  });

  return NextResponse.json({ ok: true, copy: normalizeCopy(data, fallback), source });
}

function fallbackCopy(body: MenuCopyRequest): MenuCopy {
  const name = body.name.trim();
  const lower = name.toLowerCase();
  const tags = [
    lower.includes("chicken") ? "Chicken" : "Veg",
    lower.includes("cheese") ? "Cheese" : lower.includes("mushroom") ? "Mushroom" : "Signature",
    lower.includes("peri") || lower.includes("spicy") || lower.includes("jalapeno") ? "Spicy" : "Fresh"
  ];

  if (body.section === "bases") {
    return {
      description: `${name} adds a distinct texture and holds toppings cleanly through delivery.`,
      badge: "Crust",
      tags: ["Base", "Custom"],
      prepMinutes: 8,
      merchandisingNote: "Position as an upgrade for premium builds."
    };
  }

  if (body.section === "toppings") {
    return {
      description: `${name} adds a focused finishing note to customized pizzas.`,
      badge: "Add-on",
      tags: ["Topping", "Custom"],
      prepMinutes: 2,
      merchandisingNote: "Use as a low-friction cart upsell."
    };
  }

  return {
    description: `${name} is a chef-curated pizza with balanced sauce, cheese, and delivery-ready finish.`,
    badge: "New",
    tags: [...new Set(tags)],
    prepMinutes: 24,
    merchandisingNote: "Feature near popular pizzas for launch week testing."
  };
}

function normalizeCopy(copy: MenuCopy, fallback: MenuCopy): MenuCopy {
  return {
    description: String(copy.description || fallback.description).slice(0, 180),
    badge: String(copy.badge || fallback.badge).slice(0, 24),
    tags: Array.isArray(copy.tags) && copy.tags.length ? copy.tags.map((tag) => String(tag).slice(0, 18)).slice(0, 5) : fallback.tags,
    prepMinutes: Number.isFinite(Number(copy.prepMinutes)) ? Math.min(90, Math.max(2, Math.round(Number(copy.prepMinutes)))) : fallback.prepMinutes,
    merchandisingNote: String(copy.merchandisingNote || fallback.merchandisingNote).slice(0, 140)
  };
}
