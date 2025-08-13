# pages/03_Image_Generator.py
# ⚡ 이미지 생성기(폴더 저장) → 허브스팟 Files 업로드 → 에셋 연결
# - 저장: ZIP 대신 폴더에 개별 파일 저장
# - 업로드: HubSpot Files API (v3 / legacy 폴백)
# - 에셋 연결: Website Page Featured Image / Top Section Image, Marketing Email Header

import io, os, math, datetime, time, mimetypes, json
from pathlib import Path
import requests
from PIL import Image, ImageOps
import streamlit as st

# ───────────────────────────── 페이지/사이드바 ─────────────────────────────
st.set_page_config(page_title="이미지 생성기 + 허브스팟 연동", page_icon="🖼️", layout="centered")

def sidebar_quick_link(label: str, url: str):
    st.sidebar.markdown(
        f'''
<a href="{url}" target="_blank" style="text-decoration:none;">
  <div style="
      display:flex; align-items:center; justify-content:space-between;
      padding:12px 14px; margin:6px 0;
      border:1px solid #e5e7eb; border-radius:12px;
      background:#fff; transition:all .15s ease;">
    <span style="font-weight:600; color:#111827;">{label}</span>
    <span style="font-size:14px; color:#6b7280;">↗</span>
  </div>
</a>
''',
        unsafe_allow_html=True
    )

with st.sidebar:
    st.subheader("바로가기")
    sidebar_quick_link("Hubspot File 바로가기", "https://app.hubspot.com/files/2495902/")
    sidebar_quick_link("Hubspot Website 바로가기", "https://app.hubspot.com/page-ui/2495902/management/pages/site/all")
    sidebar_quick_link("MBM 가이드북", "https://www.canva.com/design/DAGtMIVovm8/eXz5TOekAVik-uynq1JZ1Q/view?utm_content=DAGtMIVovm8&utm_campaign=designshare&utm_medium=link2&utm_source=uniquelinks&utlId=h9b120a74ea")

st.markdown("""
<style>
[data-testid="stSidebar"] .sidebar-copyright{
  position: sticky; bottom: 18px; margin-top: 24px;
}
</style>
""", unsafe_allow_html=True)
st.markdown(
    '<div class="sidebar-copyright" style="color:#6b7280; font-size:12px;">'
    '© Chacha · <a href="mailto:chb0218@midasit.com" style="color:#6b7280; text-decoration:none;">chb0218@midasit.com</a>'
    '</div>',
    unsafe_allow_html=True
)

# ───────────────────────────── 설정/상수 ─────────────────────────────
APP_TITLE = " ⚡원샷원킬 배너 생성기"
VALID_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}
PRESETS = [
    ("Landing Page_Thumbnail", (600, 350)),
    ("Landing Page_banner",   (1920, 440)),
    ("Speaker",               (250, 250)),
    ("List Thumbnail",        (720, 420)),
    ("Carousel Banner",       (1200, 370)),
    ("Email Header",          (600, 280)),
]
SCALE_OPTIONS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]

TOKEN = st.secrets.get("HUBSPOT_PRIVATE_APP_TOKEN", "")
PORTAL_ID = st.secrets.get("PORTAL_ID", "")
MBM_FQN = st.secrets.get("MBM_FQN", "")  # e.g. p123456_mbm
MBM_OBJECT_TYPE_ID = st.secrets.get("MBM_OBJECT_TYPE_ID", "")  # e.g. 2-10432789

if not TOKEN or not PORTAL_ID:
    st.error("Secrets에 HUBSPOT_PRIVATE_APP_TOKEN, PORTAL_ID를 설정해 주세요.")
    st.stop()

HS = "https://api.hubapi.com"
H  = {"Authorization": f"Bearer {TOKEN}"}

