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

# Website Page 템플릿 (Website 전용) — 기본값은 주신 템플릿의 페이지 ID
LANDING_PAGE_TEMPLATE_ID = st.secrets.get("LANDING_PAGE_TEMPLATE_ID", "194363146790")
WEBSITE_PAGE_TEMPLATE_TITLE = st.secrets.get("WEBSITE_PAGE_TEMPLATE_TITLE", "[Template] Event Landing Page_GOM")

# Email 템플릿
EMAIL_TEMPLATE_ID = st.secrets.get("EMAIL_TEMPLATE_ID", "162882078001")

# Register Form 템플릿(guid)
REGISTER_FORM_TEMPLATE_GUID = "83e40756-9929-401f-901b-8e77830d38cf"

# MBM 오브젝트 기본 설정
MBM_HIDDEN_FIELD_NAME = "title"        # Register Form 숨김 필드 이름
ACCESS_PASSWORD = "mid@sit0901"        # 본문 접근 보호 비밀번호

HS_BASE = "https://api.hubapi.com"
HEADERS_JSON = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# 스키마에서 보여줄 필드(요청하신 내부명 순서)
MBM_FIELDS = [
    "title",
    "country",
    "mbm_type",
    "city",
    "location",
    "mbm_start_date",
    "mbm_finish_date",
    "target_audience",
    "description_of_detailed_targets___________",
    "purpose_of_mbm",
    "expected_earnings",
    "product__midas_",
    "campaign_key_item",
    "market_conditions",
    "pain_point_of_target",
    "benefits",
]
# 항상 숨김 + True로 전송
MBM_HIDDEN_TRUE = "auto_generate_campaign"

# 긴 텍스트로 표시할 후보
LONG_TEXT_FIELDS = {
    "description_of_detailed_targets___________",
    "purpose_of_mbm",
    "market_conditions",
    "pain_point_of_target",
    "benefits",
}

# =============== 세션 상태 ===============
ss = st.session_state
ss.setdefault("auth_ok", False)         # 접근 허용 여부
ss.setdefault("active_stage", 1)        # 1=제출, 2=선택, 3=공유
ss.setdefault("mbm_submitted", False)   # ① 완료 여부 (MBM 생성 완료 or 스킵)
ss.setdefault("mbm_title", "")
ss.setdefault("show_prop_form", False)  # ① 타이틀 다음 → 상세 폼 펼침
ss.setdefault("results", None)          # {"title": str, "links": dict}
ss.setdefault("mbm_object", None)       # {"id": "...", "typeId": "...", "url": "record url"}

# =============== 본문 접근 암호 (사이드바 X, 본문에 표시) ===============
if not ss.auth_ok:
    box = st.container(border=True)
    with box:
        st.subheader("🔒 Access")
        st.caption("해당 기능은 마이다스아이티 구성원만 입력이 가능합니다. MBM 에셋 생성을 위해 비밀번호를 입력해주세요.")
        colp1, colp2 = st.columns([5, 1])
        with colp1:
            pwd = st.text_input("비밀번호", type="password", label_visibility="collapsed", placeholder="비밀번호를 입력하세요")
        with colp2:
            if st.button("접속", use_container_width=True):
                if pwd == ACCESS_PASSWORD:
                    ss.auth_ok = True
                    st.rerun()
                else:
                    st.error("암호가 일치하지 않습니다.")
                    st.info("도움말: 사내 공지 메일 또는 관리자에게 문의해주세요.")
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
    dt = datetime.datetime(d.year, d.month, d.day, 0, 0, 0)
    return str(int(time.mktime(dt.timetuple()) * 1000))

def human_label(internal: str) -> str:
    mapping = {
        "auto_generate_campaign": "자동 캠페인 생성 (숨김)",
        "title": "MBM 오브젝트 타이틀",
        "country": "국가",
        "mbm_type": "MBM 타입",
        "city": "도시",
        "location": "장소",
        "mbm_start_date": "시작일",
        "mbm_finish_date": "종료일",
        "target_audience": "타겟",
        "description_of_detailed_targets___________": "타겟 상세 설명",
        "purpose_of_mbm": "목적",
        "expected_earnings": "예상 수익",
        "product__midas_": "제품(MIDAS)",
        "campaign_key_item": "캠페인 핵심 항목",
        "market_conditions": "시장 상황",
        "pain_point_of_target": "타겟 Pain Point",
        "benefits": "핵심 베네핏",
    }
    return mapping.get(internal, internal)

