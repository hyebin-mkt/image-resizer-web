# pages/mbm_object_form.py
import json, uuid
import requests
import streamlit as st

# =============== 페이지 & 상단 바 ===============
st.set_page_config(page_title="MBM Object 생성기", page_icon="📄", layout="centered")

# 상단: 타이틀 + 예쁜 Refresh 버튼(아이콘+Refresh)
c_title, c_refresh = st.columns([7, 1])
with c_title:
    st.title("MBM Object 생성기")
with c_refresh:
    # 더 예쁜 버튼을 위한 약간의 스타일
    st.markdown("""
        <style>
        .refresh-btn button{
            border: 1px solid #e5e7eb; border-radius: 10px; background: #ffffff;
            padding: 0.45rem 0.8rem; font-weight: 600; box-shadow: 0 1px 2px rgba(0,0,0,.06);
        }
        .refresh-btn button:hover{ background:#f9fafb; }
        </style>
    """, unsafe_allow_html=True)
    with st.container():
        if st.button("🔁 아이콘+Refresh", key="refresh_btn", help="캐시/상태를 초기화합니다.", type="secondary"):
            try:
                st.cache_data.clear()
                st.cache_resource.clear()
            except Exception:
                pass
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

st.caption("MBM 오브젝트 형성부터 마케팅 에셋 복제까지 한번에 실행하세요")

# 전역 스타일: 탭은 항상 오른쪽으로 “늘어나는” 것처럼 보이게
st.markdown("""
<style>
/* 활성 탭을 내부적으로 첫 칸에 두더라도, 시각적으로는 ①→②→③ 순으로 보이게 */
div.stTabs [role="tablist"] { flex-direction: row-reverse; }
</style>
""", unsafe_allow_html=True)

# =============== 설정값 & 상수 ===============
TOKEN = st.secrets.get("HUBSPOT_PRIVATE_APP_TOKEN", "")
if not TOKEN:
    st.error("Streamlit Secrets에 HUBSPOT_PRIVATE_APP_TOKEN이 없습니다.")
    st.stop()

PORTAL_ID = st.secrets.get("PORTAL_ID", "2495902")
HUBSPOT_REGION = "na1"
LANDING_PAGE_TEMPLATE_ID = st.secrets.get("LANDING_PAGE_TEMPLATE_ID", "192676141393")
EMAIL_TEMPLATE_ID        = st.secrets.get("EMAIL_TEMPLATE_ID", "162882078001")
REGISTER_FORM_TEMPLATE_GUID = "83e40756-9929-401f-901b-8e77830d38cf"  # 고정
MBM_HIDDEN_FIELD_NAME = "title"
FORM_ID_FOR_EMBED = st.secrets.get("FORM_ID_FOR_EMBED", "a9e1a5e8-4c46-461f-b823-13cc4772dc6c")

HS_BASE = "https://api.hubapi.com"
HEADERS_JSON = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# =============== 세션 상태 ===============
ss = st.session_state
ss.setdefault("active_stage", 1)        # 1=제출, 2=선택, 3=공유
ss.setdefault("mbm_submitted", False)   # ① 제출 완료 여부
ss.setdefault("mbm_title", "")
ss.setdefault("results", None)          # {"title": str, "links": dict}

# =============== 유틸 ===============
def ordinal(n: int) -> str:
    n = int(n)
    if 10 <= (n % 100) <= 20: suf = "th"
    else: suf = {1:"st",2:"nd",3:"rd"}.get(n%10,"th")
    return f"{n}{suf}"

def copy_button(text: str, key: str):
    """실제로 복사되는 작고 예쁜 버튼"""
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

# =============== HubSpot API ===============
def _clone_page(endpoint: str, template_id: str, clone_name: str):
    url = f"{HS_BASE}{endpoint}"
    last_err = None
    for key in ("name", "cloneName"):
        try:
            r = requests.post(url, headers=HEADERS_JSON,
                              json={"id": str(template_id), key: clone_name},
                              timeout=45)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as e:
            last_err = e
    raise last_err

def hs_clone_page_auto(template_id: str, clone_name: str):
    try:
        data = _clone_page("/cms/v3/pages/landing-pages/clone", template_id, clone_name)
        return data, "landing"
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            data = _clone_page("/cms/v3/pages/site-pages/clone", template_id, clone_name)
            return data, "site"
        raise

