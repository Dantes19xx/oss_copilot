import { Lang, UI } from "./i18n";

type UiStrings = (typeof UI)[Lang];

export type RepoView = {
  full_name: string;
  url: string;
  description?: string | null;
  stars?: number | null;
  language?: string | null;
  open_issues?: number | null;
  good_first_issues: number;
  license?: string | null;
  pushed_at?: string | null;
  has_contributing_guide: boolean;
  archived: boolean;
  fit_score?: number | null;
  topics?: string[];
  rank?: number;
};

export type IssueView = { number: number; title: string; url: string };

const STALE_DAYS = 180;

function formatCount(n: number, lang: Lang): string {
  return new Intl.NumberFormat(lang, { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

function daysSince(iso: string): number {
  return Math.round((Date.now() - Date.parse(iso)) / 86_400_000);
}

function timeAgo(iso: string, lang: Lang): string {
  const days = daysSince(iso);
  const rtf = new Intl.RelativeTimeFormat(lang, { numeric: "auto" });
  if (days < 30) return rtf.format(-days, "day");
  if (days < 365) return rtf.format(-Math.round(days / 30), "month");
  return rtf.format(-Math.round(days / 365), "year");
}

function StarIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M8 1.3l2 4.3 4.7.6-3.4 3.2.9 4.6L8 11.7l-4.2 2.3.9-4.6L1.3 6.2 6 5.6 8 1.3z" />
    </svg>
  );
}

function Pill({
  tone,
  children,
  title,
}: {
  tone?: "good" | "warn" | "danger" | "muted";
  children: React.ReactNode;
  title?: string;
}) {
  return (
    <span className="pill" data-tone={tone ?? "neutral"} title={title}>
      {children}
    </span>
  );
}

function RepoMeta({ repo, lang, ui }: { repo: RepoView; lang: Lang; ui: UiStrings }) {
  const stale = repo.pushed_at ? daysSince(repo.pushed_at) > STALE_DAYS : false;
  return (
    <>
      <div className="repo-stats">
        {typeof repo.stars === "number" && (
          <span className="repo-stat" title={ui.starsLabel}>
            <StarIcon />
            {formatCount(repo.stars, lang)}
          </span>
        )}
        {repo.language && (
          <span className="repo-stat">
            <span className="lang-dot" aria-hidden="true" />
            {repo.language}
          </span>
        )}
        {repo.pushed_at && (
          <span className="repo-stat" data-stale={stale} title={new Date(repo.pushed_at).toLocaleDateString(lang)}>
            {ui.updatedLabel} {timeAgo(repo.pushed_at, lang)}
          </span>
        )}
      </div>

      <div className="repo-pills">
        <Pill tone={repo.good_first_issues > 0 ? "good" : "muted"}>
          <strong>{repo.good_first_issues}</strong> {ui.goodFirstIssuesLabel}
        </Pill>
        {typeof repo.open_issues === "number" && (
          <Pill>
            <strong>{formatCount(repo.open_issues, lang)}</strong> {ui.openIssuesLabel}
          </Pill>
        )}
        <Pill tone={repo.has_contributing_guide ? "good" : "muted"}>
          {repo.has_contributing_guide ? "✓ " + ui.hasContributing : "✗ " + ui.noContributing}
        </Pill>
        {repo.license && repo.license !== "NOASSERTION" && <Pill>{repo.license}</Pill>}
        {repo.archived && <Pill tone="danger">{ui.archivedLabel}</Pill>}
      </div>
    </>
  );
}

export function CandidateList({
  repos,
  maxScore,
  lang,
  ui,
  disabled,
  onSelect,
}: {
  repos: RepoView[];
  maxScore: number;
  lang: Lang;
  ui: UiStrings;
  disabled: boolean;
  onSelect: (rank: number) => void;
}) {
  return (
    <ul className="repo-list">
      {repos.map((repo) => {
        const score = repo.fit_score ?? 0;
        const pct = maxScore > 0 ? Math.max(0, Math.min(1, score / maxScore)) : 0;
        return (
          <li className="repo-card" key={repo.full_name} data-archived={repo.archived}>
            <div className="repo-head">
              <span className="repo-rank">{repo.rank}</span>
              <a className="repo-name" href={repo.url} target="_blank" rel="noopener noreferrer">
                {repo.full_name}
              </a>
              <span className="repo-fit" title={`${ui.fitLabel}: ${score.toFixed(1)} / ${maxScore.toFixed(1)}`}>
                <span className="fit-bar">
                  <span className="fit-bar-fill" style={{ width: `${pct * 100}%` }} />
                </span>
                <span className="fit-value">{Math.max(score, 0).toFixed(1)}</span>
              </span>
            </div>

            <p className="repo-desc" data-empty={!repo.description}>
              {repo.description || ui.noDescription}
            </p>

            <RepoMeta repo={repo} lang={lang} ui={ui} />

            <div className="repo-actions">
              <button
                type="button"
                className="btn btn-primary btn-sm"
                disabled={disabled}
                onClick={() => repo.rank && onSelect(repo.rank)}
              >
                {ui.selectRepo}
              </button>
              <a className="repo-link" href={repo.url} target="_blank" rel="noopener noreferrer">
                {ui.openOnGithub} ↗
              </a>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export function IssuesView({
  repo,
  issues,
  lang,
  ui,
}: {
  repo: RepoView;
  issues: IssueView[];
  lang: Lang;
  ui: UiStrings;
}) {
  return (
    <div className="issues-view">
      <div className="repo-card repo-card-static">
        <p className="issues-label">{ui.issuesRepoLabel}</p>
        <a className="repo-name" href={repo.url} target="_blank" rel="noopener noreferrer">
          {repo.full_name}
        </a>
        <p className="repo-desc" data-empty={!repo.description}>
          {repo.description || ui.noDescription}
        </p>
        <RepoMeta repo={repo} lang={lang} ui={ui} />
      </div>

      {issues.length > 0 ? (
        <>
          <p className="issues-label">
            {ui.issuesShown.replace("{shown}", String(issues.length)).replace("{total}", String(Math.max(repo.good_first_issues, issues.length)))}
          </p>
          <ul className="issue-list">
            {issues.map((issue) => (
              <li key={issue.number}>
                <a className="issue-item" href={issue.url} target="_blank" rel="noopener noreferrer">
                  <span className="issue-number">#{issue.number}</span>
                  <span className="issue-title">{issue.title}</span>
                  <span className="issue-arrow" aria-hidden="true">↗</span>
                </a>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="issues-empty">{ui.noIssues}</p>
      )}
    </div>
  );
}