# (선택) 에셋 연결용 내부 키들
EMAIL_HEADER_WIDGET_KEY   = st.secrets.get("EMAIL_HEADER_WIDGET_KEY", "")
PAGE_TOP_SECTION_MODULE_KEY = st.secrets.get("PAGE_TOP_SECTION_MODULE_KEY", "")
PAGE_FEATURED_IMAGE_FIELD = st.secrets.get("PAGE_FEATURED_IMAGE_FIELD", "")

# ───────────────────────────── 유틸 ─────────────────────────────
ss = st.session_state
ss.setdefault("generated_dir", "")
ss.setdefault("generated_files", [])   # [(abs_path, file_name, label, w, h)]
ss.setdefault("uploaded_files", [])    # [(file_name, hubspot_url, file_id)]
ss.setdefault("mbm_title", "")
ss.setdefault("show_hs_tab", False)
ss.setdefault("show_link_tab", False)
ss.setdefault("picked_page", None)
ss.setdefault("picked_email", None)

def sanitize_label(s: str) -> str:
    bad='\\/:*?"<>|'
    out=s.strip().replace(" ","_")
    for ch in bad: out=out.replace(ch,"")
    return out

def resize_cover(im: Image.Image, w: int, h: int) -> Image.Image:
    im = ImageOps.exif_transpose(im)
    sw, sh = im.size
    scale = max(w/sw, h/sh)
    nw, nh = max(1,int(sw*scale)), max(1,int(sh*scale))
    im2 = im.resize((nw,nh), Image.LANCZOS)
    x=(nw-w)//2; y=(nh-h)//2
    return im2.crop((x,y,x+w,y+h))

def ensure_rgb(img: Image.Image, bg=(255,255,255)) -> Image.Image:
    if img.mode in ("RGBA","LA") or (img.mode=="P" and "transparency" in img.info):
        from PIL import Image as PILImage
        base=PILImage.new("RGB",img.size,bg); base.paste(img, mask=img.split()[-1]); return base
    return img.convert("RGB") if img.mode!="RGB" else img

def content_type_from_name(name: str) -> str:
    return mimetypes.guess_type(name)[0] or "application/octet-stream"

# ───────────────────────────── HubSpot Files API ─────────────────────────────
def hs_create_folder(name: str, parent_id: int | None = None) -> dict:
    """v3 → 실패 시 레거시 filemanager로 폴백"""
    try:
        payload = {"name": name}
        if parent_id is not None:
            for key in ("parentFolderId", "parentId"):
                payload[key] = parent_id
        r = requests.post(f"{HS}/files/v3/folders", headers=H|{"Content-Type":"application/json"},
                          json=payload, timeout=30)
        if r.status_code < 400:
            return r.json()
    except Exception:
        pass
    # legacy
    r = requests.post(f"{HS}/filemanager/api/v3/folders",
                      headers=H|{"Content-Type":"application/json"},
                      json={"name": name, "parentFolderId": parent_id or 0}, timeout=30)
    r.raise_for_status()
    return r.json()

def hs_list_folders(name_like: str):
    r = requests.get(f"{HS}/filemanager/api/v3/folders", headers=H, timeout=30)
    if r.status_code >= 400: return []
    items = r.json().get("objects") or r.json().get("results") or []
    return [it for it in items if name_like.lower() in (it.get("name","").lower())]

def hs_upload_file(abs_path: str, folder_id: int | str | None, is_public=True) -> dict:
    with open(abs_path, "rb") as f:
        data = {
            "folderId": str(folder_id) if folder_id is not None else "",
            "options": json.dumps({
                "access": "PUBLIC" if is_public else "PRIVATE",
                "duplicateValidationStrategy": "NONE",
                "duplicateValidationScope": "EXACT_FOLDER",
            })
        }
        files = {"file": (Path(abs_path).name, f, content_type_from_name(abs_path))}
        r = requests.post(f"{HS}/files/v3/files", headers=H, data=data, files=files, timeout=90)
        r.raise_for_status()
        return r.json()

