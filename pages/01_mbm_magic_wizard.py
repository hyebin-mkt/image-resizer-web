# pages/01_mbm_magic_wizard.py
# 🧚🏻‍♂️ MBM Magic Wizard – Step 1 검색/신규작성 → Step 2 에셋 생성 → Step 3 링크 요약
# - 새 오브젝트 "생성"은 실제 HubSpot에 레코드를 만드는 것이 아니라,
#   페이지네이션 폼(위저드)로 이동하여 상세 정보를 입력받는 동작입니다.
# - 기존 MBM 오브젝트 검색은 선택사항(비어도 진행 가능).
# - 결과 요약은 항상 3번째 탭에서 보여줍니다.

import json, uuid, datetime
import requests
import streamlit as st

# -------------------- 기본 설정 --------------------
st.set_page_config(page_title="🧚🏻‍♂️ MBM Magic Wizard", page_icon="📄", layout="centered")
st.title("🧚🏻‍♂️ MBM Magic Wizard")
st.caption("MBM 오브젝트 형성부터 마케팅 에셋까지 한번에 만들어줄게요.")

# -------------------- Secrets & 상수 --------------------
TOKEN = st.secrets.get("HUBSPOT_PRIVATE_APP_TOKEN", "")
PORTAL_ID = st.secrets.get("PORTAL_ID", "2495902")
HUBSPOT_REGION = "na1"

# 템플릿(복제 원본)
WEBSITE_TEMPLATE_ID = st.secrets.get("WEBSITE_TEMPLATE_ID", "")     # site-page(website page) 템플릿 ID
EMAIL_TEMPLATE_ID   = st.secrets.get("EMAIL_TEMPLATE_ID", "162882078001")
REGISTER_FORM_TEMPLATE_GUID = "83e40756-9929-401f-901b-8e77830d38cf"

MBM_OBJECT_TYPE_ID  = st.secrets.get("MBM_OBJECT_TYPE_ID", "")      # 예: "2-10432789" 또는 "p123456_mbm"
MBM_TITLE_PROP      = "title"                                       # MBM의 primary display property

HS_BASE = "https://api.hubapi.com"
HEADERS_JSON = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# -------------------- 세션 상태 --------------------
ss = st.session_state
ss.setdefault("active_stage", 1)          # 1=제출(검색/신규작성), 2=후속작업, 3=최종링크
ss.setdefault("mbm_title", "")
ss.setdefault("search_query", "")
ss.setdefault("search_results", [])       # [(title, id)]
ss.setdefault("picked_id", None)
ss.setdefault("wizard_mode", False)       # 새 오브젝트 작성 모드
ss.setdefault("wiz_page", 1)              # 페이지네이션(1~3)
ss.setdefault("wiz_data", {})             # 위저드 폼 데이터(캐시 유지)
ss.setdefault("links", {"Website": [], "Email": [], "Form": []})  # Step2 결과
ss.setdefault("results_ready", False)

# -------------------- 유틸 --------------------
def ordinal(n: int) -> str:
    n = int(n)
    if 10 <= (n % 100) <= 20: suf = "th"
    else: suf = {1:"st", 2:"nd", 3:"rd"}.get(n % 10, "th")
    return f"{n}{suf}"

def copy_button_inline(text: str, key: str):
    """텍스트 오른쪽 상단에 겹쳐 보이는 클립보드 버튼"""
    safe = json.dumps(text or "")
    st.markdown(
        f"""
        <div style="position:relative; height:0;">
          <button
            onclick='navigator.clipboard.writeText({safe})'
            title="복사"
            style="position:absolute; right:10px; top:-46px; border:0; background:#fff;
                   width:28px; height:28px; border-radius:7px; box-shadow:0 0 0 1px #e5e7eb;
                   cursor:pointer;">📋</button>
        </div>
        """,
        unsafe_allow_html=True
    )

