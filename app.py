# app.py — ⚡원샷원킬 배너 생성기 (설정은 본문, 피드백은 별도 페이지)

import io, zipfile, math, datetime
from pathlib import Path
from PIL import Image, ImageOps
import streamlit as st

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

# ---- helpers ----
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

# ---- quick-links / footer (본문 하단) ----
st.markdown("""
<style>
.mbm-quick a {text-decoration:none;}
.mbm-quick .card {padding:12px 14px;margin:6px 0;border:1px solid #e5e7eb;border-radius:10px;}
</style>
""", unsafe_allow_html=True)

def quick_link(label: str, url: str):
    st.markdown(
        f'''<div class="mbm-quick"><a href="{url}" target="_blank">
<div class="card"><span style="font-weight:600;">{label}</span> <span>↗</span></div>
</a></div>''', unsafe_allow_html=True
    )

def render_footer_links():
    st.markdown("---")
    st.subheader("🔗 바로가기")
    quick_link("Hubspot File 바로가기", "https://app.hubspot.com/files/2495902/")
    quick_link("Hubspot Website 바로가기", "https://app.hubspot.com/page-ui/2495902/management/pages/site/all")
    quick_link("MBM 가이드북", "https://www.canva.com/design/DAGtMIVovm8/eXz5TOekAVik-uynq1JZ1Q/view")
    st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)
    st.caption("© Chacha · chb0218@midasit.com")

# ---- UI ----
st.set_page_config(page_title=APP_TITLE, page_icon="⭐", layout="centered")
st.title(APP_TITLE)
st.caption("이미지 하나로 마이다스 이벤트에 필요한 사이즈를 한방에 추출하세요")

# 본문에서 설정
st.header("설정")
colA, colB, colC = st.columns(3)
with colA:
    fmt = st.selectbox("출력 포맷", ["jpg","jpeg","png"], index=0)
with colB:
    jpg_qual = st.slider("JPEG 품질", min_value=60, max_value=100, value=88)
with colC:
    scale = st.selectbox("출력 배율", SCALE_OPTIONS, index=SCALE_OPTIONS.index(2.0))

st.markdown("---")

uploaded = st.file_uploader("이미지 업로드 (PNG/JPG 등, 1개)", type=[e.strip(".") for e in VALID_EXTS], accept_multiple_files=False)
if uploaded:
    from PIL import Image
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

    run = st.button("Run", type="primary")
    if run:
        if not targets:
            st.error("내보낼 사이즈를 하나 이상 선택/입력하세요."); st.stop()

        zip_buf = io.BytesIO(); saved=[]
        with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for label,tw,th in targets:
                stw = max(1, int(round(tw*float(scale))))
                sth = max(1, int(round(th*float(scale))))
                out = resize_cover(img, stw, sth)
                label_safe = sanitize_label(label)
                out_name = f"{sanitize_label(base_title)}_{label_safe}_{stw}x{sth}.{fmt}"
                bio = io.BytesIO()
                if fmt in ("jpg","jpeg"):
                    ensure_rgb(out).save(bio, format="JPEG", quality=int(jpg_qual), optimize=True)
                else:
                    out.save(bio, format="PNG", optimize=True)
                bio.seek(0); zf.writestr(out_name, bio.read()); saved.append(out_name)

        zip_buf.seek(0)
        st.success(f"이미지 추출 완료 ✅  (총 {len(saved)}개)")
        st.download_button("ZIP 다운로드", data=zip_buf.getvalue(),
                           file_name=f"{sanitize_label(base_title)}_resized.zip", mime="application/zip")
else:
    st.info("이미지를 업로드하면 옵션이 표시됩니다.")

# 하단 바로가기/푸터
st.markdown('<div style="height:60px"></div>', unsafe_allow_html=True)
render_footer_links()

# 여백
st.markdown('<div style="height:40px"></div>', unsafe_allow_html=True)

# Feedback 안내 (새 페이지)
st.markdown("피드백이 있으신가요? → **[Feedback 페이지로 이동](Feedback)**")
