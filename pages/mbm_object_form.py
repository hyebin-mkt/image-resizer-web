# pages/mbm_object_form.py
# 🧚🏻‍♂️ MBM Magic Wizard — MBM 오브젝트 검색/생성 → 후속자산 자동화

import json, re, uuid, datetime
import requests
import streamlit as st

# -----------------------
# 기본 페이지 설정
# -----------------------
st.set_page_config(page_title="🧚🏻‍♂️ MBM Magic Wizard", page_icon="📄", layout="centered")
st.title("🧚🏻‍♂️ MBM Magic Wizard")
st.caption("MBM 오브젝트 형성부터 마케팅 에셋까지 한번에 만들어줄게요.")

# -----------------------
# 공통 시크릿/상수
# -----------------------
TOKEN   = st.secrets.get("HUBSPOT_PRIVATE_APP_TOKEN", "")
PORTAL  = st.secrets.get("PORTAL_ID", "2495902")
HS_BASE = "https://api.hubapi.com"

if not TOKEN:
    st.error("Streamlit Secrets에 HUBSPOT_PRIVATE_APP_TOKEN이 없습니다.")
    st.stop()

HEADERS_JSON = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# 템플릿(선택사항)
TEMPLATE_SITE_PAGE_TITLE = st.secrets.get("TEMPLATE_SITE_PAGE_TITLE", "[Template] Event Landing Page_GOM")
EMAIL_TEMPLATE_ID        = st.secrets.get("EMAIL_TEMPLATE_ID",        "")
FORM_TEMPLATE_GUID       = st.secrets.get("FORM_TEMPLATE_GUID",       "")
MBM_HIDDEN_FIELD_NAME    = "title"
HUBSPOT_REGION           = "na1"

# -----------------------
# 세션 상태
# -----------------------
ss = st.session_state
ss.setdefault("active_stage", 1)          # 1=오브젝트 선택/생성, 2=후속 작업, 3=결과 공유
ss.setdefault("mbm_object_id", "")        # 선택/생성된 MBM ID
ss.setdefault("mbm_title", "")            # 선택/생성된 MBM Title
ss.setdefault("search_keyword", "")
ss.setdefault("search_results", [])       # [(id,title)]
ss.setdefault("search_choice", "")        # 사용자가 드롭다운에서 고른 기존 오브젝트 id
ss.setdefault("results_links", None)      # {"Landing Page":[(label,url)...], "Email":[...], "Form":[...]}

# -----------------------
# 스타일: 복사/페이지네이션
# -----------------------
st.markdown("""
<style>
.mbm-copy-btn{
  border:1px solid #e5e7eb; border-radius:10px; background:#fff; cursor:pointer;
  width:36px; height:36px; display:flex; align-items:center; justify-content:center;
}
</style>
""", unsafe_allow_html=True)

def copy_button_inline(text: str, key: str):
    safe = json.dumps(text or "")
    st.components.v1.html(f"""
<div>
  <button id="cpy_{key}" class="mbm-copy-btn" title="복사">📋</button>
</div>
<script>
  document.getElementById("cpy_{key}").onclick = () => {{
    navigator.clipboard.writeText({safe});
  }};
</script>
""", height=40)

def ordinal(n: int) -> str:
    n = int(n)
    if 10 <= (n % 100) <= 20: suf = "th"
    else: suf = {1:"st",2:"nd",3:"rd"}.get(n % 10, "th")
    return f"{n}{suf}"

def render_pagination(cur: int, total: int, key: str="pg"):
    cols = st.columns(total + 2)
    changed_to = None
    with cols[0]:
        if st.button("←", key=f"{key}_prev", disabled=(cur<=1)):
            changed_to = max(1, cur-1)
    for i in range(total):
        idx = i+1
        with cols[i+1]:
            if st.button(f"{idx}", key=f"{key}_{idx}", type=("primary" if idx==cur else "secondary")):
                changed_to = idx
    with cols[-1]:
        if st.button("→", key=f"{key}_next", disabled=(cur>=total)):
            changed_to = min(total, cur+1)
    return changed_to

