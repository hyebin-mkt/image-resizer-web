# pages/mbm_object_form.py
import json, uuid, time, datetime, re
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

# Website Page 템플릿(Website 전용)
LANDING_PAGE_TEMPLATE_ID = st.secrets.get("LANDING_PAGE_TEMPLATE_ID", "194363146790")
WEBSITE_PAGE_TEMPLATE_TITLE = st.secrets.get("WEBSITE_PAGE_TEMPLATE_TITLE", "[Template] Event Landing Page_GOM")

# Email 템플릿
EMAIL_TEMPLATE_ID = st.secrets.get("EMAIL_TEMPLATE_ID", "162882078001")

# Register Form 템플릿(guid)
REGISTER_FORM_TEMPLATE_GUID = "83e40756-9929-401f-901b-8e77830d38cf"

# MBM 오브젝트 / 접근보호
MBM_HIDDEN_FIELD_NAME = "title"       # Register Form 숨김 필드 이름
ACCESS_PASSWORD = "mid@sit0901"       # 본문 접근 보호 비밀번호

# 스키마 실패시 폴백용 HubSpot Form(임베드)
FALLBACK_FORM_ID = st.secrets.get("MBM_FALLBACK_FORM_ID", "a9e1a5e8-4c46-461f-b823-13cc4772dc6c")

HS_BASE = "https://api.hubapi.com"
HEADERS_JSON = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# 표시/제출할 필드 (내부명)
MBM_FIELDS = [
    "title",
    "country",
    "mbm_type",
    "city",  # 유일한 선택 항목(옵션)
    "location",
    "mbm_start_date",
    "mbm_finish_date",
    "target_audience",   # 멀티 체크
    "expected_earnings",
    "product__midas_",   # 멀티 체크
    "campaign_key_item",
    "market_conditions",
    "pain_point_of_target",
    "benefits",
    "description_of_detailed_targets___________",
    "purpose_of_mbm",
]

# 필수/선택 (city만 선택)
REQUIRED_FIELDS = {f for f in MBM_FIELDS if f != "city"}

# 긴 텍스트 후보
LONG_TEXT_FIELDS = {
    "description_of_detailed_targets___________",
    "purpose_of_mbm",
    "market_conditions",
    "pain_point_of_target",
    "benefits",
}

# 라벨(요청 반영)
LABEL_OVERRIDES = {
    "title": "MBM 오브젝트 타이틀 *",
    "country": "국가 *",
    "mbm_type": "MBM 타입 *",
    "city": "도시 (선택 사항)",
    "location": "위치 (세미나 장소 또는 온라인 플랫폼명) *",
    "mbm_start_date": "시작일 *",
    "mbm_finish_date": "종료일 *",
    "target_audience": "타겟 고객 유형 *",
    "expected_earnings": "예상 기대매출 (달러 기준) *",
    "product__midas_": "판매 타겟 제품 (MIDAS) *",
    "campaign_key_item": "캠페인 키 아이템 (제품/서비스/옵션 출시, 업데이트 항목 등) *",
    "market_conditions": "시장 상황 *",
    "pain_point_of_target": "타겟 페인포인트 *",
    "benefits": "핵심 고객가치 *",
    "description_of_detailed_targets___________": "타겟 상세 설명 *",
    "purpose_of_mbm": "목적 *",
}

# 멀티 체크 필드
MULTI_CHECK_FIELDS = {"target_audience", "product__midas_"}

# 스키마 옵션이 비어있을 때 사용할 기본 옵션(표기=값)
DEFAULT_ENUM_OPTIONS = {
    "target_audience": [
        "New customer 신규 판매",
        "Existing Customers (Renewal) MODS 재계약",
        "Existing Customers (Up sell)",
        "Existing Customers (Cross Sell)",
        "Existing Customers (Additional) 추가 판매",
        "Existing Customers (Retroactive) 소급 판매",
        "M-collection (M-collection 전환)",
    ],
    "product__midas_": [
        "MIDAS Civil",
        "MIDAS FEA NX",
        "MIDAS CIM",
        "MIDAS MeshFree",
        "MIDAS Gen",
        "MIDAS GTS NX",
        "MIDAS NFX",
        "MIDAS CIVIL NX",
    ],
}

# =============== 세션 상태 ===============
ss = st.session_state
ss.setdefault("auth_ok", False)
ss.setdefault("auth_error", False)
ss.setdefault("active_stage", 1)         # 1=제출, 2=선택, 3=공유
ss.setdefault("mbm_submitted", False)
ss.setdefault("mbm_title", "")
ss.setdefault("show_prop_form", False)
ss.setdefault("prop_step", 1)
ss.setdefault("results", None)
ss.setdefault("mbm_object", None)
# 슬러그 계산용 메타
ss.setdefault("slug_country", None)
ss.setdefault("slug_finish_ms", None)