# =============== HubSpot API ===============
# --- Website Page 전용 ---
def hs_clone_site_page(template_id: str, clone_name: str) -> dict:
    url = f"{HS_BASE}/cms/v3/pages/site-pages/clone"
    last = None
    for key in ("name", "cloneName"):
        r = requests.post(url, headers=HEADERS_JSON, json={"id": str(template_id), key: clone_name}, timeout=45)
        if r.status_code < 400:
            return r.json()
        last = r
    last.raise_for_status()

def hs_update_site_page_name(page_id: str, new_name: str) -> None:
    url = f"{HS_BASE}/cms/v3/pages/site-pages/{page_id}"
    r = requests.patch(url, headers=HEADERS_JSON, json={"name": new_name}, timeout=30)
    if r.status_code >= 400:
        st.warning(f"페이지 내부 이름 변경 실패: {r.status_code}")

def hs_push_live_site(page_id: str) -> None:
    url = f"{HS_BASE}/cms/v3/pages/site-pages/{page_id}/draft/push-live"
    r = requests.post(url, headers={"Authorization": f"Bearer {TOKEN}", "Accept": "*/*"}, timeout=30)
    r.raise_for_status()

def hs_get_site_page(page_id: str) -> dict:
    url = f"{HS_BASE}/cms/v3/pages/site-pages/{page_id}"
    r = requests.get(url, headers=HEADERS_JSON, timeout=30)
    r.raise_for_status()
    return r.json()

def extract_best_live_url(page_json: dict) -> str | None:
    for k in ("publicUrl", "url", "absoluteUrl", "absolute_url", "publishedUrl"):
        val = page_json.get(k)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None

