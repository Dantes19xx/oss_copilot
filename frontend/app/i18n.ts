export type Lang = "ru" | "en";

export const UI = {
  en: {
    headline: "Ship a review, or find your next repo.",
    subtitle: "Review a pull request, or find an open-source repo worth contributing to.",
    placeholder: "e.g. Review the pull request https://github.com/owner/repo/pull/123",
    submit: "Submit",
    working: "Working",
    send: "Send",
    newRequest: "New request",
    answerPlaceholder: "type a reply…",
    skip: "Skip",
    approve: "Approve",
    merge: "Approve & merge",
    reject: "Reject",
    examplesLabel: "Try:",
    example1: "Review the pull request https://github.com/pallets/flask/pull/5918",
    example1Label: "PR review",
    example2: "I know Python, want to contribute to a CLI tool",
    example2Label: "Find a repo",
    kickerReview: "Review draft",
    kickerRepo: "Candidates",
    kickerClarify: "Quick question",
    kickerResult: "Result",
    kickerWorking: "Thinking",
    helpLabel: "How it works",
    historyLabel: "Recent requests",
    historyClear: "Clear",
    historyBack: "Back",
  },
  ru: {
    headline: "Проверим PR или найдём репозиторий для контрибьюта.",
    subtitle: "Проверьте pull request или найдите open-source репозиторий для контрибьюта.",
    placeholder: "например: ревью PR https://github.com/owner/repo/pull/123",
    submit: "Отправить",
    working: "Работаю",
    send: "Отправить",
    newRequest: "Новый запрос",
    answerPlaceholder: "введите ответ…",
    skip: "Пропустить",
    approve: "Одобрить",
    merge: "Одобрить и смержить",
    reject: "Отклонить",
    examplesLabel: "Примеры:",
    example1: "Проверь PR https://github.com/pallets/flask/pull/5918",
    example1Label: "Ревью PR",
    example2: "Я знаю Python, хочу контрибьютить в CLI-тулзу",
    example2Label: "Найти репозиторий",
    kickerReview: "Черновик ревью",
    kickerRepo: "Кандидаты",
    kickerClarify: "Уточняющий вопрос",
    kickerResult: "Результат",
    kickerWorking: "Думаю",
    helpLabel: "Как это работает",
    historyLabel: "Последние запросы",
    historyClear: "Очистить",
    historyBack: "Назад",
  },
} as const satisfies Record<Lang, Record<string, string>>;

type Stat = { value: string; label: string };
type EvalStatsContent = { eyebrow: string; stats: Stat[]; caption: string; captionLink: string };

export const EVAL_STATS: Record<Lang, EvalStatsContent> = {
  en: {
    eyebrow: "Measured, not vibes",
    stats: [
      { value: "30", label: "golden examples" },
      { value: "0.90", label: "F1 score" },
      { value: "1.00", label: "recall" },
      { value: "4.13/5", label: "LLM-judge score" },
    ],
    caption: "From an automated eval run on a 30-example golden dataset.",
    captionLink: "Methodology & A/B experiment →",
  },
  ru: {
    eyebrow: "Измерено, не на глаз",
    stats: [
      { value: "30", label: "golden-примеров" },
      { value: "0.90", label: "F1-score" },
      { value: "1.00", label: "recall" },
      { value: "4.13/5", label: "оценка LLM-judge" },
    ],
    caption: "Автоматический прогон на golden dataset из 30 примеров.",
    captionLink: "Методология и A/B-эксперимент →",
  },
};

export function detectDefaultLang(): Lang {
  if (typeof navigator === "undefined") return "en";
  return navigator.language.toLowerCase().startsWith("ru") ? "ru" : "en";
}

type OnboardingSection = { title: string; body: string };
type OnboardingContent = { title: string; intro: string; sections: OnboardingSection[]; closeLabel: string };

