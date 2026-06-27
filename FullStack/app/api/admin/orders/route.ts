import { NextResponse } from "next/server";
import { loadAdminSummary } from "../../../../lib/data-service";
import { requireAdminSession } from "../../../../lib/admin-auth";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const authError = await requireAdminSession(request);
  if (authError) return authError;

  const url = new URL(request.url);
  const format = url.searchParams.get("format");
  const summary = await loadAdminSummary();

  if (format === "csv") {
    const header = "order_id,created_at,customer_name,phone,payment_mode,status,subtotal,discount,gst,final_total";
    const rows = summary.recentOrders.map((order) => [
      order.id,
      order.createdAt,
      order.customerName,
      order.phone,
      order.paymentMode,
      order.status,
      order.subtotal,
      order.discount,
      order.gst,
      order.finalTotal
    ].map((value) => `"${String(value).replace(/"/g, '""')}"`).join(","));
    return new Response([header, ...rows].join("\n"), {
      headers: {
        "content-type": "text/csv; charset=utf-8",
        "content-disposition": "attachment; filename=slicematic-orders.csv"
      }
    });
  }

  return NextResponse.json(summary);
}