# ───────────────────────────── MBM 검색(커스텀 오브젝트) ─────────────────────────────
def _resolve_mbm_ident():
    if MBM_FQN: return MBM_FQN
    if MBM_OBJECT_TYPE_ID: return MBM_OBJECT_TYPE_ID
    r = requests.get(f"{HS}/crm/v3/schemas", headers=H, timeout=30)
    if r.status_code >= 400: return None
    for s in r.json().get("results", []):
        if "mbm" in (s.get("name","").lower()+s.get("labels",{}).get("singular","").lower()):
            return s.get("fullyQualifiedName") or s.get("name")
    return None

def hs_search_mbm_titles(q: str, limit=20):
    ident = _resolve_mbm_ident()
    if not ident: return []
    url = f"{HS}/crm/v3/objects/{ident}/search"
    payload = {
        "limit": limit,
        "properties": ["title"],
        "filterGroups": [{
            "filters": [{"propertyName": "title", "operator": "CONTAINS_TOKEN", "value": q}]
        }],
        "sorts": [{"propertyName": "hs_lastmodifieddate", "direction": "DESCENDING"}],
    }
    r = requests.post(url, headers=H|{"Content-Type":"application/json"}, json=payload, timeout=30)
    if r.status_code >= 400: 
        # 폴백: 전체 조회 후 로컬 필터
        url2 = f"{HS}/crm/v3/objects/{ident}?limit={limit}&properties=title"
        r2 = requests.get(url2, headers=H, timeout=30)
        if r2.status_code >= 400: return []
        return [(it["id"], it.get("properties",{}).get("title","")) 
                for it in r2.json().get("results",[]) if q.lower() in it.get("properties",{}).get("title","").lower()]
    return [(it["id"], it.get("properties",{}).get("title","")) for it in r.json().get("results",[])]

# ───────────────────────────── 에셋 연결(안전 스텁) ─────────────────────────────
def list_site_pages(q: str, limit=100):
    url = f"{HS}/cms/v3/pages/site-pages?limit={limit}"
    r = requests.get(url, headers=H, timeout=30)
    if r.status_code >= 400: return []
    out=[]
    for it in r.json().get("results", []):
        name = it.get("name") or it.get("pageTitle","")
        if not q or q.lower() in name.lower():
            out.append((str(it.get("id")), name))
    return out

def list_marketing_emails(q: str, limit=100):
    url = f"{HS}/marketing/v3/emails?limit={limit}"
    r = requests.get(url, headers=H, timeout=30)
    if r.status_code >= 400: return []
    out=[]
    for it in r.json().get("results", []):
        name = it.get("name","")
        if not q or q.lower() in name.lower():
            out.append((str(it.get("id") or it.get("contentId")), name))
    return out

def set_page_featured_image(page_id: str, file_id: str):
    key = PAGE_FEATURED_IMAGE_FIELD or "featuredImageId"
    for k in (key, "featuredImage", "featuredImageId"):
        r = requests.patch(f"{HS}/cms/v3/pages/site-pages/{page_id}",
                           headers=H|{"Content-Type":"application/json"},
                           json={k: file_id}, timeout=30)
        if r.status_code < 400:
            return
    st.warning("Featured Image 업데이트 실패(필드명 확인 필요).")

def set_page_module_image(page_id: str, widget_key: str, file_id: str):
    if not widget_key:
        st.warning("페이지 모듈 이미지 키가 없어 스킵합니다. (PAGE_TOP_SECTION_MODULE_KEY 시크릿)")
        return
    r = requests.patch(f"{HS}/cms/v3/pages/site-pages/{page_id}",
                       headers=H|{"Content-Type":"application/json"},
                       json={"widgets": {widget_key: {"type": "image", "value": {"id": file_id}}}}, timeout=30)
    if r.status_code >= 400:
        st.warning("상단 섹션 이미지 위젯 교체 실패(위젯 키 확인 필요).")