export const ONBOARDING: Record<Lang, OnboardingContent> = {
  en: {
    title: "How OSS Copilot works",
    intro:
      "One field, free text — the agent figures out what you want. Nothing is ever posted to GitHub or finalized without your explicit confirmation.",
    sections: [
      {
        title: "Review a pull request",
        body: "Paste a PR link (or describe it in words). The agent fetches the diff and checks each file for bugs, security issues, missing tests, and breaking changes, then shows you a draft. Approve posts it as a GitHub comment, Approve & merge also merges the PR, Reject discards it — nothing goes out until you decide.",
      },
      {
        title: "Find a repo to contribute to",
        body: "Describe your skills and interests. The agent may ask one or two quick follow-up questions to narrow things down, then ranks candidates by how contributor-friendly they actually are — not just star count. Pick a number to get real open good-first-issues, or Skip.",
      },
      {
        title: "Multimodal by default",
        body: "If a PR description includes a screenshot or GIF, it's automatically analyzed by a vision model and folded into the review — catching visual bugs a text-only diff can't.",
      },
      {
        title: "Built-in safety",
        body: "Secrets are redacted before anything is shown or posted. Suspicious instructions hidden in a diff are flagged, not obeyed. If the primary model is slow or unavailable, a stronger one is used automatically.",
      },
    ],
    closeLabel: "Got it",
  },
  ru: {
    title: "Как работает OSS Copilot",
    intro:
      "Одно поле, свободный текст — агент сам понимает, что нужно. Ничего не публикуется в GitHub и не финализируется без вашего явного подтверждения.",
    sections: [
      {
        title: "Ревью pull request'а",
        body: "Вставьте ссылку на PR (или опишите словами). Агент скачивает diff, проверяет каждый файл на баги, security-проблемы, отсутствующие тесты и breaking changes, показывает черновик. Approve публикует его как комментарий на GitHub, Approve & merge — ещё и мержит PR, Reject — отклоняет. Ничего не уходит, пока вы не решите.",
      },
      {
        title: "Подбор репозитория для контрибьюта",
        body: "Опишите свои навыки и интересы. Агент может задать 1-2 коротких уточняющих вопроса, затем ранжирует кандидатов по реальной дружелюбности к новичкам — не по числу звёзд. Выберите номер, чтобы получить настоящие открытые good-first-issues, или нажмите Skip.",
      },
      {
        title: "Мультимодальность по умолчанию",
        body: "Если в описании PR есть скриншот или gif, он автоматически анализируется vision-моделью и встраивается в ревью — это ловит визуальные баги, которые текстовый diff в принципе не видит.",
      },
      {
        title: "Встроенная безопасность",
        body: "Секреты вычищаются из текста до того, как что-либо показывается или публикуется. Подозрительные инструкции, спрятанные в diff'е, помечаются, а не выполняются. Если основная модель недоступна или медленная — агент автоматически переключается на более сильную.",
      },
    ],
    closeLabel: "Понятно",
  },
};

type ModeCard = { title: string; body: string; accent: "review" | "repo" };
type Step = { title: string; body: string };
type LandingContent = { modesLabel: string; modes: ModeCard[]; stepsLabel: string; steps: Step[] };

export const LANDING: Record<Lang, LandingContent> = {
  en: {
    modesLabel: "Two things it does",
    modes: [
      {
        title: "PR Review",
        body: "Paste a link. Get a file-by-file review — bugs, security issues, missing tests, breaking changes — before anything is posted.",
        accent: "review",
      },
      {
        title: "Repo Match",
        body: "Describe your skills. Get repos ranked by real contributor-friendliness, not stars, plus open good-first-issues.",
        accent: "repo",
      },
    ],
    stepsLabel: "How it works",
    steps: [
      { title: "Describe what you need", body: "One free-text field — the agent classifies it automatically." },
      { title: "Review the draft", body: "See the comments or candidates before anything happens." },
      { title: "Confirm", body: "Approve, merge, reject, or pick a number — nothing goes out without you." },
    ],
  },
  ru: {
    modesLabel: "Что он умеет",
    modes: [
      {
        title: "Ревью PR",
        body: "Вставьте ссылку. Получите ревью по файлам — баги, security, отсутствующие тесты, breaking changes — прежде чем что-либо опубликуется.",
        accent: "review",
      },
      {
        title: "Подбор репозитория",
        body: "Опишите свои навыки. Получите репозитории, ранжированные по реальной дружелюбности к новичкам, а не по звёздам, плюс открытые good-first-issues.",
        accent: "repo",
      },
    ],
    stepsLabel: "Как это работает",
    steps: [
      { title: "Опишите, что нужно", body: "Одно текстовое поле — агент сам классифицирует запрос." },
      { title: "Проверьте черновик", body: "Увидите комментарии или кандидатов до того, как что-либо произойдёт." },
      { title: "Подтвердите", body: "Approve, merge, reject или номер — ничего не уйдёт без вас." },
    ],
  },
};

type StyleGuideContent = {
  trigger: string;
  title: string;
  intro: string;
  ownerLabel: string;
  repoLabel: string;
  fileLabel: string;
  uploadButton: string;
  uploading: string;
  successPrefix: string;
  successMiddle: string;
  errorPrefix: string;
  closeLabel: string;
};

export const STYLE_GUIDE: Record<Lang, StyleGuideContent> = {
  en: {
    trigger: "+ Upload a style guide",
    title: "Upload a style guide",
    intro:
      "Index a PDF or DOCX of your team's coding standards for a repo — future reviews of that repo will use it as context, the same way it already uses that repo's own CONTRIBUTING.md.",
    ownerLabel: "Repo owner",
    repoLabel: "Repo name",
    fileLabel: "PDF or DOCX file",
    uploadButton: "Upload",
    uploading: "Uploading",
    successPrefix: "Indexed",
    successMiddle: "chunk(s) from",
    errorPrefix: "Upload failed: ",
    closeLabel: "Close",
  },
  ru: {
    trigger: "+ Загрузить style-guide",
    title: "Загрузить style-guide",
    intro:
      "Проиндексируйте PDF или DOCX со стандартами вашей команды для репозитория — будущие ревью этого репозитория будут учитывать его как контекст, так же как уже учитывают собственный CONTRIBUTING.md репозитория.",
    ownerLabel: "Владелец репозитория",
    repoLabel: "Название репозитория",
    fileLabel: "Файл PDF или DOCX",
    uploadButton: "Загрузить",
    uploading: "Загружаю",
    successPrefix: "Проиндексировано",
    successMiddle: "чанк(ов) из",
    errorPrefix: "Ошибка загрузки: ",
    closeLabel: "Закрыть",
  },
};