# -----------------------
# MBM Object Type ID 해석
# -----------------------
def resolve_mbm_object_type_id() -> str:
    obj_id = (st.secrets.get("MBM_OBJECT_TYPE_ID") or "").strip()
    if obj_id:
        return obj_id
    url_hint = (st.secrets.get("MBM_OBJECT_URL") or "").strip()
    if url_hint:
        m = re.search(r"/objects/([^/]+)/", url_hint)
        if m:
            return m.group(1)
    # schemas API로 "MBM" 찾기
    try:
        u = f"{HS_BASE}/crm/v3/schemas"
        r = requests.get(u, headers=HEADERS_JSON, timeout=30)
        if r.status_code == 403:
            st.warning("스키마 조회 권한이 없습니다. Private App 스코프에 `crm.schemas.custom.read` 추가 또는 MBM_OBJECT_TYPE_ID/URL 시크릿 설정 필요.")
            return ""
        r.raise_for_status()
        for s in r.json().get("results", []):
            name = (s.get("name") or "").lower()
            sg   = (s.get("labels", {}).get("singular") or "").lower()
            pl   = (s.get("labels", {}).get("plural") or "").lower()
            if name == "mbm" or sg == "mbm" or pl == "mbm":
                return s.get("objectTypeId") or ""
    except Exception as e:
        st.warning(f"MBM 오브젝트 타입 자동해결 실패: {e}")
    return ""

MBM_OBJECT_TYPE_ID = resolve_mbm_object_type_id()
if not MBM_OBJECT_TYPE_ID:
    st.info("⚠️ MBM Object Type ID를 찾지 못했습니다. 시크릿에 `MBM_OBJECT_TYPE_ID` 또는 `MBM_OBJECT_URL`을 설정해 주세요.")

# -----------------------
# 스키마(프로퍼티) 조회
# -----------------------
MBM_PROPERTIES = {}
try:
    if MBM_OBJECT_TYPE_ID:
        u = f"{HS_BASE}/crm/v3/schemas/{MBM_OBJECT_TYPE_ID}"
        r = requests.get(u, headers=HEADERS_JSON, timeout=30)
        if r.status_code == 403:
            st.warning("스키마 로드 권한이 없습니다. Private App 스코프에 `crm.schemas.custom.read` 추가 필요.")
        else:
            r.raise_for_status()
            for p in r.json().get("properties", []):
                MBM_PROPERTIES[p["name"]] = p
except Exception as e:
    st.warning(f"스키마 로드 실패: {e}")

def is_multi_enum(prop: dict) -> bool:
    if not prop: return False
    t = (prop.get("type") or "").lower()
    ft = (prop.get("fieldType") or "").lower()
    return (t == "enumeration") and any(x in ft for x in ("checkbox", "multi"))

def enum_options(prop: dict) -> list[str]:
    out = []
    for o in prop.get("options", []) or []:
        v = o.get("value")
        if v is not None: out.append(str(v))
    return out

def to_hs_value(prop: dict, py_value):
    if py_value is None: return None
    if is_multi_enum(prop):
        if isinstance(py_value, (list, tuple, set)):
            return ";".join([str(x) for x in py_value])
        return str(py_value)
    return str(py_value)

# -----------------------
# MBM 오브젝트 검색/생성 API
# -----------------------
def hs_search_mbm_by_title(query: str, limit=12):
    if not MBM_OBJECT_TYPE_ID:
        return []
    u = f"{HS_BASE}/crm/v3/objects/{MBM_OBJECT_TYPE_ID}/search"
    payload = {"query": query, "properties": ["title"], "limit": limit}
    r = requests.post(u, headers=HEADERS_JSON, json=payload, timeout=30)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    results = []
    for it in r.json().get("results", []):
        pid  = it.get("id")
        prop = it.get("properties", {}) or {}
        ttl  = prop.get("title") or "(제목 없음)"
        results.append((pid, ttl))
    return results

def hs_create_mbm(properties: dict):
    if not MBM_OBJECT_TYPE_ID:
        raise RuntimeError("MBM Object Type ID가 없어 생성할 수 없습니다.")
    u = f"{HS_BASE}/crm/v3/objects/{MBM_OBJECT_TYPE_ID}"
    r = requests.post(u, headers=HEADERS_JSON, json={"properties": properties}, timeout=30)
    if r.status_code == 403:
        st.error("MBM 오브젝트 생성 권한이 없습니다. Private App 스코프에 "
                 "`crm.objects.custom.read`, `crm.objects.custom.write`를 추가하세요.")
    r.raise_for_status()
    return r.json()