# -------------------- HubSpot API helpers --------------------
def hs_search_mbm_by_title(q: str) -> list[tuple[str, str]]:
    """MBM 타이틀로 CRM 검색. object type id가 없으면 빈 결과."""
    if not TOKEN or not MBM_OBJECT_TYPE_ID:
        return []
    url = f"{HS_BASE}/crm/v3/objects/{MBM_OBJECT_TYPE_ID}/search"
    payload = {
        "query": q,
        "properties": [MBM_TITLE_PROP],
        "limit": 10,
        "filterGroups": [{
            "filters": [{"propertyName": MBM_TITLE_PROP, "operator": "CONTAINS_TOKEN", "value": q}]
        }]
    }
    r = requests.post(url, headers=HEADERS_JSON, json=payload, timeout=30)
    if r.status_code >= 400:
        return []
    out = []
    for row in r.json().get("results", []):
        rid = row.get("id")
        title = (row.get("properties") or {}).get(MBM_TITLE_PROP) or "(제목 없음)"
        out.append((title, rid))
    return out

def _clone_page_site(template_id: str, clone_name: str) -> dict:
    url = f"{HS_BASE}/cms/v3/pages/site-pages/clone"
    r = requests.post(url, headers=HEADERS_JSON, json={"id": str(template_id), "name": clone_name}, timeout=45)
    r.raise_for_status()
    return r.json()

def hs_push_live_site(page_id: str):
    url = f"{HS_BASE}/cms/v3/pages/site-pages/{page_id}/draft/push-live"
    r = requests.post(url, headers={"Authorization": f"Bearer {TOKEN}", "Accept": "*/*"}, timeout=30)
    r.raise_for_status()

def hs_update_page_name(page_id: str, new_name: str):
    url = f"{HS_BASE}/cms/v3/pages/site-pages/{page_id}"
    r = requests.patch(url, headers=HEADERS_JSON, json={"name": new_name}, timeout=30)
    # 실패해도 진행
    return r.status_code

def hs_clone_marketing_email(template_email_id: str, clone_name: str) -> dict:
    url = f"{HS_BASE}/marketing/v3/emails/clone"
    r = requests.post(url, headers=HEADERS_JSON, json={"id": str(template_email_id), "emailName": clone_name}, timeout=45)
    r.raise_for_status()
    return r.json()

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

# -------------------- Tabs 생성 --------------------
TAB1, TAB2, TAB3 = "MBM 오브젝트 제출", "후속 작업 선택", "최종 링크 공유"

def make_tabs():
    labels = [TAB1]
    if ss.active_stage >= 2:
        labels.append(TAB2)
    if ss.active_stage >= 3:
        labels.append(TAB3)
    return st.tabs(labels), {label: i for i, label in enumerate(labels)}

tabs, idx = make_tabs()

