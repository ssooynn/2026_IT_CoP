import { supabase } from './supabaseClient.js';
import { saveCurrentJudge, setMessage, clearCurrentJudge } from './common.js';

const form = document.getElementById('judge-login-form');
const messageEl = document.getElementById('judge-login-message');

async function ensureAnonymousAuth() {
  const { data } = await supabase.auth.getSession();
  if (data.session) return data.session;
  const { error } = await supabase.auth.signInAnonymously();
  if (error) throw error;
  const { data: newSession } = await supabase.auth.getSession();
  return newSession.session;
}

clearCurrentJudge();

form?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const empNo = document.getElementById('empNo').value.trim();
  if (!empNo) {
    setMessage(messageEl, '직원번호를 입력해 주세요.', 'error');
    return;
  }

  try {
    setMessage(messageEl, '로그인 중입니다...', 'warn');
    await ensureAnonymousAuth();
    const { data, error } = await supabase.rpc('judge_login', { p_emp_no: empNo });
    if (error) throw error;
    if (!data || !data[0]) {
      setMessage(messageEl, '등록되지 않은 직원번호입니다.', 'error');
      return;
    }
    const judge = data[0];
    saveCurrentJudge(judge);
    setMessage(messageEl, `${judge.display_name} 님으로 로그인되었습니다.`, 'success');
    window.location.href = 'judge.html';
  } catch (error) {
    console.error(error);
    setMessage(messageEl, `로그인 실패: ${error.message}`, 'error');
  }
});
