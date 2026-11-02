import os
import sqlite3
import html
import urllib.parse
import io
import zipfile
import socket
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from datetime import datetime

HOST = '0.0.0.0'
PORT = 5000
BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'cop_scores.db')
ADMIN_PIN = os.environ.get('ADMIN_PIN', '1234')

TEAMS = ['A', 'B', 'C', 'D', 'E', 'F']
CRITERIA = [
    ('창의성', '문제 정의', '업무 문제를 명확히 파악하고, 새로운 관점을 제시했는가?', 15),
    ('창의성', '해결방안 차별성', '기존과 차별화된 방법으로 지식·기술을 적용했는가?', 15),
    ('효과성', '업무 기여도', '활동 결과가 업무 개선이나 역량 향상에 도움이 되었는가?', 20),
    ('효과성', '성과 근거', '성과를 확인할 수 있는 구체적인 근거를 제시했는가?', 10),
    ('실현가능성', '결과물 완성도', '결과물이 완성도 있고, 실제 활용할 수 있는 수준인가?', 10),
    ('실현가능성', '실행 가능성', '실제 적용 가능한 구체적인 활용 계획을 제시했는가?', 10),
    ('발표·수행도', '발표 전달력', '핵심 내용을 이해하기 쉽게 구성하고 명확하게 전달했는가?', 10),
    ('발표·수행도', '질의응답', '질문을 정확히 이해하고 적절하게 답변했는가?', 10),
]
TOTAL_FIELDS = len(TEAMS) * len(CRITERIA)

CSS = '''
*{box-sizing:border-box}
body{font-family:Arial,"Malgun Gothic",sans-serif;background:#f5f7fa;margin:0;color:#222}
.wrap{max-width:1600px;margin:auto;padding:24px}
h1{font-size:26px;margin:0 0 16px}
h2{font-size:20px;margin:0 0 12px}
.card,.toolbar{background:#fff;border:1px solid #dde3ea;border-radius:12px;padding:18px;margin:14px 0}
.narrow{max-width:460px;margin:60px auto}
.toolbar{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
label{display:block;font-weight:700;margin:12px 0 6px}
input{font-size:16px;padding:10px;border:1px solid #cfd6df;border-radius:8px;width:100%}
button,.btn{background:#1f5fbf;color:#fff;border:0;border-radius:8px;padding:11px 18px;font-weight:700;text-decoration:none;cursor:pointer;display:inline-block}
button.secondary,.btn.secondary{background:#667085}
button.success,.btn.success{background:#166534}
button:hover,.btn:hover{filter:brightness(.96)}
.tablebox{overflow:auto;background:#fff;border:1px solid #dde3ea;border-radius:10px}
table{border-collapse:collapse;width:100%;min-width:1000px}
th,td{border:1px solid #e3e7ec;padding:10px;text-align:center;vertical-align:middle}
th{background:#eef3f8;position:sticky;top:0;z-index:1}
td.criteria{text-align:left;min-width:360px}
td.criteria span{font-size:13px;color:#555}
.score{width:72px;text-align:center;padding:8px}
.total td{font-weight:700;background:#f8fafc}
.msg{background:#ecfdf3;border:1px solid #a6f4c5;padding:10px 12px;border-radius:8px;margin:10px 0;color:#05603a}
.warn{background:#fff4d6;border:1px solid #f0d685;padding:10px 12px;border-radius:8px;margin:10px 0;color:#7a5d00}
.actions{text-align:right;margin-top:14px;display:flex;justify-content:flex-end;gap:8px;flex-wrap:wrap}
.small{color:#667085;font-size:13px}
.summary{min-width:0;max-width:1100px}
.badge{display:inline-block;padding:4px 8px;border-radius:999px;font-size:12px;font-weight:700}
.badge.done{background:#dcfce7;color:#166534}.badge.draft{background:#fef3c7;color:#92400e}.badge.none{background:#f2f4f7;color:#475467}
.rank1{font-weight:800}
details{background:#fff;border:1px solid #dde3ea;border-radius:10px;padding:12px 14px;margin:10px 0}
summary{cursor:pointer;font-weight:700}
.inline{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.muted{color:#667085}.right{text-align:right}
@media(max-width:700px){.wrap{padding:12px}.toolbar{flex-direction:column;align-items:flex-start}.actions{justify-content:stretch}.actions button{flex:1}}
'''


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = conn()
    c.execute('''CREATE TABLE IF NOT EXISTS scores(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        judge TEXT NOT NULL,
        team TEXT NOT NULL,
        criterion_idx INTEGER NOT NULL,
        score REAL NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(judge,team,criterion_idx)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS submissions(
        judge TEXT PRIMARY KEY,
        status TEXT NOT NULL DEFAULT 'draft',
        updated_at TEXT NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS rankings(
        team TEXT PRIMARY KEY,
        final_score REAL,
        rank_no INTEGER,
        judge_count INTEGER NOT NULL,
        high_judge TEXT,
        high_score REAL,
        low_judge TEXT,
        low_score REAL,
        saved_at TEXT NOT NULL
    )''')

    # 이전 버전 DB 자동 호환: 값이 전부 있으면 제출완료, 일부만 있으면 임시저장으로 등록
    now = datetime.now().isoformat(timespec='seconds')
    old_judges = [r['judge'] for r in c.execute('SELECT DISTINCT judge FROM scores')]
    for judge in old_judges:
        exists = c.execute('SELECT 1 FROM submissions WHERE judge=?', (judge,)).fetchone()
        if not exists:
            count = c.execute('SELECT COUNT(*) AS n FROM scores WHERE judge=?', (judge,)).fetchone()['n']
            status = 'submitted' if count == TOTAL_FIELDS else 'draft'
            c.execute('INSERT INTO submissions(judge,status,updated_at) VALUES(?,?,?)', (judge, status, now))
    c.commit()
    c.close()