def set_email_header_image(email_id: str, widget_key: str, file_id: str):
    if not widget_key:
        st.warning("이메일 헤더 위젯 키가 없어 스킵합니다. (EMAIL_HEADER_WIDGET_KEY 시크릿)")
        return
    r = requests.patch(f"{HS}/marketing/v3/emails/{email_id}",
                       headers=H|{"Content-Type":"application/json"},
                       json={"widgets": {widget_key: {"type": "image", "value": {"id": file_id}}}}, timeout=30)
    if r.status_code >= 400:
        st.warning("이메일 헤더 이미지 교체 실패(위젯 키 확인 필요).")

# ───────────────────────────── 탭 구성 ─────────────────────────────
tabs = ["이미지 생성"]
if ss.show_hs_tab:   tabs.append("허브스팟 연동")
if ss.show_link_tab: tabs.append("에셋 연결")
tab_objs = st.tabs(tabs)

# ───────────────────────────── 탭①: 이미지 생성 ─────────────────────────────
with tab_objs[0]:
    st.title(APP_TITLE)
    st.caption("이미지 하나로 마이다스 이벤트에 필요한 사이즈를 한방에 추출하세요")

    st.header("설정")
    colA, colC, colB = st.columns(3)
    with colA:
        fmt = st.selectbox("출력 포맷", ["jpg","jpeg","png"], index=0)
    with colB:
        jpg_qual = st.slider("JPEG 품질", min_value=60, max_value=100, value=88)
    with colC:
        scale = st.selectbox("출력 배율", SCALE_OPTIONS, index=SCALE_OPTIONS.index(2.0))

    st.markdown("---")

    uploaded = st.file_uploader("이미지 업로드 (PNG/JPG 등, 1개)", type=[e.strip(".") for e in VALID_EXTS], accept_multiple_files=False)
    if uploaded:
        file_ext = Path(uploaded.name).suffix.lower()
        if file_ext not in VALID_EXTS:
            st.error("지원하지 않는 이미지 형식입니다."); st.stop()

        img = Image.open(uploaded)
        w, h = img.size
        st.image(img, caption=f"원본 미리보기 — {w}x{h}px", use_column_width=True)

        base_title = st.text_input("이미지 타이틀(파일명 베이스)", value=Path(uploaded.name).stem)

        st.subheader("사이즈 선택")
        select_all = st.checkbox("전체 선택", value=True)
        chosen=[]
        for i,(name,(pw,ph)) in enumerate(PRESETS):
            checked = st.checkbox(f"{name} — {pw}x{ph}", value=True if select_all else False, key=f"preset_{i}")
            if checked: chosen.append((name,pw,ph))

        st.markdown("**커스텀 사이즈 (선택)** — 한 줄에 하나씩 `라벨, WxH` 형식 (예: `SNS, 1080x1080`)")
        custom_text = st.text_area("예시", "Banner 2, 1200x630\nSquare, 1080x1080", height=120)
        custom=[]
        if custom_text.strip():
            for line in custom_text.splitlines():
                line=line.strip()
                if not line: continue
                try:
                    left,right=line.split(",",1)
                    label=left.strip()
                    sw,sh = right.lower().replace("×","x").replace(" ","").split("x",1)
                    custom.append((label,int(sw),int(sh)))
                except Exception:
                    st.warning(f"무시된 입력: `{line}`")
        targets = chosen+custom

        if st.button("이미지 생성", type="primary"):
            if not targets:
                st.error("내보낼 사이즈를 하나 이상 선택/입력하세요."); st.stop()

            # 폴더 저장 (ZIP 대신 개별 파일 보관)
            out_dir = Path("/mnt/data") / f"{sanitize_label(base_title)}_{int(time.time())}"
            out_dir.mkdir(parents=True, exist_ok=True)

            saved=[]
            for label,tw,th in targets:
                stw = max(1, int(round(tw*float(scale))))
                sth = max(1, int(round(th*float(scale))))
                out = resize_cover(img, stw, sth)
                label_safe = sanitize_label(label)
                out_name = f"{sanitize_label(base_title)}_{label_safe}_{stw}x{sth}.{fmt}"
                abs_path = out_dir / out_name
                if fmt in ("jpg","jpeg"):
                    ensure_rgb(out).save(abs_path, format="JPEG", quality=int(jpg_qual), optimize=True)
                else:
                    out.save(abs_path, format="PNG", optimize=True)
                saved.append((str(abs_path), out_name, label, stw, sth))

            ss.generated_dir = str(out_dir)
            ss.generated_files = saved
            ss.show_hs_tab = True
            st.success(f"생성 완료 ✅  (총 {len(saved)}개) — 서버 폴더: {out_dir}")
            st.info("브라우저는 '폴더 자체' 다운로드를 지원하지 않습니다. 개별 파일 확인 또는 다음 단계로 진행하세요.")
            for p, fname, label, sw, sh in saved[:8]:
                st.write(f"- {fname}  ({sw}x{sh})")

