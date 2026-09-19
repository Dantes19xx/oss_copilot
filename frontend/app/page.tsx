"use client";

import { FormEvent, useEffect, useState } from "react";
import { detectDefaultLang, Lang, LANDING, ONBOARDING, UI } from "./i18n";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const LANG_STORAGE_KEY = "oss-copilot-lang";

type InterruptPayload = {
  type?: string;
  pr?: string;
  draft_comment?: string;
  candidates?: string;
  question?: string;
  instructions?: string;
  security_warning?: string;
  error?: string;
};

type AgentResponse = {
  status: "interrupt" | "done";
  thread_id: string;
  payload?: InterruptPayload | null;
  summary?: string | null;
};

function candidateNumbers(text?: string): number[] {
  if (!text) return [];
  return text
    .split("\n")
    .map((line) => line.trim().match(/^(\d+)\./))
    .filter((m): m is RegExpMatchArray => m !== null)
    .map((m) => Number(m[1]));
}

function Dots() {
  return (
    <span className="loading-dots" aria-hidden="true">
      <span />
      <span />
      <span />
    </span>
  );
}

function WarningIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="banner-icon" aria-hidden="true">
      <path
        d="M8 1.5 15 14H1L8 1.5Z"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinejoin="round"
      />
      <path d="M8 6v3.2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      <circle cx="8" cy="11.6" r="0.9" fill="currentColor" />
    </svg>
  );
}

function OnboardingModal({ lang, onClose }: { lang: Lang; onClose: () => void }) {
  const content = ONBOARDING[lang];

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={content.title} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{content.title}</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <p className="modal-intro">{content.intro}</p>
        <div className="onboarding-list">
          {content.sections.map((section, i) => (
            <div className="onboarding-item" key={section.title}>
              <span className="onboarding-index">{i + 1}</span>
              <div>
                <h3>{section.title}</h3>
                <p>{section.body}</p>
              </div>
            </div>
          ))}
        </div>
        <button type="button" className="btn btn-primary" onClick={onClose}>
          {content.closeLabel}
        </button>
      </div>
    </div>
  );
}

