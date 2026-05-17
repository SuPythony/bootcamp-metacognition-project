// Typed fetch wrapper. Base URL from VITE_API_URL; toggle to mock with VITE_USE_MOCK.

import type {
  ChatRequest,
  ChatResponse,
  PersonaCreateResponse,
  SessionNewRequest,
  SessionNewResponse,
  SpecializationManifestEntry,
  StreamCallbacks,
  ThinkingTrace,
} from "./types";
import * as mock from "./mock";

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function post<TIn, TOut>(path: string, body: TIn): Promise<TOut> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `${res.status}`;
    try { detail = (await res.json()).detail ?? detail; } catch { /* ignore */ }
    throw new Error(`${path} → ${detail}`);
  }
  return res.json() as Promise<TOut>;
}

async function get<TOut>(path: string): Promise<TOut> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    let detail = `${res.status}`;
    try { detail = (await res.json()).detail ?? detail; } catch { /* ignore */ }
    throw new Error(`${path} → ${detail}`);
  }
  return res.json() as Promise<TOut>;
}

async function _chatStream(body: ChatRequest, callbacks: StreamCallbacks): Promise<void> {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "text/event-stream",
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    let detail = `${res.status}`;
    try { detail = (await res.json()).detail ?? detail; } catch { /* ignore */ }
    callbacks.onError(detail);
    return;
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let currentEvent = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    // Normalise CRLF → LF so servers behind proxies that rewrite line endings
    // still parse correctly. Split on \n only after normalisation.
    const lines = buf.replace(/\r\n/g, "\n").split("\n");
    buf = lines.pop()!; // keep last incomplete line
    for (const rawLine of lines) {
      const line = rawLine.replace(/\r$/, "");
      if (line.startsWith("event: ")) {
        currentEvent = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        const payload = line.slice(6);
        let parsed: unknown;
        try {
          parsed = JSON.parse(payload);
        } catch (err) {
          // Surface, don't swallow — silent drops make SSE bugs invisible.
          // eslint-disable-next-line no-console
          console.warn("SSE: ignored malformed data line", { payload, err });
          currentEvent = "";
          continue;
        }
        const event = currentEvent || "message";
        const obj = parsed as Record<string, unknown>;
        if (event === "token") callbacks.onToken((obj.delta as string) ?? "");
        else if (event === "state") callbacks.onState(parsed as ChatResponse);
        else if (event === "error") callbacks.onError((obj.message as string) ?? "Unknown error");
        currentEvent = "";
      }
    }
  }
}

export const api = {
  sessionNew(body: SessionNewRequest): Promise<SessionNewResponse> {
    return USE_MOCK ? mock.sessionNew(body) : post("/session/new", body);
  },
  chat(body: ChatRequest): Promise<ChatResponse> {
    return USE_MOCK ? mock.chat(body) : post("/chat", body);
  },
  chatStream(body: ChatRequest, callbacks: StreamCallbacks): Promise<void> {
    return USE_MOCK ? mock.chatStream(body, callbacks) : _chatStream(body, callbacks);
  },
  personaCreate(username: string, opts?: { confirm?: boolean }): Promise<PersonaCreateResponse> {
    return USE_MOCK
      ? mock.personaCreate(username)
      : post("/persona/create", { username, confirm: opts?.confirm ?? false });
  },
  personaReset(username: string): Promise<{ status: "reset" }> {
    return USE_MOCK
      ? Promise.resolve({ status: "reset" as const })
      : post("/persona/reset", { username });
  },
  thinkingTrace(sessionId: string): Promise<ThinkingTrace> {
    return USE_MOCK
      ? mock.thinkingTrace(sessionId)
      : get(`/session/${sessionId}/thinking-trace`);
  },
  specializations(): Promise<SpecializationManifestEntry[]> {
    return USE_MOCK ? mock.specializations() : get("/specializations");
  },
};