# -----------------------
# CMS/Email/Form 유틸 (필요 시 사용)
# -----------------------
def find_site_template_by_title(title: str):
    try:
        u = f"{HS_BASE}/cms/v3/pages/site-pages?limit=100"
        r = requests.get(u, headers=HEADERS_JSON, timeout=30); r.raise_for_status()
        for p in r.json().get("results", []):
            if (p.get("name") or "") == title:
                return p
    except Exception:
        return None
    return None

def clone_site_page(template_id: str, new_name: str):
    u = f"{HS_BASE}/cms/v3/pages/site-pages/clone"
    last=None
    for key in ("name","cloneName"):
        try:
            r = requests.post(u, headers=HEADERS_JSON, json={"id": str(template_id), key: new_name}, timeout=45)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as e:
            last=e
    raise last

def push_live_site_page(page_id: str):
    u = f"{HS_BASE}/cms/v3/pages/site-pages/{page_id}/draft/push-live"
    r = requests.post(u, headers={"Authorization": f"Bearer {TOKEN}", "Accept": "*/*"}, timeout=30)
    r.raise_for_status()

def clone_marketing_email(template_id: str, new_name: str):
    u = f"{HS_BASE}/marketing/v3/emails/clone"
    last=None
    for key in ("emailName","name","cloneName"):
        try:
            r = requests.post(u, headers=HEADERS_JSON, json={"id": str(template_id), key: new_name}, timeout=45)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as e:
            last=e
    raise last

def forms_get_v2(guid: str):
    u = f"https://api.hubapi.com/forms/v2/forms/{guid}"
    r = requests.get(u, headers={"Authorization": f"Bearer {TOKEN}", "Accept":"application/json"}, timeout=30)
    r.raise_for_status()
    return r.json()

def forms_create_v2(payload: dict):
    u = f"https://api.hubapi.com/forms/v2/forms"
    r = requests.post(u, headers={"Authorization": f"Bearer {TOKEN}", "Content-Type":"application/json"}, json=payload, timeout=45)
    r.raise_for_status()
    return r.json()

def clone_register_form_with_hidden(template_guid: str, name: str, hidden_value: str, hidden_field_name: str="title"):
    t = forms_get_v2(template_guid)
    groups=[]
    for g in t.get("formFieldGroups", []):
        flds=[]
        for f in g.get("fields", []):
            keep = {k: f[k] for k in f.keys() if k in {"name","label","type","fieldType","required","hidden","defaultValue","options","placeholder","validation","inlineHelpText","description"}}
            if keep.get("name")==hidden_field_name:
                keep["hidden"]=True
                keep["defaultValue"]=hidden_value
            flds.append(keep)
        groups.append({"fields": flds})
    payload={"name":name,"method":t.get("method","POST"),"redirect":t.get("redirect",""),"submitText":t.get("submitText","Submit"),"formFieldGroups":groups}
    return forms_create_v2(payload)

# -----------------------
# 탭 헤더 구성(오른쪽으로 생김)
# -----------------------
TAB1, TAB2, TAB3 = "MBM 오브젝트 제출", "후속 작업 선택", "최종 링크 공유"

def focus_tab(label: str):
    st.components.v1.html(f"""
<script>
(function(){{
  function go(){{
    const tabs=[...window.parent.document.querySelectorAll('[role="tab"]')];
    for (const t of tabs) {{
      const tx=(t.innerText||'').trim();
      if (tx.indexOf("{label}")!==-1){{ t.click(); return; }}
    }}
  }}
  setTimeout(go,80); setTimeout(go,250); setTimeout(go,500);
}})();
</script>""", height=0)

def make_tabs():
    labels=[TAB1]
    if ss.mbm_object_id: labels.append(TAB2)
    if ss.results_links: labels.append(TAB3)
    t=st.tabs(labels)
    idx={label:i for i,label in enumerate(labels)}
    if ss.active_stage==2 and TAB2 in idx: focus_tab(TAB2)
    if ss.active_stage==3 and TAB3 in idx: focus_tab(TAB3)
    return t, idx

tabs, idx = make_tabs()

