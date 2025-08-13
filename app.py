# app.py
# ⚡원샷원킬 배너 생성기 — made by Chacha
# Upload one image and export multiple sizes (presets + custom) with scale options.
# Run locally: pip install -r requirements.txt && streamlit run app.py

import io
import zipfile
import math
from pathlib import Path
import datetime

import streamlit as st
from PIL import Image, ImageOps

APP_TITLE = " ⚡원샷원킬 배너 생성기"
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

# ---------- helpers ----------
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

# ---------- page ----------
st.set_page_config(page_title="원샷원킬 배너 생성기", page_icon="⭐", layout="centered")
st.title(APP_TITLE)
st.caption("이미지 하나로 마이다스 이벤트에 필요한 사이즈를 한방에 추출하세요")

# ---- Sidebar (links + copyright only) ----
with st.sidebar:
    tabs_sb = st.tabs(["🔗 바로가기", " "])  # 빈 탭 하나로 높이 확보 (디자인용)
    with tabs_sb[0]:
        st.subheader("바로가기")
        sidebar_quick_link("Hubspot File 바로가기", "https://app.hubspot.com/files/2495902/")
        sidebar_quick_link("Hubspot Website 바로가기", "https://app.hubspot.com/page-ui/2495902/management/pages/site/all")
        sidebar_quick_link("MBM 가이드북", "https://www.canva.com/design/DAGtMIVovm8/eXz5TOekAVik-uynq1JZ1Q/view?utm_content=DAGtMIVovm8&utm_campaign=designshare&utm_medium=link2&utm_source=uniquelinks&utlId=h9b120a74ea")
        sidebar_quick_link("Feedback 페이지로 이동", "/Feedback")  # 새 페이지

    # sticky copyright (하단 고정)
    st.sidebar.markdown("""
    <style>
    [data-testid="stSidebar"] .sidebar-copyright{
      position: sticky; bottom: 18px; margin-top: 24px;
    }
    </style>
    """, unsafe_allow_html=True)
    st.sidebar.markdown(
        '<div class="sidebar-copyright" style="color:#6b7280; font-size:12px;">'
        '© Chacha · <a href="mailto:chb0218@midasit.com" style="color:#6b7280; text-decoration:none;">chb0218@midasit.com</a>'
        '</div>',
        unsafe_allow_html=True
    )

# ===== 본문 설정 패널 (사이드바 → 본문 이동) =====
st.markdown("### 설정")
with st.container(border=True):
    colA, colB, colC = st.columns([1,1,1])
    with colA:
        fmt = st.selectbox("출력 포맷", ["jpg","jpeg","png"], index=0)
    with colC:
        scale = st.selectbox("출력 배율", SCALE_OPTIONS, index=SCALE_OPTIONS.index(2.0))
    with colB:
        jpg_qual = st.slider("JPEG 품질", min_value=60, max_value=100, value=88)

# ===== 메인 업로드/처리 =====
uploaded = st.file_uploader("이미지 업로드 (PNG/JPG 등, 1개)", type=[e.strip(".") for e in VALID_EXTS], accept_multiple_files=False)
if uploaded:
    file_ext = Path(uploaded.name).suffix.lower()
    if file_ext not in VALID_EXTS:
        st.error("지원하지 않는 이미지 형식입니다.")
        st.stop()

    img = Image.open(uploaded)
    w, h = img.size
    st.image(img, caption=f"원본 미리보기 — {w}x{h}px", use_column_width=True)

    default_title = Path(uploaded.name).stem
    base_title = st.text_input("이미지 타이틀(파일명 베이스)", value=default_title)

    st.subheader("사이즈 선택")
    col1, col2 = st.columns([1,1])
    with col1:
        select_all = st.checkbox("전체 선택", value=True)

    chosen_presets = []
    for i, (name, (pw, ph)) in enumerate(PRESETS):
        checked = st.checkbox(f"{name} — {pw}x{ph}", value=True if select_all else False, key=f"preset_{i}")
        if checked:
            chosen_presets.append((name, pw, ph))

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

    run = st.button("Run", type="primary", use_container_width=True)
    if run:
        if not targets:
            st.error("내보낼 사이즈를 하나 이상 선택/입력하세요.")
            st.stop()
        base_title_safe = sanitize_label(base_title) if base_title else Path(uploaded.name).stem

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

# 여백
st.markdown('<div style="height:40px"></div>', unsafe_allow_html=True)

# Feedback 안내 (새 페이지)
st.markdown("피드백이 있으신가요? → **[Feedback 페이지로 이동](Feedback)**")
