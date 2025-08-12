# pages/mbm_object_form.py
import json
import requests
import streamlit as st

# -----------------------
# 기본 페이지 설정
# -----------------------
st.set_page_config(page_title="MBM Object 생성기", page_icon="📄", layout="centered")
st.title("MBM Object 생성기")
st.caption("1) MBM Object Form 제출 → 2) 탭에서 옵션 선택 → 3) 자동 복제 & 링크 요약")

# -----------------------
# 설정값 (secrets + 안전한 기본값)
# -----------------------
TOKEN = st.secrets.get("HUBSPOT_PRIVATE_APP_TOKEN", "")
if not TOKEN:
    st.error("Streamlit Secrets에 HUBSPOT_PRIVATE_APP_TOKEN이 없습니다.")
    st.stop()

PORTAL_ID = st.secrets.get("PORTAL_ID", "2495902")  # 링크 생성용
HUBSPOT_REGION = "na1"

# 복제 대상 템플릿/리소스
LANDING_PAGE_TEMPLATE_ID = st.secrets.get("LANDING_PAGE_TEMPLATE_ID", "192676141393")
EMAIL_TEMPLATE_ID        = st.secrets.get("EMAIL_TEMPLATE_ID", "162882078001")

# ✅ Register Form “템플릿” GUID (고정)
REGISTER_FORM_TEMPLATE_GUID = "83e40756-9929-401f-901b-8e77830d38cf"

# Register Form 숨김 필드 내부명 (MBM Object의 'Title')
MBM_HIDDEN_FIELD_NAME = "title"

# 상단에 임베드할 “MBM Object Form”
FORM_ID_FOR_EMBED = st.secrets.get("FORM_ID_FOR_EMBED", "a9e1a5e8-4c46-461f-b823-13cc4772dc6c")

HS_BASE = "https://api.hubapi.com"
HEADERS_JSON = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# -----------------------
# 세션 상태 기본값
# -----------------------
ss = st.session_state
ss.setdefault("mbm_submitted", False)     # ① 제출 후 탭 ② 노출
ss.setdefault("mbm_outputs", None)        # ② 실행 후 결과 저장 → 탭 ③ 노출
ss.setdefault("mbm_title", "")            # ①에서 입력받는 타이틀 (②에서 사용)
ss.setdefault("goto_actions", False)      # 다음 렌더링에서 ② 탭을 첫번째에 배치
ss.setdefault("goto_outputs", False)      # 다음 렌더링에서 ③ 탭을 첫번째에 배치

# -----------------------
# 헬퍼: 서수(1st/2nd/3rd/…)
# -----------------------
def ordinal(n: int) -> str:
    n = int(n)
    if 10 <= (n % 100) <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"

# =========================================================
# ===============  동적 탭 구성(순서 제어)  ===============
# =========================================================
def make_tabs():
    labels = ["MBM Object Form"]

    if ss.mbm_submitted and not ss.mbm_outputs:
        # 제출 완료 이후, 후속 작업 탭을 노출
        if ss.goto_actions:
            labels = ["후속 작업 선택", "MBM Object Form"]   # 자동으로 ② 탭이 첫 번째로 보이도록
        else:
            labels = ["MBM Object Form", "후속 작업 선택"]

    if ss.mbm_outputs:
        if ss.goto_outputs:
            labels = ["후속 작업 산출물", "후속 작업 선택", "MBM Object Form"]
        else:
            labels = ["MBM Object Form", "후속 작업 선택", "후속 작업 산출물"]

    t = st.tabs(labels)
    index = {label: i for i, label in enumerate(labels)}
    return t, index

tabs, idx = make_tabs()

