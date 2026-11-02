# CoP 결과발표회 평가시스템 (GitHub Pages + Supabase)

## 개요
- 심사위원은 **직원번호**만 입력해서 로그인
- 관리자는 **심사위원(직원번호 / 표시 이름)** 등록·수정 가능
- 심사위원은 팀 A~F를 평가하고 **임시저장 / 최종제출** 가능
- 관리자는 심사위원별 원점수 확인 가능
- 팀별 **최고점 1개 + 최저점 1개 제외 평균**으로 순위 산정
- GitHub Pages로 무료 HTTPS 배포 가능

---

## 1. Supabase 준비
1. https://supabase.com 에서 무료 프로젝트 생성
2. 좌측 **SQL Editor**에서 `supabase_schema.sql` 전체 실행
3. 좌측 **Authentication > Users** 에서 관리자 계정 생성
   - 예: `admin@example.com` / 원하는 비밀번호
4. `public.admin_emails` 테이블에 관리자 이메일이 들어있는지 확인
   - 기본 예시는 `admin@example.com`
5. 좌측 **Project Settings > API**에서 다음 값 복사
   - Project URL
   - anon public key

---

## 2. config.js 만들기
`js/config.example.js`를 복사해서 `js/config.js` 파일 생성 후 값 입력

```javascript
export const SUPABASE_URL = 'https://YOUR-PROJECT.supabase.co';
export const SUPABASE_ANON_KEY = 'YOUR_SUPABASE_ANON_KEY';
```

---

## 3. GitHub Pages 배포
1. GitHub 새 저장소 생성
2. 현재 폴더 파일 전체 업로드
3. 저장소 `Settings > Pages`
4. **Source = Deploy from a branch**
5. Branch는 `main` / folder는 `/root`
6. 저장 후 1~3분 대기
7. 배포 주소 확인
   - 예: `https://아이디.github.io/cop-evaluation/`

> `.nojekyll` 파일이 들어 있어서 Pages에서 정적 파일이 그대로 배포됩니다.

---

## 4. 사용 방법
### 심사위원
- `index.html` 접속
- 직원번호 입력
- 관리자 등록값이 있으면 해당 이름으로 로그인됨
- 평가 후 `임시저장` 또는 `최종 제출`
- 최종 제출 시 값이 하나라도 비어 있으면 `모든 값을 입력해주시기 바랍니다.` 알림 표시

### 관리자
- `admin.html` 접속
- Supabase 인증 이메일/비밀번호로 로그인
- 심사위원 추가/수정 가능
- 심사위원별 상태 / 입력 개수 / 팀별 총점 / 상세 점수 확인 가능
- `팀별 점수·순위 저장` 클릭 시 ranking snapshot 저장
- `Excel 다운로드` 가능

---

## 5. 점수 계산 방식
- 제출 완료된 심사위원 점수만 반영
- 각 팀별 총점을 모아
  - 최고점 1개 제외
  - 최저점 1개 제외
  - 나머지 평균 사용
- 제출 인원이 3명 미만이면 제외 없이 평균 사용

---

## 6. 데이터 구조 요약
- `judges`: 직원번호 / 표시 이름
- `judge_sessions`: 로그인한 심사위원과 Supabase 익명 사용자 연결
- `evaluation_forms`: 심사위원의 평가 데이터(JSON)
- `ranking_snapshots`: 관리자가 저장한 순위 결과
- `admin_emails`: 관리자 이메일 목록

---

## 7. 주의사항
- **직원번호만으로 로그인**하는 구조이므로, 보안 강도가 높은 서비스에는 적합하지 않습니다.
- 사내 행사 / 내부 평가 목적에 맞는 간편형 구조입니다.
- 더 강한 보안을 원하면 심사위원별 PIN 추가 또는 Supabase Auth 계정화를 추천합니다.

---

## 8. 추천 추가개선
원하면 다음도 추가 가능
- 심사위원별 PIN 4자리 추가
- 팀명 A~F 대신 실제 팀명 사용
- 평가 마감시간 이후 제출 차단
- 관리자 화면 PDF 출력
