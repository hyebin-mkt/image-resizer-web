# pages/01_mbm_magic_wizard.py
import json, uuid, datetime
import requests
import streamlit as st

# --------------------------------------------------
# 기본 페이지 헤더
# --------------------------------------------------
st.set_page_config(page_title="🧚🏻‍♂️ MBM Magic Wizard", page_icon="📄", layout="centered")
st.title("🧚🏻‍♂️ MBM Magic Wizard")
st.caption("MBM 오브젝트 형성부터 마케팅 에셋까지 한번에 만들어줄게요.")

# --------------------------------------------------
# 필수 시크릿
# --------------------------------------------------
TOKEN = st.secrets.get("HUBSPOT_PRIVATE_APP_TOKEN", "")
if not TOKEN:
    st.error("Streamlit Secrets에 HUBSPOT_PRIVATE_APP_TOKEN이 없습니다.")
    st.stop()

PORTAL_ID = st.secrets.get("PORTAL_ID", "2495902")
WEBSITE_PAGE_TEMPLATE_ID = st.secrets.get("WEBSITE_PAGE_TEMPLATE_ID", "")  # 반드시 채우기
EMAIL_TEMPLATE_ID = st.secrets.get("EMAIL_TEMPLATE_ID", "162882078001")
REGISTER_FORM_TEMPLATE_GUID = st.secrets.get("REGISTER_FORM_TEMPLATE_GUID", "83e40756-9929-401f-901b-8e77830d38cf")

HS_BASE = "https://api.hubapi.com"
HEADERS_JSON = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# --------------------------------------------------
# 세션 상태
# --------------------------------------------------
ss = st.session_state
ss.setdefault("active_stage", 1)          # 1=제출, 2=선택, 3=공유
ss.setdefault("search_done", False)       # 검색 버튼을 눌렀는지
ss.setdefault("search_results", [])       # 검색 결과 [(id,title)]
ss.setdefault("selected_mbm_id", None)    # 선택한 MBM ID (있으면 편집)
ss.setdefault("mbm_title", "")            # 사용자가 타이틀 입력
ss.setdefault("results", None)            # 생성 결과

# --------------------------------------------------
# 보조 유틸
# --------------------------------------------------
def ordinal(n: int) -> str:
    n = int(n)
    if 10 <= (n % 100) <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"

# 국가 코드 프리셋(필요한 것만 유지/추가 가능)
COUNTRY_OPTIONS = [
    ("Global", "GL"), ("Korea", "KR"), ("United States", "US"), ("Japan", "JP"),
    ("China", "CN"), ("Malaysia", "MY"), ("Singapore", "SG"), ("Germany", "DE"),
    ("France", "FR"), ("United Kingdom", "GB"), ("India", "IN"), ("Indonesia", "ID"),
    ("Thailand", "TH"), ("Vietnam", "VN"), ("EU(Region)", "EU")
]
COUNTRY_LABELS = [c[0] for c in COUNTRY_OPTIONS]
COUNTRY_TO_CODE = {c: code for c, code in COUNTRY_OPTIONS}

def country_code_from_label(label: str) -> str:
    return COUNTRY_TO_CODE.get(label, "GL")

# --------------------------------------------------
# HubSpot API 래퍼 (웹페이지/이메일/폼)
# --------------------------------------------------
def hs_clone_site_page(template_id: str, clone_name: str) -> dict:
    """Website Page 복제"""
    url = f"{HS_BASE}/cms/v3/pages/site-pages/clone"
    r = requests.post(url, headers=HEADERS_JSON,
                      json={"id": str(template_id), "name": clone_name}, timeout=45)
    r.raise_for_status()
    return r.json()

def hs_push_live_site_page(page_id: str) -> None:
    url = f"{HS_BASE}/cms/v3/pages/site-pages/{page_id}/draft/push-live"
    r = requests.post(url, headers={"Authorization": f"Bearer {TOKEN}", "Accept": "*/*"}, timeout=30)
    r.raise_for_status()

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

# Forms v2
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
            "type": "string", "fieldType": "text",
            "hidden": True, "defaultValue": hidden_value,
        })
    payload = {
        "name": new_name,
        "method": tpl.get("method", "POST"),
        "redirect": tpl.get("redirect", ""),
        "submitText": tpl.get("submitText", "Submit"),
        "formFieldGroups": groups,
    }
    return hs_create_form_v2(payload)

# --------------------------------------------------
# 탭 유틸 (자동 포커스)
# --------------------------------------------------
TAB1, TAB2, TAB3 = "MBM 오브젝트 제출", "후속 작업 선택", "최종 링크 공유"