# =========================================================
# ===============  1) MBM Object Form (탭①)  =============
# =========================================================
with tabs[idx["MBM Object Form"]]:
    st.markdown("### ① MBM 오브젝트를 먼저 제출하세요")

    # ✏️ MBM 타이틀 입력을 ①로 이동하고, 옆에 복사 아이콘 제공
    st.markdown("**MBM Object 타이틀**")
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
        # 📋 복사 아이콘 버튼
        if st.button("📋 복사", help="입력한 타이틀을 클립보드에 복사합니다."):
            # JS를 이용한 클립보드 복사
            st.components.v1.html(
                f"<script>navigator.clipboard.writeText({json.dumps(ss.mbm_title)});</script>",
                height=0, width=0
            )
            st.toast("타이틀이 복사되었습니다.")

    # ── HubSpot 폼(스크롤 없이 충분히 크게 → 제출 후 접힘)
    FORM_IFRAME_HEIGHT = 1200
    FORM_COLLAPSED_HEIGHT = 140
    iframe_height = FORM_COLLAPSED_HEIGHT if ss.mbm_submitted else FORM_IFRAME_HEIGHT

    html = """
    <div id="hubspot-form"></div>
    <script>
    (function() {
      var s = document.createElement('script');
      s.src = "https://js.hsforms.net/forms/v2.js";
      s.async = true;
      s.onload = function() {
        if (!window.hbspt) return;
        window.hbspt.forms.create({
          region: "__REGION__",
          portalId: "__PORTAL__",
          formId: "__FORM__",
          target: "#hubspot-form",
          inlineMessage: "제출 완료! 상단 탭이 자동으로 ‘후속 작업 선택’으로 전환됩니다.",
          onFormSubmitted: function() {
            var c = document.getElementById('hubspot-form');
            if (c) { c.style.maxHeight = "120px"; c.style.overflow = "hidden"; }
          }
        });
      };
      document.body.appendChild(s);
    })();
    </script>
    """.replace("__REGION__", HUBSPOT_REGION)\
       .replace("__PORTAL__", PORTAL_ID)\
       .replace("__FORM__", FORM_ID_FOR_EMBED)

    st.components.v1.html(html, height=iframe_height, scrolling=False)

    st.info("폼 제출 후 아래 버튼을 누르면 ‘후속 작업 선택’ 탭으로 자동 전환됩니다.")
    if st.button("폼 제출 완료 → ‘후속 작업 선택’ 탭 열기", type="primary"):
        ss.mbm_submitted = True
        ss.goto_actions = True     # 다음 렌더링에서 ② 탭을 첫 번째로
        st.rerun()

# =========================================================
# ===============  서버 함수들 (HubSpot API)  =============
# =========================================================
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

# --- Register Form 복제 + 숨김필드 defaultValue = MBM 타이틀 (Forms v2) ---
FORMS_V2 = "https://api.hubapi.com/forms/v2"

