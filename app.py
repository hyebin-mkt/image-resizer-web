# app.py
# ⚡원샷원킬 이미지 생성기⚡ — made by Chacha
# Upload one image and export multiple sizes (presets + custom) with scale options.
# Feedback section posts to GitHub Issues via Secrets (GH_TOKEN, GH_REPO).
# Run locally: pip install -r requirements.txt && streamlit run app.py

import io
import zipfile
import math
from pathlib import Path
import datetime
import requests

import streamlit as st
from PIL import Image, ImageOps

APP_TITLE = " ⚡원샷원킬 이미지 생성기"
VALID_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}

PRESETS = [
    ("Landing Page_Thumbnail", (600, 350)),
    ("Landing Page_banner", (1920, 440)),
    ("Speaker", (250, 250)),
    ("List Thumbnail", (720, 420)),
    ("Carousel Banner", (1200, 370)),
    ("Email Header", (600, 280)),
]

SCALE_OPTIONS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]

def sanitize_label(label: str) -> str:
    bad = '\\/:*?\"<>|'
    s = label.strip().replace(" ", "_")
    for ch in bad:
        s = s.replace(ch, "")
    return s

def resize_cover(im: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Resize to fill target (no borders), then center-crop to exact size."""
    im = ImageOps.exif_transpose(im)
    src_w, src_h = im.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w = max(1, int(math.ceil(src_w * scale)))
    new_h = max(1, int(math.ceil(src_h * scale)))
    resized = im.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    right = left + target_w
    bottom = top + target_h
    return resized.crop((left, top, right, bottom))

def ensure_rgb(img: Image.Image, bg=(255, 255, 255)) -> Image.Image:
    """Flatten alpha for JPEG; keep RGB otherwise."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        from PIL import Image as PILImage
        base = PILImage.new("RGB", img.size, bg)
        base.paste(img, mask=img.split()[-1])
        return base
    return img.convert("RGB") if img.mode != "RGB" else img

# -------- Feedback helpers (GitHub Issues) --------
def _gh_headers(token: str):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "streamlit-feedback-app",
    }

def create_issue(repo_full: str, token: str, title: str, body: str, labels=None):
    """Create a GitHub issue; optionally attach labels (list of strings)."""
    url = f"https://api.github.com/repos/{repo_full}/issues"
    payload = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels
    r = requests.post(url, headers=_gh_headers(token), json=payload)
    return r

def list_issues(repo_full: str, token: str, state="open", per_page=10):
    url = f"https://api.github.com/repos/{repo_full}/issues"
    r = requests.get(url, headers=_gh_headers(token), params={"state": state, "per_page": per_page})
    if r.status_code == 200:
        return r.json()
    return []

def list_issue_comments(repo_full: str, token: str, number: int):
    url = f"https://api.github.com/repos/{repo_full}/issues/{number}/comments"
    r = requests.get(url, headers=_gh_headers(token))
    if r.status_code == 200:
        return r.json()
    return []

def sidebar_quick_link(label: str, url: str):
    st.sidebar.markdown(
        f'''<a href="{url}" target="_blank" style="text-decoration:none;">
  <div style="padding:12px 14px; margin:6px 0; border:1px solid #e5e7eb; border-radius:10px;">
    <span style="font-weight:600;">{label}</span>
  </div>
</a>''',
        unsafe_allow_html=True
    )

