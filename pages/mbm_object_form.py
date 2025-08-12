# pages/mbm_object_form.py
import requests
import streamlit as st

# -----------------------
# 기본 페이지 설정
# -----------------------
st.set_page_config(page_title="MBM Object 생성기", page_icon="📄", layout="centered")
st.title("MBM Object 생성기")
st.caption("1) MBM Object Form 제출 → 2) 옵션 선택 → 3) 자동 복제 & 링크 요약")

# -----------------------
# 설정값 (secrets + 안전한 기본값)
# -----------------------
TOKEN = st.secrets.get("HUBSPOT_PRIVATE_APP_TOKEN", "")
if not TOKEN:
    st.error("Streamlit Secrets에 HUBSPOT_PRIVATE_APP_TOKEN이 없습니다.")
    st.stop()

PORTAL_ID = st.secrets.get("PORTAL_ID", "2495902")  # 편집/미리보기 링크 생성용
HUBSPOT_REGION = "na1"

# 복제 대상 템플릿/리소스
LANDING_PAGE_TEMPLATE_ID = st.secrets.get("LANDING_PAGE_TEMPLATE_ID", "192676141393")
EMAIL_TEMPLATE_ID        = st.secrets.get("EMAIL_TEMPLATE_ID", "162882078001")
FORM_TEMPLATE_GUID       = st.secrets.get("FORM_TEMPLATE_GUID", "83e40756-9929-401f-901b-8e77830d38cf")

# Register Form 숨김 필드 내부명 (MBM Object의 'Title')
MBM_HIDDEN_FIELD_NAME    = "title"

# 화면 상단에 임베드할 MBM Object Form (원하면 secrets로 옮겨도 됨)
FORM_ID_FOR_EMBED = st.secrets.get("FORM_ID_FOR_EMBED", "a9e1a5e8-4c46-461f-b823-13cc4772dc6c")

HS_BASE = "https://api.hubapi.com"
HEADERS_JSON = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# =========================================================
# ===============  1) HubSpot 폼 임베드(컴팩트)  ==========
# =========================================================
# 제출 후 폼 영역 공백을 최소화: iframe 높이 고정(420px) + 컨테이너 접기
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
      inlineMessage: "제출 완료! 아래 옵션에서 랜딩/이메일/등록폼 복제를 선택하세요.",
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

st.components.v1.html(html, height=420, scrolling=True)
st.divider()

# =========================================================
# ===============  서버 함수들 (HubSpot API)  =============
# =========================================================

# --- (3) 랜딩페이지 복제 + 퍼블리시 ---
def hs_clone_landing_page(template_id: str, clone_name: str) -> dict:
    url = f"{HS_BASE}/cms/v3/pages/landing-pages/clone"
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

def hs_push_live_landing_page(page_id: str) -> None:
    url = f"{HS_BASE}/cms/v3/pages/landing-pages/{page_id}/draft/push-live"
    r = requests.post(url, headers={"Authorization": f"Bearer {TOKEN}", "Accept": "*/*"}, timeout=30)
    r.raise_for_status()

# --- (3) 마케팅 이메일 복제 ---
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

# --- (6) Register Form 복제 + 숨김필드 defaultValue = MBM 타이틀 (Forms v2) ---
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
# ==================  2) 후속 작업 UI  ====================
# =========================================================
st.subheader("후속 작업 선택")

with st.form("post_submit_actions"):
    col1, col2 = st.columns([2,1])
    with col1:
        st.markdown("#### MBM Object 타이틀")
        mbm_title = st.text_input(
            "1번(MBM Object Form)에서 입력한 'Title'을 그대로 입력하세요.",
            placeholder="[EU] 20250225 Algeria Seminar"
        )
    with col2:
        st.markdown("#### 생성할 자산")
        make_lp = st.checkbox("랜딩페이지 복제", value=True)
        make_em = st.checkbox("이메일 복제", value=True)
        email_count = st.number_input("이메일 복제 개수", min_value=1, max_value=10, value=1, step=1)

    submitted = st.form_submit_button("생성하기", type="primary")

# =========================================================
# ===================  3~7 자동 실행  =====================
# =========================================================
if submitted:
    if not mbm_title:
        st.error("MBM Object 타이틀을 입력하세요.")
        st.stop()

    created_links = {"Landing Page": [], "Email": [], "Form": []}

    try:
        # (3) 랜딩페이지 복제 + 퍼블리시
        if make_lp:
            clone_name = f"{mbm_title}_Landing Page"
            with st.spinner(f"랜딩페이지 복제 중… ({clone_name})"):
                lp = hs_clone_landing_page(LANDING_PAGE_TEMPLATE_ID, clone_name)
                lp_id = str(lp.get("id") or lp.get("objectId") or "")
                hs_push_live_landing_page(lp_id)  # 퍼블리시
                edit_url   = f"https://app.hubspot.com/cms/{PORTAL_ID}/pages/{lp_id}/edit"
                public_url = lp.get("url") or lp.get("publicUrl") or ""
                created_links["Landing Page"].append(edit_url)
                if public_url:
                    created_links["Landing Page"].append(public_url)
            st.success("랜딩페이지 복제 완료")

        # (3) 이메일 복제 (횟수)
        if make_em:
            for i in range(int(email_count)):
                clone_name = f"{mbm_title}_Email_{i+1}"
                with st.spinner(f"마케팅 이메일 복제 중… ({clone_name})"):
                    em = hs_clone_marketing_email(EMAIL_TEMPLATE_ID, clone_name)
                    em_id = str(em.get("id") or em.get("contentId") or "")
                    email_edit_url = f"https://app.hubspot.com/email/{PORTAL_ID}/edit/{em_id}/settings"
                    created_links["Email"].append(email_edit_url)
            st.success(f"이메일 {email_count}개 복제 완료")

        # (6) Register Form 복제 + 숨김 필드 defaultValue = MBM 타이틀
        form_name = f"{mbm_title}_Register Form"
        with st.spinner(f"Register Form 복제 중… ({form_name})"):
            new_form = clone_form_with_hidden_value(
                FORM_TEMPLATE_GUID, form_name, mbm_title, MBM_HIDDEN_FIELD_NAME
            )
            new_guid = new_form.get("guid") or new_form.get("id")
            form_edit_url = f"https://app.hubspot.com/forms/{PORTAL_ID}/{new_guid}/edit"
            created_links["Form"].append(form_edit_url)
        st.success("Register Form 복제 완료")

        # (4)(7) 링크 요약 텍스트 (복사하기 편하게)
        lines = []
        lines.append(f"[MBM] 생성 결과 - {mbm_title}")
        lines.append("")
        if created_links["Landing Page"]:
            lines.append("▼ Landing Page")
            for u in created_links["Landing Page"]:
                lines.append(f"- {u}")
            lines.append("")
        if created_links["Email"]:
            lines.append("▼ Marketing Emails")
            for idx, u in enumerate(created_links["Email"], start=1):
                lines.append(f"- Email {idx}: {u}")
            lines.append("")
        if created_links["Form"]:
            lines.append("▼ Register Form")
            for u in created_links["Form"]:
                lines.append(f"- {u}")
            lines.append("")

        summary_text = "\n".join(lines)
        st.success("✅ 생성 완료! 아래 텍스트를 복사해서 영업팀에 공유하세요.")
        st.code(summary_text, language=None)  # Copy 버튼 제공

    except requests.HTTPError as http_err:
        st.error(f"HubSpot API 오류: {http_err.response.status_code} - {http_err.response.text}")
    except Exception as e:
        st.error(f"실패: {e}")
