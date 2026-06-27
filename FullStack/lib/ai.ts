type OpenRouterInput<T> = {
  system: string;
  user: unknown;
  fallback: T;
  temperature?: number;
};

export async function callOpenRouterJson<T>({ system, user, fallback, temperature = 0.25 }: OpenRouterInput<T>): Promise<{ data: T; source: "openrouter" | "fallback" }> {
  if (!process.env.OPENROUTER_API_KEY) {
    return { data: fallback, source: "fallback" };
  }

  try {
    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${process.env.OPENROUTER_API_KEY}`,
        "http-referer": "https://slicematic.vercel.app",
        "x-title": "SliceMatic PizzaFlow"
      },
      body: JSON.stringify({
        model: process.env.OPENROUTER_MODEL ?? "openai/gpt-oss-20b",
        temperature,
        response_format: { type: "json_object" },
        messages: [
          { role: "system", content: system },
          { role: "user", content: JSON.stringify(user) }
        ]
      })
    });

    if (!response.ok) throw new Error("OpenRouter request failed");
    const payload = await response.json();
    const content = payload.choices?.[0]?.message?.content ?? "{}";
    return { data: JSON.parse(stripJsonFence(content)) as T, source: "openrouter" };
  } catch {
    return { data: fallback, source: "fallback" };
  }
}

export function stripJsonFence(content: string) {
  return String(content).trim().replace(/^```(?:json)?/i, "").replace(/```$/i, "").trim();
}