def feedback_ui():
    st.markdown("---")
    st.header("💬 피드백")

    gh_token = st.secrets.get("GH_TOKEN")
    gh_repo  = st.secrets.get("GH_REPO")  # 예: "hyebin-mkt/image-resizer-web"

    if not gh_token or not gh_repo:
        st.info(
            """**관리자 안내:** Streamlit Secrets에 `GH_TOKEN`, `GH_REPO`를 설정하면
여기서 접수된 내용이 GitHub Issues로 자동 저장됩니다.

- GH_TOKEN: 해당 레포에 Issues 작성 권한이 있는 Personal Access Token
- GH_REPO: 예) `owner/repo`  (본인 저장소 경로)

Secrets가 설정되지 않으면 사용자에겐 이 안내만 보입니다."""
        )
        return

    tab1, tab2 = st.tabs(["💬 댓글달기", "❓ 문의하기"])

    with tab1:
        with st.form("form_praise"):
            name = st.text_input("이름 (선택)")
            email = st.text_input("이메일 (선택)")
            subject = st.text_input("제목", placeholder="예: 덕분에 배너 작업이 빨라졌어요!")
            msg = st.text_area("내용", height=160, placeholder="내용을 자유롭게 남겨주세요.")
            submitted = st.form_submit_button("보내기")
            if submitted:
                if not subject or not msg:
                    st.error("제목과 내용을 입력해주세요.")
                else:
                    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
                    title = f"[댓글] {subject}"
                    body = f"""{msg}

---
**유형**: 댓글
**이름**: {name or '-'}
**이메일**: {email or '-'}
**시간(UTC)**: {now}
"""
                    res = create_issue(gh_repo, gh_token, title, body, labels=["댓글"])
                    if 200 <= res.status_code < 300:
                        st.success("감사합니다! 접수되었습니다.")
                    else:
                        st.error(f"전송 실패: {res.status_code} - {res.text}")

    with tab2:
        with st.form("form_question"):
            name = st.text_input("이름 (선택)", key="q_name")
            email = st.text_input("이메일 (선택)", key="q_email")
            subject = st.text_input("제목", placeholder="예: 특정 사이즈에서 크롭이 이상해요", key="q_subject")
            msg = st.text_area("내용", height=200, placeholder="문의 내용을 자세히 적어주세요.", key="q_msg")
            submitted = st.form_submit_button("보내기")
            if submitted:
                if not subject or not msg:
                    st.error("제목과 내용을 입력해주세요.")
                else:
                    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
                    title = f"[문의] {subject}"
                    body = f"""{msg}

---
**유형**: 문의
**이름**: {name or '-'}
**이메일**: {email or '-'}
**시간(UTC)**: {now}
"""
                    res = create_issue(gh_repo, gh_token, title, body, labels=["문의"])
                    if 200 <= res.status_code < 300:
                        st.success("문의가 접수되었습니다. 확인 후 답변드릴게요!")
                    else:
                        st.error(f"전송 실패: {res.status_code} - {res.text}")

    # 최근 이슈 10개 — 아코디언으로 본문/대댓글 보기
    with st.expander("최근 접수된 피드백 보기(최대 10개)"):
        try:
            items = list_issues(gh_repo, gh_token, state="all", per_page=10)
            if not items or isinstance(items, dict) and items.get("message"):
                st.write("표시할 항목이 없습니다.")
            else:
                for it in items:
                    number = it.get("number")
                    title = it.get("title") or "(제목 없음)"
                    user  = it.get("user", {}).get("login", "")
                    labels = [lb.get("name") for lb in it.get("labels", []) if isinstance(lb, dict)]
                    label_badge = " / ".join(labels) if labels else ""
                    header = f"#{number} {title} — {user}"
                    if label_badge:
                        header += f"  ·  [{label_badge}]"

                    with st.expander(header):
                        body = it.get("body") or "_(본문 없음)_"
                        st.markdown(body)
                        # 댓글 불러오기
                        comments = list_issue_comments(gh_repo, gh_token, number=number)
                        if comments:
                            st.markdown("---")
                            st.write(f"**대댓글 {len(comments)}개**")
                            for c in comments:
                                cuser = c.get("user", {}).get("login", "")
                                ctime = c.get("created_at", "")[:16].replace("T", " ")
                                cbody = c.get("body") or ""
                                with st.expander(f"↳ {cuser} — {ctime}"):
                                    st.markdown(cbody)
                        else:
                            st.caption("대댓글이 없습니다.")
        except Exception as e:
            st.write("목록을 불러오지 못했습니다.")

# ---- UI ----
st.set_page_config(page_title=APP_TITLE, page_icon="⭐", layout="centered")
st.title(APP_TITLE)
st.caption("이미지 하나로 마이다스 이벤트에 필요한 사이즈를 한방에 추출하세요")

with st.sidebar:
    st.header("설정")
    fmt = st.selectbox("출력 포맷", ["jpg","jpeg","png"], index=0)
    jpg_qual = st.slider("JPEG 품질", min_value=60, max_value=100, value=88)
    scale = st.selectbox("출력 배율", SCALE_OPTIONS, index=SCALE_OPTIONS.index(2.0))  # 기본 2.0

    st.markdown("---")
    st.subheader("🔗 바로가기")
    sidebar_quick_link("Hubspot File 바로가기", "https://app.hubspot.com/files/2495902/")
    sidebar_quick_link("Hubspot Website 바로가기", "https://app.hubspot.com/page-ui/2495902/management/pages/site/all")
    sidebar_quick_link("MBM 가이드북", "https://www.canva.com/design/DAGtMIVovm8/eXz5TOekAVik-uynq1JZ1Q/view?utm_content=DAGtMIVovm8&utm_campaign=designshare&utm_medium=link2&utm_source=uniquelinks&utlId=h9b120a74ea")
    st.write("© Chacha")

