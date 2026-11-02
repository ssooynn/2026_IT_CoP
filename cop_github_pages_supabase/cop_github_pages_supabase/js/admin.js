import { supabase } from './supabaseClient.js';
import {
  TEAMS,
  CRITERIA,
  setMessage,
  formatDateTime,
  mergePayload,
  payloadCompletion,
  teamTotal,
  escapeHtml,
} from './common.js';

const loginCard = document.getElementById('admin-login-card');
const content = document.getElementById('admin-content');
const loginForm = document.getElementById('admin-login-form');
const loginMessage = document.getElementById('admin-login-message');
const logoutBtn = document.getElementById('admin-logout-btn');
const judgeCreateForm = document.getElementById('judge-create-form');
const judgeCreateMessage = document.getElementById('judge-create-message');
const judgesTableBody = document.getElementById('judges-table-body');
const responsesTableBody = document.getElementById('responses-table-body');
const rankingTableBody = document.getElementById('ranking-table-body');
const latestSnapshotEl = document.getElementById('latest-snapshot');
const saveRankingMessage = document.getElementById('save-ranking-message');

let judges = [];
let forms = [];
let currentRanking = [];

function statusBadge(status, filled, total) {
  if (status === 'submitted') return '<span class="badge submitted">제출완료</span>';
  if (status === 'draft') return `<span class="badge draft">임시저장 (${filled}/${total})</span>`;
  return '<span class="badge not-started">미작성</span>';
}

async function ensureAdminSession() {
  const { data: sessionData } = await supabase.auth.getSession();
  if (!sessionData.session) return false;

  const { data, error } = await supabase.rpc('is_admin');
  if (error || !data) return false;
  loginCard.classList.add('hidden');
  content.classList.remove('hidden');
  logoutBtn.classList.remove('hidden');
  await refreshAll();
  return true;
}

async function refreshAll() {
  await Promise.all([loadJudges(), loadForms(), loadLatestSnapshot()]);
  renderJudges();
  renderResponses();
  calculateRanking();
}

async function loadJudges() {
  const { data, error } = await supabase
    .from('judges')
    .select('*')
    .order('emp_no', { ascending: true });
  if (error) throw error;
  judges = data || [];
}

async function loadForms() {
  const { data, error } = await supabase
    .from('evaluation_forms_admin')
    .select('*')
    .order('judge_emp_no', { ascending: true });
  if (error) throw error;
  forms = data || [];
}

async function loadLatestSnapshot() {
  const { data, error } = await supabase
    .from('ranking_snapshots')
    .select('*')
    .order('created_at', { ascending: false })
    .limit(1)
    .maybeSingle();
  if (error) throw error;
  if (!data) {
    latestSnapshotEl.textContent = '저장된 순위가 없습니다.';
    return;
  }
  const ranking = data.payload?.ranking || [];
  latestSnapshotEl.innerHTML = `저장 시각: ${formatDateTime(data.created_at)}<br>${ranking.map(item => `${item.rank}위 팀 ${item.team} (${item.average})`).join('<br>')}`;
}

function renderJudges() {
  judgesTableBody.innerHTML = judges.map(judge => `
    <tr>
      <td><input data-id="${judge.id}" data-field="emp_no" type="text" value="${escapeHtml(judge.emp_no)}"></td>
      <td><input data-id="${judge.id}" data-field="display_name" type="text" value="${escapeHtml(judge.display_name)}"></td>
      <td>
        <select data-id="${judge.id}" data-field="is_active">
          <option value="true" ${judge.is_active ? 'selected' : ''}>활성</option>
          <option value="false" ${!judge.is_active ? 'selected' : ''}>비활성</option>
        </select>
      </td>
      <td><button class="secondary save-judge-btn" data-id="${judge.id}" type="button">저장</button></td>
    </tr>
  `).join('');

  document.querySelectorAll('.save-judge-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.id;
      const emp_no = document.querySelector(`[data-id="${id}"][data-field="emp_no"]`).value.trim();
      const display_name = document.querySelector(`[data-id="${id}"][data-field="display_name"]`).value.trim();
      const is_active = document.querySelector(`[data-id="${id}"][data-field="is_active"]`).value === 'true';
      try {
        const { error } = await supabase.from('judges').update({ emp_no, display_name, is_active }).eq('id', id);
        if (error) throw error;
        setMessage(judgeCreateMessage, '심사위원 정보를 저장했습니다.', 'success');
        await refreshAll();
      } catch (error) {
        console.error(error);
        setMessage(judgeCreateMessage, `저장 실패: ${error.message}`, 'error');
      }
    });
  });
}

function buildDetailHtml(payload) {
  return `<div class="detail-grid">${TEAMS.map(team => `
    <div class="detail-block">
      <strong>팀 ${team}</strong> (총점 ${teamTotal(payload, team)})
      <table>
        ${CRITERIA.map(c => `<tr><td>${c.label}</td><td>${payload?.teams?.[team]?.[c.key] ?? ''}</td></tr>`).join('')}
      </table>
    </div>
  `).join('')}</div>`;
}