# ---- Website pages 목록 검색 (제목/키워드로 자동 해결) ----
def list_site_pages(limit_per_page: int = 100):
    after = None
    while True:
        params = {"limit": limit_per_page}
        if after:
            params["after"] = after
        r = requests.get(f"{HS_BASE}/cms/v3/pages/site-pages", headers=HEADERS_JSON, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        items = data.get("results") or data.get("items") or []
        for it in items:
            yield it
        after = (data.get("paging") or {}).get("next", {}).get("after")
        if not after:
            break

def find_site_page_id_smart(title_hint: str | None) -> str | None:
    title_hint = (title_hint or "").strip()
    if title_hint:
        for it in list_site_pages():
            name = (it.get("name") or "").strip()
            page_title = (it.get("pageTitle") or it.get("htmlTitle") or "").strip()
            if name == title_hint or page_title == title_hint:
                return str(it.get("id") or it.get("objectId") or "")
    best = None; best_score = -1
    for it in list_site_pages():
        text = " ".join([
            (it.get("name") or ""),
            (it.get("pageTitle") or ""),
            (it.get("htmlTitle") or "")
        ]).lower()
        score = 0
        if "template" in text: score += 2
        if "mbm" in text: score += 2
        if "landing" in text: score += 1
        if "webinar" in text: score += 1
        if score > best_score:
            best_score = score; best = it
    if best and best_score > 0:
        return str(best.get("id") or best.get("objectId") or "")
    return None

def clone_site_page_with_fallback(primary_id: str, clone_name: str, title_hint: str | None) -> dict:
    try:
        return hs_clone_site_page(primary_id, clone_name)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            resolved = find_site_page_id_smart(title_hint)
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

# ---- MBM Custom Object 스키마/생성 ----
def get_custom_object_schemas() -> dict:
    url = f"{HS_BASE}/crm/v3/schemas"
    r = requests.get(url, headers=HEADERS_JSON, timeout=30)
    r.raise_for_status()
    return r.json()

def resolve_mbm_schema() -> dict | None:
    data = get_custom_object_schemas()
    for s in data.get("results", []):
        name = (s.get("name") or "").lower()
        label = (s.get("labels", {}).get("singular") or "").lower()
        if "mbm" in name or "mbm" in label:
            return s
    for s in data.get("results", []):
        if any(p.get("name") == "title" for p in s.get("properties", [])):
            return s
    return None

def get_mbm_properties_map() -> dict[str, dict]:
    sch = resolve_mbm_schema()
    if not sch:
        raise RuntimeError("MBM 오브젝트 스키마를 찾지 못했습니다.")
    return {p.get("name"): p for p in sch.get("properties", [])}

def hs_create_mbm_object(properties: dict) -> dict:
    schema = resolve_mbm_schema()
    if not schema:
        raise RuntimeError("MBM 오브젝트 스키마를 찾지 못했습니다. (포털에서 커스텀 오브젝트 정의를 확인하세요)")
    fqn = schema.get("fullyQualifiedName") or schema.get("name")
    url = f"{HS_BASE}/crm/v3/objects/{fqn}"
    r = requests.post(url, headers=HEADERS_JSON, json={"properties": properties}, timeout=45)
    r.raise_for_status()
    obj = r.json()
    obj_id = str(obj.get("id") or obj.get("objectId") or "")
    type_id = schema.get("objectTypeId") or ""
    record_url = f"https://app.hubspot.com/contacts/{PORTAL_ID}/record/{type_id}/{obj_id}"
    return {"id": obj_id, "typeId": type_id, "url": record_url, "raw": obj}

# =============== 탭 구성 ===============
TAB1 = "MBM 오브젝트 제출"
TAB2 = "후속 작업 선택"
TAB3 = "최종 링크 공유"

def _focus_tab(label: str):
    import json as _json
    safe_label = _json.dumps(label)
    st.components.v1.html(
        f"""
        <script>
        (function(){{
          const targetText = {safe_label};
          function clickTarget(root) {{
            const tabs = root.querySelectorAll('[role="tab"]');
            for (const t of tabs) {{
              const txt = (t.innerText || t.textContent || "").trim();
              if (txt === targetText || txt.indexOf(targetText) !== -1) {{ t.click(); return true; }}
            }}
            return false;
          }}
          function tryClick() {{
            const doc = window.parent?.document || document;
            if (clickTarget(doc)) return true;
            const frames = doc.querySelectorAll('iframe');
            for (const f of frames) {{
              try {{ if (f.contentDocument && clickTarget(f.contentDocument)) return true; }} catch (e) {{}}
            }}
            return false;
          }}
          let attempts = 0;
          const id = setInterval(() => {{
            attempts++;
            if (tryClick() || attempts >= 20) clearInterval(id);
          }}, 200);
          const targetDoc = window.parent?.document || document;
          const obs = new MutationObserver(() => tryClick());
          obs.observe(targetDoc, {{subtree:true, childList:true}});
          setTimeout(()=>obs.disconnect(), 5000);
        }})();
        </script>
        """,
        height=0, width=0
    )

def make_tabs():
    labels = [TAB1]
    if ss.mbm_submitted:
        labels.append(TAB2)
    if ss.results:
        labels.append(TAB3)
    try:
        t = st.tabs(labels, key="mbm_tabs")
    except TypeError:
        t = st.tabs(labels)
    idx = {label: i for i, label in enumerate(labels)}
    if ss.active_stage == 2 and TAB2 in idx:
        _focus_tab(TAB2)
    elif ss.active_stage == 3 and TAB3 in idx:
        _focus_tab(TAB3)
    return t, idx

# === 탭바는 단 한 번만 생성 (중복 렌더 방지) ===
tabs, idx = make_tabs()

# =============== 탭①: MBM 오브젝트 제출 (스키마 기반 위젯) ===============
with tabs[idx[TAB1]]:
    st.markdown("### ① MBM 오브젝트 제출")

    # 1-1) 타이틀 먼저 입력 → [다음] 누르면 상세 폼이 펼쳐짐
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

    ca, cb, cc = st.columns([2,2,1])
    with ca:
        if st.button("다음 ▶ 필드 입력 열기", use_container_width=True, type="primary", disabled=not ss.mbm_title):
            if not ss.mbm_title:
                st.error("MBM 오브젝트 타이틀을 먼저 입력하세요.")
            else:
                ss.show_prop_form = True
                ss.mbm_submitted = False  # Skip 후 다시 폼 열릴 수 있도록 리셋
                st.rerun()
    with cb:
        # 이미 생성한 경우 스킵
        if st.button("이미 생성했어요 ▶ 스킵", use_container_width=True):
            if not ss.mbm_title:
                st.error("타이틀을 입력해야 다음 단계로 이동할 수 있어요.")
            else:
                ss.mbm_submitted = True
                ss.active_stage = 2
                st.success("MBM 오브젝트 생성 단계를 건너뜁니다. ‘후속 작업 선택’ 탭으로 이동합니다.")
                st.rerun()
    with cc:
        st.empty()

    # 1-2) 상세 속성 폼 (타이틀 제출 후 표시) — 스키마 기반 위젯
    if ss.show_prop_form and not ss.mbm_submitted:
        st.markdown("---")
        st.markdown("#### MBM 오브젝트 세부 항목")

        # 스키마 메타 불러오기
        try:
            props_map = get_mbm_properties_map()
        except Exception as e:
            st.error(f"스키마 로드 실패: {e}")
            props_map = {}

        def render_field(name: str, meta: dict):
            lbl = human_label(name)
            ptype = (meta.get("type") or "").lower()
            options = meta.get("options") or []
            key = f"fld_{name}"

            # 열거형 → selectbox
            if ptype in ("enumeration", "enumerationoptions", "enum") or options:
                labels = [opt.get("label") or opt.get("display") or opt.get("value") for opt in options]
                values = [opt.get("value") for opt in options]
                if not labels:
                    return st.text_input(lbl, key=key)
                idx_opt = st.selectbox(lbl, options=list(range(len(labels))),
                                       format_func=lambda i: labels[i], key=key)
                return values[idx_opt]

            # 날짜/일시
            if ptype in ("date", "datetime"):
                d = st.date_input(lbl, value=None, format="YYYY-MM-DD", key=key)
                return to_epoch_ms(d) if d else None

            # 불리언
            if ptype in ("bool", "boolean"):
                v = st.checkbox(lbl, value=False, key=key)
                return "true" if v else "false"

            # 숫자
            if ptype in ("number", "integer", "long", "double"):
                return str(int(st.number_input(lbl, min_value=0.0, step=1.0, format="%.0f", key=key)))

            # 긴 텍스트 후보 → text_area
            if name in LONG_TEXT_FIELDS:
                return st.text_area(lbl, height=100, key=key)

            # 기본: 텍스트
            return st.text_input(lbl, key=key)

        with st.form("mbm_props_form", clear_on_submit=False):
            hidden_true = "true"  # auto_generate_campaign

            values = {}
            for n in MBM_FIELDS:
                meta = props_map.get(n, {})
                if n == "title":
                    values[n] = st.text_input(human_label(n), value=ss.mbm_title, key="fld_title_override")
                else:
                    values[n] = render_field(n, meta)

            submitted_obj = st.form_submit_button("MBM 오브젝트 생성하기", type="primary")

        if submitted_obj:
            if not values.get("title"):
                st.error("타이틀은 필수입니다.")
                st.stop()

            payload = {k: v for k, v in values.items() if v not in (None, "")}
            payload[MBM_HIDDEN_TRUE] = hidden_true

            try:
                with st.spinner("HubSpot에 MBM 오브젝트 생성 중…"):
                    created = hs_create_mbm_object(payload)
                    ss.mbm_object = created
                    ss.mbm_title = values["title"]
                    ss.mbm_submitted = True
                    ss.active_stage = 2
                    st.success("생성 완료! ‘후속 작업 선택’ 탭으로 이동합니다.")
                    st.rerun()
            except requests.HTTPError as http_err:
                st.error(f"HubSpot API 오류: {http_err.response.status_code} - {http_err.response.text}")
            except Exception as e:
                st.error(f"실패: {e}")

# =============== 탭②: 후속 작업 선택 ===============
if ss.mbm_submitted:
    with tabs[idx[TAB2]]:
        st.markdown("### ② 후속 작업 선택")
        if ss.mbm_object:
            st.info(f"MBM 오브젝트 생성됨: [열기]({ss.mbm_object.get('url')})")

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
            links = {"Website Page": [], "Email": [], "Form": []}
            try:
                # Website Page
                if make_wp:
                    page_name = f"{ss.mbm_title}_landing page"
                    with st.spinner(f"웹페이지 복제 중… ({page_name})"):
                        page_data = clone_site_page_with_fallback(
                            LANDING_PAGE_TEMPLATE_ID, page_name, WEBSITE_PAGE_TEMPLATE_TITLE
                        )
                        page_id = str(page_data.get("id") or page_data.get("objectId") or "")
                        hs_update_site_page_name(page_id, page_name)
                        hs_push_live_site(page_id)
                        try:
                            refreshed = hs_get_site_page(page_id)
                        except Exception:
                            refreshed = page_data
                        live_url = extract_best_live_url(refreshed) or f"https://app.hubspot.com/cms/{PORTAL_ID}/website/pages/{page_id}/view"
                        links["Website Page"].append(("보기", live_url))

                # Emails
                if make_em:
                    for i in range(1, int(email_count) + 1):
                        email_name = f"{ss.mbm_title}_email_{ordinal(i)}"
                        with st.spinner(f"마케팅 이메일 복제 중… ({email_name})"):
                            em = hs_clone_marketing_email(EMAIL_TEMPLATE_ID, email_name)
                            em_id = str(em.get("id") or em.get("contentId") or "")
                            hs_update_email_name(em_id, email_name)
                            edit_url = f"https://app.hubspot.com/email/{PORTAL_ID}/edit/{em_id}/settings"
                            links["Email"].append((f"Email {ordinal(i)}", edit_url))

                # Register Form
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
        st.text_area("전체 결과 (미리보기)", value=all_text, height=180, label_visibility="collapsed")
        if st.button("전체 결과물 복사", type="primary"):
            st.components.v1.html(
                f"<script>navigator.clipboard.writeText({json.dumps(all_text)});</script>",
                height=0, width=0
            )
            st.toast("복사가 완료되었습니다. 메모장에 붙여넣기 하세요")