def hs_push_live(page_id: str, page_type: str) -> None:
    if page_type == "site":
        url = f"{HS_BASE}/cms/v3/pages/site-pages/{page_id}/draft/push-live"
    else:
        url = f"{HS_BASE}/cms/v3/pages/landing-pages/{page_id}/draft/push-live"
    r = requests.post(url, headers={"Authorization": f"Bearer {TOKEN}", "Accept": "*/*"}, timeout=30)
    r.raise_for_status()

def hs_update_page_name(page_id: str, page_type: str, new_name: str):
    if page_type == "site":
        url = f"{HS_BASE}/cms/v3/pages/site-pages/{page_id}"
    else:
        url = f"{HS_BASE}/cms/v3/pages/landing-pages/{page_id}"
    r = requests.patch(url, headers=HEADERS_JSON, json={"name": new_name}, timeout=30)
    if r.status_code >= 400:
        st.warning(f"페이지 내부 이름 변경 실패: {r.status_code}")

def hs_clone_marketing_email(template_email_id: str, clone_name: str) -> dict:
    url = f"{HS_BASE}/marketing/v3/emails/clone"
    last_err = None
    for key in ("emailName", "name", "cloneName"):
        try:
            r = requests.post(url, headers=HEADERS_JSON,
                              json={"id": str(template_email_id), key: clone_name},
                              timeout=45)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as e:
            last_err = e
    raise last_err

def hs_update_email_name(email_id: str, new_name: str):
    url = f"{HS_BASE}/marketing/v3/emails/{email_id}"
    r = requests.patch(url, headers=HEADERS_JSON, json={"name": new_name}, timeout=30)
    if r.status_code >= 400:
        st.warning(f"이메일 내부 이름 변경 실패: {r.status_code}")

# ---- Forms v2: Register Form 복제 + 숨김값 주입 ----
FORMS_V2 = "https://api.hubapi.com/forms/v2"

