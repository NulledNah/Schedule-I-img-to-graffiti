import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import pyautogui
import json
import os
import time
import threading
import keyboard

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.001

COLORS = {
    'black':   (0, 0, 0),
    'white':   (255, 255, 255),
    'red':     (255, 0, 0),
    'green':   (0, 255, 0),
    'blue':    (0, 0, 255),
    'yellow':  (255, 255, 0),
    'magenta': (255, 0, 255),
    'brown':   (139, 69, 19),
}

COLOR_NAMES = list(COLORS.keys())
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')


def closest_color(pixel):
    r, g, b = pixel[:3]
    best, best_d = None, float('inf')
    for name, (cr, cg, cb) in COLORS.items():
        dr, dg, db = r - cr, g - cg, b - cb
        d = 2*dr*dr + 4*dg*dg + 3*db*db
        if d < best_d:
            best_d, best = d, name
    return best


class CalibrationPopup(tk.Toplevel):

    STEPS = (
        [('color', n) for n in COLOR_NAMES] +
        [('thickness', f'thickness_{i}') for i in range(1, 5)] +
        [('area_tl', 'draw_area_tl'),
         ('area_br', 'draw_area_br')]
    )

    def __init__(self, master, callback, existing=None):
        super().__init__(master)
        self.callback = callback
        self.points = dict(existing) if existing else {}
        self.idx = 0
        self.transient(master)
        self.attributes('-topmost', True)
        self.resizable(False, False)
        self.title('Calibration')
        self.configure(bg='#1a1a2e')

        self._build_ui()
        self._show_step()

    def _build_ui(self):
        self.lbl_step = tk.Label(self, text='', font=('Segoe UI', 11, 'bold'),
                                 fg='#ddd', bg='#1a1a2e', wraplength=340, justify=tk.CENTER)
        self.lbl_step.pack(padx=16, pady=(12, 6), fill=tk.X)

        self.lbl_pos = tk.Label(self, text='Not captured', font=('Consolas', 10),
                                fg='#888', bg='#1a1a2e')
        self.lbl_pos.pack(padx=16, pady=(0, 8))

        btn_frame = tk.Frame(self, bg='#1a1a2e')
        btn_frame.pack(padx=16, pady=(0, 12), fill=tk.X)

        self.btn_capture = tk.Button(btn_frame, text='Capture position (CTRL+S)',
                                     font=('Segoe UI', 10, 'bold'),
                                     bg='#2d6a4f', fg='white', activebackground='#40916c',
                                     activeforeground='white', relief=tk.FLAT, padx=10, pady=4,
                                     command=self._capture)
        self.btn_capture.pack(fill=tk.X)

        nav_frame = tk.Frame(self, bg='#1a1a2e')
        nav_frame.pack(padx=16, pady=(0, 12), fill=tk.X)

        tk.Button(nav_frame, text='< Back', font=('Segoe UI', 9),
                  bg='#333355', fg='#ccc', relief=tk.FLAT, padx=8, pady=2,
                  command=self._back).pack(side=tk.LEFT)

        self.lbl_progress = tk.Label(nav_frame, text='', font=('Segoe UI', 9),
                                     fg='#888', bg='#1a1a2e')
        self.lbl_progress.pack(side=tk.RIGHT)

        self.bind('<Control-s>', lambda e: self._capture())
        self.bind('<Control-z>', lambda e: self._back())
        self.bind('<Escape>', lambda e: self._finish())
        self.focus_set()

    def _show_step(self):
        self.lbl_progress.config(text=f'{self.idx}/{len(self.STEPS)}')
        if self.idx >= len(self.STEPS):
            self.lbl_step.config(text='Done! Press ESC to save.')
            self.btn_capture.config(text='Done', state=tk.DISABLED, bg='#444')
            self.lbl_pos.config(text='')
            return

        stype, name = self.STEPS[self.idx]
        if stype == 'color':
            self.lbl_step.config(text=f'Move mouse over the {name.upper()}\ncolor button in-game\nand press CAPTURE')
        elif stype == 'thickness':
            n = name.split('_')[1]
            self.lbl_step.config(text=f'Move mouse over the THICKNESS {n}\nbutton in-game\nand press CAPTURE')
        elif name == 'draw_area_tl':
            self.lbl_step.config(text='Move mouse over the\nTOP-LEFT corner of the draw area\nand press CAPTURE')
        elif name == 'draw_area_br':
            self.lbl_step.config(text='Move mouse over the\nBOTTOM-RIGHT corner of the draw area\nand press CAPTURE')

        self.btn_capture.config(state=tk.NORMAL, bg='#2d6a4f', text='Capture position (CTRL+S)')
        self.lbl_pos.config(text=f'Current: {self.points.get(name, "not set")}')

    def _capture(self):
        if self.idx >= len(self.STEPS):
            return
        x, y = pyautogui.position()
        _, name = self.STEPS[self.idx]
        self.points[name] = (x, y)
        self.lbl_pos.config(text=f'Captured! ({x}, {y})')
        self.idx += 1
        self._show_step()

    def _back(self):
        if self.idx > 0:
            self.idx -= 1
            _, name = self.STEPS[self.idx]
            self.points.pop(name, None)
            self._show_step()

    def _finish(self):
        self.destroy()
        self.callback(self.points)


