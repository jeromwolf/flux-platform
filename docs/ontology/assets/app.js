/* ===================================================================
   IMSP 프로젝트 워크벤치 — 공통 스크립트
=================================================================== */

/* ---- 태스크 정의 (단일 원천) ---- */
const TASKS = [
  { code:'REQ-001', title:'해사 데이터 현황 조사 및 의미적 연관성 분석', file:'req-001.html', stage:1, owner:'이부일·이재현', deadline:'M+2', status:'active'  },
  { code:'REQ-002', title:'지식그래프 구축 대상 자산 선정 및 로드맵',     file:'req-002.html', stage:1, owner:'이부일·이재현', deadline:'M+2', status:'pending' },
  { code:'REQ-003', title:'그래프 DB 기술 조사 및 최적 솔루션 평가',     file:'req-003.html', stage:1, owner:'신동욱',       deadline:'M+2', status:'pending' },
  { code:'REQ-004', title:'해사 도메인 국제 표준 및 온톨로지 매핑 분석', file:'req-004.html', stage:1, owner:'양선희',       deadline:'M+5', status:'pending' },
  { code:'DES-001', title:'해사 도메인 온톨로지 모델 설계',               file:'des-001.html', stage:2, owner:'양선희',       deadline:'M+5', status:'pending' },
  { code:'DES-002', title:'지식그래프 물리 스키마 설계',                   file:'des-002.html', stage:2, owner:'신동욱',       deadline:'M+5', status:'pending' },
  { code:'DES-003', title:'멀티모달 데이터 ETL 파이프라인 설계',          file:'des-003.html', stage:2, owner:'이부일·이재현', deadline:'M+5', status:'pending' },
  { code:'DES-004', title:'지식 탐색·복합 질의 아키텍처 설계',           file:'des-004.html', stage:2, owner:'양선희·신동욱', deadline:'M+5', status:'pending' },
  { code:'TER-001', title:'PoC 구축 및 기능 검증',                         file:'ter-001.html', stage:3, owner:'신동욱',       deadline:'M+7', status:'pending' },
  { code:'TER-002', title:'지식그래프 시각화·탐색 인터페이스 PoC',       file:'ter-002.html', stage:3, owner:'신동욱',       deadline:'M+7', status:'pending' },
  { code:'COM-001', title:'보안 요건',                                     file:'com-001.html', stage:'com', owner:'전원',    deadline:'상시', status:'active'  },
  { code:'COM-002', title:'기술 지원 (연구소 교육)',                       file:'com-002.html', stage:'com', owner:'양선희·신동욱', deadline:'요청 시', status:'pending' },
  { code:'COM-003', title:'상호 협의',                                     file:'com-003.html', stage:'com', owner:'전원',    deadline:'상시', status:'active'  },
  { code:'COM-004', title:'필요 장비 및 SW 확보',                          file:'com-004.html', stage:'com', owner:'신동욱',  deadline:'M+5 이전', status:'pending' },
  { code:'COM-005', title:'GitHub 산출물 관리',                            file:'com-005.html', stage:'com', owner:'전원',    deadline:'상시', status:'active'  },
];

const STAGE_META = {
  1:   { label:'1단계 · 데이터 분석',  color:'#0d7377' },
  2:   { label:'2단계 · 모델 설계',     color:'#2196f3' },
  3:   { label:'3단계 · PoC 검증',      color:'#f0a500' },
  com: { label:'공통 · 방법론',          color:'#27ae60' },
};

/* ---- 경로 prefix (index.html=루트, 하위 폴더=../) ---- */
const IN_SUB = location.pathname.includes('/tasks/') || location.pathname.includes('/meetings/');
const ROOT = IN_SUB ? '../' : '';