# =============== 사이드바(바로가기/작성자) ===============
st.sidebar.markdown("### 🔗 바로가기")
st.sidebar.link_button("HubSpot File 바로가기", "https://app.hubspot.com/files/2495902", use_container_width=True)
st.sidebar.link_button("HubSpot Website 바로가기", "https://app.hubspot.com/website/2495902", use_container_width=True)
st.sidebar.link_button("MBM 가이드북", "https://example.com", use_container_width=True)  # 필요 시 실제 링크로 교체
st.sidebar.divider()
st.sidebar.caption("© Chacha")

# =============== 본문 접근 암호(입력란 바로 아래 에러) ===============
if not ss.auth_ok:
    box = st.container(border=True)
    with box:
        st.subheader("🔒 Access")
        st.caption("해당 기능은 마이다스아이티 구성원만 입력이 가능합니다. MBM 에셋 생성을 위해 비밀번호를 입력해주세요.")
        with st.form("access_gate"):
            pwd = st.text_input("비밀번호", type="password",
                                label_visibility="collapsed", placeholder="비밀번호를 입력하세요")
            submitted = st.form_submit_button("접속", use_container_width=True)
        if submitted:
            if pwd == ACCESS_PASSWORD:
                ss.auth_ok = True
                ss.auth_error = False
                st.rerun()
            else:
                ss.auth_error = True
        if ss.auth_error:
            st.error("암호가 일치하지 않습니다.")
            st.help("도움말: 사내 공지 메일 또는 관리자에게 문의해주세요.")
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

def yyyymmdd_from_epoch_ms(ms: str | None) -> str | None:
    if not ms: return None
    try:
        return datetime.datetime.utcfromtimestamp(int(ms) / 1000).strftime("%Y%m%d")
    except Exception:
        return None

COUNTRY_CODE_MAP = {
    "korea": "KR", "south korea": "KR", "대한민국": "KR", "한국": "KR",
    "japan": "JP", "일본": "JP",
    "china": "CN", "중국": "CN",
    "taiwan": "TW", "대만": "TW",
    "hong kong": "HK",
    "vietnam": "VN", "베트남": "VN",
    "thailand": "TH", "태국": "TH",
    "malaysia": "MY", "말레이시아": "MY",
    "singapore": "SG", "싱가포르": "SG",
    "indonesia": "ID", "인도네시아": "ID",
    "india": "IN", "인도": "IN",
    "philippines": "PH", "필리핀": "PH",
    "uae": "AE", "united arab emirates": "AE",
    "saudi": "SA", "saudi arabia": "SA", "사우디": "SA",
    "algeria": "DZ", "알제리": "DZ",
    "united kingdom": "GB", "uk": "GB", "영국": "GB",
    "germany": "DE", "독일": "DE",
    "france": "FR", "프랑스": "FR",
    "italy": "IT", "이탈리아": "IT",
    "spain": "ES", "스페인": "ES",
    "united states": "US", "usa": "US", "미국": "US",
    "canada": "CA", "캐나다": "CA",
    "brazil": "BR", "브라질": "BR",
    "mexico": "MX", "멕시코": "MX",
    "australia": "AU", "호주": "AU",
    "new zealand": "NZ", "뉴질랜드": "NZ",
    "turkey": "TR", "터키": "TR",
}

def country_code_from_value(v: str | None, fallback_title: str | None = None) -> str | None:
    if not v: v = ""
    s = str(v).strip()
    if len(s) == 2 and s.isalpha():
        return s.upper()
    m = re.search(r"\b([A-Z]{2})\b", s)
    if m: return m.group(1).upper()
    low = s.lower()
    for name, code in COUNTRY_CODE_MAP.items():
        if name in low:
            return code
    if fallback_title:
        m2 = re.search(r"\[([A-Za-z]{2})\]", fallback_title)
        if m2: return m2.group(1).upper()
    return (s[:2] or "XX").upper()

def build_content_slug(country_value: str | None, finish_ms: str | None, title_hint: str | None) -> str | None:
    code = country_code_from_value(country_value, fallback_title=title_hint)
    date_str = yyyymmdd_from_epoch_ms(finish_ms)
    if code and date_str:
        return f"{code}_{date_str}"
    if not date_str and title_hint:
        m = re.search(r"(20\d{6}|\d{8})", title_hint)
        if m:
            date_str = m.group(1)
            if len(date_str) == 8:
                return f"{code}_{date_str}"
    return None

