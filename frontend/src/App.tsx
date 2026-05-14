import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import {
  Activity,
  Bug,
  ChevronRight,
  ClipboardList,
  Code2,
  Database,
  FileText,
  Gauge,
  Layers,
  Loader2,
  MessageSquare,
  Play,
  RefreshCw,
  Search,
  Send,
  Sparkles,
  StopCircle,
  Trash2,
} from "lucide-react";
import { chatStream, explore, fetchHealth, runIngest } from "./api/client";
import type { CollectionName, Health, Source, Trace, Turn } from "./types";

type View = "chat" | "explorer" | "status";
type Mode = "answer" | "generate";
type Meta = { rewritten: string; router: { collections: string[]; reason: string }; timings_ms: Record<string, number> };
type DisplayTurn = Turn & { meta?: Meta; sources?: Source[]; streaming?: boolean };

const COLLECTIONS: { id: CollectionName; label: string; short: string }[] = [
  { id: "selenium_code", label: "Selenium", short: "Java" },
  { id: "playwright_code", label: "Playwright", short: "TS" },
  { id: "vwo_testcases", label: "Test Cases", short: "TC" },
  { id: "vwo_docs", label: "PRD Docs", short: "PDF" },
  { id: "vwo_bugs", label: "Jira Bugs", short: "Jira" },
];

const EXAMPLES = [
  "Show the BasePage waitForElement implementation",
  "How is the login fixture set up in Playwright?",
  "List P0 Blocker test cases for the Admin module",
  "What does the PRD say about login dashboard auth flow?",
  "Show open bugs related to login failures",
];