init_db()


def page(title, body):
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{CSS}</style></head><body><div class="wrap"><h1>CoP 결과발표회 평가</h1>{body}</div></body></html>'''.encode('utf-8')


def parse_form(handler):
    n = int(handler.headers.get('Content-Length', '0') or 0)
    raw = handler.rfile.read(n).decode('utf-8')
    return urllib.parse.parse_qs(raw)


def judge_progress(c, judge):
    return c.execute('SELECT COUNT(*) AS n FROM scores WHERE judge=?', (judge,)).fetchone()['n']


def judge_status(c, judge):
    r = c.execute('SELECT status,updated_at FROM submissions WHERE judge=?', (judge,)).fetchone()
    if r:
        return r['status'], r['updated_at']
    return 'none', ''


def team_totals_for_submitted(c, team):
    judges = [r['judge'] for r in c.execute("SELECT judge FROM submissions WHERE status='submitted' ORDER BY judge")]
    totals = []
    for judge in judges:
        rows = c.execute('SELECT criterion_idx,score FROM scores WHERE judge=? AND team=? ORDER BY criterion_idx', (judge, team)).fetchall()
        if len(rows) == len(CRITERIA):
            totals.append((judge, sum(float(r['score']) for r in rows)))
    return totals


def trimmed_team_result(c, team):
    totals = team_totals_for_submitted(c, team)
    if len(totals) < 3:
        return {
            'team': team, 'judge_count': len(totals), 'final_score': None,
            'low': None, 'high': None, 'included': totals
        }
    ordered = sorted(totals, key=lambda x: (x[1], x[0]))
    low = ordered[0]
    high = ordered[-1]
    included = ordered[1:-1]
    final_score = sum(x[1] for x in included) / len(included)
    return {
        'team': team, 'judge_count': len(totals), 'final_score': final_score,
        'low': low, 'high': high, 'included': included
    }


def compute_rankings(c):
    results = [trimmed_team_result(c, t) for t in TEAMS]
    rankable = [r for r in results if r['final_score'] is not None]
    rankable.sort(key=lambda r: (-r['final_score'], r['team']))
    rank_map = {}
    prev_score = None
    current_rank = 0
    for idx, r in enumerate(rankable, 1):
        score_key = round(r['final_score'], 10)
        if prev_score is None or score_key != prev_score:
            current_rank = idx
            prev_score = score_key
        rank_map[r['team']] = current_rank
    for r in results:
        r['rank_no'] = rank_map.get(r['team'])
    return results


def xlsx_bytes(rows, sheet='평가결과'):
    def esc(v):
        return html.escape(str(v), quote=False)

    shared = []
    idx = {}

    def sidx(v):
        v = str(v)
        if v not in idx:
            idx[v] = len(shared)
            shared.append(v)
        return idx[v]

    xmlrows = []
    for r, row in enumerate(rows, 1):
        cells = []
        for c, v in enumerate(row, 1):
            col = ''
            x = c
            while x:
                x, rem = divmod(x - 1, 26)
                col = chr(65 + rem) + col
            ref = f'{col}{r}'
            if isinstance(v, (int, float)) and v is not None:
                cells.append(f'<c r="{ref}"><v>{v}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="s"><v>{sidx("" if v is None else v)}</v></c>')
        xmlrows.append(f'<row r="{r}">' + ''.join(cells) + '</row>')

    shared_xml = ''.join(f'<si><t>{esc(v)}</t></si>' for v in shared)
    files = {
        '[Content_Types].xml': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>''',
        '_rels/.rels': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>''',
        'xl/workbook.xml': f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="{esc(sheet)}" sheetId="1" r:id="rId1"/></sheets></workbook>''',
        'xl/_rels/workbook.xml.rels': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/></Relationships>''',
        'xl/worksheets/sheet1.xml': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>''' + ''.join(xmlrows) + '''</sheetData></worksheet>''',
        'xl/sharedStrings.xml': f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(shared)}" uniqueCount="{len(shared)}">{shared_xml}</sst>'''
    }
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data.encode('utf-8'))
    return bio.getvalue()