class GraffitiDrawer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Schedule I - Graffiti Drawer')
        self.root.geometry('420x650')
        self.root.minsize(380, 560)
        self.root.configure(bg='#151525')

        self.config = self._load_config()
        self.image = None
        self._preview_tk = None
        self._drawing = False

        self._build_ui()
        self._update_status()
        keyboard.add_hotkey('ctrl+shift+x', lambda: self.root.after(0, self._cancel))

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2)

    def _is_calibrated(self):
        needed = set(COLOR_NAMES + [f'thickness_{i}' for i in range(1, 5)] +
                     ['draw_area_tl', 'draw_area_br'])
        return needed.issubset(self.config.keys())

    def _build_ui(self):
        p = {'padx': 10, 'pady': 4}

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TLabel', background='#151525', foreground='#ddd')
        style.configure('TFrame', background='#151525')
        style.configure('TLabelframe', background='#151525', foreground='#aaa')
        style.configure('TLabelframe.Label', background='#151525', foreground='#999')
        style.configure('TButton', background='#1e1e3a', foreground='#ddd')
        style.configure('TCheckbutton', background='#151525', foreground='#ddd')

        f_img = ttk.LabelFrame(self.root, text=' Image ', padding=8)
        f_img.pack(fill=tk.X, **p)
        r = ttk.Frame(f_img)
        r.pack(fill=tk.X)
        ttk.Button(r, text='Load image (PNG/JPG/JPEG)',
                   command=self._load_image).pack(side=tk.LEFT, padx=4)
        self.lbl_img = ttk.Label(r, text='None')
        self.lbl_img.pack(side=tk.LEFT, padx=8)

        self.lbl_preview_img = tk.Label(f_img, bg='#1a1a2e', width=42, height=12)
        self.lbl_preview_img.pack(pady=6)
        self.lbl_preview = ttk.Label(f_img, text='')
        self.lbl_preview.pack()

        f_cal = ttk.LabelFrame(self.root, text=' Calibration ', padding=8)
        f_cal.pack(fill=tk.X, **p)

        ttk.Button(f_cal, text='Open calibration popup',
                   command=self._open_calibration).pack(fill=tk.X)

        self.lbl_cal = ttk.Label(f_cal, text='Not calibrated', foreground='#e74c3c')
        self.lbl_cal.pack(pady=2)

        info = ttk.Frame(f_cal)
        info.pack(fill=tk.X)
        self.lbl_area = ttk.Label(info, text='Area: --')
        self.lbl_area.pack(side=tk.LEFT)
        self.lbl_colors = ttk.Label(info, text='Colors: 0/8')
        self.lbl_colors.pack(side=tk.RIGHT)

        f_set = ttk.LabelFrame(self.root, text=' Settings ', padding=8)
        f_set.pack(fill=tk.X, **p)

        r1 = ttk.Frame(f_set)
        r1.pack(fill=tk.X, pady=2)
        ttk.Label(r1, text='Thickness:').pack(side=tk.LEFT)
        self.var_thickness = tk.IntVar(value=4)
        ttk.Spinbox(r1, from_=1, to=4, textvariable=self.var_thickness, width=4).pack(side=tk.LEFT, padx=6)
        ttk.Label(r1, text='(1-4)').pack(side=tk.LEFT)

        r2 = ttk.Frame(f_set)
        r2.pack(fill=tk.X, pady=2)
        ttk.Label(r2, text='Resolution:').pack(side=tk.LEFT)
        self.var_res = tk.IntVar(value=100)
        tk.Scale(r2, from_=10, to=500, orient=tk.HORIZONTAL, variable=self.var_res,
                 bg='#1e1e3a', fg='#ddd', troughcolor='#2a2a4a', highlightthickness=0,
                 length=200).pack(side=tk.LEFT, padx=6, fill=tk.X, expand=True)
        self.lbl_res_val = ttk.Label(r2, text='100')
        self.lbl_res_val.pack(side=tk.LEFT, padx=2)
        self.var_res.trace_add('write', lambda *a: (
            self.lbl_res_val.config(text=str(self.var_res.get())),
            self._update_preview()
        ))

        r_fit = ttk.Frame(f_set)
        r_fit.pack(fill=tk.X, pady=2)
        ttk.Label(r_fit, text='Fit:').pack(side=tk.LEFT)
        self.var_fit = tk.StringVar(value='contain')
        ttk.Radiobutton(r_fit, text='Contain (keep ratio)', variable=self.var_fit,
                        value='contain', command=self._update_preview).pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(r_fit, text='Stretch (fill area)', variable=self.var_fit,
                        value='stretch', command=self._update_preview).pack(side=tk.LEFT, padx=4)

        r_skip = ttk.Frame(f_set)
        r_skip.pack(fill=tk.X, pady=2)
        self.var_skip_bg = tk.BooleanVar(value=True)
        ttk.Checkbutton(r_skip, text='Skip background color',
                        variable=self.var_skip_bg,
                        command=self._update_preview).pack(side=tk.LEFT)

        r3 = ttk.Frame(f_set)
        r3.pack(fill=tk.X, pady=2)
        ttk.Label(r3, text='Delay (ms):').pack(side=tk.LEFT)
        self.var_delay = tk.IntVar(value=0)
        ttk.Spinbox(r3, from_=0, to=100, textvariable=self.var_delay, width=5).pack(side=tk.LEFT, padx=6)

        r4 = ttk.Frame(f_set)
        r4.pack(fill=tk.X, pady=2)
        ttk.Label(r4, text='Countdown (sec):').pack(side=tk.LEFT)
        self.var_cd = tk.IntVar(value=3)
        ttk.Spinbox(r4, from_=0, to=10, textvariable=self.var_cd, width=5).pack(side=tk.LEFT, padx=6)

        ttk.Button(f_set, text='Refresh preview', command=self._update_preview).pack(fill=tk.X, pady=4)

        f_act = ttk.Frame(self.root)
        f_act.pack(fill=tk.X, padx=10, pady=(8, 4))

        self.btn_draw = ttk.Button(f_act, text='DRAW', command=self._start_drawing)
        self.btn_draw.pack(fill=tk.X, ipady=8)

        self.btn_cancel = ttk.Button(f_act, text='CANCEL (Esc)',
                                     command=self._cancel, state=tk.DISABLED)
        self.btn_cancel.pack(fill=tk.X, ipady=4, pady=4)

        self.bar = ttk.Progressbar(self.root, mode='determinate')
        self.bar.pack(fill=tk.X, padx=10, pady=4)
        self.lbl_status = ttk.Label(self.root, text='Ready', foreground='#777')
        self.lbl_status.pack()

        self.root.bind('<Escape>', lambda e: self._cancel())

    def _update_status(self):
        if self._is_calibrated():
            self.lbl_cal.config(text='Calibrated', foreground='#2ecc71')
        else:
            self.lbl_cal.config(text='Not calibrated', foreground='#e74c3c')

        if 'draw_area_tl' in self.config and 'draw_area_br' in self.config:
            tl, br = self.config['draw_area_tl'], self.config['draw_area_br']
            self.lbl_area.config(text=f'Area: {br[0]-tl[0]}x{br[1]-tl[1]} px')

        cc = sum(1 for n in COLOR_NAMES if n in self.config)
        self.lbl_colors.config(text=f'Colors: {cc}/8')
        self._update_preview()

    def _compute_dims(self):
        thickness = self.var_thickness.get()
        if self._is_calibrated():
            tl = self.config['draw_area_tl']
            br = self.config['draw_area_br']
            area_w, area_h = br[0] - tl[0], br[1] - tl[1]
            max_w = max(1, area_w // thickness)
            max_h = max(1, area_h // thickness)
        else:
            max_w = self.var_res.get()
            max_h = 99999

        fit = self.var_fit.get()
        if fit == 'stretch':
            img_w, img_h = max_w, max_h
            off_x, off_y = 0, 0
        else:
            w = min(self.var_res.get(), max_w)
            h = max(1, int(self.image.height * w / self.image.width))
            if h > max_h:
                h = max_h
                w = max(1, int(h * self.image.width / self.image.height))
            img_w, img_h = w, h
            off_x = (max_w - img_w) // 2
            off_y = (max_h - img_h) // 2

        return img_w, img_h, off_x, off_y

    def _update_preview(self):
        if self.image is None:
            self.lbl_preview_img.config(image='')
            self._preview_tk = None
            return
        try:
            w, h, off_x, off_y = self._compute_dims()
            img = self.image.resize((w, h), Image.LANCZOS)

            prev = Image.new('RGB', (w, h))
            px_in = img.load()
            px_out = prev.load()
            for y in range(h):
                for x in range(w):
                    px_out[x, y] = COLORS[closest_color(px_in[x, y])]

            scale = min(250 / w, 150 / h)
            dw, dh = max(1, int(w * scale)), max(1, int(h * scale))
            prev = prev.resize((dw, dh), Image.NEAREST)

            self._preview_tk = ImageTk.PhotoImage(prev)
            self.lbl_preview_img.config(image=self._preview_tk, text='',
                                         width=dw, height=dh)
            self.lbl_preview.config(text=f'Output: {w}x{h} pixels')
        except Exception as e:
            self.lbl_preview.config(text=f'Preview error: {e}')

    def _load_image(self):
        path = filedialog.askopenfilename(
            filetypes=[('Images', '*.png *.jpg *.jpeg'), ('All files', '*.*')]
        )
        if not path:
            return
        try:
            img = Image.open(path)
            if img.mode == 'RGBA':
                bg = Image.new('RGB', img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                img = bg
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            self.image = img
            self.lbl_img.config(text=os.path.basename(path))
            self._update_preview()
        except Exception as e:
            messagebox.showerror('Error', f'Cannot load image:\n{e}')

    def _open_calibration(self):
        CalibrationPopup(self.root, self._on_calibration_done, self.config)

    def _on_calibration_done(self, points):
        self.config.update(points)
        self._save_config()
        self._update_status()

    def _start_drawing(self):
        if self.image is None:
            messagebox.showwarning('No image', 'Load an image first.')
            return
        if not self._is_calibrated():
            messagebox.showwarning('Not calibrated', 'Run calibration first.')
            return

        self._drawing = True
        self.btn_draw.config(state=tk.DISABLED)
        self.btn_cancel.config(state=tk.NORMAL)
        self.bar['value'] = 0
        self.lbl_status.config(text='Preparing...')

        threading.Thread(target=self._draw_thread, daemon=True).start()

    def _cancel(self):
        if self._drawing:
            self._drawing = False
            self.lbl_status.config(text='Cancelled')
            self.btn_draw.config(state=tk.NORMAL)
            self.btn_cancel.config(state=tk.DISABLED)

    def _draw_thread(self):
        try:
            tl = self.config['draw_area_tl']
            thickness = self.var_thickness.get()
            delay = self.var_delay.get() / 1000.0
            countdown = self.var_cd.get()
            skip_bg = self.var_skip_bg.get()
            ox, oy = tl[0], tl[1]

            img_w, img_h, off_x, off_y = self._compute_dims()
            ox += off_x * thickness
            oy += off_y * thickness

            img = self.image.resize((img_w, img_h), Image.LANCZOS)
            pixels = img.load()

            grid = [[closest_color(pixels[x, y]) for x in range(img_w)] for y in range(img_h)]
            color_counts = {}
            for row in grid:
                for c in row:
                    color_counts[c] = color_counts.get(c, 0) + 1
            colors_used = sorted(color_counts, key=color_counts.get, reverse=True)
            bg_color = colors_used[0] if colors_used else None
            if skip_bg and bg_color:
                colors_used = [c for c in colors_used if c != bg_color] or colors_used
            total = img_w * img_h

            covered = [[False] * img_w for _ in range(img_h)]
            layers = []

            l4 = {}
            for by in range(0, img_h - img_h % 4, 4):
                for bx in range(0, img_w - img_w % 4, 4):
                    c = grid[by][bx]
                    if c == bg_color and skip_bg:
                        continue
                    if all(grid[by+dy][bx+dx] == c for dy in range(4) for dx in range(4)):
                        for dy in range(4):
                            for dx in range(4):
                                covered[by+dy][bx+dx] = True
                        l4.setdefault(c, []).extend(
                            (bx+dx, by+dy) for dy in range(4) for dx in range(4))
            if l4:
                layers.append((4, l4))

            l2 = {}
            for by in range(0, img_h - img_h % 2, 2):
                for bx in range(0, img_w - img_w % 2, 2):
                    if all(covered[by+dy][bx+dx] for dy in range(2) for dx in range(2)):
                        continue
                    c = grid[by][bx]
                    if c == bg_color and skip_bg:
                        continue
                    if all(grid[by+dy][bx+dx] == c for dy in range(2) for dx in range(2)):
                        for dy in range(2):
                            for dx in range(2):
                                covered[by+dy][bx+dx] = True
                        l2.setdefault(c, []).extend(
                            (bx+dx, by+dy) for dy in range(2) for dx in range(2))
            if l2:
                layers.append((2, l2))

            l1 = {}
            for y in range(img_h):
                for x in range(img_w):
                    if covered[y][x]:
                        continue
                    c = grid[y][x]
                    if c == bg_color and skip_bg:
                        continue
                    covered[y][x] = True
                    l1.setdefault(c, []).append((x, y))
            if l1:
                layers.append((1, l1))

            self.root.after(0, lambda: self.bar.configure(maximum=total))

            if countdown > 0:
                for i in range(countdown, 0, -1):
                    if not self._drawing:
                        return
                    self.root.after(0, lambda v=i: self.lbl_status.config(
                        text=f'Switch to game window! {v}...'))
                    time.sleep(1)

            self.root.after(0, lambda: self.lbl_status.config(text='Drawing...'))
            drawn = 0

            for brush_size, layer in layers:
                if not self._drawing:
                    break

                key = f'thickness_{brush_size}'
                if key in self.config:
                    pyautogui.click(self.config[key][0], self.config[key][1])
                    time.sleep(0.05)

                lines_per_row = max(1, (thickness + brush_size - 1) // brush_size)

                for color_name in colors_used:
                    if not self._drawing:
                        break
                    cp = layer.get(color_name)
                    if not cp:
                        continue

                    if color_name in self.config:
                        cx, cy = self.config[color_name]
                        pyautogui.click(cx, cy)
                        time.sleep(0.03)

                    cp.sort(key=lambda p: (p[1], p[0]))
                    runs = []
                    cur = []
                    for px, py_ in cp:
                        if cur and (py_ != cur[-1][1] or px != cur[-1][0] + 1):
                            runs.append(cur)
                            cur = []
                        cur.append((px, py_))
                    if cur:
                        runs.append(cur)

                    for run in runs:
                        if not self._drawing:
                            break

                        sx = ox + run[0][0] * thickness
                        sy = oy + run[0][1] * thickness
                        seg_w = len(run) * thickness

                        for ty in range(lines_per_row):
                            if not self._drawing:
                                break
                            pyautogui.moveTo(sx, sy + ty)
                            time.sleep(0.005)
                            pyautogui.drag(seg_w, 0, duration=0.01, button='left')

                        drawn += len(run)
                        if delay:
                            time.sleep(delay)

                        if drawn % 50 == 0:
                            d = drawn
                            self.root.after(0, lambda v=d: self._update_progress(v))

                    time.sleep(0.02)

            self.root.after(0, lambda: self._drawing_done(drawn))

        except pyautogui.FailSafeException:
            self.root.after(0, lambda: self._drawing_done(error='FailSafe: mouse moved to corner.'))
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.root.after(0, lambda: self._drawing_done(error=str(e)))

    def _update_progress(self, value):
        self.bar['value'] = value
        self.lbl_status.config(text=f'Drawing... {value} pixels')

    def _drawing_done(self, total=0, error=None):
        self._drawing = False
        self.btn_draw.config(state=tk.NORMAL)
        self.btn_cancel.config(state=tk.DISABLED)
        if error:
            self.bar['value'] = 0
            self.lbl_status.config(text='Error')
            messagebox.showerror('Drawing error', error)
        else:
            self.bar['value'] = total
            self.lbl_status.config(text=f'Done! {total} pixels drawn.')

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    GraffitiDrawer().run()
