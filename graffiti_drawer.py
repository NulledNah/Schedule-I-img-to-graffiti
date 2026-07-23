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

COLORI = {
    'nero':    (0, 0, 0),
    'bianco':  (255, 255, 255),
    'rosso':   (255, 0, 0),
    'verde':   (0, 255, 0),
    'blu':     (0, 0, 255),
    'giallo':  (255, 255, 0),
    'magenta': (255, 0, 255),
    'marrone': (139, 69, 19),
}

NOMI_COLORI = list(COLORI.keys())
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')


def colore_piu_vicino(pixel):
    r, g, b = pixel[:3]
    best, best_d = None, float('inf')
    for name, (cr, cg, cb) in COLORI.items():
        d = (r - cr)**2 + (g - cg)**2 + (b - cb)**2
        if d < best_d:
            best_d, best = d, name
    return best


class PopupCalibrazione(tk.Toplevel):
    """Finestrella always-on-top per catturare posizioni del mouse."""

    STEP = (
        [('colore', n) for n in NOMI_COLORI] +
        [('spessore', f'spessore_{i}') for i in range(1, 5)] +
        [('area_tl', 'area_disegno_tl'),
         ('area_br', 'area_disegno_br')]
    )

    def __init__(self, master, callback, esistenti=None):
        super().__init__(master)
        self.callback = callback
        self.punti = dict(esistenti) if esistenti else {}
        self.idx = 0
        self.transient(master)
        self.attributes('-topmost', True)
        self.resizable(False, False)
        self.title('Calibrazione')
        self.configure(bg='#1a1a2e')

        self._crea_ui()
        self._mostra_step()

    def _crea_ui(self):
        self.lbl_step = tk.Label(self, text='', font=('Segoe UI', 11, 'bold'),
                                 fg='#ddd', bg='#1a1a2e', wraplength=340, justify=tk.CENTER)
        self.lbl_step.pack(padx=16, pady=(12, 6), fill=tk.X)

        self.lbl_pos = tk.Label(self, text='Non catturato', font=('Consolas', 10),
                                fg='#888', bg='#1a1a2e')
        self.lbl_pos.pack(padx=16, pady=(0, 8))

        btn_frame = tk.Frame(self, bg='#1a1a2e')
        btn_frame.pack(padx=16, pady=(0, 12), fill=tk.X)

        self.btn_cattura = tk.Button(btn_frame, text='Cattura posizione (CTRL+S)',
                                     font=('Segoe UI', 10, 'bold'),
                                     bg='#2d6a4f', fg='white', activebackground='#40916c',
                                     activeforeground='white', relief=tk.FLAT, padx=10, pady=4,
                                     command=self._cattura)
        self.btn_cattura.pack(fill=tk.X)

        nav_frame = tk.Frame(self, bg='#1a1a2e')
        nav_frame.pack(padx=16, pady=(0, 12), fill=tk.X)

        tk.Button(nav_frame, text='< Indietro', font=('Segoe UI', 9),
                  bg='#333355', fg='#ccc', relief=tk.FLAT, padx=8, pady=2,
                  command=self._indietro).pack(side=tk.LEFT)

        self.lbl_progresso = tk.Label(nav_frame, text='', font=('Segoe UI', 9),
                                      fg='#888', bg='#1a1a2e')
        self.lbl_progresso.pack(side=tk.RIGHT)

        self.bind('<Control-s>', lambda e: self._cattura())
        self.bind('<Control-z>', lambda e: self._indietro())
        self.bind('<Escape>', lambda e: self._fine())
        self.focus_set()

    def _mostra_step(self):
        self.lbl_progresso.config(text=f'{self.idx}/{len(self.STEP)}')
        if self.idx >= len(self.STEP):
            self.lbl_step.config(text='Completato! Premi ESC per salvare.')
            self.btn_cattura.config(text='Completato', state=tk.DISABLED, bg='#444')
            self.lbl_pos.config(text='')
            return

        tipo, nome = self.STEP[self.idx]
        if tipo == 'colore':
            self.lbl_step.config(text=f'Posiziona il mouse sul pulsante\ndel colore {nome.upper()} nel gioco\ne premi CATTURA')
        elif tipo == 'spessore':
            n = nome.split('_')[1]
            self.lbl_step.config(text=f'Posiziona il mouse sul pulsante\ndello SPESSORE {n} nel gioco\ne premi CATTURA')
        elif nome == 'area_disegno_tl':
            self.lbl_step.config(text=f'Posiziona il mouse sull\'angolo\nIN ALTO A SINISTRA dell\'area di disegno\ne premi CATTURA')
        elif nome == 'area_disegno_br':
            self.lbl_step.config(text=f'Posiziona il mouse sull\'angolo\nIN BASSO A DESTRA dell\'area di disegno\ne premi CATTURA')

        self.btn_cattura.config(state=tk.NORMAL, bg='#2d6a4f', text='Cattura posizione (CTRL+S)')
        self.lbl_pos.config(text=f'Attuale: {self.punti.get(nome, "non impostato")}')

    def _cattura(self):
        if self.idx >= len(self.STEP):
            return
        x, y = pyautogui.position()
        _, nome = self.STEP[self.idx]
        self.punti[nome] = (x, y)
        self.lbl_pos.config(text=f'Catturato! ({x}, {y})')
        self.idx += 1
        self._mostra_step()

    def _indietro(self):
        if self.idx > 0:
            self.idx -= 1
            _, nome = self.STEP[self.idx]
            self.punti.pop(nome, None)
            self._mostra_step()

    def _fine(self):
        self.destroy()
        self.callback(self.punti)


