"use strict";
const payments=[
  {id:"demo-pay-001",customer:"게스트 01",method:"신용카드 · 1234",amount:"₩84,000",status:"승인 완료",tone:"success",time:"14:32"},
  {id:"demo-pay-002",customer:"게스트 02",method:"간편결제",amount:"₩126,500",status:"승인 완료",tone:"success",time:"14:28"},
  {id:"demo-pay-003",customer:"게스트 03",method:"신용카드 · 9081",amount:"₩32,000",status:"처리 중",tone:"pending",time:"14:19"},
  {id:"demo-pay-004",customer:"게스트 04",method:"계좌이체",amount:"₩215,000",status:"승인 실패",tone:"failed",time:"14:03"}
];
const escapeHtml=value=>String(value).replace(/[&<>'"]/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[char]);
const rows=document.querySelector("#payment-rows");
function renderRows(query=""){
  if(!rows)return;
  const needle=query.trim().toLowerCase();
  const visible=payments.filter(item=>`${item.id} ${item.customer}`.toLowerCase().includes(needle));
  rows.innerHTML=visible.map(item=>`<tr><td><a href="/guest/payments/${encodeURIComponent(item.id)}">${escapeHtml(item.id)}</a><small>demo-order</small></td><td>${escapeHtml(item.customer)}<small>가상 고객</small></td><td>${escapeHtml(item.method)}</td><td><b>${escapeHtml(item.amount)}</b></td><td><span class="status ${item.tone}">${escapeHtml(item.status)}</span></td><td>${escapeHtml(item.time)}</td><td><a class="row-link" href="/guest/payments/${encodeURIComponent(item.id)}" aria-label="${escapeHtml(item.id)} 상세 보기">›</a></td></tr>`).join("");
  document.querySelector(".empty")?.toggleAttribute("hidden",visible.length!==0);
}
renderRows();
document.querySelector("input[type=search]")?.addEventListener("input",event=>renderRows(event.target.value));
const menu=document.querySelector(".menu");
menu?.addEventListener("click",()=>{const open=document.body.classList.toggle("nav-open");menu.setAttribute("aria-expanded",String(open));});
document.addEventListener("click",event=>{if(document.body.classList.contains("nav-open")&&!event.target.closest(".sidebar")&&!event.target.closest(".menu")){document.body.classList.remove("nav-open");menu?.setAttribute("aria-expanded","false");}});
const dialog=document.querySelector("dialog");
const dialogContent={
  guest:["게스트 체험 계정","상용 인증 전 분석을 위한 임시 계정입니다. 합성 데이터의 조회만 가능하며 실제 운영 데이터나 변경 기능에는 연결되지 않습니다."],
  access:["게스트 권한 범위","허용: 합성 대시보드와 가상 결제 상세 탐색. 차단: 실제 DB·운영 데이터·비밀키·결제키·Webhook 원문 및 모든 결제·재처리·설정 변경."],
  report:["분석 리포트 미리보기","가상 거래의 승인율, 처리 흐름, 정산 상태를 화면에서 분석할 수 있습니다. 파일 내보내기는 정식 인증 적용 후 제공됩니다."],
  status:["상태 집계 기준","표시된 수치는 화면 구조 분석을 위해 고정 생성된 합성 데이터이며 실제 운영 성과를 의미하지 않습니다."],
  blocked:["게스트 작업 차단","읽기 전용 체험 환경에서는 금전 또는 운영 상태를 변경하는 작업을 실행할 수 없습니다. 이 버튼은 동작을 설명하기 위한 시뮬레이션입니다."],
  commercial:["상용 인증 준비 중","로그인·회원가입·본인인증은 상용화 단계에서 연결됩니다. 현재는 개인정보를 수집하지 않는 게스트 분석 모드만 제공합니다."]
};
document.querySelectorAll("[data-dialog]").forEach(button=>button.addEventListener("click",()=>{const [title,copy]=dialogContent[button.dataset.dialog];dialog.querySelector("h2").textContent=title;dialog.querySelector(".dialog-copy").textContent=copy;dialog.showModal();}));
dialog?.querySelector(".dialog-close")?.addEventListener("click",()=>dialog.close());
dialog?.addEventListener("click",event=>{if(event.target===dialog)dialog.close();});
const pathId=decodeURIComponent(location.pathname.split("/").pop()||"");
if(document.querySelector("#detail-id")&&/^demo-pay-\d{3}$/.test(pathId)){document.querySelector("#detail-id").textContent=pathId;document.querySelector("#crumb-id").textContent=pathId;}
