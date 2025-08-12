
#!/usr/bin/env python3
# key_image_resizer_chacha_v8.py
# Key Image Resizer_made by Chacha (ver.1.0)

import math
import sys
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.font as tkfont
from PIL import Image, ImageOps

# Drag & Drop (optional)
DND_AVAILABLE = False
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_AVAILABLE = True
except Exception:
    DND_AVAILABLE = False

APP_TITLE = "Image Resizer_by Chacha | ver.1.0 "
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

# --------- Font helpers (Windows private font load) ---------
def load_private_font(ttf_path: Path) -> bool:
    try:
        from ctypes import windll
        FR_PRIVATE = 0x10
        AddFontResourceEx = windll.gdi32.AddFontResourceExW
        res = AddFontResourceEx(str(ttf_path), FR_PRIVATE, 0)
        # Broadcast font change
        windll.user32.SendMessageW(0xFFFF, 0x001D, 0, 0)  # HWND_BROADCAST, WM_FONTCHANGE
        return res > 0
    except Exception:
        return False

def apply_global_font(family="Pretendard", size_delta=2):
    # Increase base Tk fonts by +2 and set family
    for name in ("TkDefaultFont","TkTextFont","TkMenuFont","TkHeadingFont","TkTooltipFont","TkFixedFont","TkIconFont","TkCaptionFont","TkSmallCaptionFont","TkStatusFont"):
        try:
            f = tkfont.nametofont(name)
            cur_size = f.cget("size")
            try:
                new_size = int(cur_size) + size_delta
            except Exception:
                new_size = cur_size
            f.configure(family=family, size=new_size)
        except Exception:
            pass

def try_load_pretendard_fonts(script_dir: Path):
    # Look for fonts in current dir or ./fonts
    candidates = [
        script_dir / "Pretendard-Regular.ttf",
        script_dir / "Pretendard-Bold.ttf",
        script_dir / "fonts" / "Pretendard-Regular.ttf",
        script_dir / "fonts" / "Pretendard-Bold.ttf",
    ]
    any_loaded = False
    for p in candidates:
        if p.exists():
            if load_private_font(p):
                any_loaded = True
    if any_loaded:
        apply_global_font("Pretendard", size_delta=2)

# --------- Image helpers ---------
def sanitize_label(label: str) -> str:
    bad = '\\/:*?"<>|'
    s = label.strip().replace(" ", "_")
    for ch in bad:
        s = s.replace(ch, "")
    return s

def resize_cover(im: Image.Image, target_w: int, target_h: int) -> Image.Image:
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
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        base = Image.new("RGB", img.size, bg)
        base.paste(img, mask=img.split()[-1])
        return base
    return img.convert("RGB") if img.mode != "RGB" else img

