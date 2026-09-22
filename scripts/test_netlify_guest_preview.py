"""Post-deploy smoke test for the synthetic-only Netlify guest preview."""
from __future__ import annotations
import sys
from urllib.request import Request,urlopen

def get(base:str,path:str)->tuple[str,dict[str,str]]:
 request=Request(base.rstrip("/")+path,headers={"User-Agent":"nurion-pg-preview-audit/1"})
 with urlopen(request,timeout=15) as response:return response.read().decode(),{k.lower():v for k,v in response.headers.items()}

def main()->None:
 if len(sys.argv)!=2 or not sys.argv[1].startswith("https://"):raise SystemExit("usage: test_netlify_guest_preview.py https://deploy-url")
 base=sys.argv[1]
 home,headers=get(base,"/guest");detail,_=get(base,"/guest/payments/demo-pay-001");script,_=get(base,"/guest/assets/app.js")
 assert "게스트 분석 모드" in home and "합성 데이터" in home and "disabled" in home
 assert "합성 결제 상세" in detail and "변경 작업은 사용할 수 없습니다" in detail
 assert "fetch(" not in script and "/v1/merchants" not in script
 assert headers.get("x-frame-options")=="DENY" and headers.get("x-content-type-options")=="nosniff"
 assert "payment=()" in headers.get("permissions-policy","") and "no-store" in headers.get("cache-control","")
 print("Netlify guest preview smoke: PASS")
if __name__=="__main__":main()
