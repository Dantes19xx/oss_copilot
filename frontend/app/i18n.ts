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
  },
} as const satisfies Record<Lang, Record<string, string>>;

export function detectDefaultLang(): Lang {
  if (typeof navigator === "undefined") return "en";
  return navigator.language.toLowerCase().startsWith("ru") ? "ru" : "en";
}