# =========================================================
# ① MBM 오브젝트 제출 — "검색 → 기존 선택" + "드롭다운 아래 새로 생성"
# =========================================================
with tabs[idx[TAB1]]:
    st.markdown("### ① MBM 오브젝트 제출")
    st.markdown("**MBM 오브젝트 타이틀**을 기준에서 검색해서 선택하거나, 새로 생성할 수 있어요.")

    with st.form("search_form", border=True):
        c1, c2 = st.columns([5,1])
        with c1:
            ss.search_keyword = st.text_input("키워드로 검색", value=ss.search_keyword, placeholder="예: [EU] 20250803 GTS NX Webinar", label_visibility="collapsed")
        with c2:
            copy_button_inline(ss.search_keyword, key="kw_copy")

        run = st.form_submit_button("검색")
        if run and ss.search_keyword.strip():
            try:
                ss.search_results = hs_search_mbm_by_title(ss.search_keyword.strip())
            except requests.HTTPError as e:
                st.error(f"검색 실패: {e.response.status_code} - {e.response.text}")
            except Exception as e:
                st.error(f"검색 실패: {e}")

    # 드롭다운: 기존 오브젝트만 표시
    if ss.search_keyword.strip():
        labels = [f'{ttl}  ·  #{oid}' for oid, ttl in (ss.search_results or [])]
        values = [oid for oid, _ in (ss.search_results or [])]
        if labels:
            sel = st.selectbox("결과에서 선택", labels, index=0)
            ss.search_choice = values[labels.index(sel)]
        else:
            st.info("검색 결과가 없습니다.")

        # 드롭다운 아래 — 새로 생성 버튼 + 다음 버튼
        colA, colB = st.columns([1,1])
        with colA:
            if st.button(f'➕ "{ss.search_keyword}" 로 새 오브젝트 생성', type="secondary"):
                try:
                    created = hs_create_mbm({"title": ss.search_keyword.strip()})
                    ss.mbm_object_id = created.get("id")
                    ss.mbm_title     = ss.search_keyword.strip()
                    st.success(f"새 MBM 오브젝트 생성 완료: #{ss.mbm_object_id}")
                except requests.HTTPError as e:
                    st.error(f"HubSpot API 오류: {e.response.status_code} - {e.response.text}")
                except Exception as e:
                    st.error(f"실패: {e}")

        with colB:
            if st.button("다음 ▶", type="primary"):
                try:
                    if ss.mbm_object_id:
                        ss.active_stage = 2
                        st.rerun()
                    elif ss.search_choice:
                        # 기존 오브젝트 선택 후 다음
                        sel_id = str(ss.search_choice)
                        ss.mbm_object_id = sel_id
                        # 제목은 검색결과에서 찾아 저장
                        sel = next(((i,t) for i,t in ss.search_results if str(i)==sel_id), None)
                        ss.mbm_title = sel[1] if sel else ss.search_keyword.strip()
                        ss.active_stage = 2
                        st.rerun()
                    else:
                        st.error("목록에서 하나를 선택하거나, 새 오브젝트를 먼저 생성하세요.")
                except Exception as e:
                    st.error(f"실패: {e}")