export default function App() {
  const [view, setView] = useState<View>("chat");
  const [turns, setTurns] = useState<DisplayTurn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [forced, setForced] = useState<string[] | null>(null);
  const [mode, setMode] = useState<Mode>("answer");
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [runningIngest, setRunningIngest] = useState<string | null>(null);
  const [trace, setTrace] = useState<Trace | null>(null);
  const [traceQuery, setTraceQuery] = useState(EXAMPLES[2]);
  const [traceBusy, setTraceBusy] = useState(false);
  const [traceError, setTraceError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const counts = health?.collections ?? health?.counts ?? {};
  const forcedForRequest = forced && forced.length > 0 ? forced : null;
  const lastAssistant = [...turns].reverse().find((t) => t.role === "assistant" && t.sources);
  const traceSources = useMemo<Source[]>(
    () =>
      trace?.context_blocks.map((block) => ({
        id: block.id,
        chunk_id: block.chunk_id,
        collection: block.collection,
        source: block.source,
        rerank_score: block.rerank_score,
        preview: block.text.slice(0, 500),
        payload: block.payload,
      })) ?? [],
    [trace],
  );
  const activeSources = view === "explorer" ? traceSources : lastAssistant?.sources ?? [];

  useEffect(() => {
    void refreshHealth();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  async function refreshHealth() {
    try {
      setHealth(await fetchHealth());
      setHealthError(null);
    } catch (e) {
      setHealthError(messageOf(e));
    }
  }

  function updateLastAssistant(patch: Partial<DisplayTurn>) {
    setTurns((prev) => {
      const idx = prev.length - 1;
      if (idx < 0 || prev[idx].role !== "assistant") return prev;
      const next = prev.slice();
      next[idx] = { ...next[idx], ...patch };
      return next;
    });
  }

  function appendLastAssistant(piece: string) {
    setTurns((prev) => {
      const idx = prev.length - 1;
      if (idx < 0 || prev[idx].role !== "assistant") return prev;
      const next = prev.slice();
      next[idx] = { ...next[idx], content: next[idx].content + piece };
      return next;
    });
  }

  async function sendChat(text = input.trim()) {
    const question = text.trim();
    if (!question || busy) return;
    setView("chat");
    setInput("");
    setBusy(true);

    const history = turns
      .filter((t) => !t.streaming)
      .map(({ role, content }) => ({ role, content }));

    setTurns((prev) => [
      ...prev,
      { role: "user", content: question },
      { role: "assistant", content: "", streaming: true },
    ]);

    const ac = new AbortController();
    abortRef.current = ac;

    try {
      await chatStream(
        { question, history, forced_collections: forcedForRequest, mode },
        {
          onMeta: (meta) => updateLastAssistant({ meta }),
          onSources: (sources) => updateLastAssistant({ sources }),
          onToken: (piece) => appendLastAssistant(piece),
          onDone: () => updateLastAssistant({ streaming: false }),
          onError: (err) => appendLastAssistant(`\n\n${err}`),
        },
        ac.signal,
      );
    } catch (e) {
      if ((e as DOMException).name !== "AbortError") {
        appendLastAssistant(`\n\n${messageOf(e)}`);
      }
    } finally {
      updateLastAssistant({ streaming: false });
      setBusy(false);
      abortRef.current = null;
    }
  }

  function stopChat() {
    abortRef.current?.abort();
    updateLastAssistant({ streaming: false });
    setBusy(false);
  }

  async function runTrace() {
    const question = traceQuery.trim();
    if (!question || traceBusy) return;
    setTraceBusy(true);
    setTraceError(null);
    setTrace(null);
    try {
      setTrace(await explore({ question, history: [], forced_collections: forcedForRequest, mode }));
    } catch (e) {
      setTraceError(messageOf(e));
    } finally {
      setTraceBusy(false);
    }
  }

  async function triggerIngest(name: string, recreate = false) {
    setRunningIngest(`${name}:${recreate ? "recreate" : "run"}`);
    try {
      await runIngest(name, recreate);
      await refreshHealth();
    } catch (e) {
      setHealthError(messageOf(e));
    } finally {
      setRunningIngest(null);
    }
  }

  return (
    <div className="h-screen overflow-hidden bg-background text-text-primary">
      <div className="h-full grid grid-cols-1 lg:grid-cols-[280px_minmax(0,1fr)_360px]">
        <aside className="border-r border-border bg-surface/95 p-4 overflow-y-auto">
          <Brand />
          <nav className="mt-6 grid gap-2">
            <NavButton active={view === "chat"} icon={<MessageSquare size={17} />} label="Chat" onClick={() => setView("chat")} />
            <NavButton active={view === "explorer"} icon={<Search size={17} />} label="Explorer" onClick={() => setView("explorer")} />
            <NavButton active={view === "status"} icon={<Activity size={17} />} label="Status" onClick={() => setView("status")} />
          </nav>

          <div className="mt-8">
            <SectionLabel>Sources</SectionLabel>
            <SourceFilter forced={forced} onChange={setForced} counts={counts} />
          </div>

          <div className="mt-8">
            <SectionLabel>Mode</SectionLabel>
            <div className="grid grid-cols-2 gap-2">
              <button className={modeButton(mode === "answer")} onClick={() => setMode("answer")}>Answer</button>
              <button className={modeButton(mode === "generate")} onClick={() => setMode("generate")}>Generate</button>
            </div>
          </div>

          <div className="mt-8">
            <SectionLabel>Index</SectionLabel>
            <div className="grid gap-2">
              <button className="tool-button" onClick={() => void refreshHealth()}>
                <RefreshCw size={16} /> Refresh
              </button>
              <button className="tool-button" onClick={() => void triggerIngest("all")}>
                <Database size={16} /> Run all
              </button>
            </div>
            {runningIngest && <p className="mt-2 text-xs text-amber-300">Running {runningIngest}</p>}
          </div>
        </aside>

        <main className="min-h-0 overflow-hidden bg-[#0d1117]">
          {view === "chat" && (
            <ChatView
              turns={turns}
              input={input}
              busy={busy}
              onInput={setInput}
              onSend={() => void sendChat()}
              onStop={stopChat}
              onClear={() => setTurns([])}
              onExample={(q) => void sendChat(q)}
              endRef={chatEndRef}
            />
          )}
          {view === "explorer" && (
            <ExplorerView
              query={traceQuery}
              onQuery={setTraceQuery}
              busy={traceBusy}
              trace={trace}
              error={traceError}
              onRun={() => void runTrace()}
            />
          )}
          {view === "status" && (
            <StatusView
              health={health}
              error={healthError}
              running={runningIngest}
              onRefresh={() => void refreshHealth()}
              onIngest={(name, recreate) => void triggerIngest(name, recreate)}
            />
          )}
        </main>

        <aside className="border-l border-border bg-surface/90 p-4 overflow-y-auto">
          <SourceInspector sources={activeSources} meta={lastAssistant?.meta} trace={view === "explorer" ? trace : null} />
        </aside>
      </div>
    </div>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-3">
      <div className="h-10 w-10 rounded-lg bg-accent text-slate-950 grid place-items-center font-black">QA</div>
      <div>
        <h1 className="font-semibold leading-tight">QA Copilot</h1>
        <p className="text-xs text-text-muted">multi-source RAG</p>
      </div>
    </div>
  );
}

function ChatView({
  turns,
  input,
  busy,
  onInput,
  onSend,
  onStop,
  onClear,
  onExample,
  endRef,
}: {
  turns: DisplayTurn[];
  input: string;
  busy: boolean;
  onInput: (value: string) => void;
  onSend: () => void;
  onStop: () => void;
  onClear: () => void;
  onExample: (query: string) => void;
  endRef: React.RefObject<HTMLDivElement>;
}) {
  return (
    <div className="h-full flex flex-col">
      <div className="h-14 border-b border-border px-5 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-text-secondary">
          <Layers size={16} className="text-accent" />
          <span>Chat</span>
        </div>
        <button className="icon-text-button" onClick={onClear} disabled={turns.length === 0}>
          <Trash2 size={16} /> Clear
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        {turns.length === 0 && <Welcome onPick={onExample} />}
        {turns.map((turn, idx) => <MessageBubble key={idx} turn={turn} />)}
        <div ref={endRef} />
      </div>

      <div className="border-t border-border p-4 bg-background/70">
        <div className="relative">
          <textarea
            className="w-full min-h-24 resize-none rounded-lg border border-border bg-surface p-4 pr-16 text-sm outline-none focus:border-accent"
            value={input}
            onChange={(e) => onInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSend();
              }
            }}
            placeholder="Ask about login, fixtures, test cases, PRDs, bugs..."
            disabled={busy}
          />
          {busy ? (
            <button className="send-button bg-rose-500 hover:bg-rose-400" onClick={onStop} title="Stop">
              <StopCircle size={20} />
            </button>
          ) : (
            <button className="send-button" onClick={onSend} disabled={!input.trim()} title="Send">
              <Send size={20} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function Welcome({ onPick }: { onPick: (query: string) => void }) {
  return (
    <div className="mx-auto max-w-2xl py-14">
      <div className="mb-5 flex items-center gap-2 text-accent">
        <Sparkles size={18} />
        <span className="text-sm font-semibold">Ready</span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {EXAMPLES.map((query) => (
          <button key={query} className="example-button" onClick={() => onPick(query)}>
            {query}
          </button>
        ))}
      </div>
    </div>
  );
}

function MessageBubble({ turn }: { turn: DisplayTurn }) {
  if (turn.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[82%] rounded-lg bg-accent px-4 py-3 text-sm font-medium text-slate-950">
          {turn.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[92%] rounded-lg border border-border bg-surface px-4 py-3">
        {turn.meta && (
          <div className="mb-3 flex flex-wrap items-center gap-2 text-[11px] text-text-muted">
            {turn.meta.router.collections.map((collection) => (
              <span key={collection} className="source-chip">{collection}</span>
            ))}
            {turn.meta.timings_ms.search_ms != null && <span>search {turn.meta.timings_ms.search_ms}ms</span>}
            {turn.meta.timings_ms.rerank_ms != null && <span>rerank {turn.meta.timings_ms.rerank_ms}ms</span>}
          </div>
        )}
        {turn.content ? (
          <Markdown text={turn.content} />
        ) : (
          <div className="flex items-center gap-2 text-sm text-text-muted">
            <Loader2 className="animate-spin" size={16} /> Retrieving
          </div>
        )}
      </div>
    </div>
  );
}

function ExplorerView({
  query,
  onQuery,
  busy,
  trace,
  error,
  onRun,
}: {
  query: string;
  onQuery: (value: string) => void;
  busy: boolean;
  trace: Trace | null;
  error: string | null;
  onRun: () => void;
}) {
  return (
    <div className="h-full overflow-y-auto p-5">
      <div className="mx-auto max-w-5xl space-y-4">
        <div className="flex items-center gap-2 text-sm text-text-secondary">
          <Search size={16} className="text-accent" />
          <span>Explorer</span>
        </div>
        <div className="flex gap-2">
          <textarea
            className="flex-1 rounded-lg border border-border bg-surface p-3 text-sm outline-none focus:border-accent"
            rows={2}
            value={query}
            onChange={(e) => onQuery(e.target.value)}
          />
          <button className="primary-button self-stretch" onClick={onRun} disabled={busy || !query.trim()}>
            {busy ? <Loader2 className="animate-spin" size={16} /> : <Play size={16} />}
            Run
          </button>
        </div>
        {error && <div className="error-box">{error}</div>}
        {trace && <TraceView trace={trace} />}
      </div>
    </div>
  );
}

function TraceView({ trace }: { trace: Trace }) {
  return (
    <div className="space-y-3">
      <TraceStage title="Query" open>
        <KV label="Original" value={trace.query.original} />
        <KV label="Rewritten" value={trace.query.rewritten} />
      </TraceStage>

      <TraceStage title="Router" open>
        <div className="flex flex-wrap gap-2">
          {trace.router.collections.map((collection) => <span key={collection} className="source-chip">{collection}</span>)}
        </div>
        <p className="mt-2 text-sm text-text-secondary">{trace.router.reason || "No router reason returned"}</p>
      </TraceStage>

      <TraceStage title="Collection Hits">
        <div className="grid gap-3">
          {Object.entries(trace.per_collection).map(([collection, hits]) => (
            <div key={collection} className="rounded-lg border border-border overflow-hidden">
              <div className="bg-background px-3 py-2 text-sm font-semibold">{collection}</div>
              <div className="grid grid-cols-1 md:grid-cols-3">
                <HitList title="Dense" hits={hits.dense_hits} scoreKey="score" />
                <HitList title="Sparse" hits={hits.sparse_hits} scoreKey="score" />
                <HitList title="Fused" hits={hits.fused} scoreKey="rrf_score" />
              </div>
            </div>
          ))}
        </div>
      </TraceStage>

      <TraceStage title="Rerank" open>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-text-muted">
              <tr>
                <th className="py-2 pr-3">Rank</th>
                <th className="py-2 pr-3">Collection</th>
                <th className="py-2 pr-3">Score</th>
                <th className="py-2 pr-3">Chunk</th>
              </tr>
            </thead>
            <tbody>
              {trace.rerank.map((hit, idx) => (
                <tr key={`${hit.chunk_id}-${idx}`} className="border-t border-border">
                  <td className="py-2 pr-3 font-mono">{hit.rerank_rank ?? idx + 1}</td>
                  <td className="py-2 pr-3">{hit.collection ?? String(hit.payload.collection ?? "")}</td>
                  <td className="py-2 pr-3 font-mono text-accent">{formatScore(hit.rerank_score)}</td>
                  <td className="py-2 pr-3 font-mono break-all">{hit.chunk_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </TraceStage>

      <TraceStage title="Context">
        <div className="grid gap-2">
          {trace.context_blocks.map((block) => (
            <details key={block.id} className="source-card">
              <summary className="cursor-pointer text-sm">
                [{block.id}] {block.source}
              </summary>
              <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap text-xs text-text-secondary">{block.text}</pre>
            </details>
          ))}
        </div>
      </TraceStage>

      {trace.answer && (
        <TraceStage title="Answer" open>
          <Markdown text={trace.answer.text} />
        </TraceStage>
      )}
    </div>
  );
}

function StatusView({
  health,
  error,
  running,
  onRefresh,
  onIngest,
}: {
  health: Health | null;
  error: string | null;
  running: string | null;
  onRefresh: () => void;
  onIngest: (name: string, recreate: boolean) => void;
}) {
  const counts = health?.collections ?? health?.counts ?? {};
  const pipelines = ["selenium", "playwright", "testcases", "pdfs", "jira", "all"];
  return (
    <div className="h-full overflow-y-auto p-5">
      <div className="mx-auto max-w-5xl space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-text-secondary">
            <Gauge size={16} className="text-accent" />
            <span>Status</span>
          </div>
          <button className="icon-text-button" onClick={onRefresh}>
            <RefreshCw size={16} /> Refresh
          </button>
        </div>

        {error && <div className="error-box">{error}</div>}

        {health && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <Metric label="Groq" value={health.groq_model} />
              <Metric label="Embed" value={health.embed_model} />
              <Metric label="Rerank" value={health.rerank_model} />
              <Metric label="Qdrant" value={health.qdrant} />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-3">
              {COLLECTIONS.map((item) => (
                <div className="source-card" key={item.id}>
                  <div className="flex items-center gap-2 text-text-secondary">
                    {collectionIcon(item.id)}
                    <span className="text-xs">{item.label}</span>
                  </div>
                  <div className="mt-2 text-3xl font-bold text-accent">{counts[item.id] ?? 0}</div>
                </div>
              ))}
            </div>

            <div className="grid gap-2">
              {pipelines.map((name) => (
                <div key={name} className="flex flex-wrap items-center justify-between gap-2 border-b border-border py-3">
                  <span className="font-mono text-sm">{name}</span>
                  <div className="flex gap-2">
                    <button className="small-button" onClick={() => onIngest(name, false)} disabled={!!running}>
                      {running === `${name}:run` ? "Running" : "Run"}
                    </button>
                    <button className="small-button danger" onClick={() => onIngest(name, true)} disabled={!!running}>
                      Recreate
                    </button>
                  </div>
                </div>
              ))}
            </div>

            <div className="rounded-lg border border-border bg-surface p-4">
              <div className="mb-3 text-sm font-semibold text-text-secondary">Paths</div>
              <div className="grid gap-2 text-xs">
                {Object.entries(health.data_paths).map(([key, value]) => (
                  <div key={key} className="grid grid-cols-[140px_minmax(0,1fr)] gap-3">
                    <span className="text-text-muted">{key}</span>
                    <span className="font-mono break-all">{value}</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function SourceInspector({ sources, meta, trace }: { sources: Source[]; meta?: Meta; trace: Trace | null }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-text-secondary">
        <Database size={16} className="text-accent" />
        Evidence
      </div>

      {meta && (
        <div className="rounded-lg border border-border bg-background p-3 text-xs text-text-secondary">
          <div className="mb-2 flex flex-wrap gap-1">
            {meta.router.collections.map((collection) => <span key={collection} className="source-chip">{collection}</span>)}
          </div>
          <div>{meta.rewritten}</div>
        </div>
      )}

      {trace && (
        <div className="rounded-lg border border-border bg-background p-3 text-xs text-text-secondary">
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(trace.timings_ms).map(([key, value]) => (
              <div key={key}>
                <span className="text-text-muted">{key}</span>
                <div className="font-mono text-accent">{value}ms</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid gap-3">
        {sources.length === 0 && (
          <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-text-muted">
            No sources
          </div>
        )}
        {sources.map((source) => <SourceCard key={`${source.id}-${source.chunk_id}`} source={source} />)}
      </div>
    </div>
  );
}

function SourceCard({ source }: { source: Source }) {
  return (
    <details className="source-card">
      <summary className="cursor-pointer list-none">
        <div className="flex items-start gap-3">
          <span className="grid h-6 w-6 shrink-0 place-items-center rounded-md bg-accent text-xs font-bold text-slate-950">
            {source.id}
          </span>
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">{source.source}</div>
            <div className="mt-1 flex flex-wrap gap-2 text-[11px] text-text-muted">
              <span>{source.collection}</span>
              {source.rerank_score != null && <span>{formatScore(source.rerank_score)}</span>}
            </div>
          </div>
        </div>
      </summary>
      <p className="mt-3 text-xs leading-relaxed text-text-secondary">{source.preview}</p>
      <Payload payload={source.payload} />
    </details>
  );
}

function Payload({ payload }: { payload: Record<string, unknown> }) {
  const entries = Object.entries(payload).filter(([key]) => key !== "text").slice(0, 8);
  if (entries.length === 0) return null;
  return (
    <div className="mt-3 grid gap-1 border-t border-border pt-3 text-[11px]">
      {entries.map(([key, value]) => (
        <div key={key} className="grid grid-cols-[90px_minmax(0,1fr)] gap-2">
          <span className="text-text-muted">{key}</span>
          <span className="truncate font-mono">{String(value)}</span>
        </div>
      ))}
    </div>
  );
}

function SourceFilter({ forced, onChange, counts }: { forced: string[] | null; onChange: (value: string[] | null) => void; counts: Record<string, number> }) {
  const auto = !forced || forced.length === 0;
  const toggle = (collection: string) => {
    const current = forced ?? [];
    const next = current.includes(collection)
      ? current.filter((item) => item !== collection)
      : [...current, collection];
    onChange(next.length > 0 ? next : null);
  };

  return (
    <div className="grid gap-2">
      <button className={filterButton(auto)} onClick={() => onChange(null)}>
        <span className="flex items-center gap-2"><Sparkles size={15} /> Auto router</span>
        <ChevronRight size={14} />
      </button>
      {COLLECTIONS.map((item) => {
        const active = !auto && forced?.includes(item.id);
        return (
          <button key={item.id} className={filterButton(!!active)} onClick={() => toggle(item.id)}>
            <span className="flex items-center gap-2">
              {collectionIcon(item.id)}
              {item.label}
            </span>
            <span className="font-mono text-xs">{counts[item.id] ?? 0}</span>
          </button>
        );
      })}
    </div>
  );
}

function NavButton({ active, icon, label, onClick }: { active: boolean; icon: ReactNode; label: string; onClick: () => void }) {
  return (
    <button className={`nav-button ${active ? "active" : ""}`} onClick={onClick}>
      {icon}
      <span>{label}</span>
    </button>
  );
}

function TraceStage({ title, children, open = false }: { title: string; children: ReactNode; open?: boolean }) {
  return (
    <details className="rounded-lg border border-border bg-surface" open={open}>
      <summary className="cursor-pointer px-4 py-3 text-sm font-semibold">{title}</summary>
      <div className="border-t border-border px-4 py-3">{children}</div>
    </details>
  );
}

function HitList({ title, hits, scoreKey }: { title: string; hits: { chunk_id: string; score?: number; rrf_score?: number }[]; scoreKey: "score" | "rrf_score" }) {
  return (
    <div className="border-t border-border p-3 md:border-t-0 md:border-r">
      <div className="mb-2 text-xs uppercase tracking-wide text-text-muted">{title}</div>
      <div className="space-y-1">
        {hits.slice(0, 7).map((hit, idx) => (
          <div key={`${hit.chunk_id}-${idx}`} className="grid grid-cols-[24px_52px_minmax(0,1fr)] gap-2 text-xs">
            <span className="font-mono text-text-muted">{idx + 1}</span>
            <span className="font-mono text-accent">{formatScore(hit[scoreKey])}</span>
            <span className="truncate font-mono">{hit.chunk_id}</span>
          </div>
        ))}
        {hits.length === 0 && <div className="text-xs text-text-muted">None</div>}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="source-card">
      <div className="text-xs text-text-muted">{label}</div>
      <div className="mt-2 truncate font-mono text-sm">{value}</div>
    </div>
  );
}

function KV({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[100px_minmax(0,1fr)] gap-3 py-1 text-sm">
      <span className="text-text-muted">{label}</span>
      <span className="font-mono break-all">{value}</span>
    </div>
  );
}

function Markdown({ text }: { text: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown>{text}</ReactMarkdown>
    </div>
  );
}

function SectionLabel({ children }: { children: ReactNode }) {
  return <div className="mb-3 text-[11px] font-bold uppercase tracking-[0.18em] text-text-muted">{children}</div>;
}

function collectionIcon(collection: string) {
  if (collection === "selenium_code") return <Code2 size={15} />;
  if (collection === "playwright_code") return <Code2 size={15} />;
  if (collection === "vwo_testcases") return <ClipboardList size={15} />;
  if (collection === "vwo_docs") return <FileText size={15} />;
  if (collection === "vwo_bugs") return <Bug size={15} />;
  return <Database size={15} />;
}

function modeButton(active: boolean) {
  return `rounded-lg border px-3 py-2 text-sm transition ${
    active ? "border-accent bg-accent text-slate-950" : "border-border bg-background text-text-secondary hover:text-text-primary"
  }`;
}

function filterButton(active: boolean) {
  return `flex items-center justify-between rounded-lg border px-3 py-2 text-sm transition ${
    active ? "border-accent bg-accent/10 text-accent" : "border-border bg-background text-text-secondary hover:text-text-primary"
  }`;
}

function formatScore(value: number | undefined) {
  return typeof value === "number" ? value.toFixed(3) : "-";
}

function messageOf(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}