# ======================== 탭 1: 검색/신규작성 ========================
with tabs[idx[TAB1]]:
    st.markdown("### ① MBM 오브젝트 제출")
    st.write("MBM **오브젝트 타이틀**을 기준에서 검색해서 선택하거나, **새로 작성**할 수 있어요.")

    # 검색 인풋 + 복사 아이콘 + 검색 버튼을 같은 행에 배치
    c1, c2 = st.columns([6, 1])
    with c1:
        ss.search_query = st.text_input(
            "검색어",
            key="mbm_search_text",
            value=ss.search_query,
            placeholder="예: [EU] 20250803 GTS NX Webinar",
            label_visibility="collapsed",
        )
        # 입력박스 '안쪽' 오른쪽 상단에 복사 버튼 오버레이
        copy_button_inline(ss.search_query, key="q")

    with c2:
        if st.button("검색", use_container_width=True):
            ss.search_results = hs_search_mbm_by_title(ss.search_query.strip()) if ss.search_query.strip() else []
            ss.picked_id = None

    # 검색 결과 드롭다운
    st.markdown("**결과에서 선택**")
    if ss.search_results:
        options = [f"{t} · #{rid}" for (t, rid) in ss.search_results]
        picked = st.selectbox("", options=options, label_visibility="collapsed")
        # 선택된 항목의 title 추출
        if picked:
            picked_title = picked.split(" · #", 1)[0]
            ss.mbm_title = picked_title
            # 우측 정렬의 '다음' 버튼
            _, r = st.columns([5, 1])
            with r:
                if st.button("다음▶", use_container_width=True):
                    ss.active_stage = 2
                    st.rerun()
    else:
        st.info("검색 결과가 없습니다.", icon="🔎")

    # --- 새 오브젝트 작성 링크(텍스트 스타일, 한 줄) ---
    st.markdown(
        f"""
        <div style="margin-top:10px; padding:10px 12px; border:1px solid #e5e7eb; border-radius:10px;">
          <span style="font-size:14px;">➕ <b>"{(ss.search_query or '').strip() or '새 제목' }"</b> 로
          <a href="#" onclick="parent.postMessage({{'type':'mbm_new'}}, '*'); return false;">새 오브젝트 작성</a></span>
        </div>
        <script>
        window.addEventListener('message', (e) => {{
          if (e.data && e.data.type === 'mbm_new') {{
            const el = window.parent.document.querySelector('button[kind="secondary"]');
          }}
        }});
        </script>
        """,
        unsafe_allow_html=True,
    )
    # 텍스트 링크를 실제로 트리거할 버튼 (JS에서 세션 못바꾸므로 같은 줄에 작은 버튼 준비)
    if st.button("새 오브젝트 작성(위 링크와 동일)", key="btn_new_inline", help="위 링크와 동일 동작입니다.", type="secondary"):
        # 위저드 모드로 전환(실제 CRM 생성 대신 상세 입력 폼 열기)
        ss.wizard_mode = True
        ss.wiz_page = 1
        # 기본 타이틀 프리필
        ss.mbm_title = ss.search_query.strip() or ss.mbm_title or ""
        st.rerun()

    # ---- 위저드(페이지네이션 폼) : 새 오브젝트 작성 시 열림 ----
    if ss.wizard_mode:
        st.markdown("---")
        st.markdown("#### MBM 오브젝트 세부 항목")
        st.caption("※ * 표시는 필수 항목입니다.")
        data = ss.wiz_data

        # 페이지 1
        if ss.wiz_page == 1:
            c1, c2 = st.columns(2)
            with c1:
                ss.mbm_title = st.text_input("MBM 오브젝트 타이틀 *", value=ss.mbm_title or data.get("title",""))
                data["country"] = st.text_input("국가 *", value=data.get("country",""))
            with c2:
                data["mbm_type"] = st.selectbox("MBM 타입 *", ["A MBM : Conference (offline)","B Webinar (online)"], index=0 if data.get("mbm_type") in (None,"A MBM : Conference (offline)") else 1)
                data["city"] = st.text_input("도시 (선택 사항)", value=data.get("city",""))

        # 페이지 2
        if ss.wiz_page == 2:
            c1, c2 = st.columns(2)
            with c1:
                data["mbm_start_date"] = st.date_input("시작일 *", value=data.get("mbm_start_date") or datetime.date.today())
                data["target_audience"] = st.multiselect("타겟 고객 유형 *", ["New customer","Existing (Renewal)","Up sell","Cross sell","Additional","Retroactive","M-collection"], default=data.get("target_audience") or [])
            with c2:
                data["mbm_finish_date"] = st.date_input("종료일 *", value=data.get("mbm_finish_date") or datetime.date.today())
                data["expected_earnings"] = st.number_input("예상 기대매출 (달러 기준) *", min_value=0, value=int(data.get("expected_earnings") or 0), step=10)

            # 판매 타겟 제품(2열 모두 넓게)
            st.markdown("**판매 타겟 제품 (MIDAS) * **")
            products_all = ["MIDAS Civil","MIDAS Gen","MIDAS FEA NX","MIDAS GTS NX","MIDAS CIM","MIDAS NFX","MIDAS MeshFree","MIDAS Civil NX"]
            data["product__midas_"] = st.multiselect("", options=products_all, default=data.get("product__midas_") or [], label_visibility="collapsed")

        # 페이지 3 (서술형은 1열 배치)
        if ss.wiz_page == 3:
            data["campaign_key_item"] = st.text_area("캠페인 키 아이템 (제품/서비스/옵션 출시, 업데이트 항목 등) *", height=80, value=data.get("campaign_key_item",""))
            data["market_conditions"] = st.text_area("시장 상황 *", height=80, value=data.get("market_conditions",""))
            data["pain_point_of_target"] = st.text_area("타겟 페인포인트 *", height=80, value=data.get("pain_point_of_target",""))
            data["benefits"] = st.text_area("핵심 고객가치 *", height=80, value=data.get("benefits",""))
            data["purpose_of_mbm"] = st.selectbox("목적 *", ["기존 고객 제품 사용성 강화 (Training)","신규 리드 창출","세일즈 기회 창출"], index=0 if (data.get("purpose_of_mbm") in (None,"기존 고객 제품 사용성 강화 (Training)")) else (["기존 고객 제품 사용성 강화 (Training)","신규 리드 창출","세일즈 기회 창출"].index(data["purpose_of_mbm"]) if data.get("purpose_of_mbm") in ["기존 고객 제품 사용성 강화 (Training)","신규 리드 창출","세일즈 기회 창출"] else 0))
            data["description_of_detailed_targets___________"] = st.text_area("타겟 상세 설명 *", height=80, value=data.get("description_of_detailed_targets___________",""))

        # 페이지네이션(인풋 아래)
        cprev, cpages, cnext = st.columns([1,5,1])
        with cprev:
            st.button("←", disabled=ss.wiz_page<=1, on_click=lambda: setattr(ss, "wiz_page", ss.wiz_page-1))
        with cpages:
            st.markdown(f"<div style='text-align:center;'>페이지 {ss.wiz_page} / 3</div>", unsafe_allow_html=True)
        with cnext:
            st.button("→", disabled=ss.wiz_page>=3, on_click=lambda: setattr(ss, "wiz_page", ss.wiz_page+1))

        # 생성 버튼(폼 폭 100%)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if st.button("MBM 오브젝트 생성하기", type="primary", use_container_width=True):
            # 필수값 체크(간단)
            must = [
                ("title", ss.mbm_title),
                ("country", data.get("country")),
                ("mbm_type", data.get("mbm_type")),
                ("mbm_start_date", data.get("mbm_start_date")),
                ("mbm_finish_date", data.get("mbm_finish_date")),
                ("target_audience", data.get("target_audience")),
                ("expected_earnings", data.get("expected_earnings")),
                ("product__midas_", data.get("product__midas_")),
                ("campaign_key_item", data.get("campaign_key_item")),
                ("market_conditions", data.get("market_conditions")),
                ("pain_point_of_target", data.get("pain_point_of_target")),
                ("benefits", data.get("benefits")),
                ("purpose_of_mbm", data.get("purpose_of_mbm")),
                ("description_of_detailed_targets___________", data.get("description_of_detailed_targets___________")),
            ]
            if any(not v for k, v in must):
                st.error("모든 필수 항목을 작성해주세요.")
            else:
                ss.active_stage = 2
                st.success("임시 MBM 데이터가 저장되었습니다. 다음 단계로 이동합니다.")
                st.rerun()

