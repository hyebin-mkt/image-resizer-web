# pages/mbm_object_form.py
import json, uuid
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

# Website Page 템플릿 ID (Secrets 키 이름은 기존 그대로 사용)
LANDING_PAGE_TEMPLATE_ID = st.secrets.get("LANDING_PAGE_TEMPLATE_ID", "192676141393")
# (백업) 템플릿 '제목'으로 자동 검색할 때 사용 — UI로는 노출하지 않음
WEBSITE_PAGE_TEMPLATE_TITLE = st.secrets.get("WEBSITE_PAGE_TEMPLATE_TITLE", "[Landing Page Template] YYMMDD_MBM Title")

EMAIL_TEMPLATE_ID        = st.secrets.get("EMAIL_TEMPLATE_ID", "162882078001")
REGISTER_FORM_TEMPLATE_GUID = "83e40756-9929-401f-901b-8e77830d38cf"  # 고정
MBM_HIDDEN_FIELD_NAME = "title"
FORM_ID_FOR_EMBED = st.secrets.get("FORM_ID_FOR_EMBED", "a9e1a5e8-4c46-461f-b823-13cc4772dc6c")

# 사이드바 접근 제어(요청 3)
ACCESS_PASSWORD = "mid@sit0901"

HS_BASE = "https://api.hubapi.com"
HEADERS_JSON = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# =============== 세션 상태 ===============
ss = st.session_state
ss.setdefault("auth_ok", False)         # 접근 허용 여부
ss.setdefault("active_stage", 1)        # 1=제출, 2=선택, 3=공유
ss.setdefault("mbm_submitted", False)
ss.setdefault("mbm_title", "")
ss.setdefault("results", None)          # {"title": str, "links": dict}

# =============== 사이드바 암호 확인 ===============
with st.sidebar:
    st.header("🔒 Access")
    if not ss.auth_ok:
        pwd = st.text_input("암호 입력", type="password", placeholder="비밀번호를 입력하세요")
        if st.button("접속"):
            if pwd == ACCESS_PASSWORD:
                ss.auth_ok = True
                st.rerun()   # ← 여기! st.experimental_rerun() 대신 st.rerun()
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

# =============== HubSpot API ===============
# --- Website Page 전용 ---
def hs_clone_site_page(template_id: str, clone_name: str) -> dict:
    """POST /cms/v3/pages/site-pages/clone"""
    url = f"{HS_BASE}/cms/v3/pages/site-pages/clone"
    last = None
    for key in ("name", "cloneName"):
        r = requests.post(url, headers=HEADERS_JSON, json={"id": str(template_id), key: clone_name}, timeout=45)
        if r.status_code < 400:
            return r.json()
        last = r
    last.raise_for_status()

def hs_update_site_page_name(page_id: str, new_name: str) -> None:
    """PATCH /cms/v3/pages/site-pages/{id}"""
    url = f"{HS_BASE}/cms/v3/pages/site-pages/{page_id}"
    r = requests.patch(url, headers=HEADERS_JSON, json={"name": new_name}, timeout=30)
    if r.status_code >= 400:
        st.warning(f"페이지 내부 이름 변경 실패: {r.status_code}")

def hs_push_live_site(page_id: str) -> None:
    """POST /cms/v3/pages/site-pages/{id}/draft/push-live"""
    url = f"{HS_BASE}/cms/v3/pages/site-pages/{page_id}/draft/push-live"
    r = requests.post(url, headers={"Authorization": f"Bearer {TOKEN}", "Accept": "*/*"}, timeout=30)
    r.raise_for_status()

def hs_get_site_page(page_id: str) -> dict:
    url = f"{HS_BASE}/cms/v3/pages/site-pages/{page_id}"
    r = requests.get(url, headers=HEADERS_JSON, timeout=30)
    r.raise_for_status()
    return r.json()

def extract_best_live_url(page_json: dict) -> str | None:
    # 가능한 key들을 순서대로 확인
    for k in ("publicUrl", "url", "absoluteUrl", "absolute_url", "publishedUrl"):
        val = page_json.get(k)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None

