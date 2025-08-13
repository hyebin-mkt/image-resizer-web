# pages/mbm_object_form.py
import json, uuid, time, datetime
import requests
import streamlit as st

# =============== 페이지 헤더 ===============
st.set_page_config(page_title="🧚🏻‍♂️ MBM Magic Wizard", page_icon="📄", layout="centered")
st.title("🧚🏻‍♂️ MBM Magic Wizard")
st.caption("MBM 오브젝트 형성부터 마케팅 에셋까지 한번에 만들어줄게요.")

# =============== 설정값 & 상수 ===============
TOKEN = st.secrets.get("HUBSPOT_PRIVATE_APP_TOKEN", "")
if not TOKEN:
    st.error("Streamlit Secrets에 HUBSPOT_PRIVATE_APP_TOKEN이 없습니다.")
    st.stop()

PORTAL_ID = st.secrets.get("PORTAL_ID", "2495902")
HUBSPOT_REGION = "na1"

# Website Page 템플릿 (Website 전용)
LANDING_PAGE_TEMPLATE_ID = st.secrets.get("LANDING_PAGE_TEMPLATE_ID", "192676141393")
WEBSITE_PAGE_TEMPLATE_TITLE = st.secrets.get("WEBSITE_PAGE_TEMPLATE_TITLE", "")

# Email 템플릿
EMAIL_TEMPLATE_ID = st.secrets.get("EMAIL_TEMPLATE_ID", "162882078001")

# Register Form 템플릿(guid)
REGISTER_FORM_TEMPLATE_GUID = "83e40756-9929-401f-901b-8e77830d38cf"

# MBM 오브젝트 기본 설정
MBM_HIDDEN_FIELD_NAME = "title"  # Register Form 숨김 필드 이름
ACCESS_PASSWORD = "mid@sit0901"  # 사이드바 보호

HS_BASE = "https://api.hubapi.com"
HEADERS_JSON = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# =============== 세션 상태 ===============
ss = st.session_state
ss.setdefault("auth_ok", False)
ss.setdefault("active_stage", 1)      # 1=제출, 2=선택, 3=공유
ss.setdefault("mbm_submitted", False) # ① 완료 여부 (MBM 오브젝트 생성 완료)
ss.setdefault("mbm_title", "")
ss.setdefault("show_prop_form", False) # ① 내부에서: 타이틀 '다음' 누르면 상세 폼 표시
ss.setdefault("results", None)         # {"title": str, "links": dict}
ss.setdefault("mbm_object", None)      # {"id": "...", "typeId": "...", "url": "record url"}

# =============== 사이드바 암호 확인 ===============
with st.sidebar:
    st.header("🔒 Access")
    if not ss.auth_ok:
        pwd = st.text_input("암호 입력", type="password", placeholder="비밀번호를 입력하세요")
        if st.button("접속"):
            if pwd == ACCESS_PASSWORD:
                ss.auth_ok = True
                st.rerun()
            else:
                st.error("암호가 일치하지 않습니다.")

if not ss.auth_ok:
    st.stop()

# =============== 유틸 ===============
def ordinal(n: int) -> str:
    n = int(n)
    if 10 <= (n % 100) <= 20: suf = "th"
    else: suf = {1:"st", 2:"nd", 3:"rd"}.get(n % 10, "th")
    return f"{n}{suf}"

def copy_button(text: str, key: str):
    safe = json.dumps(text)
    st.components.v1.html(
        f"""
        <button id="copybtn_{key}" title="복사"
          style="padding:8px 10px;border:1px solid #e5e7eb;border-radius:10px;background:#fff;cursor:pointer;">📋</button>
        <span id="copied_{key}" style="display:none;margin-left:6px;color:#16a34a;font-size:12px;">복사됨</span>
        <script>
        document.getElementById('copybtn_{key}').onclick=()=>{{
          navigator.clipboard.writeText({safe}).then(() => {{
            const m=document.getElementById('copied_{key}');
            m.style.display='inline'; setTimeout(()=>{{m.style.display='none'}}, 1500);
          }});
        }};
        </script>
        """,
        height=40, width=120
    )

def to_epoch_ms(d: datetime.date | None) -> str | None:
    if not d: return None
    # 날짜 00