def hs_get_form_v2(form_guid: str) -> dict:
    url = f"{FORMS_V2}/forms/{form_guid}"
    r = requests.get(url, headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    return r.json()

def _strip_field_for_create(field: dict) -> dict:
    allow = {"name","label","type","fieldType","required","hidden","defaultValue",
             "placeholder","validation","displayAsCheckbox","options","description","inlineHelpText"}
    return {k: v for k, v in field.items() if k in allow}

def _normalize_groups(form_json: dict) -> list[dict]:
    groups = []
    for g in form_json.get("formFieldGroups", []):
        fields = [_strip_field_for_create(f) for f in g.get("fields", [])]
        groups.append({"fields": fields})
    return groups

def hs_create_form_v2(payload: dict) -> dict:
    url = f"{FORMS_V2}/forms"
    r = requests.post(url, headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
                      json=payload, timeout=45)
    r.raise_for_status()
    return r.json()

def clone_form_with_hidden_value(template_guid: str, new_name: str, hidden_value: str, hidden_field_name: str) -> dict:
    tpl = hs_get_form_v2(template_guid)
    groups = _normalize_groups(tpl)

    found = False
    for g in groups:
        for f in g["fields"]:
            if f.get("name") == hidden_field_name:
                f["hidden"] = True
                f["defaultValue"] = hidden_value
                found = True
    if not found:
        if not groups:
            groups = [{"fields": []}]
        groups[-1]["fields"].append({
            "name": hidden_field_name,
            "label": "MBM Title (auto)",
            "type": "string",
            "fieldType": "text",
            "hidden": True,
            "defaultValue": hidden_value,
        })

    payload = {
        "name": new_name,
        "method": tpl.get("method", "POST"),
        "redirect": tpl.get("redirect", ""),
        "submitText": tpl.get("submitText", "Submit"),
        "formFieldGroups": groups,
    }
    return hs_create_form_v2(payload)

# =============== 탭 구성 ===============
TAB1 = "MBM 오브젝트 제출"
TAB2 = "후속 작업 선택"
TAB3 = "최종 링크 공유"

def make_tabs():
    # “활성 탭을 첫 칸”에 두고(자동 전환 효과), CSS로는 row-reverse라 시각적 순서는 ①→②→③로 보임
    if ss.active_stage == 1:
        labels = [TAB1, TAB2, TAB3]
    elif ss.active_stage == 2:
        labels = [TAB2, TAB1, TAB3]
    else:  # 3
        labels = [TAB3, TAB2, TAB1]
    t = st.tabs(labels)
    return t, {label: i for i, label in enumerate(labels)}

tabs, idx = make_tabs()

# =============== 탭①: MBM 오브젝트 제출 ===============
with tabs[idx[TAB1]]:
    st.markdown("### ① MBM 오브젝트 제출")

    # (수정 3) 라벨/헬프 텍스트 변경
    st.markdown("**MBM 오브젝트 타이틀 설정**")
    st.markdown("네이밍 규칙: `[국가코드] YYYYMMDD 웨비나명` 형식으로 입력하세요.", help=None)
    c1, c2 = st.columns([6, 1])
    with c1:
        ss.mbm_title = st.text_input(
            "폼의 'Title'과 동일하게 입력",
            key="mbm_title_input",
            value=ss.mbm_title,
            placeholder="[EU] 20250803 GTS NX Webinar",
            label_visibility="collapsed",
        )
    with c2:
        copy_button(ss.mbm_title, key=f"title_{uuid.uuid4()}")

    # (수정 2/4) 제출 후에는 폼 iFrame/헬프텍스트 숨김
    if not ss.mbm_submitted:
        st.markdown("#### MBM Object Create Form\n(내부 구성원 MBM Object 생성용)")
        FORM_IFRAME_HEIGHT = 1200
        html = f"""
        <div id="hubspot-form"></div>
        <script>
        (function() {{
          var s = document.createElement('script');
          s.src = "https://js.hsforms.net/forms/v2.js";
          s.async = true;
          s.onload = function() {{
            if (!window.hbspt) return;
            window.hbspt.forms.create({{
              region: "{HUBSPOT_REGION}",
              portalId: "{PORTAL_ID}",
              formId: "{FORM_ID_FOR_EMBED}",
              target: "#hubspot-form",
              inlineMessage: "제출 완료! 상단 탭이 ‘후속 작업 선택’으로 전환됩니다."
            }});
          }};
          document.body.appendChild(s);
        }})();
        </script>
        """
        st.components.v1.html(html, height=FORM_IFRAME_HEIGHT, scrolling=False)

        st.info("폼을 제출한 뒤, 아래 버튼을 누르면 ‘후속 작업 선택’ 탭으로 전환됩니다.")
        if st.button("폼 제출 완료 → ‘후속 작업 선택’ 탭 열기", type="primary"):
            ss.mbm_submitted = True
            ss.active_stage = 2         # 자동으로 ②로 이동
            st.rerun()

# =============== 탭②: 후속 작업 선택 ===============
if ss.mbm_submitted:
    with tabs[idx[TAB2]]:
        st.markdown("### ② 후속 작업 선택")

        with st.form("post_submit_actions"):
            c1, c2 = st.columns([2, 1], gap="large")
            with c1:
                st.markdown("**MBM 오브젝트 타이틀 (읽기 전용)**")
                st.text_input("MBM Title", value=ss.mbm_title, disabled=True, label_visibility="collapsed")
            with c2:
                st.markdown("**생성할 자산**")
                make_lp = st.checkbox("랜딩/웹페이지 복제", value=True)
                make_em = st.checkbox("이메일 복제", value=True)
                email_count = st.number_input("이메일 복제 개수", min_value=1, max_value=10, value=1, step=1)

            submitted_actions = st.form_submit_button("생성하기", type="primary")

        if submitted_actions:
            if not ss.mbm_title:
                st.error("① 탭에서 MBM 오브젝트 타이틀을 입력하세요.")
                st.stop()

            links = {"Landing Page": [], "Email": [], "Form": []}

            try:
                # --- 페이지 클론 & 내부명 업데이트 & 퍼블리시 ---
                if make_lp:
                    page_name = f"{ss.mbm_title}_landing page"
                    with st.spinner(f"페이지 복제 중… ({page_name})"):
                        page_data, used_type = hs_clone_page_auto(LANDING_PAGE_TEMPLATE_ID, page_name)
                        page_id = str(page_data.get("id") or page_data.get("objectId") or "")
                        hs_update_page_name(page_id, used_type, page_name)
                        hs_push_live(page_id, used_type)
                        if used_type == "site":
                            edit_url = f"https://app.hubspot.com/cms/{PORTAL_ID}/website/pages/{page_id}/edit"
                        else:
                            edit_url = f"https://app.hubspot.com/cms/{PORTAL_ID}/pages/{page_id}/edit"
                        public_url = page_data.get("url") or page_data.get("publicUrl") or ""
                        links["Landing Page"].append(("편집", edit_url))
                        if public_url:
                            links["Landing Page"].append(("공개", public_url))

                # --- 이메일 N개 클론 & 내부명 업데이트 ---
                if make_em:
                    for i in range(1, int(email_count) + 1):
                        email_name = f"{ss.mbm_title}_email_{ordinal(i)}"
                        with st.spinner(f"마케팅 이메일 복제 중… ({email_name})"):
                            em = hs_clone_marketing_email(EMAIL_TEMPLATE_ID, email_name)
                            em_id = str(em.get("id") or em.get("contentId") or "")
                            hs_update_email_name(em_id, email_name)
                            edit_url = f"https://app.hubspot.com/email/{PORTAL_ID}/edit/{em_id}/settings"
                            links["Email"].append((f"Email {ordinal(i)}", edit_url))

                # --- Register Form 클론 & 숨김 필드 주입 ---
                form_name = f"{ss.mbm_title}_register form"
                with st.spinner(f"Register Form 복제 중… ({form_name})"):
                    new_form = clone_form_with_hidden_value(
                        REGISTER_FORM_TEMPLATE_GUID, form_name, ss.mbm_title, MBM_HIDDEN_FIELD_NAME
                    )
                    new_guid = new_form.get("guid") or new_form.get("id")
                    edit_url = f"https://app.hubspot.com/forms/{PORTAL_ID}/{new_guid}/edit"
                    links["Form"].append(("편집", edit_url))

                ss.results = {"title": ss.mbm_title, "links": links}
                ss.active_stage = 3        # (수정1) 생성 후 ③으로 확실히 전환
                st.success("생성이 완료되었습니다. ‘최종 링크 공유’ 탭으로 이동합니다.")
                st.rerun()

            except requests.HTTPError as http_err:
                st.error(f"HubSpot API 오류: {http_err.response.status_code} - {http_err.response.text}")
            except Exception as e:
                st.error(f"실패: {e}")

# =============== 탭③: 최종 링크 공유 ===============
if ss.results:
    with tabs[idx[TAB3]]:
        st.markdown("### ③ 최종 링크 공유")
        st.success(f"MBM 생성 결과 – **{ss.results['title']}**")

        # 카드형 박스 + 복사 버튼
        def link_box(title: str, items: list[tuple[str, str]], prefix_key: str):
            st.markdown(f"#### {title}")
            for i, (label, url) in enumerate(items, start=1):
                box = st.container(border=True)
                with box:
                    c1, c2 = st.columns([8, 1])
                    with c1:
                        st.markdown(f"**{label}**  \n{url}")
                    with c2:
                        copy_button(url, key=f"{prefix_key}_{i}_{uuid.uuid4()}")

        if ss.results["links"].get("Landing Page"):
            link_box("Landing / Website Page", ss.results["links"]["Landing Page"], "lp")

        if ss.results["links"].get("Email"):
            link_box("Marketing Emails", ss.results["links"]["Email"], "em")

        if ss.results["links"].get("Form"):
            link_box("Register Form", ss.results["links"]["Form"], "fm")

        st.divider()

        # 전체 결과 텍스트 + 버튼(아래에 단독 배치)
        all_lines = [f"[MBM] 생성 결과 - {ss.results['title']}", ""]
        if ss.results["links"].get("Landing Page"):
            all_lines.append("▼ Landing / Website Page")
            for label, url in ss.results["links"]["Landing Page"]:
                all_lines.append(f"- {label}: {url}")
            all_lines.append("")
        if ss.results["links"].get("Email"):
            all_lines.append("▼ Marketing Emails")
            for label, url in ss.results["links"]["Email"]:
                all_lines.append(f"- {label}: {url}")
            all_lines.append("")
        if ss.results["links"].get("Form"):
            all_lines.append("▼ Register Form")
            for label, url in ss.results["links"]["Form"]:
                all_lines.append(f"- {label}: {url}")
            all_lines.append("")

        all_text = "\n".join(all_lines)
        st.text_area("전체 결과 (미리보기)", value=all_text, height=180, label_visibility="collapsed")

        if st.button("전체 결과물 복사", type="primary"):
            st.components.v1.html(
                f"<script>navigator.clipboard.writeText({json.dumps(all_text)});</script>",
                height=0, width=0
            )
            st.toast("복사가 완료되었습니다. 메모장에 붙여넣기 하세요")