# =========================================================
# ② 후속 작업 선택 — 페이지/메일/폼 생성(선택)
# =========================================================
if ss.mbm_object_id and (TAB2 in idx):
    with tabs[idx[TAB2]]:
        st.markdown("### ② 후속 작업 선택")
        with st.form("post_actions", border=True):
            col1, col2 = st.columns([2,1])
            with col1:
                st.markdown("**선택된 MBM 오브젝트**")
                st.text_input("선택된 MBM", value=ss.mbm_title or "", disabled=True, label_visibility="collapsed")
            with col2:
                st.markdown("**생성할 자산**")
                make_site = st.checkbox("웹페이지 생성", value=True)
                make_em   = st.checkbox("이메일 생성", value=False)
                make_form = st.checkbox("신청 폼 생성", value=False)
                email_cnt = st.number_input("이메일 개수", min_value=1, max_value=10, value=1, step=1)

            submitted = st.form_submit_button("생성하기", type="primary")

        if submitted:
            links = {"Landing Page": [], "Email": [], "Form": []}
            try:
                # 사이트 페이지 생성
                if make_site and TEMPLATE_SITE_PAGE_TITLE:
                    with st.spinner("사이트 페이지 템플릿 검색/복제 중…"):
                        tpl = find_site_template_by_title(TEMPLATE_SITE_PAGE_TITLE)
                        if not tpl:
                            st.warning(f"사이트 템플릿을 찾지 못했습니다: {TEMPLATE_SITE_PAGE_TITLE}")
                        else:
                            clone_name = f"{ss.mbm_title}_landing page"
                            cloned = clone_site_page(str(tpl.get("id")), clone_name)
                            pid = str(cloned.get("id") or cloned.get("objectId") or "")
                            push_live_site_page(pid)
                            edit_url = f"https://app.hubspot.com/cms/{PORTAL}/website/pages/{pid}/edit"
                            links["Landing Page"].append(("편집", edit_url))

                # 이메일 생성
                if make_em and EMAIL_TEMPLATE_ID:
                    for i in range(1, int(email_cnt)+1):
                        nm = f"{ss.mbm_title}_email_{ordinal(i)}"
                        with st.spinner(f"이메일 생성 중… ({nm})"):
                            em = clone_marketing_email(EMAIL_TEMPLATE_ID, nm)
                            em_id = str(em.get("id") or em.get("contentId") or "")
                            edit_url = f"https://app.hubspot.com/email/{PORTAL}/edit/{em_id}/settings"
                            links["Email"].append((f"Email {ordinal(i)}", edit_url))

                # 신청 폼 생성
                if make_form and FORM_TEMPLATE_GUID:
                    nm = f"{ss.mbm_title}_register form"
                    with st.spinner("신청 폼 생성 중…"):
                        nf = clone_register_form_with_hidden(FORM_TEMPLATE_GUID, nm, ss.mbm_title, MBM_HIDDEN_FIELD_NAME)
                        guid = nf.get("guid") or nf.get("id")
                        edit_url = f"https://app.hubspot.com/forms/{PORTAL}/{guid}/edit"
                        links["Form"].append(("편집", edit_url))

                ss.results_links = links
                ss.active_stage  = 3
                st.success("생성 완료! ‘최종 링크 공유’ 탭으로 이동합니다.")
                st.rerun()

            except requests.HTTPError as e:
                st.error(f"HubSpot API 오류: {e.response.status_code} - {e.response.text}")
            except Exception as e:
                st.error(f"실패: {e}")

# =========================================================
# ③ 최종 링크 공유 — 카드형 + 전체 복사
# =========================================================
if ss.results_links and (TAB3 in idx):
    with tabs[idx[TAB3]]:
        st.markdown("### ③ 최종 링크 공유")
        st.success(f"MBM 생성 결과 – **{ss.mbm_title}**")

        def link_box(title: str, items: list[tuple[str,str]], prefix_key: str):
            st.markdown(f"#### {title}")
            for i,(label,url) in enumerate(items, start=1):
                box = st.container(border=True)
                with box:
                    c1, c2 = st.columns([8,1])
                    with c1:
                        st.markdown(f"**{label}**  \n{url}")
                    with c2:
                        copy_button_inline(url, key=f"{prefix_key}_{i}_{uuid.uuid4()}")

        if ss.results_links.get("Landing Page"):
            link_box("Landing / Website Page", ss.results_links["Landing Page"], "lp")

        if ss.results_links.get("Email"):
            link_box("Marketing Emails", ss.results_links["Email"], "em")

        if ss.results_links.get("Form"):
            link_box("Register Form", ss.results_links["Form"], "fm")

        st.divider()
        lines=[f"[MBM] 생성 결과 - {ss.mbm_title}",""]
        if ss.results_links.get("Landing Page"):
            lines.append("▼ Landing / Website Page")
            for lb,u in ss.results_links["Landing Page"]:
                lines.append(f"- {lb}: {u}")
            lines.append("")
        if ss.results_links.get("Email"):
            lines.append("▼ Marketing Emails")
            for lb,u in ss.results_links["Email"]:
                lines.append(f"- {lb}: {u}")
            lines.append("")
        if ss.results_links.get("Form"):
            lines.append("▼ Register Form")
            for lb,u in ss.results_links["Form"]:
                lines.append(f"- {lb}: {u}")
            lines.append("")
        all_text="\n".join(lines)

        st.text_area("전체 결과 (미리보기)", value=all_text, height=180, label_visibility="collapsed")
        if st.button("전체 결과물 복사", type="primary"):
            st.components.v1.html(f"<script>navigator.clipboard.writeText({json.dumps(all_text)});</script>", height=0, width=0)
            st.toast("복사가 완료되었습니다. 메모장에 붙여넣기 하세요")