def human_label(internal: str) -> str:
    return LABEL_OVERRIDES.get(internal, internal + (" *" if internal in REQUIRED_FIELDS else ""))

# =============== HubSpot API(페이지/이메일/폼/스키마) ===============
def hs_clone_site_page(template_id: str, clone_name: str) -> dict:
    url = f"{HS_BASE}/cms/v3/pages/site-pages/clone"
    last = None
    for key in ("name", "cloneName"):
        r = requests.post(url, headers=HEADERS_JSON, json={"id": str(template_id), key: clone_name}, timeout=45)
        if r.status_code < 400: return r.json()
        last = r
    last.raise_for_status()

def hs_update_site_page(page_id: str, patch: dict) -> requests.Response:
    url = f"{HS_BASE}/cms/v3/pages/site-pages/{page_id}"
    r = requests.patch(url, headers=HEADERS_JSON, json=patch, timeout=30)
    return r

def update_site_page_slug_safely(page_id: str, slug: str):
    for key in ("slug", "path", "urlSlug", "pageSlug"):
        r = hs_update_site_page(page_id, {key: slug})
        if r.status_code < 400:
            return True, key
    return False, None

def hs_push_live_site(page_id: str) -> None:
    url = f"{HS_BASE}/cms/v3/pages/site-pages/{page_id}/draft/push-live"
    r = requests.post(url, headers={"Authorization": f"Bearer {TOKEN}", "Accept": "*/*"}, timeout=30)
    r.raise_for_status()

def hs_clone_marketing_email(template_email_id: str, clone_name: str) -> dict:
    url = f"{HS_BASE}/marketing/v3/emails/clone"
    last_err = None
    for key in ("emailName", "name", "cloneName"):
        try:
            r = requests.post(url, headers=HEADERS_JSON, json={"id": str(template_email_id), key: clone_name}, timeout=45)
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

# ---- Forms v2 (Register Form) ----
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
    if ss.mbm_submitted: labels.append(TAB2)
    if ss.results: labels.append(TAB3)
    try:
        t = st.tabs(labels, key="mbm_tabs")
    except TypeError:
        t = st.tabs(labels)
    idx = {label: i for i, label in enumerate(labels)}
    if ss.active_stage == 2 and TAB2 in idx: _focus_tab(TAB2)
    elif ss.active_stage == 3 and TAB3 in idx: _focus_tab(TAB3)
    return t, idx

tabs, idx = make_tabs()

