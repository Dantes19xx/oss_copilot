"use client";

import { FormEvent, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type InterruptPayload = {
  type?: string;
  pr?: string;
  draft_comment?: string;
  candidates?: string;
  instructions?: string;
  security_warning?: string;
};

type AgentResponse = {
  status: "interrupt" | "done";
  thread_id: string;
  payload?: InterruptPayload | null;
  summary?: string | null;
};

export default function Home() {
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState("");
  const [response, setResponse] = useState<AgentResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function post(path: string, body: unknown): Promise<AgentResponse> {
    const res = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      throw new Error(`Request failed (${res.status})`);
    }
    return res.json();
  }

  async function handleStart(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      setResponse(await post("/api/agent/start", { message }));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleResume(e: FormEvent) {
    e.preventDefault();
    if (!response) return;
    setLoading(true);
    setError(null);
    try {
      setResponse(await post("/api/agent/resume", { thread_id: response.thread_id, answer }));
      setAnswer("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    setResponse(null);
    setMessage("");
    setAnswer("");
    setError(null);
  }

  const payload = response?.payload;

  return (
    <main>
      <h1>OSS Copilot</h1>
      <p className="subtitle">
        Ask it to review a GitHub pull request, or describe your skills/interests to find one to
        contribute to.
      </p>

      {!response && (
        <form onSubmit={handleStart}>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="e.g. Review the pull request https://github.com/owner/repo/pull/123"
            rows={4}
            required
          />
          <button type="submit" disabled={loading || !message.trim()}>
            {loading ? "Working…" : "Submit"}
          </button>
        </form>
      )}

      {response?.status === "interrupt" && (
        <section className="interrupt">
          {payload?.security_warning && <div className="warning">⚠️ {payload.security_warning}</div>}
          {payload?.pr && <p className="meta">PR: {payload.pr}</p>}
          <pre>{payload?.draft_comment ?? payload?.candidates}</pre>
          <p className="instructions">{payload?.instructions}</p>
          <form onSubmit={handleResume}>
            <input
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="approve / reject / a number…"
              required
            />
            <button type="submit" disabled={loading || !answer.trim()}>
              {loading ? "Working…" : "Send"}
            </button>
          </form>
        </section>
      )}

      {response?.status === "done" && (
        <section className="result">
          <pre>{response.summary}</pre>
          <button onClick={handleReset}>New request</button>
        </section>
      )}

      {error && <p className="error">{error}</p>}
    </main>
  );
}