def hs_get_form_v2(form_guid: str) -> dict:
    url = f"{FORMS_V2}/forms/{form_guid}"
    r = requests.get(url, headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    return r.json()

def _strip_field_for_create(field: dict) -> dict:
    ALLOWED = {
        "name","label","type","fieldType","required","hidden","defaultValue",
        "placeholder","validation","displayAsCheckbox","options","description","inlineHelpText"
    }
    return {k: v for k, v in field.items() if k in ALLOWED}

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

    # 숨김 필드 찾기/주입, 없으면 추가
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

# =========================================================
# ===============  2) 후속 작업 선택 (탭②)  ===============
# =========================================================
if ss.mbm_submitted:
    with tabs[idx["후속 작업 선택" if "후속 작업 선택" in idx else list(idx.keys())[0]]]:
        st.markdown("### ② 후속 작업 선택")

        with st.form("post_submit_actions"):
            col1, col2 = st.columns([2, 1], gap="large")
            with col1:
                st.markdown("**MBM Object 타이틀 (읽기 전용)**")
                st.text_input("MBM Title", value=ss.mbm_title, disabled=True, label_visibility="collapsed")
            with col2:
                st.markdown("**생성할 자산**")
                make_lp = st.checkbox("랜딩/웹페이지 복제", value=True)
                make_em = st.checkbox("이메일 복제", value=True)
                email_count = st.number_input("이메일 복제 개수", min_value=1, max_value=10, value=1, step=1)

            submitted_actions = st.form_submit_button("생성하기", type="primary")

        if submitted_actions:
            if not ss.mbm_title:
                st.error("① 탭에서 MBM Object 타이틀을 입력하세요.")
                st.stop()

            created_links = {"Landing Page": [], "Email": [], "Form": []}

            try:
                # (3) 페이지(landing 또는 site) 복제 + 퍼블리시
                if make_lp:
                    clone_name = f"{ss.mbm_title}_landing page"
                    with st.spinner(f"페이지 복제 중… ({clone_name})"):
                        page_data, used_type = hs_clone_page_auto(LANDING_PAGE_TEMPLATE_ID, clone_name)
                        page_id = str(page_data.get("id") or page_data.get("objectId") or "")
                        hs_push_live(page_id, used_type)

                        # 편집/공개 링크
                        if used_type == "site":
                            edit_url = f"https://app.hubspot.com/cms/{PORTAL_ID}/website/pages/{page_id}/edit"
                        else:
                            edit_url = f"https://app.hubspot.com/cms/{PORTAL_ID}/pages/{page_id}/edit"
                        public_url = page_data.get("url") or page_data.get("publicUrl") or ""
                        created_links["Landing Page"].append(edit_url)
                        if public_url:
                            created_links["Landing Page"].append(public_url)

                # (3) 이메일 복제 (횟수, 서수 규칙)
                if make_em:
                    for i in range(1, int(email_count) + 1):
                        clone_name = f"{ss.mbm_title}_email_{ordinal(i)}"
                        with st.spinner(f"마케팅 이메일 복제 중… ({clone_name})"):
                            em = hs_clone_marketing_email(EMAIL_TEMPLATE_ID, clone_name)
                            em_id = str(em.get("id") or em.get("contentId") or "")
                            email_edit_url = f"https://app.hubspot.com/email/{PORTAL_ID}/edit/{em_id}/settings"
                            created_links["Email"].append(email_edit_url)

                # (6) Register Form 복제 + 숨김 필드 defaultValue = MBM 타이틀
                form_name = f"{ss.mbm_title}_register form"
                with st.spinner(f"Register Form 복제 중… ({form_name})"):
                    new_form = clone_form_with_hidden_value(
                        REGISTER_FORM_TEMPLATE_GUID, form_name, ss.mbm_title, MBM_HIDDEN_FIELD_NAME
                    )
                    new_guid = new_form.get("guid") or new_form.get("id")
                    form_edit_url = f"https://app.hubspot.com/forms/{PORTAL_ID}/{new_guid}/edit"
                    created_links["Form"].append(form_edit_url)

                # (4)(7) 링크 요약 텍스트
                lines = [f"[MBM] 생성 결과 - {ss.mbm_title}", ""]
                if created_links["Landing Page"]:
                    lines.append("▼ Landing / Website Page")
                    lines += [f"- {u}" for u in created_links["Landing Page"]]
                    lines.append("")
                if created_links["Email"]:
                    lines.append("▼ Marketing Emails")
                    lines += [f"- Email {idx}: {u}" for idx, u in enumerate(created_links["Email"], start=1)]
                    lines.append("")
                if created_links["Form"]:
                    lines.append("▼ Register Form")
                    lines += [f"- {u}" for u in created_links["Form"]]
                    lines.append("")

                ss.mbm_outputs = "\n".join(lines)
                ss.goto_outputs = True      # 다음 렌더링에서 ③ 탭이 첫 번째에
                st.success("생성이 완료되었습니다. 상단의 ‘후속 작업 산출물’ 탭으로 이동합니다.")
                st.rerun()

            except requests.HTTPError as http_err:
                st.error(f"HubSpot API 오류: {http_err.response.status_code} - {http_err.response.text}")
            except Exception as e:
                st.error(f"실패: {e}")

# =========================================================
# ===============  3) 결과(복사용 텍스트)  ================
# =========================================================
if ss.mbm_outputs:
    with tabs[idx["후속 작업 산출물"]]:
        st.markdown("### ③ 후속 작업 산출물")
        st.success("아래 텍스트를 복사하여 팀에 공유하세요.")
        st.code(ss.mbm_outputs, language=None)
