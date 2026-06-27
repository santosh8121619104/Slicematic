import { NextResponse } from "next/server";
import { getSupabaseServerClient, hasSupabaseAdminEnv } from "./supabase";

export async function requireAdminSession(request: Request) {
  if (!hasSupabaseAdminEnv()) return null;

  const token = request.headers.get("authorization")?.replace(/^Bearer\s+/i, "");
  if (!token) {
    return NextResponse.json({ error: "Admin authentication required." }, { status: 401 });
  }

  const supabase = getSupabaseServerClient();
  if (!supabase) {
    return NextResponse.json({ error: "Supabase admin client is not configured." }, { status: 503 });
  }

  const { data, error } = await supabase.auth.getUser(token);
  if (error || !data.user) {
    return NextResponse.json({ error: "Invalid or expired admin session." }, { status: 401 });
  }

  return null;
}