# ======================== 탭 2: 후속작업 ========================
if ss.active_stage >= 2:
    with tabs[idx[TAB2]]:
        st.markdown("### ② 후속 작업 선택")

        with st.form("post_actions"):
            c1, c2 = st.columns([2, 1])
            with c1:
                st.markdown("**MBM 오브젝트 타이틀 (읽기 전용)**")
                st.text_input("MBM Title", value=ss.mbm_title, disabled=True, label_visibility="collapsed")
            with c2:
                st.markdown("**생성할 자산**")
                make_web = st.checkbox("웹페이지 생성", value=True)
                make_em  = st.checkbox("이메일 생성", value=False)
                make_form = st.checkbox("신청 폼 생성", value=True)
                email_count = st.number_input("이메일 개수", min_value=1, max_value=10, value=1, step=1, disabled=not make_em)

            submitted = st.form_submit_button("생성하기", type="primary")

        if submitted:
            ss.links = {"Website": [], "Email": [], "Form": []}
            try:
                # Website page
                if make_web and WEBSITE_TEMPLATE_ID:
                    name = f"{ss.mbm_title}_landing page"
                    with st.spinner("웹페이지 생성 중…"):
                        site = _clone_page_site(WEBSITE_TEMPLATE_ID, name)
                        pid  = str(site.get("id") or site.get("objectId") or "")
                        hs_update_page_name(pid, name)
                        hs_push_live_site(pid)
                        edit_url = f"https://app.hubspot.com/cms/{PORTAL_ID}/website/pages/{pid}/edit"
                        ss.links["Website"].append(("편집", edit_url))

                # Emails
                if make_em:
                    for i in range(1, int(email_count)+1):
                        ename = f"{ss.mbm_title}_email_{ordinal(i)}"
                        with st.spinner(f"이메일 생성 중… ({ename})"):
                            em = hs_clone_marketing_email(EMAIL_TEMPLATE_ID, ename)
                            em_id = str(em.get("id") or em.get("contentId") or "")
                            edit_url = f"https://app.hubspot.com/email/{PORTAL_ID}/edit/{em_id}/settings"
                            ss.links["Email"].append((f"Email {ordinal(i)}", edit_url))

                # Register form
                if make_form:
                    fname = f"{ss.mbm_title}_register form"
                    with st.spinner("신청 폼 생성 중…"):
                        fm = clone_form_with_hidden_value(REGISTER_FORM_TEMPLATE_GUID, fname, ss.mbm_title, MBM_TITLE_PROP)
                        gid = fm.get("guid") or fm.get("id")
                        edit_url = f"https://app.hubspot.com/forms/{PORTAL_ID}/{gid}/edit"
                        ss.links["Form"].append(("편집", edit_url))

                ss.active_stage = 3
                ss.results_ready = True
                st.success("생성이 완료되었습니다. ‘최종 링크 공유’ 탭으로 이동합니다.")
                st.rerun()
            except requests.HTTPError as http_err:
                st.error(f"HubSpot API 오류: {http_err.response.status_code} - {http_err.response.text}")
            except Exception as e:
                st.error(f"실패: {e}")

