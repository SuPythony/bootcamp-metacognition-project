// Typed fetch wrapper. Base URL from VITE_API_URL; toggle to mock with VITE_USE_MOCK.

import type {
  ChatRequest,
  ChatResponse,
  PersonaCreateResponse,
  SessionNewRequest,
  SessionNewResponse,
  SpecializationManifestEntry,
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

export const api = {
  sessionNew(body: SessionNewRequest): Promise<SessionNewResponse> {
    return USE_MOCK ? mock.sessionNew(body) : post("/session/new", body);
  },
  chat(body: ChatRequest): Promise<ChatResponse> {
    return USE_MOCK ? mock.chat(body) : post("/chat", body);
  },
  personaCreate(username: string): Promise<PersonaCreateResponse> {
    return USE_MOCK
      ? mock.personaCreate(username)
      : post("/persona/create", { username });
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
