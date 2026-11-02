export const TEAMS = ['A', 'B', 'C', 'D', 'E', 'F'];

export const CRITERIA = [
  { key: 'problem_definition', label: '문제 정의', max: 15, group: '창의성' },
  { key: 'solution_differentiation', label: '해결방안 차별성', max: 15, group: '창의성' },
  { key: 'work_contribution', label: '업무 기여도', max: 20, group: '효과성' },
  { key: 'evidence', label: '성과 근거', max: 10, group: '효과성' },
  { key: 'output_quality', label: '결과물 완성도', max: 10, group: '실현가능성' },
  { key: 'feasibility', label: '실행 가능성', max: 10, group: '실현가능성' },
  { key: 'presentation', label: '발표 전달력', max: 10, group: '발표·수행도' },
  { key: 'qna', label: '질의응답', max: 10, group: '발표·수행도' },
];

export const MAX_TOTAL = CRITERIA.reduce((sum, item) => sum + item.max, 0);

export function setMessage(element, text, type = '') {
  if (!element) return;
  element.textContent = text || '';
  element.className = `message ${type}`.trim();
}

export function formatDateTime(value) {
  if (!value) return '-';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString('ko-KR');
}

export function emptyPayload() {
  const teams = {};
  TEAMS.forEach(team => {
    teams[team] = {};
    CRITERIA.forEach(c => {
      teams[team][c.key] = null;
    });
  });
  return { teams };
}

export function mergePayload(raw) {
  const base = emptyPayload();
  if (!raw || typeof raw !== 'object' || !raw.teams) return base;
  TEAMS.forEach(team => {
    CRITERIA.forEach(c => {
      const value = raw.teams?.[team]?.[c.key];
      base.teams[team][c.key] = value === null || value === undefined || value === '' ? null : Number(value);
    });
  });
  return base;
}

export function payloadCompletion(payload) {
  let filled = 0;
  let total = TEAMS.length * CRITERIA.length;
  TEAMS.forEach(team => {
    CRITERIA.forEach(c => {
      const v = payload?.teams?.[team]?.[c.key];
      if (v !== null && v !== undefined && v !== '') filled += 1;
    });
  });
  return { filled, total };
}

export function teamTotal(payload, team) {
  return CRITERIA.reduce((sum, c) => sum + (Number(payload?.teams?.[team]?.[c.key]) || 0), 0);
}

export function teamTotals(payload) {
  const result = {};
  TEAMS.forEach(team => { result[team] = teamTotal(payload, team); });
  return result;
}

export function isPayloadComplete(payload) {
  const { filled, total } = payloadCompletion(payload);
  return filled === total;
}

export function validatePayload(payload) {
  for (const team of TEAMS) {
    for (const c of CRITERIA) {
      const raw = payload?.teams?.[team]?.[c.key];
      if (raw === null || raw === undefined || raw === '') return false;
      const num = Number(raw);
      if (Number.isNaN(num) || num < 0 || num > c.max) return false;
    }
  }
  return true;
}

export function buildScoreInputId(team, key) {
  return `score-${team}-${key}`;
}

export function currentJudgeStorageKey() {
  return 'cop_current_judge';
}

export function saveCurrentJudge(judge) {
  localStorage.setItem(currentJudgeStorageKey(), JSON.stringify(judge));
}

export function getCurrentJudge() {
  try {
    return JSON.parse(localStorage.getItem(currentJudgeStorageKey()) || 'null');
  } catch {
    return null;
  }
}

export function clearCurrentJudge() {
  localStorage.removeItem(currentJudgeStorageKey());
}

export function escapeHtml(str = '') {
  return String(str)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}