# --------- App ---------
class App(TkinterDnD.Tk if DND_AVAILABLE else tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("980x760")
        self.minsize(880, 680)

        self.configure(bg="#F3F3F3")  # non-input area background

        # Theming
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Embedded icon (optional)
        self._icon_img = None
        try:
            from app_icon_base64 import ICON_PNG_BASE64
            if ICON_PNG_BASE64:
                self._icon_img = tk.PhotoImage(data=ICON_PNG_BASE64)
                self.iconphoto(True, self._icon_img)
        except Exception:
            pass

        # Try load Pretendard fonts and apply globally (+2)
        here = Path(__file__).resolve().parent
        try_load_pretendard_fonts(here)

        # White styles for input sections
        style.configure("White.TFrame", background="#FFFFFF")
        style.configure("White.TLabelframe", background="#FFFFFF")
        style.configure("White.TLabelframe.Label", background="#FFFFFF", foreground="#000000")
        style.configure("White.TLabel", background="#FFFFFF", foreground="#000000")
        style.configure("White.TCheckbutton", background="#FFFFFF", foreground="#000000")
        style.configure("White.TButton", background="#FFFFFF", foreground="#000000")
        style.configure("White.TEntry", fieldbackground="#FFFFFF", background="#FFFFFF")
        style.configure("White.TCombobox", fieldbackground="#FFFFFF", background="#FFFFFF", foreground="#000000")

        # State
        self.selected_file: Path | None = None
        self.output_dir_var = tk.StringVar()
        self.format_var = tk.StringVar(value="jpg")
        self.quality_var = tk.IntVar(value=88)
        self.base_title_var = tk.StringVar()
        self.select_all_var = tk.BooleanVar(value=True)
        self.scale_var = tk.StringVar(value="2.0")  # default 2x
        self.preset_vars = []
        self.custom_items = []

        self._build_ui(style)

    def _build_ui(self, style: ttk.Style):
        # Top section: 저장 경로 및 출력 형식 (white)
        top = ttk.LabelFrame(self, text="저장 경로 및 출력 형식", style="White.TLabelframe")
        top.pack(fill="x", padx=14, pady=(25, 5))

        ttk.Label(top, text="저장 폴더:", style="White.TLabel").grid(row=0, column=0, padx=8, pady=6, sticky="w")
        ttk.Entry(top, textvariable=self.output_dir_var, width=64, style="White.TEntry").grid(row=0, column=1, padx=4, pady=6, sticky="we")
        ttk.Button(top, text="찾기…", command=self.browse_output_dir, style="White.TButton").grid(row=0, column=2, padx=8, pady=6)

        opts = ttk.Frame(top, style="White.TFrame")
        opts.grid(row=0, column=3, padx=8, pady=6, sticky="e")
        ttk.Label(opts, text="포맷:", style="White.TLabel").grid(row=0, column=0, padx=(4,4), sticky="e")
        ttk.Combobox(opts, textvariable=self.format_var, values=["jpg","jpeg","png"], width=8, state="readonly").grid(row=0, column=1, padx=(0,8))

        ttk.Label(opts, text="JPEG 품질:", style="White.TLabel").grid(row=0, column=2, padx=(4,4), sticky="e")
        ttk.Spinbox(opts, from_=60, to=100, textvariable=self.quality_var, width=6).grid(row=0, column=3, padx=(0,8))

        ttk.Label(opts, text="출력 배율:", style="White.TLabel").grid(row=0, column=4, padx=(4,4), sticky="e")
        scale_box = ttk.Combobox(opts, values=[str(x) for x in (0.5,1.0,1.5,2.0,2.5,3.0)], textvariable=self.scale_var, width=6, state="readonly")
        scale_box.grid(row=0, column=5, padx=(0,0))
        try:
            scale_box.set("2.0")
        except Exception:
            pass

        top.columnconfigure(1, weight=1)

        # File selection section (white)
        file_frame = ttk.LabelFrame(self, text="이미지 선택 / 파일명 베이스", style="White.TLabelframe")
        file_frame.pack(fill="x", padx=14, pady=(0,8))

        file_row = ttk.Frame(file_frame, style="White.TFrame")
        file_row.pack(fill="x", padx=8, pady=(8,4))
        ttk.Button(file_row, text="이미지 선택…", command=self.pick_single_file, width=16, style="White.TButton").pack(side="left")
        self.file_path_var = tk.StringVar()
        ttk.Entry(file_row, textvariable=self.file_path_var, style="White.TEntry").pack(side="left", fill="x", expand=True, padx=8)

        dnd_text = "여기로 드래그&드롭" + ("" if DND_AVAILABLE else " (tkinterdnd2 미설치 시 비활성)")
        self.drop_area = tk.Label(file_frame, text=dnd_text, borderwidth=1, relief="solid", anchor="center", bg="#FFFFFF")
        self.drop_area.pack(fill="x", padx=8, pady=(0,8), ipady=8)
        if DND_AVAILABLE:
            self.drop_area.drop_target_register(DND_FILES)
            self.drop_area.dnd_bind("<<Drop>>", self.on_drop_file)

        base_row = ttk.Frame(file_frame, style="White.TFrame")
        base_row.pack(fill="x", padx=8, pady=(0,8))
        ttk.Label(base_row, text="이미지 타이틀(파일명 베이스):", style="White.TLabel").pack(side="left")
        ttk.Entry(base_row, textvariable=self.base_title_var, width=36, style="White.TEntry").pack(side="left", padx=8)

        # Sizes section (white)
        sizes_frame = ttk.LabelFrame(self, text="사이즈 선택", style="White.TLabelframe")
        sizes_frame.pack(fill="both", expand=True, padx=14, pady=(0,8))

        top_row = ttk.Frame(sizes_frame, style="White.TFrame")
        top_row.pack(fill="x", padx=10, pady=(10,4))
        ttk.Checkbutton(top_row, text="전체 선택/해제", variable=self.select_all_var, command=self.toggle_all_presets, style="White.TCheckbutton").pack(side="left")

        preset_box = ttk.Frame(sizes_frame, style="White.TFrame")
        preset_box.pack(fill="x", padx=14, pady=(0,12))

        for name, (w,h) in PRESETS:
            var = tk.BooleanVar(value=True)
            self.preset_vars.append((name, (w,h), var))
            ttk.Checkbutton(preset_box, text=f"{name}  —  {w}x{h}", variable=var, style="White.TCheckbutton").pack(anchor="w", pady=2)

        custom_box = ttk.LabelFrame(sizes_frame, text="커스텀 사이즈 추가 (라벨 + 가로x세로 px)", style="White.TLabelframe")
        custom_box.pack(fill="x", padx=8, pady=(0,10))

        ttk.Label(custom_box, text="라벨:", style="White.TLabel").grid(row=0, column=0, padx=6, pady=6, sticky="e")
        self.custom_label_var = tk.StringVar(value="Custom")
        ttk.Entry(custom_box, textvariable=self.custom_label_var, width=18, style="White.TEntry").grid(row=0, column=1, padx=4, pady=6, sticky="w")

        ttk.Label(custom_box, text="가로(px):", style="White.TLabel").grid(row=0, column=2, padx=6, pady=6, sticky="e")
        self.custom_w_var = tk.StringVar()
        ttk.Entry(custom_box, textvariable=self.custom_w_var, width=8, style="White.TEntry").grid(row=0, column=3, padx=4, pady=6, sticky="w")

        ttk.Label(custom_box, text="세로(px):", style="White.TLabel").grid(row=0, column=4, padx=6, pady=6, sticky="e")
        self.custom_h_var = tk.StringVar()
        ttk.Entry(custom_box, textvariable=self.custom_h_var, width=8, style="White.TEntry").grid(row=0, column=5, padx=4, pady=6, sticky="w")

        ttk.Button(custom_box, text="추가", command=self.add_custom_size, style="White.TButton").grid(row=0, column=6, padx=10, pady=6)
        custom_box.columnconfigure(1, weight=1)

        self.custom_list = ttk.Frame(sizes_frame, style="White.TFrame")
        self.custom_list.pack(fill="x", padx=8, pady=(0,4))

        # Bottom Run bar (F3F3F3 background area)
        run_bar = tk.Frame(self, bg="#F3F3F3", height=100)
        run_bar.pack(fill="x", padx=14, pady=(5, 10))
        run_bar.pack_propagate(False)

        # Use tk.Button for explicit color control; font keep 12 bold
        self.run_btn = tk.Button(run_bar, text="Run",
                                 font=("Segoe UI", 12, "bold"),
                                 bd=1, relief="solid",
                                 bg="#FFFFFF", fg="#000000",
                                 activebackground="#2563EB", activeforeground="#FFFFFF",
                                 command=self.run_resize)

        # Place button centered; width 70% of frame, height 50px
        self.run_btn.place(relx=0.5, rely=0.5, anchor="center", width=int(self.winfo_width()*0.7), height=50)

        # Update placement on resize
        def resize_run_btn(event):
            w = event.width
            btn_w = int(w * 0.7)
            self.run_btn.place_configure(width=btn_w, height=50)
        run_bar.bind("<Configure>", resize_run_btn)

        # Hover effect: only colors
        def on_enter(_e):
            self.run_btn.configure(bg="#2563EB", fg="#FFFFFF")
        def on_leave(_e):
            self.run_btn.configure(bg="#FFFFFF", fg="#000000")
        self.run_btn.bind("<Enter>", on_enter)
        self.run_btn.bind("<Leave>", on_leave)

    # -------- Handlers --------
    def browse_output_dir(self):
        d = filedialog.askdirectory(title="저장 폴더 선택")
        if d:
            self.output_dir_var.set(d)

    def pick_single_file(self):
        types = [("이미지 파일", "*.png *.jpg *.jpeg *.webp *.bmp *.tiff")]
        path = filedialog.askopenfilename(title="이미지 선택", filetypes=types)
        if path:
            p = Path(path)
            if p.suffix.lower() not in VALID_EXTS:
                messagebox.showerror("파일 오류", "지원하는 이미지 파일이 아닙니다.")
                return
            self.selected_file = p
            self.file_path_var.set(str(p))

    def on_drop_file(self, event):
        try:
            paths = self.tk.splitlist(event.data)
            path = paths[0] if paths else None
            if path:
                p = Path(path)
                if p.suffix.lower() in VALID_EXTS and p.exists():
                    self.selected_file = p
                    self.file_path_var.set(str(p))
                else:
                    messagebox.showerror("파일 오류", "지원하는 이미지 파일이 아닙니다.")
        except Exception as e:
            messagebox.showerror("드롭 오류", str(e))

    def toggle_all_presets(self):
        val = self.select_all_var.get()
        for _, _, var in self.preset_vars:
            var.set(val)

    def add_custom_size(self):
        label = self.custom_label_var.get().strip()
        w = self.custom_w_var.get().strip()
        h = self.custom_h_var.get().strip()
        if not label or not w.isdigit() or not h.isdigit():
            messagebox.showerror("입력 오류", "라벨과 가로/세로(px)를 올바르게 입력하세요.")
            return
        w, h = int(w), int(h)
        row = ttk.Frame(self.custom_list, style="White.TFrame")
        row.pack(fill="x", pady=2)
        chk_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row, variable=chk_var, style="White.TCheckbutton").pack(side="left", padx=(4,6))
        ttk.Label(row, text=f"{label} — {w}x{h}", style="White.TLabel").pack(side="left")
        ttk.Button(row, text="삭제", width=6, command=lambda r=row: self.remove_custom_row(r), style="White.TButton").pack(side="right", padx=4)
        self.custom_items.append((tk.StringVar(value=label), tk.IntVar(value=w), tk.IntVar(value=h), chk_var, row))
        self.custom_w_var.set("")
        self.custom_h_var.set("")

    def remove_custom_row(self, row):
        for i, (_, _, _, _, r) in enumerate(self.custom_items):
            if r == row:
                self.custom_items.pop(i)
                break
        row.destroy()

    # -------- Core --------
    def run_resize(self):
        if not self.selected_file:
            messagebox.showerror("실행 불가", "이미지 파일을 선택하세요.")
            return
        out_dir = self.output_dir_var.get().strip()
        if not out_dir:
            messagebox.showerror("실행 불가", "저장 폴더를 선택하세요.")
            return
        out_root = Path(out_dir)
        try:
            out_root.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            messagebox.showerror("출력 오류", f"저장 폴더를 만들 수 없습니다:\n{e}")
            return

        targets = []
        for name, (w,h), var in self.preset_vars:
            if var.get():
                targets.append((name, w, h))
        for label_var, w_var, h_var, chk_var, _ in self.custom_items:
            if chk_var.get():
                targets.append((label_var.get(), int(w_var.get()), int(h_var.get())))
        if not targets:
            messagebox.showerror("실행 불가", "내보낼 사이즈를 선택하세요.")
            return

        try:
            scale = float(self.scale_var.get())
            if scale <= 0:
                raise ValueError
        except Exception:
            messagebox.showerror("배율 오류", "출력 배율을 올바르게 선택하세요.")
            return

        fmt = self.format_var.get().lower().strip()
        if fmt not in ("jpg","jpeg","png"):
            messagebox.showerror("형식 오류", "출력 포맷은 jpg, jpeg 또는 png만 지원합니다.")
            return
        q = int(self.quality_var.get())
        if q < 60 or q > 100:
            q = 88

        base_title = self.base_title_var.get().strip()
        base_title = sanitize_label(base_title) if base_title else None

        p = self.selected_file
        try:
            with Image.open(p) as im:
                for label, tw, th in targets:
                    stw = max(1, int(round(tw * scale)))
                    sth = max(1, int(round(th * scale)))
                    out_img = resize_cover(im, stw, sth)
                    label_safe = sanitize_label(label)
                    stem = base_title if base_title else p.stem
                    out_name = f"{stem}_{label_safe}_{stw}x{sth}.{fmt}"
                    out_path = out_root / out_name
                    if fmt in ("jpg", "jpeg"):
                        out_to_save = ensure_rgb(out_img)
                        out_to_save.save(out_path, quality=q, optimize=True)
                    else:
                        out_img.save(out_path, optimize=True)

            # Open folder and show completion message
            try:
                os.startfile(str(out_root))
            except Exception:
                pass
            messagebox.showinfo("완료", "이미지 추출이 완료되었습니다")
        except Exception as e:
            messagebox.showerror("오류", f"처리 중 문제가 발생했습니다:\n{e}")
            print(f"[ERR] {p}: {e}", file=sys.stderr)

if __name__ == "__main__":
    app = App()
    app.mainloop()