# ───────────────────────────── 탭②: 허브스팟 연동 (파일 업로드) ─────────────────────────────
if ss.show_hs_tab and len(tab_objs) >= 2:
    with tab_objs[1]:
        st.header("허브스팟 연동 — 파일 업로드")
        if not ss.generated_files:
            st.info("먼저 ‘이미지 생성’ 탭에서 파일을 만들어 주세요.")
        else:
            qcol, _ = st.columns([2,1])
            with qcol:
                st.caption("업로드될 폴더 이름으로 사용할 MBM 오브젝트 타이틀을 선택하거나 직접 입력하세요.")
                query = st.text_input("MBM 검색", value=ss.mbm_title, placeholder="예: [EU] 20250803 GTS NX Webinar")
                if st.button("검색"):
                    results = hs_search_mbm_titles(query)
                    if results:
                        picked = st.selectbox("검색 결과", options=[t for (_id,t) in results])
                        ss.mbm_title = picked
                    else:
                        st.warning("검색 결과가 없습니다. 직접 입력값을 사용합니다.")
                ss.mbm_title = st.text_input("선택/입력된 MBM 타이틀", value=ss.mbm_title)

            st.markdown("---")
            if st.button("허브스팟에 업로드 시작", type="primary", disabled=not ss.mbm_title):
                try:
                    folder_name = sanitize_label(ss.mbm_title or "generated")
                    existing = hs_list_folders(folder_name)
                    if existing:
                        folder_id = existing[0].get("id") or existing[0].get("folder_id")
                    else:
                        f = hs_create_folder(folder_name, parent_id=0)
                        folder_id = f.get("id") or f.get("folder_id")

                    uploaded=[]
                    for abs_path, fname, _, _, _ in ss.generated_files:
                        with st.spinner(f"업로드 중… {fname}"):
                            info = hs_upload_file(abs_path, folder_id, is_public=True)
                            file_url = info.get("url") or info.get("full_url") or info.get("cdnUrl") or ""
                            file_id  = info.get("id")
                            uploaded.append((fname, file_url, file_id))
                    ss.uploaded_files = uploaded
                    ss.show_link_tab = True
                    st.success("허브스팟 업로드 완료! ‘에셋 연결’ 탭으로 이동하세요.")
                except requests.HTTPError as e:
                    st.error(f"업로드 실패: {e.response.status_code} - {e.response.text}")
                except Exception as e:
                    st.error(f"업로드 실패: {e}")

            if ss.uploaded_files:
                st.markdown("#### 업로드 결과 요약")
                for fname, url, fid in ss.uploaded_files:
                    st.write(f"- {fname} → {url} (id={fid})")

