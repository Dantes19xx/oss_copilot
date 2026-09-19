"use client";

import { FormEvent, useEffect, useState } from "react";
import { detectDefaultLang, EVAL_STATS, Lang, LANDING, ONBOARDING, STYLE_GUIDE, UI } from "./i18n";

const SHOW_EVAL_STATS = process.env.NEXT_PUBLIC_SHOW_EVAL_STATS === "true";
const EVALS_URL = "https://github.com/Dantes19xx/oss_copilot/blob/main/EVALS.md";

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

type StyleGuideResult = { repo: string; source: string; chunks: number };

function StyleGuideModal({ lang, onClose }: { lang: Lang; onClose: () => void }) {
  const content = STYLE_GUIDE[lang];
  const [owner, setOwner] = useState("");
  const [repo, setRepo] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<StyleGuideResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!file || !owner.trim() || !repo.trim() || uploading) return;
    setUploading(true);
    setError(null);
    setResult(null);
    try {
      const formData = new FormData();
      formData.append("owner", owner.trim());
      formData.append("repo", repo.trim());
      formData.append("file", file);
      const res = await fetch(`${API_URL}/api/style-guide/upload`, { method: "POST", body: formData });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error((body && body.detail) || `Request failed (${res.status})`);
      }
      setResult(body as StyleGuideResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setUploading(false);
    }
  }

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

        <form className="upload-form" onSubmit={handleSubmit}>
          <div className="upload-row">
            <div className="field">
              <label htmlFor="sg-owner">{content.ownerLabel}</label>
              <input
                id="sg-owner"
                type="text"
                value={owner}
                onChange={(e) => setOwner(e.target.value)}
                placeholder="owner"
                required
              />
            </div>
            <div className="field">
              <label htmlFor="sg-repo">{content.repoLabel}</label>
              <input
                id="sg-repo"
                type="text"
                value={repo}
                onChange={(e) => setRepo(e.target.value)}
                placeholder="repo"
                required
              />
            </div>
          </div>
          <div className="field">
            <label htmlFor="sg-file">{content.fileLabel}</label>
            <input
              id="sg-file"
              type="file"
              accept=".pdf,.docx"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              required
            />
          </div>

          {result && (
            <div className="banner banner-success">
              <span>
                {content.successPrefix} {result.chunks} {content.successMiddle} &quot;{result.source}&quot; →{" "}
                {result.repo}.
              </span>
            </div>
          )}
          {error && (
            <div className="banner banner-error">
              <WarningIcon />
              <span>
                {content.errorPrefix}
                {error}
              </span>
            </div>
          )}

          <button
            type="submit"
            className="btn btn-primary"
            disabled={uploading || !file || !owner.trim() || !repo.trim()}
          >
            {uploading ? (
              <>
                {content.uploading}
                <Dots />
              </>
            ) : (
              content.uploadButton
            )}
          </button>
        </form>
      </div>
    </div>
  );
}

export default function Home() {
  const [lang, setLang] = useState<Lang>("en");
  const [showHelp, setShowHelp] = useState(false);
  const [showStyleGuide, setShowStyleGuide] = useState(false);
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
  const evalStats = EVAL_STATS[lang];
  const styleGuideCopy = STYLE_GUIDE[lang];

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
      {showStyleGuide && <StyleGuideModal lang={lang} onClose={() => setShowStyleGuide(false)} />}

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

            <button type="button" className="upload-trigger" onClick={() => setShowStyleGuide(true)}>
              {styleGuideCopy.trigger}
            </button>

            {SHOW_EVAL_STATS && (
              <div className="landing-section stats-strip">
                <p className="section-label">{evalStats.eyebrow}</p>
                <div className="stats-grid">
                  {evalStats.stats.map((stat) => (
                    <div key={stat.label}>
                      <div className="stat-value">{stat.value}</div>
                      <div className="stat-label">{stat.label}</div>
                    </div>
                  ))}
                </div>
                <p className="stats-caption">
                  {evalStats.caption}{" "}
                  <a href={EVALS_URL} target="_blank" rel="noopener noreferrer">
                    {evalStats.captionLink}
                  </a>
                </p>
              </div>
            )}

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