class GraffitiDrawer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Schedule I - Graffiti Drawer')
        self.root.geometry('420x620')
        self.root.minsize(380, 540)
        self.root.configure(bg='#151525')

        self.config = self._carica_config()
        self.immagine = None
        self._preview_tk = None
        self._disegnando = False

        self._crea_ui()
        self._aggiorna_stato()
        keyboard.add_hotkey('ctrl+shift+x', lambda: self.root.after(0, self._annulla))

    def _carica_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _salva_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2)

    def _calibrato(self):
        necessari = set(NOMI_COLORI + [f'spessore_{i}' for i in range(1, 5)] +
                        ['area_disegno_tl', 'area_disegno_br'])
        return necessari.issubset(self.config.keys())

    def _crea_ui(self):
        p = {'padx': 10, 'pady': 4}

        stile = ttk.Style()
        stile.theme_use('clam')
        stile.configure('TLabel', background='#151525', foreground='#ddd')
        stile.configure('TFrame', background='#151525')
        stile.configure('TLabelframe', background='#151525', foreground='#aaa')
        stile.configure('TLabelframe.Label', background='#151525', foreground='#999')
        stile.configure('TButton', background='#1e1e3a', foreground='#ddd')

        # --- Immagine ---
        f_img = ttk.LabelFrame(self.root, text=' Immagine ', padding=8)
        f_img.pack(fill=tk.X, **p)
        r = ttk.Frame(f_img)
        r.pack(fill=tk.X)
        ttk.Button(r, text='Carica immagine (PNG/JPG/JPEG)',
                   command=self._carica_immagine).pack(side=tk.LEFT, padx=4)
        self.lbl_img = ttk.Label(r, text='Nessuna')
        self.lbl_img.pack(side=tk.LEFT, padx=8)

        self.lbl_preview_img = tk.Label(f_img, bg='#1a1a2e', width=42, height=12)
        self.lbl_preview_img.pack(pady=6)
        self.lbl_preview = ttk.Label(f_img, text='')
        self.lbl_preview.pack()

        # --- Calibrazione ---
        f_cal = ttk.LabelFrame(self.root, text=' Calibrazione ', padding=8)
        f_cal.pack(fill=tk.X, **p)

        ttk.Button(f_cal, text='Apri popup di calibrazione',
                   command=self._apri_calibrazione).pack(fill=tk.X)

        self.lbl_cal = ttk.Label(f_cal, text='Non calibrato', foreground='#e74c3c')
        self.lbl_cal.pack(pady=2)

        info = ttk.Frame(f_cal)
        info.pack(fill=tk.X)
        self.lbl_area = ttk.Label(info, text='Area: --')
        self.lbl_area.pack(side=tk.LEFT)
        self.lbl_colori = ttk.Label(info, text='Colori: 0/8')
        self.lbl_colori.pack(side=tk.RIGHT)

        # --- Impostazioni ---
        f_set = ttk.LabelFrame(self.root, text=' Impostazioni ', padding=8)
        f_set.pack(fill=tk.X, **p)

        r1 = ttk.Frame(f_set)
        r1.pack(fill=tk.X, pady=2)
        ttk.Label(r1, text='Spessore:').pack(side=tk.LEFT)
        self.var_spessore = tk.IntVar(value=4)
        ttk.Spinbox(r1, from_=1, to=4, textvariable=self.var_spessore, width=4).pack(side=tk.LEFT, padx=6)
        ttk.Label(r1, text='(1-4)').pack(side=tk.LEFT)

        r2 = ttk.Frame(f_set)
        r2.pack(fill=tk.X, pady=2)
        ttk.Label(r2, text='Risoluzione:').pack(side=tk.LEFT)
        self.var_ris = tk.IntVar(value=100)
        tk.Scale(r2, from_=10, to=500, orient=tk.HORIZONTAL, variable=self.var_ris,
                 bg='#1e1e3a', fg='#ddd', troughcolor='#2a2a4a', highlightthickness=0,
                 length=200).pack(side=tk.LEFT, padx=6, fill=tk.X, expand=True)
        self.lbl_ris_val = ttk.Label(r2, text='100')
        self.lbl_ris_val.pack(side=tk.LEFT, padx=2)
        self.var_ris.trace_add('write', lambda *a: (
            self.lbl_ris_val.config(text=str(self.var_ris.get())),
            self._aggiorna_preview()
        ))

        r_fit = ttk.Frame(f_set)
        r_fit.pack(fill=tk.X, pady=2)
        ttk.Label(r_fit, text='Adatta:').pack(side=tk.LEFT)
        self.var_fit = tk.StringVar(value='contain')
        ttk.Radiobutton(r_fit, text='Centrato (proporzioni)', variable=self.var_fit,
                        value='contain', command=self._aggiorna_preview).pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(r_fit, text='Esteso (tutta l\'area)', variable=self.var_fit,
                        value='stretch', command=self._aggiorna_preview).pack(side=tk.LEFT, padx=4)

        r3 = ttk.Frame(f_set)
        r3.pack(fill=tk.X, pady=2)
        ttk.Label(r3, text='Ritardo (ms):').pack(side=tk.LEFT)
        self.var_ritardo = tk.IntVar(value=0)
        ttk.Spinbox(r3, from_=0, to=100, textvariable=self.var_ritardo, width=5).pack(side=tk.LEFT, padx=6)

        r4 = ttk.Frame(f_set)
        r4.pack(fill=tk.X, pady=2)
        ttk.Label(r4, text='Countdown (sec):').pack(side=tk.LEFT)
        self.var_cd = tk.IntVar(value=3)
        ttk.Spinbox(r4, from_=0, to=10, textvariable=self.var_cd, width=5).pack(side=tk.LEFT, padx=6)

        ttk.Button(f_set, text='Aggiorna anteprima', command=self._aggiorna_preview).pack(fill=tk.X, pady=4)

        # --- Azioni ---
        f_act = ttk.Frame(self.root)
        f_act.pack(fill=tk.X, padx=10, pady=(8, 4))

        self.btn_disegna = ttk.Button(f_act, text='DISEGNA', command=self._avvia_disegno)
        self.btn_disegna.pack(fill=tk.X, ipady=8)

        self.btn_annulla = ttk.Button(f_act, text='ANNULLA (Esc)',
                                       command=self._annulla, state=tk.DISABLED)
        self.btn_annulla.pack(fill=tk.X, ipady=4, pady=4)

        self.barra = ttk.Progressbar(self.root, mode='determinate')
        self.barra.pack(fill=tk.X, padx=10, pady=4)
        self.lbl_stato = ttk.Label(self.root, text='Pronto', foreground='#777')
        self.lbl_stato.pack()

        self.root.bind('<Escape>', lambda e: self._annulla())

    def _aggiorna_stato(self):
        if self._calibrato():
            self.lbl_cal.config(text='Calibrato', foreground='#2ecc71')
        else:
            self.lbl_cal.config(text='Non calibrato', foreground='#e74c3c')

        if 'area_disegno_tl' in self.config and 'area_disegno_br' in self.config:
            tl, br = self.config['area_disegno_tl'], self.config['area_disegno_br']
            self.lbl_area.config(text=f'Area: {br[0]-tl[0]}x{br[1]-tl[1]} px')

        cc = sum(1 for n in NOMI_COLORI if n in self.config)
        self.lbl_colori.config(text=f'Colori: {cc}/8')
        self._aggiorna_preview()

    def _compute_dims(self):
        """Returns (img_w, img_h, offset_x, offset_y) based on current settings."""
        spessore = self.var_spessore.get()
        if self._calibrato():
            tl = self.config['area_disegno_tl']
            br = self.config['area_disegno_br']
            area_w, area_h = br[0] - tl[0], br[1] - tl[1]
            max_w = max(1, area_w // spessore)
            max_h = max(1, area_h // spessore)
        else:
            max_w = self.var_ris.get()
            max_h = 99999

        fit = self.var_fit.get()
        if fit == 'stretch':
            img_w, img_h = max_w, max_h
            off_x, off_y = 0, 0
        else:
            w = min(self.var_ris.get(), max_w)
            h = max(1, int(self.immagine.height * w / self.immagine.width))
            if h > max_h:
                h = max_h
                w = max(1, int(h * self.immagine.width / self.immagine.height))
            img_w, img_h = w, h
            off_x = (max_w - img_w) // 2
            off_y = (max_h - img_h) // 2

        return img_w, img_h, off_x, off_y

    def _aggiorna_preview(self):
        if self.immagine is None:
            self.lbl_preview_img.config(image='')
            self._preview_tk = None
            return
        try:
            w, h, off_x, off_y = self._compute_dims()
            img = self.immagine.resize((w, h), Image.LANCZOS)

            prev = Image.new('RGB', (w, h))
            px_in = img.load()
            px_out = prev.load()
            for y in range(h):
                for x in range(w):
                    px_out[x, y] = COLORI[colore_piu_vicino(px_in[x, y])]

            scala = min(250 / w, 150 / h)
            dw, dh = max(1, int(w * scala)), max(1, int(h * scala))
            prev = prev.resize((dw, dh), Image.NEAREST)

            self._preview_tk = ImageTk.PhotoImage(prev)
            self.lbl_preview_img.config(image=self._preview_tk, text='',
                                         width=dw, height=dh)
            self.lbl_preview.config(text=f'Output: {w}x{h} pixel')
        except Exception as e:
            self.lbl_preview.config(text=f'Errore anteprima: {e}')

    def _carica_immagine(self):
        path = filedialog.askopenfilename(
            filetypes=[('Immagini', '*.png *.jpg *.jpeg'), ('Tutti i file', '*.*')]
        )
        if not path:
            return
        try:
            img = Image.open(path)
            if img.mode == 'RGBA':
                sfondo = Image.new('RGB', img.size, (255, 255, 255))
                sfondo.paste(img, mask=img.split()[3])
                img = sfondo
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            self.immagine = img
            self.lbl_img.config(text=os.path.basename(path))
            self._aggiorna_preview()
        except Exception as e:
            messagebox.showerror('Errore', f'Impossibile caricare l\'immagine:\n{e}')

    def _apri_calibrazione(self):
        PopupCalibrazione(self.root, self._fine_calibrazione, self.config)

    def _fine_calibrazione(self, punti):
        self.config.update(punti)
        self._salva_config()
        self._aggiorna_stato()

    def _avvia_disegno(self):
        if self.immagine is None:
            messagebox.showwarning('Nessuna immagine', 'Carica prima un\'immagine.')
            return
        if not self._calibrato():
            messagebox.showwarning('Non calibrato', 'Esegui prima la calibrazione.')
            return

        self._disegnando = True
        self.btn_disegna.config(state=tk.DISABLED)
        self.btn_annulla.config(state=tk.NORMAL)
        self.barra['value'] = 0
        self.lbl_stato.config(text='Preparazione...')

        threading.Thread(target=self._thread_disegno, daemon=True).start()

    def _annulla(self):
        if self._disegnando:
            self._disegnando = False
            self.lbl_stato.config(text='Annullato')
            self.btn_disegna.config(state=tk.NORMAL)
            self.btn_annulla.config(state=tk.DISABLED)

    def _thread_disegno(self):
        try:
            tl = self.config['area_disegno_tl']
            spessore = self.var_spessore.get()
            ritardo = self.var_ritardo.get() / 1000.0
            tasto_spessore = f'spessore_{spessore}'
            countdown = self.var_cd.get()
            ox, oy = tl[0], tl[1]
            lines_per_row = max(1, spessore // 2)

            img_w, img_h, off_x, off_y = self._compute_dims()
            ox += off_x * spessore
            oy += off_y * spessore

            img = self.immagine.resize((img_w, img_h), Image.LANCZOS)
            pixels = img.load()

            grid = [[colore_piu_vicino(pixels[x, y]) for x in range(img_w)] for y in range(img_h)]
            flat = [p for row in grid for p in row]
            colori_in_uso = sorted(set(flat), key=lambda c: flat.count(c), reverse=True)
            totale = img_w * img_h

            self.root.after(0, lambda: self.barra.configure(maximum=totale))

            if countdown > 0:
                for i in range(countdown, 0, -1):
                    if not self._disegnando:
                        return
                    self.root.after(0, lambda v=i: self.lbl_stato.config(
                        text=f'Passa alla finestra di gioco! {v}...'))
                    time.sleep(1)

            self.root.after(0, lambda: self.lbl_stato.config(text='Disegno in corso...'))
            disegnati = 0

            if tasto_spessore in self.config:
                bx, by = self.config[tasto_spessore]
                pyautogui.click(bx, by)
                time.sleep(0.05)

            for nome_colore in colori_in_uso:
                if not self._disegnando:
                    break

                if nome_colore in self.config:
                    cx, cy = self.config[nome_colore]
                    pyautogui.click(cx, cy)
                    time.sleep(0.03)

                for y in range(img_h):
                    if not self._disegnando:
                        break
                    x = 0
                    while x < img_w:
                        if not self._disegnando:
                            break
                        if grid[y][x] != nome_colore:
                            x += 1
                            continue
                        seg_start = x
                        while x < img_w and grid[y][x] == nome_colore:
                            x += 1
                        seg_end = x

                        sx = ox + seg_start * spessore
                        sy = oy + y * spessore
                        seg_w = (seg_end - seg_start) * spessore

                        durata = max(0.02, seg_w * 0.001)
                        for ty in range(lines_per_row):
                            if not self._disegnando:
                                break
                            pyautogui.moveTo(sx, sy + ty * spessore // lines_per_row)
                            pyautogui.drag(seg_w, 0, duration=durata, button='left')

                        disegnati += (seg_end - seg_start)
                        if ritardo:
                            time.sleep(ritardo)

                        if disegnati % 50 == 0:
                            d = disegnati
                            self.root.after(0, lambda v=d: self._aggiorna_progresso(v))

                time.sleep(0.02)

            self.root.after(0, lambda: self._fine_disegno(disegnati))

        except pyautogui.FailSafeException:
            self.root.after(0, lambda: self._fine_disegno(errore='Failsafe: mouse spostato in un angolo.'))
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.root.after(0, lambda: self._fine_disegno(errore=str(e)))

    def _aggiorna_progresso(self, valore):
        self.barra['value'] = valore
        self.lbl_stato.config(text=f'Disegnando... {valore} pixel')

    def _fine_disegno(self, totale=0, errore=None):
        self._disegnando = False
        self.btn_disegna.config(state=tk.NORMAL)
        self.btn_annulla.config(state=tk.DISABLED)
        if errore:
            self.barra['value'] = 0
            self.lbl_stato.config(text='Errore')
            messagebox.showerror('Errore disegno', errore)
        else:
            self.barra['value'] = totale
            self.lbl_stato.config(text=f'Completato! {totale} pixel disegnati.')

    def avvia(self):
        self.root.mainloop()


if __name__ == '__main__':
    GraffitiDrawer().avvia()