uploaded = st.file_uploader("이미지 업로드 (PNG/JPG 등, 1개)", type=[e.strip(".") for e in VALID_EXTS], accept_multiple_files=False)
if uploaded:
    file_ext = Path(uploaded.name).suffix.lower()
    if file_ext not in VALID_EXTS:
        st.error("지원하지 않는 이미지 형식입니다.")
        st.stop()

    # Load once
    img = Image.open(uploaded)
    w, h = img.size
    st.image(img, caption=f"원본 미리보기 — {w}x{h}px", use_column_width=True)

    # Base title
    default_title = Path(uploaded.name).stem
    base_title = st.text_input("이미지 타이틀(파일명 베이스)", value=default_title)

    # Presets (checkboxes + select all)
    st.subheader("사이즈 선택")
    col1, col2 = st.columns([1,1])
    with col1:
        select_all = st.checkbox("전체 선택", value=True)
    # individual checkboxes
    chosen_presets = []
    for i, (name, (pw, ph)) in enumerate(PRESETS):
        checked = st.checkbox(f"{name} — {pw}x{ph}", value=True if select_all else False, key=f"preset_{i}")
        if checked:
            chosen_presets.append((name, pw, ph))

    # Custom sizes: one per line: "Label, WxH"
    st.markdown("**커스텀 사이즈 (선택)** — 한 줄에 하나씩 `라벨, WxH` 형식으로 입력하세요. 예: `SNS, 1080x1080`")
    custom_text = st.text_area("""예: Banner 2, 1200x630
Square, 1080x1080""", height=120)
    custom_targets = []
    if custom_text.strip():
        for line in custom_text.splitlines():
            if not line.strip():
                continue
            try:
                left, right = line.split(",", 1)
                label = left.strip()
                size_part = right.strip().lower().replace("×", "x").replace(" ", "")
                if "x" not in size_part:
                    continue
                sw, sh = size_part.split("x", 1)
                sw, sh = int(sw), int(sh)
                custom_targets.append((label, sw, sh))
            except Exception:
                st.warning(f"무시된 입력: `{line}` (형식: 라벨, WxH)")
                continue

    targets = chosen_presets + custom_targets

    # Process
    run = st.button("Run", type="primary", use_container_width=True)
    if run:
        if not targets:
            st.error("내보낼 사이즈를 하나 이상 선택/입력하세요.")
            st.stop()
        base_title_safe = sanitize_label(base_title) if base_title else Path(uploaded.name).stem

        # Build ZIP in memory
        zip_buf = io.BytesIO()
        saved_files = []
        with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for label, tw, th in targets:
                stw = max(1, int(round(tw * float(scale))))
                sth = max(1, int(round(th * float(scale))))
                out_img = resize_cover(img, stw, sth)
                label_safe = sanitize_label(label)
                out_name = f"{base_title_safe}_{label_safe}_{stw}x{sth}.{fmt}"

                bio = io.BytesIO()
                if fmt in ("jpg","jpeg"):
                    ensure_rgb(out_img).save(bio, format="JPEG", quality=int(jpg_qual), optimize=True)
                else:
                    out_img.save(bio, format="PNG", optimize=True)
                bio.seek(0)
                zf.writestr(out_name, bio.read())
                saved_files.append(out_name)

        zip_buf.seek(0)
        st.success("이미지 추출이 완료되었습니다 ✅")
        st.write(f"총 {len(saved_files)}개 파일이 포함되었습니다.")
        st.download_button("ZIP 다운로드", data=zip_buf.getvalue(), file_name=f"{base_title_safe}_resized.zip", mime="application/zip")
else:
    st.info("이미지를 업로드하면 옵션이 표시됩니다.")

# ======= extra vertical space before feedback section =======
st.markdown('<div style="height:80px"></div>', unsafe_allow_html=True)

# Feedback section at the bottom
feedback_ui()
