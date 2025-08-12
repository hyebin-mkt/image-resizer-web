
# app.py
# Key Image Resizer (Web) — made by Chacha
# Upload one image and export multiple sizes (presets + custom) with scale options.
# Run locally:   pip install -r requirements.txt && streamlit run app.py

import io
import zipfile
import math
from pathlib import Path

import streamlit as st
from PIL import Image, ImageOps

APP_TITLE = "Image Resizer — by Chacha"
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
        base = Image.new("RGB", img.size, bg)
        base.paste(img, mask=img.split()[-1])
        return base
    return img.convert("RGB") if img.mode != "RGB" else img

# ---- UI ----
st.set_page_config(page_title=APP_TITLE, page_icon="⭐", layout="centered")
st.title(APP_TITLE)
st.caption("하나의 이미지를 여러 사이즈로 자동 추출합니다. (중앙 크롭/FILL)")

with st.sidebar:
    st.header("설정")
    fmt = st.selectbox("출력 포맷", ["jpg","jpeg","png"], index=0)
    jpg_qual = st.slider("JPEG 품질", min_value=60, max_value=100, value=88)
    scale = st.selectbox("출력 배율", SCALE_OPTIONS, index=SCALE_OPTIONS.index(2.0))  # 기본 2.0
    st.markdown("---")
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
    custom_text = st.text_area("예: Banner 2, 1200x630\nSquare, 1080x1080", height=120)
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