/* ---- 사이드바 렌더 ---- */
function renderSidebar(currentCode) {
  const el = document.getElementById('sidebar');
  if (!el) return;

  const doneCount = TASKS.filter(t => t.status === 'done').length;
  const pct = Math.round((doneCount / TASKS.length) * 100);

  let groups = '';
  for (const stage of [1, 2, 3, 'com']) {
    const items = TASKS.filter(t => t.stage === stage);
    if (!items.length) continue;
    const m = STAGE_META[stage];
    let links = '';
    for (const t of items) {
      const active = t.code === currentCode ? ' active' : '';
      const stCls = t.status === 'done' ? 'done' : t.status === 'active' ? 'active' : '';
      const stTxt = t.status === 'done' ? '완료' : t.status === 'active' ? '진행' : '대기';
      links += `<a class="sb-link${active}" href="${ROOT}tasks/${t.file}">
        <span class="dot" style="background:${m.color}"></span>
        <span class="sb-code">${t.code}</span>
        <span class="sb-st ${stCls}">${stTxt}</span></a>`;
    }
    groups += `<div class="sb-group">
      <div class="sb-group-title">${m.label}</div>${links}</div>`;
  }

  // 온톨로지 방법론 링크
  groups += `<div class="sb-group">
    <div class="sb-group-title">온톨로지 방법론</div>
    <a class="sb-link" href="${ROOT}stanford_7step_ontology.html">
      <span class="dot" style="background:#9c6ade"></span>
      <span class="sb-code">Stanford 7-Step</span></a></div>`;

  el.innerHTML = `
    <div class="sb-brand">
      <a href="${ROOT}index.html">
        <div class="sb-logo">IMSP <span>워크벤치</span></div>
        <div class="sb-sub">지식그래프 모델 설계 연구 용역</div>
      </a>
    </div>
    <div class="sb-progress">
      <div class="sb-progress-label"><span>전체 태스크</span><span>${doneCount}/${TASKS.length} 완료</span></div>
      <div class="sb-bar"><div class="sb-bar-fill" style="width:${pct}%"></div></div>
    </div>
    <nav class="sb-nav">
      <a class="sb-home" href="${ROOT}index.html">⬚  프로젝트 대시보드</a>
      <a class="sb-home" href="${ROOT}kickoff-report.html">▣  착수보고서 (Draft)</a>
      <a class="sb-home" href="${ROOT}meetings.html">▦  회의록</a>
      <a class="sb-home" href="${ROOT}submissions.html">▤  제출 문서 관리</a>
      <a class="sb-home" href="${ROOT}cooperation.html">✉  KRISO 협조 요청</a>
      <a class="sb-home" href="${ROOT}references.html">⌕  조사 참고자료</a>
      ${groups}
    </nav>`;
}

/* ---- 체크리스트 localStorage 저장/복원 ---- */
function initChecklists() {
  const checks = document.querySelectorAll('.check[data-ck]');
  checks.forEach(row => {
    const key = 'imsp:ck:' + row.dataset.ck;
    const box = row.querySelector('input[type=checkbox]');
    if (localStorage.getItem(key) === '1') {
      box.checked = true;
      row.classList.add('checked');
    }
    const sync = () => {
      row.classList.toggle('checked', box.checked);
      localStorage.setItem(key, box.checked ? '1' : '0');
      updateInlineProgress();
    };
    box.addEventListener('change', sync);
    row.addEventListener('click', e => {
      if (e.target.tagName === 'A') return;
      if (e.target !== box) { box.checked = !box.checked; sync(); }
    });
  });
  updateInlineProgress();
}

/* ---- 페이지 내 체크리스트 진행률 ---- */
function updateInlineProgress() {
  const bar = document.getElementById('inlineProgress');
  if (!bar) return;
  const checks = document.querySelectorAll('.check[data-ck]');
  if (!checks.length) return;
  const done = [...checks].filter(c => c.querySelector('input').checked).length;
  const pct = Math.round((done / checks.length) * 100);
  bar.querySelector('.ip-fill').style.width = pct + '%';
  bar.querySelector('.ip-text').textContent = `${done} / ${checks.length} 완료 (${pct}%)`;
}

/* ---- 문제점 아코디언 ---- */
function initIssues() {
  document.querySelectorAll('.issue-head').forEach(head => {
    head.addEventListener('click', () => {
      const body = head.nextElementSibling;
      if (!body) return;
      const open = body.style.display !== 'none';
      body.style.display = open ? 'none' : 'block';
    });
    // 기본: 펼침
    const body = head.nextElementSibling;
    if (body) body.style.display = 'block';
  });
}

/* ---- 모바일 사이드바 토글 ---- */
function initMobileToggle() {
  const btn = document.getElementById('sbToggle');
  if (!btn) return;
  btn.addEventListener('click', () => {
    document.querySelector('.sidebar').classList.toggle('open');
  });
}

/* ---- 초기화 ---- */
document.addEventListener('DOMContentLoaded', () => {
  renderSidebar(document.body.dataset.task || '');
  initChecklists();
  initIssues();
  initMobileToggle();
});