# ---- site-pages 목록 검색(템플릿 제목으로 ID 찾기; UI 표시 없이 자동 백업) ----
def find_site_page_id_by_title_exact(title: str) -> str | None:
    after = None
    while True:
        params = {"limit": 100}
        if after:
            params["after"] = after
        r = requests.get(f"{HS_BASE}/cms/v3/pages/site-pages", headers=HEADERS_JSON, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        items = data.get("results") or data.get("items") or []
        for it in items:
            name = (it.get("name") or "").strip()
            if name == title.strip():
                return str(it.get("id") or it.get("objectId") or "")
        after = (data.get("paging") or {}).get("next", {}).get("after")
        if not after:
            break
    return None

def clone_site_page_with_fallback(primary_id: str, clone_name: str, title_backup: str | None) -> dict:
    try:
        return hs_clone_site_page(primary_id, clone_name)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404 and title_backup:
            resolved = find_site_page_id_by_title_exact(title_backup)
            if resolved:
                return hs_clone_site_page(resolved, clone_name)
        raise

# ---- Emails ----
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

# =============== 탭 구성 (새 탭은 오른쪽에 추가) ===============
TAB1 = "MBM 오브젝트 제출"
TAB2 = "후속 작업 선택"
TAB3 = "최종 링크 공유"

def _focus_tab(label: str):
    # 렌더 직후 해당 라벨 탭을 자동 클릭하여 전환
    st.components.v1.html(f"""
    <script>
    (function(){{
      function clickTab(){{
        const tabs = window.parent.document.querySelectorAll('[role="tab"]');
        for (const t of tabs) {{
          const txt = (t.innerText || "").trim();
          if (txt.indexOf("{label}") !== -1) {{ t.click(); return; }}
        }}
      }}
      setTimeout(clickTab, 50);
      setTimeout(clickTab, 250);
      setTimeout(clickTab, 500);
    }})();
    </script>
    """, height=0, width=0)

def make_tabs():
    labels = [TAB1]
    if ss.mbm_submitted:
        labels.append(TAB2)
    if ss.results:
        labels.append(TAB3)
    t = st.tabs(labels)
    idx = {label: i for i, label in enumerate(labels)}
    # 자동 포커스
    if ss.active_stage == 2 and TAB2 in idx:
        _focus_tab(TAB2)
    elif ss.active_stage == 3 and TAB3 in idx:
        _focus_tab(TAB3)
    return t, idx

tabs, idx = make_tabs()

# =============== 탭①: MBM 오브젝트 제출 ===============
with tabs[idx[TAB1]]:
    st.markdown("### ① MBM 오브젝트 제출")

    st.markdown("**MBM 오브젝트 타이틀 설정**")
    st.markdown("네이밍 규칙: `[국가코드] YYYYMMDD 웨비나명` 형식으로 입력하세요.")
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

    # 제출 후에는 폼/안내 숨김
    if not ss.mbm_submitted:
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
            ss.active_stage = 2
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
                make_wp = st.checkbox("웹페이지 복제", value=True)  # Website 전용
                make_em = st.checkbox("이메일 복제", value=True)
                email_count = st.number_input("이메일 복제 개수", min_value=1, max_value=10, value=1, step=1)

            submitted_actions = st.form_submit_button("생성하기", type="primary")

        if submitted_actions:
            if not ss.mbm_title:
                st.error("① 탭에서 MBM 오브젝트 타이틀을 입력하세요.")
                st.stop()

            links = {"Website Page": [], "Email": [], "Form": []}

            try:
                # Website Page 클론 & 내부명 업데이트 & 퍼블리시
                if make_wp:
                    page_name = f"{ss.mbm_title}_landing page"  # 네이밍 규칙 유지
                    with st.spinner(f"웹페이지 복제 중… ({page_name})"):
                        page_data = clone_site_page_with_fallback(
                            LANDING_PAGE_TEMPLATE_ID,
                            page_name,
                            WEBSITE_PAGE_TEMPLATE_TITLE  # UI 없이 자동 백업 검색
                        )
                        page_id = str(page_data.get("id") or page_data.get("objectId") or "")
                        hs_update_site_page_name(page_id, page_name)
                        hs_push_live_site(page_id)

                        # 퍼블리시 후, 페이지 정보를 다시 조회하여 접속 가능한 URL을 확보
                        try:
                            refreshed = hs_get_site_page(page_id)
                        except Exception:
                            refreshed = page_data
                        live_url = extract_best_live_url(refreshed)
                        if not live_url:
                            # 퍼블릭 URL이 아직 없으면 내부 보기 링크를 제공(접속 가능한 단일 링크)
                            live_url = f"https://app.hubspot.com/cms/{PORTAL_ID}/website/pages/{page_id}/view"

                        # 요청 2: Website Page는 "접속 가능한 링크 하나만" 제공
                        links["Website Page"].append(("보기", live_url))

                # 이메일 N개 클론 & 내부명 업데이트
                if make_em:
                    for i in range(1, int(email_count) + 1):
                        email_name = f"{ss.mbm_title}_email_{ordinal(i)}"
                        with st.spinner(f"마케팅 이메일 복제 중… ({email_name})"):
                            em = hs_clone_marketing_email(EMAIL_TEMPLATE_ID, email_name)
                            em_id = str(em.get("id") or em.get("contentId") or "")
                            hs_update_email_name(em_id, email_name)
                            edit_url = f"https://app.hubspot.com/email/{PORTAL_ID}/edit/{em_id}/settings"
                            links["Email"].append((f"Email {ordinal(i)}", edit_url))

                # Register Form 클론 & 숨김 값 주입
                form_name = f"{ss.mbm_title}_register form"
                with st.spinner(f"Register Form 복제 중… ({form_name})"):
                    new_form = clone_form_with_hidden_value(
                        REGISTER_FORM_TEMPLATE_GUID, form_name, ss.mbm_title, MBM_HIDDEN_FIELD_NAME
                    )
                    new_guid = new_form.get("guid") or new_form.get("id")
                    edit_url = f"https://app.hubspot.com/forms/{PORTAL_ID}/{new_guid}/edit"
                    links["Form"].append(("편집", edit_url))

                ss.results = {"title": ss.mbm_title, "links": links}
                ss.active_stage = 3
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

        if ss.results["links"].get("Website Page"):
            link_box("Website Page", ss.results["links"]["Website Page"], "lp")

        if ss.results["links"].get("Email"):
            link_box("Marketing Emails", ss.results["links"]["Email"], "em")

        if ss.results["links"].get("Form"):
            link_box("Register Form", ss.results["links"]["Form"], "fm")

        st.divider()

        # 전체 결과 텍스트 + 복사 버튼(아래)
        all_lines = [f"[MBM] 생성 결과 - {ss.results['title']}", ""]
        if ss.results["links"].get("Website Page"):
            all_lines.append("▼ Website Page")
            for label, url in ss.results["links"]["Website Page"]:
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