# ───────────────────────────── 탭③: 에셋 연결 ─────────────────────────────
if ss.show_link_tab and len(tab_objs) >= 3:
    with tab_objs[2]:
        st.header("에셋 연결")
        if not ss.uploaded_files:
            st.info("먼저 ‘허브스팟 연동’ 탭에서 파일을 업로드 해주세요.")
        else:
            st.caption("연동할 Website Page/Marketing Email을 검색해서 선택하세요. (없다면 아래 버튼으로 MBM Wizard로 이동)")
            c1, c2 = st.columns(2)
            with c1:
                qpage = st.text_input("Website Page 검색", "")
                if st.button("페이지 검색"):
                    pages = list_site_pages(qpage)
                    if pages:
                        page_label = st.selectbox("검색 결과", options=[name for (_id,name) in pages], key="page_sel")
                        pick = [pid for (pid,name) in pages if name==page_label][0]
                        ss.picked_page = (pick, page_label)
                    else:
                        st.warning("페이지 검색 결과가 없습니다.")
            with c2:
                qmail = st.text_input("Marketing Email 검색", "")
                if st.button("이메일 검색"):
                    emails = list_marketing_emails(qmail)
                    if emails:
                        mail_label = st.selectbox("검색 결과", options=[name for (_id,name) in emails], key="mail_sel")
                        pick = [eid for (eid,name) in emails if name==mail_label][0]
                        ss.picked_email = (pick, mail_label)
                    else:
                        st.warning("이메일 검색 결과가 없습니다.")

            # MBM Wizard 이동
            go_col1, go_col2 = st.columns([1,3])
            with go_col1:
                clicked = st.button("MBM Wizard 열기")
            if clicked:
                try:
                    # Streamlit 1.32+ (있으면)
                    st.switch_page("pages/01_mbm_magic_wizard.py")
                except Exception:
                    st.markdown('<a href="/01_mbm_magic_wizard" target="_self">페이지로 이동</a>', unsafe_allow_html=True)

            # 파일-에셋 매핑 안내(자동 추천)
            banner = next((u for u in ss.uploaded_files if "Landing_Page_banner"     in u[0] or "Landing Page_banner"     in u[0]), None)
            thumb  = next((u for u in ss.uploaded_files if "Landing_Page_Thumbnail"  in u[0] or "Landing Page_Thumbnail"  in u[0]), None)
            speaker= next((u for u in ss.uploaded_files if "Speaker"                 in u[0]), None)
            header = next((u for u in ss.uploaded_files if "Email_Header"            in u[0] or "Email Header"            in u[0]), None)

            st.markdown("#### 자동 매핑 제안")
            st.write(f"- Landing page **Top Section Image**  → {banner[0] if banner else '매칭 없음'}")
            st.write(f"- Website **Featured Image**        → {thumb[0] if thumb else '매칭 없음'}")
            st.write(f"- Email **Header(600x280)**         → {header[0] if header else '매칭 없음'}")
            st.caption("※ ‘Speaker 250x250’ → 페이지에 해당 모듈이 없으면 생략됩니다.")

            if st.button("연결 실행", type="primary",
                         disabled=not (ss.picked_page or ss.picked_email)):
                try:
                    if ss.picked_page:
                        page_id, page_name = ss.picked_page
                        if thumb:
                            set_page_featured_image(page_id, thumb[2])
                        if banner:
                            set_page_module_image(page_id, PAGE_TOP_SECTION_MODULE_KEY, banner[2])
                        # (선택) Speaker 모듈도 필요 시 동일 방식으로 구현 가능
                    if ss.picked_email and header:
                        email_id, email_name = ss.picked_email
                        set_email_header_image(email_id, EMAIL_HEADER_WIDGET_KEY, header[2])

                    st.success("연결 완료(설정된 키 기준). 반영이 안 보이면 모듈/필드 키를 확인해 주세요.")
                except requests.HTTPError as e:
                    st.error(f"연결 실패: {e.response.status_code} - {e.response.text}")
                except Exception as e:
                    st.error(f"연결 실패: {e}")