# =============== 탭①: MBM 오브젝트 제출 (페이지네이션 + 검증 + 폴백) ===============
with tabs[idx[TAB1]]:
    st.markdown("### ① MBM 오브젝트 제출")

    # (A) 타이틀 설정
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
                ss.mbm_submitted = False
                ss.prop_step = 1
                st.rerun()
    with cb:
        if st.button("이미 생성했어요 ▶ 스킵", use_container_width=True):
            if not ss.mbm_title:
                st.error("타이틀을 입력해야 다음 단계로 이동할 수 있어요.")
            else:
                ss.mbm_submitted = True
                ss.active_stage = 2
                st.success("MBM 오브젝트 생성 단계를 건너뜁니다. ‘후속 작업 선택’ 탭으로 이동합니다.")
                st.rerun()
    with cc: st.empty()

    # (B) 상세 속성 폼 (스키마 시도 → 실패시 폴백 iFrame)
    if ss.show_prop_form and not ss.mbm_submitted:
        st.markdown("---")
        st.markdown("#### MBM 오브젝트 세부 항목")
        st.caption("※ * 표시는 필수 항목입니다.")

        schema_failed = False
        try:
            props_map = get_mbm_properties_map()
        except Exception:
            schema_failed = True

        if schema_failed:
            st.warning(
                "스키마 조회 권한이 없어 기본 폼 대신 임시 HubSpot 폼을 표시합니다. "
                "제출 후 아래 버튼으로 다음 단계로 이동하세요. (관리자에게 **crm.schemas.read** 권한 추가 요청 권장)"
            )
            html = f"""
            <div id="hubspot-form"></div>
            <script>
            (function(){{
              var s=document.createElement('script');
              s.src="https://js.hsforms.net/forms/v2.js"; s.async=true;
              s.onload=function(){{
                if(!window.hbspt) return;
                window.hbspt.forms.create({{
                  region:"{HUBSPOT_REGION}",
                  portalId:"{PORTAL_ID}",
                  formId:"{FALLBACK_FORM_ID}",
                  target:"#hubspot-form",
                  inlineMessage:"제출 완료! 아래 버튼으로 다음 단계로 이동하세요."
                }});
              }};
              document.body.appendChild(s);
            }})();
            </script>
            """
            st.components.v1.html(html, height=1200, scrolling=False)
            if st.button("임시 폼 제출 완료 → ‘후속 작업 선택’ 이동", type="primary"):
                ss.mbm_submitted = True
                ss.active_stage = 2
                st.rerun()
            st.stop()

        # ── 정상: 스키마 기반 입력 폼 (페이지네이션) ─────────────────────
        PAGES = [
            ["country", "mbm_type", "city", "location"],
            ["mbm_start_date", "mbm_finish_date", "target_audience", "expected_earnings", "product__midas_"],
            ["campaign_key_item", "market_conditions", "pain_point_of_target", "benefits",
             "description_of_detailed_targets___________", "purpose_of_mbm"],
        ]
        total_steps = len(PAGES)
        ss.prop_step = max(1, min(ss.prop_step, total_steps))

        # --- 위젯 렌더러들 ---
        def _get_options(meta: dict, name: str):
            """스키마 옵션이 비었으면 기본 옵션으로 대체"""
            opts = meta.get("options") or []
            if not opts and name in DEFAULT_ENUM_OPTIONS:
                return [{"label": o, "value": o} for o in DEFAULT_ENUM_OPTIONS[name]]
            return opts

        def render_multi_check(name: str, meta: dict):
            """체크박스 2열 그리드 (값은 세미콜론 연결) – state 유지"""
            opts = _get_options(meta, name)
            labels = [o.get("label") or o.get("display") or o.get("value") for o in opts]
            values = [o.get("value") for o in opts]
            sel_key = f"mchk_{name}"
            selected: set = set(ss.get(sel_key) or [])
            cols = st.columns(2)
            for i, (lab, val) in enumerate(zip(labels, values)):
                with cols[i % 2]:
                    ck = st.checkbox(lab, value=(val in selected), key=f"chk_{name}_{i}")
                if ck: selected.add(val)
                else: selected.discard(val)
            ss[sel_key] = list(selected)
            return ";".join(ss[sel_key])

        def render_field(name: str, meta: dict):
            lbl = LABEL_OVERRIDES.get(name, human_label(name))
            ptype = (meta.get("type") or "").lower()
            options = _get_options(meta, name)
            key = f"fld_{name}"

            if name in MULTI_CHECK_FIELDS:
                # 보이는 라벨은 굵게 처리하지 않음(요청 6)
                st.markdown(lbl)
                return render_multi_check(name, meta)

            if ptype in ("enumeration", "enumerationoptions", "enum") or options:
                labels = [opt.get("label") or opt.get("display") or opt.get("value") for opt in options]
                values = [opt.get("value") for opt in options]
                if not labels:
                    return st.text_input(lbl, key=key)
                # state 보존(기존 선택값이 있으면 그 index로 복구)
                cur_val = ss.get(key)
                default_index = values.index(cur_val) if cur_val in values else 0
                idx_opt = st.selectbox(lbl, options=list(range(len(labels))),
                                       index=default_index,
                                       format_func=lambda i: labels[i], key=f"{key}_idx")
                ss[key] = values[idx_opt]
                return ss[key]

            if ptype in ("date", "datetime"):
                # state 보존: epoch ms → date
                prev_ms = ss.get(key)
                default_date = None
                if prev_ms:
                    try:
                        default_date = datetime.date.fromtimestamp(int(prev_ms)/1000)
                    except Exception:
                        default_date = None
                d = st.date_input(lbl, value=default_date, format="YYYY-MM-DD", key=f"{key}_date")
                val = to_epoch_ms(d) if d else None
                ss[key] = val
                return val

            if name == "expected_earnings" or ptype in ("number", "integer", "long", "double"):
                prev = float(ss.get(key, 0) or 0)
                v = st.number_input(lbl, min_value=0.0, step=1.0, format="%.0f", value=prev, key=f"{key}_num")
                ss[key] = str(int(v))
                return ss[key]

            if name in LONG_TEXT_FIELDS:
                prev = ss.get(key, "")
                val = st.text_area(lbl, height=100, value=prev, key=f"{key}_txt")
                ss[key] = val
                return val

            prev = ss.get(key, "")
            val = st.text_input(lbl, value=prev, key=key)
            ss[key] = val
            return val

        # ---- 입력 영역(페이지별 레이아웃) ----
        form_box = st.container(border=True)

        with form_box:
            current_fields = PAGES[ss.prop_step-1]

            # 페이지 3은 1열 배치(요청 3)
            if ss.prop_step == 3:
                for fname in current_fields:
                    meta = props_map.get(fname, {})
                    render_field(fname, meta)
            else:
                # 페이지 1·2 기본은 2열
                cols = st.columns(2)
                # 페이지 2의 "판매 타겟 제품"은 전체 너비 사용(요청 4)
                full_span_field = "product__midas_" if ss.prop_step == 2 else None

                for i, fname in enumerate(current_fields):
                    meta = props_map.get(fname, {})
                    if fname == full_span_field:
                        # 먼저 target_audience가 안 보이는 문제 방지: 명시적으로 렌더 순서 유지
                        st.markdown(LABEL_OVERRIDES.get(fname, fname))
                        render_multi_check(fname, meta)
                    else:
                        with cols[i % 2]:
                            if fname == "title":  # 타이틀은 위에서 입력했으니 건너뜀
                                continue
                            render_field(fname, meta)

        # ---- 페이지 네비게이션(아래 배치, 요청 1) ----
        nav = st.container()
        with nav:
            col_prev, col_ctr, col_next = st.columns([1,1,1])
            with col_prev:
                if ss.prop_step > 1 and st.button("◀ 이전", use_container_width=True, key="nav_prev"):
                    ss.prop_step -= 1; st.rerun()
            with col_ctr:
                st.markdown(
                    f"<div style='text-align:center;'>페이지 {ss.prop_step} / {total_steps}</div>",
                    unsafe_allow_html=True
                )
            with col_next:
                if ss.prop_step < total_steps and st.button("다음 ▶", use_container_width=True, key="nav_next"):
                    ss.prop_step += 1; st.rerun()

        # ---- (버튼은 폼 바깥·가운데·80%폭 근사치, 요청 2) ----
        gap_l, main, gap_r = st.columns([1, 8, 1])
        with main:
            if st.button("MBM 오브젝트 생성하기", type="primary", use_container_width=True, key="create_mbm"):
                payload = {"title": ss.mbm_title}
                missing = []

                def get_val_for(name: str):
                    if name in MULTI_CHECK_FIELDS:
                        return ";".join(ss.get(f"mchk_{name}", [])) or None
                    return ss.get(f"fld_{name}") or ss.get(f"fld_{name}_num") or ss.get(f"fld_{name}_txt") or ss.get(f"fld_{name}_date")

                for n in MBM_FIELDS:
                    if n == "title": 
                        continue
                    v = get_val_for(n)
                    if (n in REQUIRED_FIELDS) and (v in (None, "", ";")):
                        missing.append(n)
                    elif v not in (None, ""):
                        payload[n] = v

                if missing:
                    st.error("모든 필수 항목을 작성해주세요")
                else:
                    payload["auto_generate_campaign"] = "true"
                    try:
                        with st.spinner("HubSpot에 MBM 오브젝트 생성 중…"):
                            created = hs_create_mbm_object(payload)
                            ss.mbm_object = created
                            ss.mbm_submitted = True
                            ss.active_stage = 2
                            # 슬러그용 메타 저장
                            ss.slug_country = payload.get("country")
                            ss.slug_finish_ms = payload.get("mbm_finish_date") or payload.get("mbm_start_date")
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
                make_wp = st.checkbox("웹페이지 복제", value=True)
                make_em = st.checkbox("이메일 복제", value=True)
                email_count = st.number_input("이메일 복제 개수", min_value=1, max_value=10, value=1, step=1)

            submitted_actions = st.form_submit_button("생성하기", type="primary")

        if submitted_actions:
            links = {"Website Page": [], "Email": [], "Form": []}
            try:
                # Website Page → 편집 링크 + Content slug
                if make_wp:
                    page_name = f"{ss.mbm_title}_landing page"
                    with st.spinner(f"웹페이지 복제 중… ({page_name})"):
                        page_data = hs_clone_site_page(LANDING_PAGE_TEMPLATE_ID, page_name)
                        page_id = str(page_data.get("id") or page_data.get("objectId") or "")
                        _ = hs_update_site_page(page_id, {"name": page_name})
                        slug = build_content_slug(ss.get("slug_country"), ss.get("slug_finish_ms"), ss.mbm_title)
                        if slug:
                            ok, _ = update_site_page_slug_safely(page_id, slug)
                            if not ok: st.warning("콘텐츠 슬러그 업데이트 실패(필드명 불일치). 포털에서 수동 확인하세요.")
                        else:
                            st.warning("슬러그를 계산하지 못했습니다. (국가/종료일 확인 필요)")
                        hs_push_live_site(page_id)
                        edit_url = f"https://app.hubspot.com/cms/{PORTAL_ID}/website/pages/{page_id}/edit"
                        links["Website Page"].append(("편집", edit_url))

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
