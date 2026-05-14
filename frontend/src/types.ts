export type Turn = { role: "user" | "assistant"; content: string };

export type CollectionName =
  | "selenium_code"
  | "playwright_code"
  | "vwo_testcases"
  | "vwo_docs"
  | "vwo_bugs";

export type Source = {
  id: number;
  chunk_id: string;
  collection: CollectionName | string;
  source: string;
  rerank_score?: number;
  preview: string;
  payload: Record<string, unknown>;
};

export type Hit = {
  chunk_id: string;
  score?: number;
  rrf_score?: number;
  collection?: string;
  payload: Record<string, unknown>;
};

export type RouterDecision = {
  collections: string[];
  reason: string;
};

export type Trace = {
  query: { original: string; history: Turn[]; rewritten: string };
  router: RouterDecision;
  selected_collections: string[];
  per_collection: Record<string, {
    dense_hits: Hit[];
    sparse_hits: Hit[];
    fused: Hit[];
  }>;
  fused_topk: Hit[];
  rerank: (Hit & { rerank_score?: number; rerank_rank?: number; fused_rank?: number })[];
  context_blocks: {
    id: number;
    chunk_id: string;
    collection: string;
    source: string;
    text: string;
    rerank_score?: number;
    rrf_score?: number;
    payload: Record<string, unknown>;
  }[];
  timings_ms: Record<string, number>;
  llm?: {
    model: string;
    temperature: number;
    system: string;
    user: string;
    usage: Record<string, number>;
  };
  answer?: { text: string };
};

export type Health = {
  ok: boolean;
  status?: string;
  groq_model: string;
  embed_model: string;
  rerank_model: string;
  qdrant: string;
  collections: Record<string, number>;
  counts?: Record<string, number>;
  data_paths: Record<string, string>;
};
