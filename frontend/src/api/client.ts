import type { Health, Source, Trace, Turn } from "../types";

export type ChatRequest = {
  question: string;
  history: Turn[];
  forced_collections?: string[] | null;
  mode?: "answer" | "generate";
  temperature?: number;
};

export async function fetchHealth(): Promise<Health> {
  const r = await fetch("/api/health");
  if (!r.ok) throw new Error(`health ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function explore(req: ChatRequest): Promise<Trace> {
  const r = await fetch("/api/explore", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req)
  });
  if (!r.ok) throw new Error(`explore ${r.status}: ${await r.text()}`);
  return r.json();
}

export type ChatStreamHandlers = {
  onMeta?: (meta: { rewritten: string; router: { collections: string[]; reason: string }; timings_ms: Record<string, number> }) => void;
  onSources?: (sources: Source[]) => void;
  onToken?: (text: string) => void;
  onDone?: () => void;
  onError?: (err: string) => void;
};

export async function chatStream(
  req: ChatRequest,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal
) {
  const r = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal
  });
  if (!r.ok || !r.body) {
    throw new Error(`chat ${r.status}: ${await r.text()}`);
  }

  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const block of events) {
      const lines = block.split("\n");
      let event = "message";
      const dataLines: string[] = [];

      for (const line of lines) {
        if (line.startsWith("event: ")) event = line.slice(7).trim();
        if (line.startsWith("data: ")) dataLines.push(line.slice(6));
      }

      const data = dataLines.join("\n");
      try {
        if (event === "meta") handlers.onMeta?.(JSON.parse(data));
        if (event === "sources") handlers.onSources?.(JSON.parse(data));
        if (event === "token") handlers.onToken?.(data);
        if (event === "done") handlers.onDone?.();
        if (event === "error") handlers.onError?.(data);
      } catch (e) {
        handlers.onError?.(String(e));
      }
    }
  }
}

export async function runIngest(name: string, recreate = false) {
  const r = await fetch(`/api/ingest/${name}?recreate=${recreate}`, { method: "POST" });
  if (!r.ok) throw new Error(`ingest ${name} ${r.status}: ${await r.text()}`);
  return r.json();
}