def _focus_tab(label: str):
    st.components.v1.html(
        f"""
        <script>
        (function(){{
          function clickTab(){{
            const tabs = window.parent.document.querySelectorAll('[role="tab"]');
            for (const t of tabs) {{
              const txt = (t.innerText || "").trim();
              if (txt.indexOf("{label}") !== -1) {{ t.click(); return; }}
            }}
          }}
          setTimeout(clickTab, 60);
          setTimeout(clickTab, 200);
          setTimeout(clickTab, 450);
        }})();
        </script>
        """, height=0, width=0
    )

def make_tabs():
    labels = [TAB1]
    if ss.active_stage >= 2:
        labels.append(TAB2)
    if ss.active_stage >= 3 and ss.results:
        labels.append(TAB3)
    t = st.tabs(labels, key="mbm_tabs_v2")
    idx = {label: i for i, label in enumerate(labels)}
    if ss.active_stage == 2 and TAB2 in idx:
        _focus_tab(TAB2)
    elif ss.active_stage == 3 and TAB3 in idx:
        _focus_tab(TAB3)
    return t, idx

tabs, idx = make_tabs()

# --------------------------------------------------
# ① MBM 오브젝트 제출
# --------------------------------------------------
with tabs[idx[TAB1]]:
    st.markdown("### ① MBM 오브젝트 제출")
    st.markdown("MBM **오브젝트 타이틀**을 기준에서 검색해서 선택하거나, **새로 작성**할 수 있어요.")

    c1, c2 = st.columns([6,1])
    with c1:
        ss.mbm_title = st.text_input(
            "검색어", placeholder="예: [EU] 20250803 GTS NX Webinar",
            value=ss.mbm_title, label_visibility="collapsed", key="mbm_title_input_main"
        )
    with c2:
        # 아이콘(클립보드) 제거 요청 → 없음
        pass

    # 검색 버튼
    search_clicked = st.button("검색", key="btn_search")
    if search_clicked:
        ss.search_done = True
        # 실제 검색 로직 대신, 데모용 모의 결과:
        q = (ss.mbm_title or "").strip().lower()
        demo = []
        if q:
            demo.append(("13328771108", f"[EU] 24.06.06 (WEB) 교량/건축분야_유럽 2024 웨비나 컨퍼런스 - #{13328771108}"))
        ss.search_results = demo

    # 검색 후에만 결과/헬프 표시
    if ss.search_done:
        st.markdown("#### 결과에서 선택")
        if not ss.search_results:
            st.info("🔎 검색 결과가 없습니다.")

        # 결과 드롭다운
        if ss.search_results:
            opt_labels = [t for (_id, t) in ss.search_results]
            sel = st.selectbox("검색 결과", options=["선택 안함"] + opt_labels, label_visibility="collapsed")
            if sel != "선택 안함":
                # 데모이므로 id는 임의
                pick = next((_id for _id, t in ss.search_results if t == sel), None)
                ss.selected_mbm_id = pick
                ss.mbm_title = sel  # 선택한 타이틀을 제목으로 사용

        # 새 오브젝트 작성(텍스트 한 줄)
        st.markdown(
            f'<div style="margin-top:10px;padding:10px 12px;border:1px solid #e5e7eb;border-radius:10px;">'
            f'➕ <b>"{ss.mbm_title or "입력한 제목"}"</b> 로 <b>새 오브젝트 작성</b></div>',
            unsafe_allow_html=True
        )
        if st.button("새 오브젝트 작성(위 링크와 동일)", key="btn_create_new_obj", use_container_width=False):
            # 설문 페이지네이션(자체 입력 양식)으로 이동 → 후속 탭으로
            ss.active_stage = 2
            st.rerun()

    # 다음
    right = st.columns([6,1])[1]
    with right:
        if st.button("다음 ▶", key="go_next_from_search"):
            ss.active_stage = 2
            st.rerun()

