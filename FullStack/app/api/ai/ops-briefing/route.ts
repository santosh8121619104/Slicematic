import { NextResponse } from "next/server";
import { requireAdminSession } from "../../../../lib/admin-auth";
import { callOpenRouterJson } from "../../../../lib/ai";
import { loadAdminSummary } from "../../../../lib/data-service";

export const dynamic = "force-dynamic";

type OpsAction = {
  title: string;
  detail: string;
  priority: "High" | "Medium" | "Low";
};

type OpsBriefing = {
  briefing: string;
  staffing: string;
  prepList: string[];
  revenueWatch: string;
  actions: OpsAction[];
};

const SYSTEM = `You are SliceMatic's AI operations analyst for a single pizza outlet.
Return strict JSON only.
Use order summary, payment mix, hourly demand, forecast, top pizza, busiest hour, and revenue to create a practical shift briefing.
Think like a QSR operator: staffing, prep batching, rider readiness, discount leakage, top item availability, and peak-hour readiness.
Keep advice specific and executable.`;

export async function GET(request: Request) {
  const authError = await requireAdminSession(request);
  if (authError) return authError;

  const summary = await loadAdminSummary();
  const fallback = fallbackBriefing(summary);
  const { data, source } = await callOpenRouterJson<OpsBriefing>({
    system: SYSTEM,
    user: {
      summary,
      output_schema: {
        briefing: "string under 35 words",
        staffing: "string under 25 words",
        prepList: "array of 3 strings",
        revenueWatch: "string under 25 words",
        actions: "array of 3 objects with title, detail, priority"
      }
    },
    fallback,
    temperature: 0.2
  });

  return NextResponse.json({ ok: true, briefing: normalizeBriefing(data, fallback), source });
}

function fallbackBriefing(summary: Awaited<ReturnType<typeof loadAdminSummary>>): OpsBriefing {
  const topForecast = summary.forecast[0];
  return {
    briefing: `${summary.topPizza} is leading demand. Prepare for the strongest window around ${summary.busiestHour}.`,
    staffing: `Keep oven and rider coverage tight for ${summary.busiestHour}.`,
    prepList: [
      `Pre-batch ingredients for ${summary.topPizza}.`,
      `Stage boxes before ${topForecast?.label ?? "the evening peak"}.`,
      "Watch large orders that trigger quantity discounts."
    ],
    revenueWatch: `AOV is ${Math.round(summary.avgOrderValue)}; monitor discount-heavy carts.`,
    actions: [
      { title: "Prep bestseller", detail: `Reserve topping stock for ${summary.topPizza}.`, priority: "High" },
      { title: "Peak-hour coverage", detail: `Plan extra counter focus around ${summary.busiestHour}.`, priority: "Medium" },
      { title: "Payment readiness", detail: "Keep UPI/Card confirmation flow visible to staff.", priority: "Low" }
    ]
  };
}

function normalizeBriefing(briefing: OpsBriefing, fallback: OpsBriefing): OpsBriefing {
  return {
    briefing: String(briefing.briefing || fallback.briefing).slice(0, 220),
    staffing: String(briefing.staffing || fallback.staffing).slice(0, 140),
    prepList: Array.isArray(briefing.prepList) && briefing.prepList.length
      ? briefing.prepList.map((item) => String(item).slice(0, 120)).slice(0, 4)
      : fallback.prepList,
    revenueWatch: String(briefing.revenueWatch || fallback.revenueWatch).slice(0, 140),
    actions: Array.isArray(briefing.actions) && briefing.actions.length
      ? briefing.actions.slice(0, 4).map((action) => ({
          title: String(action.title || "Action").slice(0, 60),
          detail: String(action.detail || "").slice(0, 140),
          priority: ["High", "Medium", "Low"].includes(action.priority) ? action.priority : "Medium"
        }))
      : fallback.actions
  };
}