function renderResponses() {
  const map = new Map(forms.map(row => [row.judge_id, row]));
  responsesTableBody.innerHTML = judges.map(judge => {
    const row = map.get(judge.id);
    const payload = mergePayload(row?.payload);
    const { filled, total } = payloadCompletion(payload);
    const updatedAt = row?.updated_at ? formatDateTime(row.updated_at) : '-';
    const detailId = `detail-${judge.id}`;
    return `
      <tr>
        <td>${escapeHtml(judge.display_name)}</td>
        <td class="mono">${escapeHtml(judge.emp_no)}</td>
        <td>${statusBadge(row?.status, filled, total)}</td>
        <td>${filled}/${total}</td>
        <td>${updatedAt}</td>
        ${TEAMS.map(team => `<td>${row ? teamTotal(payload, team) : '-'}</td>`).join('')}
        <td><button class="secondary toggle-detail-btn" type="button" data-target="${detailId}">상세</button></td>
      </tr>
      <tr id="${detailId}" class="hidden">
        <td colspan="12">${row ? buildDetailHtml(payload) : '작성 내역이 없습니다.'}</td>
      </tr>
    `;
  }).join('');

  document.querySelectorAll('.toggle-detail-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.getElementById(btn.dataset.target).classList.toggle('hidden');
    });
  });
}

function calculateRanking() {
  const submitted = forms.filter(row => row.status === 'submitted');
  const results = TEAMS.map(team => {
    const values = submitted.map(row => {
      const payload = mergePayload(row.payload);
      return {
        judge_id: row.judge_id,
        judge_emp_no: row.judge_emp_no,
        judge_name: row.judge_display_name,
        total: teamTotal(payload, team),
      };
    }).sort((a, b) => a.total - b.total);

    let included = [...values];
    let minExcluded = null;
    let maxExcluded = null;

    if (values.length >= 3) {
      minExcluded = values[0];
      maxExcluded = values[values.length - 1];
      included = values.slice(1, values.length - 1);
    }

    const average = included.length
      ? (included.reduce((sum, v) => sum + v.total, 0) / included.length)
      : 0;

    return {
      team,
      submittedCount: values.length,
      minExcluded,
      maxExcluded,
      average: Number(average.toFixed(2)),
    };
  }).sort((a, b) => b.average - a.average)
    .map((item, index) => ({ ...item, rank: index + 1 }));

  currentRanking = results;
  rankingTableBody.innerHTML = results.map(item => `
    <tr>
      <td>${item.rank}</td>
      <td>팀 ${item.team}</td>
      <td>${item.submittedCount}</td>
      <td>${item.maxExcluded ? `${escapeHtml(item.maxExcluded.judge_name)} (${item.maxExcluded.total})` : '-'}</td>
      <td>${item.minExcluded ? `${escapeHtml(item.minExcluded.judge_name)} (${item.minExcluded.total})` : '-'}</td>
      <td>${item.average}</td>
    </tr>
  `).join('');
}

function buildExcelWorkbook() {
  const rows = [];
  forms.forEach(row => {
    const payload = mergePayload(row.payload);
    TEAMS.forEach(team => {
      const base = {
        심사위원명: row.judge_display_name,
        직원번호: row.judge_emp_no,
        상태: row.status,
        팀: team,
        팀총점: teamTotal(payload, team),
      };
      CRITERIA.forEach(c => {
        base[c.label] = payload?.teams?.[team]?.[c.key] ?? '';
      });
      rows.push(base);
    });
  });

  const rankingRows = currentRanking.map(item => ({
    순위: item.rank,
    팀: item.team,
    제출인원: item.submittedCount,
    최고점제외: item.maxExcluded ? `${item.maxExcluded.judge_name} (${item.maxExcluded.total})` : '',
    최저점제외: item.minExcluded ? `${item.minExcluded.judge_name} (${item.minExcluded.total})` : '',
    산정평균: item.average,
  }));

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(rows), 'responses');
  XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(rankingRows), 'ranking');
  return wb;
}

loginForm?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const email = document.getElementById('admin-email').value.trim();
  const password = document.getElementById('admin-password').value;
  try {
    setMessage(loginMessage, '로그인 중...', 'warn');
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
    const ok = await ensureAdminSession();
    if (!ok) throw new Error('관리자 권한이 없습니다. admin_emails 테이블 설정을 확인해 주세요.');
  } catch (error) {
    console.error(error);
    setMessage(loginMessage, `로그인 실패: ${error.message}`, 'error');
  }
});

logoutBtn?.addEventListener('click', async () => {
  await supabase.auth.signOut();
  window.location.reload();
});

judgeCreateForm?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const emp_no = document.getElementById('new-emp-no').value.trim();
  const display_name = document.getElementById('new-display-name').value.trim();
  const is_active = document.getElementById('new-active').value === 'true';
  try {
    const { error } = await supabase.from('judges').insert({ emp_no, display_name, is_active });
    if (error) throw error;
    setMessage(judgeCreateMessage, '심사위원을 추가했습니다.', 'success');
    judgeCreateForm.reset();
    document.getElementById('new-active').value = 'true';
    await refreshAll();
  } catch (error) {
    console.error(error);
    setMessage(judgeCreateMessage, `추가 실패: ${error.message}`, 'error');
  }
});

document.getElementById('refresh-admin-btn')?.addEventListener('click', refreshAll);
document.getElementById('calculate-ranking-btn')?.addEventListener('click', calculateRanking);

document.getElementById('save-ranking-btn')?.addEventListener('click', async () => {
  try {
    const payload = { ranking: currentRanking, saved_at: new Date().toISOString() };
    const { error } = await supabase.from('ranking_snapshots').insert({ payload });
    if (error) throw error;
    setMessage(saveRankingMessage, '팀별 점수·순위를 저장했습니다.', 'success');
    await loadLatestSnapshot();
  } catch (error) {
    console.error(error);
    setMessage(saveRankingMessage, `저장 실패: ${error.message}`, 'error');
  }
});

document.getElementById('download-excel-btn')?.addEventListener('click', () => {
  const wb = buildExcelWorkbook();
  XLSX.writeFile(wb, `cop_evaluation_${new Date().toISOString().slice(0,10)}.xlsx`);
});

ensureAdminSession();
