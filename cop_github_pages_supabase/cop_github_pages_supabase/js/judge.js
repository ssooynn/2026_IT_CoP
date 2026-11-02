import { supabase } from './supabaseClient.js';
import {
  CRITERIA,
  TEAMS,
  MAX_TOTAL,
  clearCurrentJudge,
  getCurrentJudge,
  setMessage,
  emptyPayload,
  mergePayload,
  payloadCompletion,
  validatePayload,
  teamTotal,
  buildScoreInputId,
  formatDateTime,
} from './common.js';

const judge = getCurrentJudge();
if (!judge) {
  window.location.href = 'index.html';
}

const judgeInfoEl = document.getElementById('judge-info');
const criteriaGuideEl = document.getElementById('criteria-guide');
const teamsContainer = document.getElementById('teams-container');
const formStatusEl = document.getElementById('form-status');
const lastSavedEl = document.getElementById('last-saved');
const progressTextEl = document.getElementById('progress-text');
const saveDraftBtn = document.getElementById('save-draft-btn');
const submitFinalBtn = document.getElementById('submit-final-btn');
const logoutBtn = document.getElementById('logout-btn');

let formRow = null;
let currentPayload = emptyPayload();
let isSubmitted = false;

function renderGuide() {
  criteriaGuideEl.innerHTML = CRITERIA.map(item => `
    <div class="criteria-box">
      <div><strong>${item.label}</strong></div>
      <div class="subtle">${item.group}</div>
      <div>배점: ${item.max}점</div>
    </div>
  `).join('');
}

function renderTeams() {
  teamsContainer.innerHTML = TEAMS.map(team => `
    <div class="card team-card">
      <div class="row space-between align-center">
        <h2>팀 ${team}</h2>
        <div class="team-total">총점: <span id="total-${team}">0</span> / ${MAX_TOTAL}</div>
      </div>
      <div class="score-grid">
        <div class="head">세부 평가항목</div>
        <div class="head">배점</div>
        <div class="head">점수 입력</div>
        ${CRITERIA.map(c => `
          <div>${c.label}</div>
          <div>${c.max}</div>
          <div><input id="${buildScoreInputId(team, c.key)}" type="number" min="0" max="${c.max}" step="1" /></div>
        `).join('')}
      </div>
    </div>
  `).join('');

  document.querySelectorAll('input[type="number"]').forEach(input => {
    input.addEventListener('input', () => {
      refreshPayloadFromInputs();
      updateSummary();
    });
  });
}

function fillInputs(payload) {
  TEAMS.forEach(team => {
    CRITERIA.forEach(c => {
      const input = document.getElementById(buildScoreInputId(team, c.key));
      const value = payload?.teams?.[team]?.[c.key];
      input.value = value === null || value === undefined ? '' : value;
    });
  });
}

function refreshPayloadFromInputs() {
  const payload = emptyPayload();
  TEAMS.forEach(team => {
    CRITERIA.forEach(c => {
      const input = document.getElementById(buildScoreInputId(team, c.key));
      const value = input.value === '' ? null : Number(input.value);
      payload.teams[team][c.key] = value;
    });
  });
  currentPayload = payload;
}

function updateSummary() {
  const { filled, total } = payloadCompletion(currentPayload);
  progressTextEl.textContent = `${filled} / ${total}`;
  TEAMS.forEach(team => {
    document.getElementById(`total-${team}`).textContent = teamTotal(currentPayload, team);
  });
}

function setReadonly(readonly) {
  document.querySelectorAll('input[type="number"]').forEach(input => { input.disabled = readonly; });
  saveDraftBtn.disabled = readonly;
  submitFinalBtn.disabled = readonly;
}

async function loadMyForm() {
  const { data: sessionData } = await supabase.auth.getSession();
  if (!sessionData.session) {
    window.location.href = 'index.html';
    return;
  }

  const { data, error } = await supabase
    .from('evaluation_forms')
    .select('*')
    .eq('judge_id', judge.judge_id)
    .maybeSingle();
  if (error) throw error;

  formRow = data;
  currentPayload = mergePayload(data?.payload);
  fillInputs(currentPayload);
  updateSummary();
  isSubmitted = data?.status === 'submitted';
  formStatusEl.textContent = isSubmitted ? '제출 완료' : (data ? '임시저장' : '미작성');
  lastSavedEl.textContent = formatDateTime(data?.updated_at);
  if (isSubmitted) setReadonly(true);
}

async function upsertForm(status) {
  refreshPayloadFromInputs();
  if (status === 'submitted' && !validatePayload(currentPayload)) {
    alert('모든 값을 입력해주시기 바랍니다.');
    return;
  }

  const row = {
    judge_id: judge.judge_id,
    payload: currentPayload,
    status,
    submitted_at: status === 'submitted' ? new Date().toISOString() : null,
    updated_at: new Date().toISOString(),
  };

  const { data, error } = await supabase
    .from('evaluation_forms')
    .upsert(row, { onConflict: 'judge_id' })
    .select()
    .single();
  if (error) throw error;
  formRow = data;
  isSubmitted = data.status === 'submitted';
  formStatusEl.textContent = isSubmitted ? '제출 완료' : '임시저장';
  lastSavedEl.textContent = formatDateTime(data.updated_at);
  if (isSubmitted) {
    setReadonly(true);
    alert('최종 제출이 완료되었습니다.');
  } else {
    alert('임시저장되었습니다.');
  }
}

saveDraftBtn.addEventListener('click', async () => {
  try {
    await upsertForm('draft');
  } catch (error) {
    console.error(error);
    alert(`임시저장 실패: ${error.message}`);
  }
});

submitFinalBtn.addEventListener('click', async () => {
  try {
    await upsertForm('submitted');
  } catch (error) {
    console.error(error);
    alert(`제출 실패: ${error.message}`);
  }
});

logoutBtn.addEventListener('click', async () => {
  clearCurrentJudge();
  await supabase.auth.signOut();
  window.location.href = 'index.html';
});

async function init() {
  judgeInfoEl.textContent = `${judge.display_name} (${judge.emp_no})`;
  renderGuide();
  renderTeams();
  try {
    await loadMyForm();
  } catch (error) {
    console.error(error);
    alert(`데이터를 불러오지 못했습니다: ${error.message}`);
  }
}

init();