# ======================== 탭 3: 최종 링크 공유 ========================
if ss.active_stage >= 3:
    with tabs[idx[TAB3]]:
        st.markdown("### ③ 최종 링크 공유")
        st.success(f"MBM 생성 결과 – **{ss.mbm_title or '(제목 없음)'}**")

        def link_box(title: str, items: list[tuple[str,str]], prefix_key: str):
            st.markdown(f"#### {title}")
            for i, (label, url) in enumerate(items, start=1):
                box = st.container(border=True)
                with box:
                    c1, c2 = st.columns([8, 1])
                    with c1:
                        st.markdown(f"**{label}**  \n{url}")
                    with c2:
                        # 복사 버튼
                        safe = json.dumps(url or "")
                        st.markdown(
                            f"""
                            <button onclick='navigator.clipboard.writeText({safe})'
                              style="padding:8px 10px;border:1px solid #e5e7eb;border-radius:10px;background:#fff;cursor:pointer;">📋</button>
                            """,
                            unsafe_allow_html=True
                        )

        if ss.links.get("Website"):
            link_box("Website Page", ss.links["Website"], "web")
        if ss.links.get("Email"):
            link_box("Marketing Emails", ss.links["Email"], "em")
        if ss.links.get("Form"):
            link_box("Register Form", ss.links["Form"], "fm")

        st.divider()

        # 전체 결과 텍스트(사라지지 않도록 ss.links 기반으로 항상 재생성)
        lines = [f"[MBM] 생성 결과 - {ss.mbm_title or ''}", ""]
        if ss.links.get("Website"):
            lines.append("▼ Website Page")
            for label, url in ss.links["Website"]:
                lines.append(f"- {label}: {url}")
            lines.append("")
        if ss.links.get("Email"):
            lines.append("▼ Marketing Emails")
            for label, url in ss.links["Email"]:
                lines.append(f"- {label}: {url}")
            lines.append("")
        if ss.links.get("Form"):
            lines.append("▼ Register Form")
            for label, url in ss.links["Form"]:
                lines.append(f"- {label}: {url}")
            lines.append("")

        all_text = "\n".join(lines).strip()
        st.text_area("전체 결과 (미리보기)", value=all_text, height=200, label_visibility="collapsed")
        if st.button("전체 결과물 복사", type="primary"):
            st.components.v1.html(
                f"<script>navigator.clipboard.writeText({json.dumps(all_text)});</script>",
                height=0, width=0
            )
            st.toast("복사가 완료되었습니다. 메모장에 붙여넣기 하세요")