export default function Home() {
  const [lang, setLang] = useState<Lang>("en");
  const [showHelp, setShowHelp] = useState(false);
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState("");
  const [response, setResponse] = useState<AgentResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stored: string | null = null;
    try {
      stored = window.localStorage.getItem(LANG_STORAGE_KEY);
    } catch {
      // localStorage unavailable (private mode, etc.) — fall back to detection below
    }
    setLang(stored === "ru" || stored === "en" ? stored : detectDefaultLang());
  }, []);

  const ui = UI[lang];
  const landing = LANDING[lang];

  function chooseLang(next: Lang) {
    setLang(next);
    try {
      window.localStorage.setItem(LANG_STORAGE_KEY, next);
    } catch {
      // best-effort persistence only
    }
  }

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
    if (!message.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      setResponse(await post("/api/agent/start", { message, language: lang }));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function submitAnswer(value: string) {
    if (!response || loading) return;
    setLoading(true);
    setError(null);
    try {
      setResponse(await post("/api/agent/resume", { thread_id: response.thread_id, answer: value }));
      setAnswer("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  function handleResume(e: FormEvent) {
    e.preventDefault();
    if (!answer.trim()) return;
    submitAnswer(answer.trim());
  }

  function handleReset() {
    setResponse(null);
    setMessage("");
    setAnswer("");
    setError(null);
  }

  const payload = response?.payload;
  const kind = payload?.type;
  const candidates = kind === "repo_selection" ? candidateNumbers(payload?.candidates) : [];

  const kickerLabel =
    kind === "review_confirmation"
      ? ui.kickerReview
      : kind === "repo_selection"
        ? ui.kickerRepo
        : kind === "clarifying_question"
          ? ui.kickerClarify
          : ui.kickerWorking;

  return (
    <div className="page">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">$</span>OSS Copilot
        </div>
        <div className="topbar-right">
          <button
            type="button"
            className="icon-btn"
            onClick={() => setShowHelp(true)}
            aria-label={ui.helpLabel}
            title={ui.helpLabel}
          >
            ?
          </button>
          {!response ? (
            <div className="lang-toggle" role="group" aria-label="Language">
              <button type="button" data-active={lang === "ru"} onClick={() => chooseLang("ru")}>
                RU
              </button>
              <button type="button" data-active={lang === "en"} onClick={() => chooseLang("en")}>
                EN
              </button>
            </div>
          ) : (
            <span className="lang-pill">{lang.toUpperCase()}</span>
          )}
        </div>
      </header>

      {showHelp && <OnboardingModal lang={lang} onClose={() => setShowHelp(false)} />}

      <main>
        {!response && (
          <section className="intro">
            <h1>{ui.headline}</h1>
            <p className="subtitle">{ui.subtitle}</p>
            <form className="composer" onSubmit={handleStart}>
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder={ui.placeholder}
                rows={4}
                required
              />
              <div className="composer-footer">
                <div className="examples">
                  <span className="examples-label">{ui.examplesLabel}</span>
                  <button type="button" className="chip" onClick={() => setMessage(ui.example1)}>
                    {ui.example1Label}
                  </button>
                  <button type="button" className="chip" onClick={() => setMessage(ui.example2)}>
                    {ui.example2Label}
                  </button>
                </div>
                <button type="submit" className="btn btn-primary" disabled={loading || !message.trim()}>
                  {loading ? (
                    <>
                      {ui.working}
                      <Dots />
                    </>
                  ) : (
                    ui.submit
                  )}
                </button>
              </div>
            </form>

            <div className="landing-section">
              <p className="section-label">{landing.modesLabel}</p>
              <div className="mode-cards">
                {landing.modes.map((mode) => (
                  <div className="mode-card" data-accent={mode.accent} key={mode.title}>
                    <h3>{mode.title}</h3>
                    <p>{mode.body}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="landing-section">
              <p className="section-label">{landing.stepsLabel}</p>
              <div className="steps">
                {landing.steps.map((step, i) => (
                  <div className="step" key={step.title}>
                    <span className="step-index">{i + 1}</span>
                    <h3>{step.title}</h3>
                    <p>{step.body}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {response?.status === "interrupt" && (
          <section className="card" data-kind={kind}>
            <span className="card-kicker">
              <span className="card-kicker-dot" />
              {kickerLabel}
            </span>

            {payload?.security_warning && (
              <div className="banner banner-warning">
                <WarningIcon />
                <span>{payload.security_warning}</span>
              </div>
            )}
            {payload?.error && (
              <div className="banner banner-error">
                <WarningIcon />
                <span>{payload.error}</span>
              </div>
            )}

            {payload?.pr && <p className="meta">{payload.pr}</p>}

            {kind === "clarifying_question" ? (
              <p className="question">{payload?.question}</p>
            ) : (
              <pre className="draft">{payload?.draft_comment ?? payload?.candidates}</pre>
            )}

            {kind === "review_confirmation" && (
              <div className="quick-actions">
                <button className="btn btn-primary" disabled={loading} onClick={() => submitAnswer("approve")}>
                  {ui.approve}
                </button>
                <button className="btn btn-ghost" disabled={loading} onClick={() => submitAnswer("merge")}>
                  {ui.merge}
                </button>
                <button className="btn btn-danger" disabled={loading} onClick={() => submitAnswer("reject")}>
                  {ui.reject}
                </button>
              </div>
            )}

            {kind === "repo_selection" && candidates.length > 0 && (
              <div className="chip-row">
                {candidates.map((n) => (
                  <button key={n} className="chip" disabled={loading} onClick={() => submitAnswer(String(n))}>
                    #{n}
                  </button>
                ))}
                <button className="chip" disabled={loading} onClick={() => submitAnswer("skip")}>
                  {ui.skip}
                </button>
              </div>
            )}

            {kind === "clarifying_question" && (
              <div className="quick-actions">
                <button className="btn btn-ghost" disabled={loading} onClick={() => submitAnswer("skip")}>
                  {ui.skip}
                </button>
              </div>
            )}

            <p className="instructions">{payload?.instructions}</p>

            <form className="inline-form" onSubmit={handleResume}>
              <input
                type="text"
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder={ui.answerPlaceholder}
                required
              />
              <button type="submit" className="btn btn-ghost" disabled={loading || !answer.trim()}>
                {loading ? <Dots /> : ui.send}
              </button>
            </form>
          </section>
        )}

        {response?.status === "done" && (
          <section className="card result-card">
            <span className="card-kicker">
              <span className="card-kicker-dot" />
              {ui.kickerResult}
            </span>
            <pre className="draft">{response.summary}</pre>
            <button className="btn btn-ghost" onClick={handleReset}>
              {ui.newRequest}
            </button>
          </section>
        )}

        {error && (
          <div className="banner banner-error">
            <WarningIcon />
            <span>{error}</span>
          </div>
        )}
      </main>
    </div>
  );
}