# --------------------------------------------------
# ② 후속 작업 선택
# --------------------------------------------------
if ss.active_stage >= 2:
    with tabs[idx[TAB2]]:
        st.markdown("### ② 후속 작업 선택")

        with st.form("post_actions_form"):
            c1, c2 = st.columns([2,1])
            with c1:
                st.markdown("**MBM 오브젝트 타이틀 (읽기 전용)**")
                st.text_input("mbm-title", value=ss.mbm_title, disabled=True, label_visibility="collapsed")
            with c2:
                st.markdown("**생성할 자산**")
                make_site = st.checkbox("웹페이지 생성", value=True)
                make_em   = st.checkbox("이메일 생성", value=True)
                make_form = st.checkbox("신청 폼 생성", value=True)
                email_count = st.number_input("이메일 개수", min_value=1, max_value=10, value=1, step=1)

            submitted = st.form_submit_button("생성하기", type="primary")

        if submitted:
            if not ss.mbm_title:
                st.error("MBM 오브젝트 타이틀을 입력하세요.")
                st.stop()

            links = {"Website Page": [], "Email": [], "Form": []}

            try:
                # 웹사이트 생성
                if make_site:
                    page_name = f"{ss.mbm_title}_landing page"
                    with st.spinner("웹페이지 생성 중…"):
                        data = hs_clone_site_page(WEBSITE_PAGE_TEMPLATE_ID, page_name)
                        pid = str(data.get("id") or data.get("objectId") or "")
                        # 퍼블리시
                        hs_push_live_site_page(pid)
                        edit_url = f"https://app.hubspot.com/cms/{PORTAL_ID}/website/pages/{pid}/edit"
                        links["Website Page"].append(("편집", edit_url))

                # 이메일 N개
                if make_em:
                    for i in range(1, int(email_count)+1):
                        em_name = f"{ss.mbm_title}_email_{ordinal(i)}"
                        with st.spinner(f"이메일 생성 중… ({em_name})"):
                            em = hs_clone_marketing_email(EMAIL_TEMPLATE_ID, em_name)
                            em_id = str(em.get("id") or em.get("contentId") or "")
                            edit_url = f"https://app.hubspot.com/email/{PORTAL_ID}/edit/{em_id}/settings"
                            links["Email"].append((f"Email {ordinal(i)}", edit_url))

                # 신청 폼
                if make_form:
                    form_name = f"{ss.mbm_title}_register form"
                    with st.spinner("신청 폼 생성 중…"):
                        new_form = clone_form_with_hidden_value(
                            REGISTER_FORM_TEMPLATE_GUID, form_name, ss.mbm_title, "title"
                        )
                        guid = new_form.get("guid") or new_form.get("id")
                        edit_url = f"https://app.hubspot.com/forms/{PORTAL_ID}/{guid}/edit"
                        links["Form"].append(("편집", edit_url))

                ss.results = {"title": ss.mbm_title, "links": links}
                ss.active_stage = 3
                st.success("생성이 완료되었습니다. ‘최종 링크 공유’ 탭으로 이동합니다.")
                st.rerun()

            except requests.HTTPError as http_err:
                st.error(f"HubSpot API 오류: {http_err.response.status_code} - {http_err.response.text}")
            except Exception as e:
                st.error(f"실패: {e}")

# --------------------------------------------------
# ③ 최종 링크 공유
# --------------------------------------------------
if ss.active_stage >= 3 and ss.results:
    with tabs[idx[TAB3]]:
        st.markdown("### ③ 최종 링크 공유")
        st.success(f"MBM 생성 결과 - {ss.results['title']}")

        def link_box(title: str, items: list[tuple[str, str]], prefix_key: str):
            st.markdown(f"#### {title}")
            for i, (label, url) in enumerate(items, start=1):
                box = st.container(border=True)
                with box:
                    c1, c2 = st.columns([8,1])
                    with c1:
                        st.markdown(f"**{label}**  \n{url}")
                    with c2:
                        st.button("📋", key=f"copy_{prefix_key}_{i}",
                                  help="링크 복사",
                                  on_click=lambda u=url: st.session_state.update({_copy_key(u): True}))
                        # 실제 복사는 아래 컴포넌트로
                        st.components.v1.html(
                            f"<script> if ({json.dumps(st.session_state.get(_copy_key(url), False))}) "
                            f"{{ navigator.clipboard.writeText({json.dumps(url)}); }} </script>",
                            height=0, width=0
                        )

        def _copy_key(u: str) -> str:
            return f"copied__{hash(u)}"

        if ss.results["links"].get("Website Page"):
            link_box("Website Page", ss.results["links"]["Website Page"], "wp")

        if ss.results["links"].get("Email"):
            link_box("Marketing Emails", ss.results["links"]["Email"], "em")

        if ss.results["links"].get("Form"):
            link_box("Register Form", ss.results["links"]["Form"], "fm")

        # 전체 텍스트
        st.divider()
        lines = [f"[MBM] 생성 결과 - {ss.results['title']}", ""]
        if ss.results["links"].get("Website Page"):
            lines.append("▼ Website Page")
            for label, url in ss.results["links"]["Website Page"]:
                lines.append(f"- {label}: {url}")
            lines.append("")
        if ss.results["links"].get("Email"):
            lines.append("▼ Marketing Emails")
            for label, url in ss.results["links"]["Email"]:
                lines.append(f"- {label}: {url}")
            lines.append("")
        if ss.results["links"].get("Form"):
            lines.append("▼ Register Form")
            for label, url in ss.results["links"]["Form"]:
                lines.append(f"- {label}: {url}")
            lines.append("")
        all_text = "\n".join(lines)
        st.text_area("전체 결과 (미리보기)", value=all_text, height=160, label_visibility="collapsed")
        if st.button("전체 결과물 복사", type="primary"):
            st.components.v1.html(
                f"<script>navigator.clipboard.writeText({json.dumps(all_text)});</script>",
                height=0, width=0
            )
            st.toast("복사가 완료되었습니다. 메모장에 붙여넣기 하세요")