class H(BaseHTTPRequestHandler):
    def send_html(self, data, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, loc):
        self.send_response(303)
        self.send_header('Location', loc)
        self.end_headers()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        p = u.path
        q = urllib.parse.parse_qs(u.query)

        if p == '/':
            body = '''<div class="card narrow"><h2>심사위원 접속</h2><form method="post" action="/start"><label>심사위원명</label><input name="judge" required autofocus placeholder="예: 홍길동"><button style="margin-top:14px">평가 시작</button></form><p class="small"><a href="/admin">관리자 화면</a></p></div>'''
            return self.send_html(page('심사위원 접속', body))

        if p == '/evaluate':
            judge = (q.get('judge') or [''])[0].strip()
            if not judge:
                return self.redirect('/')

            c = conn()
            ex = {(r['team'], r['criterion_idx']): r['score'] for r in c.execute('SELECT team,criterion_idx,score FROM scores WHERE judge=?', (judge,))}
            status, updated_at = judge_status(c, judge)
            progress = judge_progress(c, judge)
            c.close()

            rows = ''
            for i, (area, name, desc, maxs) in enumerate(CRITERIA):
                cells = ''.join(
                    f'<td><input class="score" type="number" min="0" max="{maxs}" step="1" name="s_{t}_{i}" value="{ex.get((t, i), "")}" oninput="calc()"></td>'
                    for t in TEAMS
                )
                rows += f'<tr><td><b>{area}</b></td><td class="criteria"><b>{name}</b><br><span>{desc}</span></td><td><b>{maxs}</b></td>{cells}</tr>'

            teamheads = ''.join(f'<th>팀 {t}</th>' for t in TEAMS)
            tots = ''.join(f'<td id="tot_{t}">0</td>' for t in TEAMS)
            status_text = '제출 완료' if status == 'submitted' else ('임시저장' if progress else '작성 전')
            status_class = 'done' if status == 'submitted' else ('draft' if progress else 'none')
            msg = ''
            if (q.get('saved') or [''])[0] == 'draft':
                msg = '<div class="msg">임시저장되었습니다. 나중에 같은 이름으로 다시 접속하면 이어서 작성할 수 있습니다.</div>'
            elif (q.get('saved') or [''])[0] == 'submitted':
                msg = '<div class="msg">최종 제출되었습니다.</div>'

            alert_script = ''
            if (q.get('alert') or [''])[0] == 'missing':
                alert_script = "alert('모든 값을 입력해주시기 바랍니다.');"
            elif (q.get('alert') or [''])[0] == 'range':
                alert_script = "alert('배점 범위 내 점수를 입력해주시기 바랍니다.');"

            body = f'''
            <div class="toolbar">
              <div><b>{html.escape(judge)}</b> 심사위원 &nbsp; <span class="badge {status_class}">{status_text}</span> <span class="small">({progress}/{TOTAL_FIELDS} 입력)</span></div>
              <a href="/">이름 변경</a>
            </div>
            {msg}
            <form id="scoreForm" method="post" action="/save">
              <input type="hidden" name="judge" value="{html.escape(judge)}">
              <div class="tablebox"><table>
                <thead><tr><th>평가영역</th><th>평가기준</th><th>배점</th>{teamheads}</tr></thead>
                <tbody>{rows}<tr class="total"><td colspan="2">총점</td><td>100</td>{tots}</tr></tbody>
              </table></div>
              <div class="actions">
                <button class="secondary" type="submit" name="mode" value="draft">임시저장</button>
                <button type="submit" name="mode" value="submit">최종 제출</button>
              </div>
            </form>
            <script>
            function calc(){{
              const teams={TEAMS!r};
              teams.forEach(t=>{{
                let s=0;
                document.querySelectorAll('input[name^="s_'+t+'_"]' ).forEach(i=>s+=Number(i.value||0));
                document.getElementById('tot_'+t).innerText=s;
              }});
            }}
            document.getElementById('scoreForm').addEventListener('submit', function(e){{
              const mode = e.submitter ? e.submitter.value : 'submit';
              if(mode !== 'submit') return;
              const inputs=[...document.querySelectorAll('.score')];
              if(inputs.some(i => i.value.trim() === '')){{
                e.preventDefault();
                alert('모든 값을 입력해주시기 바랍니다.');
                const first=inputs.find(i => i.value.trim() === '');
                if(first) first.focus();
                return;
              }}
              for(const i of inputs){{
                const v=Number(i.value), min=Number(i.min), max=Number(i.max);
                if(Number.isNaN(v) || v < min || v > max){{
                  e.preventDefault();
                  alert('배점 범위 내 점수를 입력해주시기 바랍니다.');
                  i.focus();
                  return;
                }}
              }}
            }});
            calc();
            {alert_script}
            </script>'''
            return self.send_html(page('평가', body))

        if p == '/admin':
            pin = (q.get('pin') or [''])[0]
            if pin != ADMIN_PIN:
                body = '''<div class="card narrow"><h2>관리자 로그인</h2><form method="get" action="/admin"><label>관리자 PIN</label><input type="password" name="pin" required><button style="margin-top:14px">확인</button></form><p class="small">기본 PIN: 1234</p></div>'''
                return self.send_html(page('관리자', body))

            c = conn()
            judges = [r['judge'] for r in c.execute('SELECT judge FROM submissions ORDER BY judge')]
            live_results = compute_rankings(c)
            saved_rankings = c.execute('SELECT * FROM rankings ORDER BY rank_no IS NULL, rank_no, team').fetchall()

            # 상태 요약
            judge_rows = ''
            for j in judges:
                status, updated_at = judge_status(c, j)
                progress = judge_progress(c, j)
                cls = 'done' if status == 'submitted' else ('draft' if progress else 'none')
                text_status = '제출 완료' if status == 'submitted' else ('임시저장' if progress else '작성 전')
                team_total_cells = ''
                for t in TEAMS:
                    vals = c.execute('SELECT score FROM scores WHERE judge=? AND team=? ORDER BY criterion_idx', (j, t)).fetchall()
                    team_total_cells += f'<td>{sum(float(r["score"]) for r in vals):.1f}' + ('' if len(vals) == len(CRITERIA) else f' <span class="small">({len(vals)}/{len(CRITERIA)})</span>') + '</td>'
                judge_rows += f'<tr><td>{html.escape(j)}</td><td><span class="badge {cls}">{text_status}</span></td><td>{progress}/{TOTAL_FIELDS}</td>{team_total_cells}<td>{html.escape(updated_at or "-")}</td></tr>'

            if not judge_rows:
                judge_rows = '<tr><td colspan="11">아직 저장된 평가가 없습니다.</td></tr>'

            # 현재 산정 미리보기
            preview_rows = ''
            for r in live_results:
                if r['final_score'] is None:
                    preview_rows += f'<tr><td>팀 {r["team"]}</td><td>{r["judge_count"]}</td><td>-</td><td>-</td><td><b>산정 대기</b><br><span class="small">제출완료 3명 이상 필요</span></td></tr>'
                else:
                    low = f'{html.escape(r["low"][0])} ({r["low"][1]:.1f})'
                    high = f'{html.escape(r["high"][0])} ({r["high"][1]:.1f})'
                    included = ', '.join(f'{html.escape(j)} {s:.1f}' for j, s in r['included']) or '-'
                    preview_rows += f'<tr><td>팀 {r["team"]}</td><td>{r["judge_count"]}</td><td>{high}</td><td>{low}</td><td><b>{r["final_score"]:.2f}</b><br><span class="small">반영: {included}</span></td></tr>'

            # 평가자별 세부 입력값
            detail_blocks = ''
            for j in judges:
                status, updated_at = judge_status(c, j)
                progress = judge_progress(c, j)
                text_status = '제출 완료' if status == 'submitted' else ('임시저장' if progress else '작성 전')
                drows = ''
                for i, (area, name, desc, maxs) in enumerate(CRITERIA):
                    cells = ''
                    for t in TEAMS:
                        rr = c.execute('SELECT score FROM scores WHERE judge=? AND team=? AND criterion_idx=?', (j, t, i)).fetchone()
                        cells += f'<td>{rr["score"] if rr else "-"}</td>'
                    drows += f'<tr><td>{area}</td><td>{name}</td><td>{maxs}</td>{cells}</tr>'
                detail_blocks += f'''<details><summary>{html.escape(j)} — {text_status} ({progress}/{TOTAL_FIELDS})</summary><div class="tablebox" style="margin-top:10px"><table><thead><tr><th>영역</th><th>항목</th><th>배점</th>{''.join(f'<th>팀 {t}</th>' for t in TEAMS)}</tr></thead><tbody>{drows}</tbody></table></div><p class="small">마지막 저장: {html.escape(updated_at or '-')}</p></details>'''

            # 저장된 최종 순위
            if saved_rankings:
                saved_at = saved_rankings[0]['saved_at']
                sr = ''
                for row in saved_rankings:
                    score = '-' if row['final_score'] is None else f'{row["final_score"]:.2f}'
                    rank = '-' if row['rank_no'] is None else str(row['rank_no'])
                    high_display = html.escape(row['high_judge'] or '-')
                    if row['high_score'] is not None:
                        high_display += f' ({row["high_score"]:.1f})'
                    low_display = html.escape(row['low_judge'] or '-')
                    if row['low_score'] is not None:
                        low_display += f' ({row["low_score"]:.1f})'
                    sr += f'<tr><td class="rank1">{rank}</td><td>팀 {row["team"]}</td><td><b>{score}</b></td><td>{row["judge_count"]}</td><td>{high_display}</td><td>{low_display}</td></tr>'
                ranking_section = f'''<div class="card"><div class="toolbar" style="margin:0 0 12px;padding:0;border:0"><div><h2>확정 순위</h2><span class="small">저장 시각: {html.escape(saved_at)}</span></div></div><table class="summary"><tr><th>순위</th><th>팀</th><th>최종 점수</th><th>제출완료 심사위원 수</th><th>제외 최고점</th><th>제외 최저점</th></tr>{sr}</table></div>'''
            else:
                ranking_section = '<div class="card"><h2>확정 순위</h2><p class="muted">아직 관리자가 순위를 저장하지 않았습니다.</p></div>'

            c.close()

            body = f'''
            <div class="toolbar"><div><b>관리자 집계 화면</b><div class="small">임시저장은 확인용이며, 점수 산정에는 최종 제출된 평가만 반영됩니다.</div></div><a class="btn" href="/export.xlsx?pin={urllib.parse.quote(ADMIN_PIN)}">Excel 다운로드</a></div>

            <div class="card"><h2>평가자별 제출 현황</h2><div class="tablebox"><table><thead><tr><th>심사위원</th><th>상태</th><th>입력 수</th>{''.join(f'<th>팀 {t} 총점</th>' for t in TEAMS)}<th>마지막 저장</th></tr></thead><tbody>{judge_rows}</tbody></table></div></div>

            <div class="card"><h2>팀별 산정 점수 미리보기</h2><p class="small">최종 제출된 심사위원의 팀 총점 중 최고점 1개와 최저점 1개를 각각 제외한 뒤 나머지 점수의 평균을 계산합니다.</p><div class="tablebox"><table class="summary"><tr><th>팀</th><th>제출완료 수</th><th>제외 최고점</th><th>제외 최저점</th><th>산정 점수</th></tr>{preview_rows}</table></div><form method="post" action="/admin/finalize" onsubmit="return confirm('현재 제출완료 데이터를 기준으로 순위를 저장하시겠습니까?');"><input type="hidden" name="pin" value="{html.escape(ADMIN_PIN)}"><div class="actions"><button class="success">팀별 점수·순위 저장</button></div></form></div>

            {ranking_section}

            <div class="card"><h2>평가자별 세부 입력값</h2><p class="small">평가자 이름을 눌러 팀별·항목별 원점수를 확인할 수 있습니다.</p>{detail_blocks or '<p class="muted">아직 저장된 평가가 없습니다.</p>'}</div>
            '''
            return self.send_html(page('관리자', body))

        if p == '/export.xlsx':
            pin = (q.get('pin') or [''])[0]
            if pin != ADMIN_PIN:
                return self.redirect('/admin')
            c = conn()
            judges = [r['judge'] for r in c.execute('SELECT judge FROM submissions ORDER BY judge')]
            rows = [['심사위원', '상태', '팀'] + [x[1] for x in CRITERIA] + ['팀 총점']]
            for j in judges:
                status, _ = judge_status(c, j)
                status_text = '제출완료' if status == 'submitted' else '임시저장'
                for t in TEAMS:
                    vals = []
                    anyv = False
                    for i in range(len(CRITERIA)):
                        r = c.execute('SELECT score FROM scores WHERE judge=? AND team=? AND criterion_idx=?', (j, t, i)).fetchone()
                        v = r['score'] if r else None
                        vals.append(v)
                        anyv = anyv or v is not None
                    if anyv:
                        rows.append([j, status_text, t] + vals + [sum(v or 0 for v in vals)])

            rows += [[], ['팀별 산정 결과'], ['팀', '제출완료 수', '제외 최고점', '제외 최저점', '산정 점수', '순위']]
            for r in compute_rankings(c):
                rows.append([
                    r['team'], r['judge_count'],
                    '' if r['high'] is None else f'{r["high"][0]} ({r["high"][1]:.1f})',
                    '' if r['low'] is None else f'{r["low"][0]} ({r["low"][1]:.1f})',
                    '' if r['final_score'] is None else round(r['final_score'], 2),
                    '' if r['rank_no'] is None else r['rank_no']
                ])
            c.close()

            data = xlsx_bytes(rows)
            self.send_response(200)
            self.send_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.send_header('Content-Disposition', 'attachment; filename="CoP_scores.xlsx"')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        self.send_error(404)

    def do_POST(self):
        if self.path == '/start':
            f = parse_form(self)
            judge = (f.get('judge') or [''])[0].strip()
            return self.redirect('/evaluate?judge=' + urllib.parse.quote(judge))

        if self.path == '/save':
            f = parse_form(self)
            judge = (f.get('judge') or [''])[0].strip()
            mode = (f.get('mode') or ['submit'])[0]
            if not judge:
                return self.redirect('/')

            # 서버에서도 최종 제출 시 전체 입력 여부와 배점 범위를 검증
            values = {}
            missing = False
            invalid = False
            for t in TEAMS:
                for i, crit in enumerate(CRITERIA):
                    raw = (f.get(f's_{t}_{i}') or [''])[0].strip()
                    if raw == '':
                        values[(t, i)] = None
                        if mode == 'submit':
                            missing = True
                        continue
                    try:
                        val = float(raw)
                    except ValueError:
                        invalid = True
                        continue
                    if not (0 <= val <= crit[3]):
                        invalid = True
                    values[(t, i)] = val

            if mode == 'submit' and missing:
                return self.redirect('/evaluate?judge=' + urllib.parse.quote(judge) + '&alert=missing')
            if invalid:
                return self.redirect('/evaluate?judge=' + urllib.parse.quote(judge) + '&alert=range')

            c = conn()
            now = datetime.now().isoformat(timespec='seconds')
            for (t, i), val in values.items():
                if val is None:
                    # 임시저장에서 사용자가 값을 지운 경우 DB에서도 지움
                    if mode == 'draft':
                        c.execute('DELETE FROM scores WHERE judge=? AND team=? AND criterion_idx=?', (judge, t, i))
                    continue
                c.execute('''INSERT INTO scores(judge,team,criterion_idx,score,updated_at)
                             VALUES(?,?,?,?,?)
                             ON CONFLICT(judge,team,criterion_idx)
                             DO UPDATE SET score=excluded.score,updated_at=excluded.updated_at''',
                          (judge, t, i, val, now))

            status = 'submitted' if mode == 'submit' else 'draft'
            c.execute('''INSERT INTO submissions(judge,status,updated_at) VALUES(?,?,?)
                         ON CONFLICT(judge) DO UPDATE SET status=excluded.status,updated_at=excluded.updated_at''',
                      (judge, status, now))
            c.commit()
            c.close()
            saved = 'submitted' if mode == 'submit' else 'draft'
            return self.redirect('/evaluate?judge=' + urllib.parse.quote(judge) + '&saved=' + saved)

        if self.path == '/admin/finalize':
            f = parse_form(self)
            pin = (f.get('pin') or [''])[0]
            if pin != ADMIN_PIN:
                return self.redirect('/admin')
            c = conn()
            results = compute_rankings(c)
            now = datetime.now().isoformat(timespec='seconds')
            c.execute('DELETE FROM rankings')
            for r in results:
                high_judge, high_score = (r['high'] if r['high'] else (None, None))
                low_judge, low_score = (r['low'] if r['low'] else (None, None))
                c.execute('''INSERT INTO rankings(team,final_score,rank_no,judge_count,high_judge,high_score,low_judge,low_score,saved_at)
                             VALUES(?,?,?,?,?,?,?,?,?)''',
                          (r['team'], r['final_score'], r['rank_no'], r['judge_count'],
                           high_judge, high_score, low_judge, low_score, now))
            c.commit()
            c.close()
            return self.redirect('/admin?pin=' + urllib.parse.quote(ADMIN_PIN))

        self.send_error(404)

    def log_message(self, fmt, *args):
        pass


if __name__ == '__main__':
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        local_ip = '담당자 노트북 IP'
    print('\nCoP 평가 시스템 실행 중')
    print(f'담당자: http://127.0.0.1:{PORT}')
    print(f'심사위원 접속 예시: http://{local_ip}:{PORT}')
    print(f'관리자: http://{local_ip}:{PORT}/admin  (기본 PIN: {ADMIN_PIN})\n')
    ThreadingHTTPServer((HOST, PORT), H).serve_forever()
