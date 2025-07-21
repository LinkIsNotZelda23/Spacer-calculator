"""
B&K Spacer Calculator - 2025 Ultimate Optimized Edition
Author: Hayden Charles Cantwell (+ ChatGPT, 2025)
Full features: inventory, optimized calculation, live preview, games, print/export, tooltips, robust error handling.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from collections import Counter
from itertools import combinations_with_replacement
from PIL import Image, ImageTk, ImageDraw
import json, os, random, platform, logging

# ================== CONFIG & CONSTANTS ==================

ICON_PATH = "spacer_icon.png"
ABOUT_ICON_PATH = "knife_icon.png"
BG_IMAGE_PATH = "B&K slitter backround.png"
JOBS_DIR = "jobs"
INVENTORY_FILE = "inventory.json"
LAST_JOB_FILE = "last_job.json"
SNAKE_HIGHSCORE_FILE = "snake_highscore.txt"
PASSWORD = "ArmourAlloys2025"

METAL_DEFAULT = {
    3: 7, 2: 11, 1: 20, 0.750: 18, 0.500: 29, 0.375: 27, 0.250: 29, 0.129: 21,
    0.125: 62, 0.065: 16, 0.063: 16, 0.062: 29, 0.0315: 26, 0.025: 20
}
PLASTIC_DEFAULT = {
    0.030: 50, 0.020: 50, 0.015: 50, 0.013: 50, 0.010: 50, 0.0075: 50, 0.005: 50,
    0.004: 50, 0.003: 50, 0.002: 50
}

if not os.path.exists(JOBS_DIR):
    os.makedirs(JOBS_DIR)

logging.basicConfig(filename="spacer_calc.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ================== UTILITY FUNCTIONS ==================

def rgb(hexcode):
    """Convert hex to RGB tuple."""
    hexcode = hexcode.lstrip("#")
    return tuple(int(hexcode[i:i+2], 16) for i in (0, 2, 4))

def create_composite_bg(bg_path, w, h):
    try:
        base = Image.open(bg_path).convert("RGBA").resize((w, h), Image.LANCZOS)
    except Exception:
        base = Image.new("RGBA", (w, h), (41, 22, 80, 255))
    gradient = Image.new("RGBA", (w, h), color=0)
    draw = ImageDraw.Draw(gradient)
    for y in range(h):
        frac = y / h
        color = (
            int(41 + frac * (146 - 41)),
            int(22 + frac * (91 - 22)),
            int(80 + frac * (255 - 80)),
            int(120)
        )
        draw.line([(0, y), (w, y)], fill=color)
    final = Image.alpha_composite(base, gradient)
    return final

# ================== TOOLTIP ==================

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        widget.bind("<Enter>", self.enter)
        widget.bind("<Leave>", self.leave)
        widget.bind("<ButtonPress>", self.leave)
    def enter(self, event=None):
        self.schedule()
    def leave(self, event=None):
        self.unschedule()
        self.hidetip()
    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(300, self.showtip)
    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)
    def showtip(self, event=None):
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx() + self.widget.winfo_width() + 10
        y = self.widget.winfo_rooty() + 10
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw, text=self.text, justify=tk.LEFT,
            background="#ffffe0", relief=tk.SOLID, borderwidth=1,
            font=("Arial", 10), wraplength=300
        )
        label.pack(ipadx=1)
    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

# ================== DATA CLASSES ==================

class SpacerInventory:
    """Class for managing metal/plastic inventory and persistence."""
    def __init__(self):
        self.metal = Counter(METAL_DEFAULT)
        self.plastic = Counter(PLASTIC_DEFAULT)
        self.load()

    def load(self):
        try:
            with open(INVENTORY_FILE, "r") as f:
                data = json.load(f)
            self.metal = Counter({float(k): v for k, v in data["metal"].items()})
            self.plastic = Counter({float(k): v for k, v in data["plastic"].items()})
            logging.info("Inventory loaded.")
        except Exception:
            self.save()

    def save(self):
        data = {"metal": dict(self.metal), "plastic": dict(self.plastic)}
        with open(INVENTORY_FILE, "w") as f:
            json.dump(data, f)
        logging.info("Inventory saved.")

    def reset(self):
        self.metal = Counter(METAL_DEFAULT)
        self.plastic = Counter(PLASTIC_DEFAULT)
        self.save()

    def snapshot(self):
        return {
            "metal": dict(self.metal),
            "plastic": dict(self.plastic)
        }

    def use_spacers(self, combo):
        inv = self.metal + self.plastic
        for sz in combo:
            if self.metal.get(sz, 0) > 0:
                self.metal[sz] -= 1
            elif self.plastic.get(sz, 0) > 0:
                self.plastic[sz] -= 1
            else:
                raise ValueError(f"No inventory left for spacer {sz:.4f}")
        self.save()

    def check_availability(self, combo):
        inv = self.metal + self.plastic
        test = Counter(combo)
        for sz in test:
            if test[sz] > inv[sz]:
                return False
        return True

# ================== MAIN APPLICATION ==================

class SpacerCalculatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("B&K Spacer Calculator (2025 Ultimate Optimized)")
        self.state('zoomed')
        try:
            self.iconphoto(True, tk.PhotoImage(file=ICON_PATH))
        except Exception:
            pass

        # State
        self.inventory = SpacerInventory()
        self.job = {}
        self.cut_stacks = []
        self.top_lines = []
        self.bottom_lines = []
        self.used_spacers = Counter()
        self.settings = {}
        self.canvas_scale = [1.0]
        self.canvas_pan = [0, 0]

        # UI
        self._setup_menu()
        self._setup_frames()
        self._setup_form()
        self._setup_summary()
        self._setup_preview_tab()

        # Try load last job
        self.try_load_last_job()
        self.after(150, self._resize_bg)

    # ========== MENUS ==========

    def _setup_menu(self):
        menubar = tk.Menu(self)
        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="About", command=self._show_about)
        helpmenu.add_command(label="Play Spacer Snake", command=self._play_snake)
        helpmenu.add_command(label="Play Spacer Stack Tetris", command=self._play_tetris)
        menubar.add_cascade(label="Help", menu=helpmenu)
        self.config(menu=menubar)

    # ========== FRAMES ==========

    def _setup_frames(self):
        self.notebook = ttk.Notebook(self)
        self.frm_main = tk.Frame(self.notebook, bg="white")
        self.frm_preview = tk.Frame(self.notebook, bg="white")
        self.notebook.add(self.frm_main, text="Calculator")
        self.notebook.add(self.frm_preview, text="Knife Layout Preview")
        self.notebook.pack(fill="both", expand=True)
        try:
            self.bg_img = Image.open(BG_IMAGE_PATH)
            self.frm_main.bind("<Configure>", lambda e: self._resize_bg())
        except Exception:
            self.bg_img = None

    def _resize_bg(self):
        try:
            width = self.frm_main.winfo_width()
            height = self.frm_main.winfo_height()
            if width < 2 or height < 2 or self.bg_img is None:
                return
            glass_bg = create_composite_bg(BG_IMAGE_PATH, width, height)
            self.frm_main.bg_photo = ImageTk.PhotoImage(glass_bg)
            if hasattr(self.frm_main, 'bg_label'):
                self.frm_main.bg_label.config(image=self.frm_main.bg_photo)
            else:
                self.frm_main.bg_label = tk.Label(self.frm_main, image=self.frm_main.bg_photo)
                self.frm_main.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
                self.frm_main.bg_label.lower()
        except Exception as e:
            logging.error("BG error: %s", e)

    # ========== FORM ==========

    def _setup_form(self):
        labels = [
            "Customer Name:", "Cut Sizes (e.g. 1x3,3x2):", "Thickness (inches):",
            "Clearance %:", "Female Knife Thickness:", "Male Knife Thickness:",
            "Master Coil Width:", "Master Coil Weight (lbs):",
            "Width Tolerance (+):", "Width Tolerance (-):"
        ]
        help_texts = [
            "The customer or job name for reference.",
            "Sizes and quantities for each strip (format: width x count, comma-separated). Example: 1.125x3,0.745x2",
            "Material thickness in inches (e.g., 0.015).",
            "Percent clearance between knives (typically 15–17% depending on material).",
            "Thickness of the female knife in inches.",
            "Thickness of the male knife in inches.",
            "Total incoming coil width before slitting.",
            "Weight of the coil. Used for per-strip weight and scrap estimates.",
            "Allowable extra width on each cut (+).",
            "Allowable reduction on each cut (–)."
        ]
        self.entries = {}
        frame = tk.Frame(self.frm_main, bg="white")
        frame.place(relx=0.5, rely=0.44, anchor="center")
        for i, lbl in enumerate(labels):
            tk.Label(frame, text=lbl).grid(row=i, column=1, sticky="e", padx=5, pady=2)
            e = tk.Entry(frame)
            e.grid(row=i, column=2)
            self.entries[lbl] = e
            help_btn = tk.Label(frame, text="?", fg="#1976d2", bg="white", font=("Arial", 10, "bold"), cursor="question_arrow")
            help_btn.grid(row=i, column=3, padx=(2, 7), sticky="w")
            ToolTip(help_btn, help_texts[i])

        # Suggested clearance
        self.label_suggested = tk.Label(frame, text="Suggested: ---", bg="white", fg="blue")
        self.label_suggested.grid(row=3, column=4, sticky="w", padx=5)
        self.entries["Thickness (inches):"].bind("<KeyRelease>", self._update_suggested_clearance)
        self.entries["Clearance %:"].bind("<KeyRelease>", self._update_suggested_clearance)

        # Material menu
        self.material_var = tk.StringVar(value="Aluminum")
        tk.Label(frame, text="Material Type:").grid(row=11, column=1, sticky="e", padx=5)
        material_menu = tk.OptionMenu(frame, self.material_var, "Aluminum", "Galvanized", "Stainless")
        material_menu.grid(row=11, column=2)
        ToolTip(material_menu, "Material being slit. Affects recommended clearance and (if provided) the density used for weight calculation.")
        # Deflection
        self.auto_deflect_var = tk.IntVar(value=1)
        auto_deflect_box = tk.Checkbutton(frame, text="Enable Auto-Deflection", variable=self.auto_deflect_var)
        self.minimize_shims_var = tk.IntVar(value=1)
        minimize_shims_box = tk.Checkbutton(frame, text="Minimize Plastic Shims", variable=self.minimize_shims_var)
        minimize_shims_box.grid(row=13, column=1, sticky="w", padx=5)
        ToolTip(minimize_shims_box, "If enabled, only use plastic shims if no metal combo fits.")

        self.smart_balance_var = tk.IntVar(value=1)
        smart_balance_box = tk.Checkbutton(frame, text="Smart Inventory Balancing", variable=self.smart_balance_var)
        smart_balance_box.grid(row=13, column=3, sticky="w", padx=5)
        ToolTip(smart_balance_box, "If enabled, rotates combos to protect rare spacers and balance usage.")

        auto_deflect_box.grid(row=13, column=2, sticky="w")
        ToolTip(auto_deflect_box, "If enabled, the calculator will auto-apply an estimated deflection offset to spacer stacks.")

        # Button row
        row_btn = 15
        tk.Button(frame, text="Calculate", command=self.calculate_spacers).grid(row=row_btn, column=0, padx=6, pady=8)
        tk.Button(frame, text="Edit Inventory", command=self._open_inventory_editor).grid(row=row_btn, column=2, padx=6, pady=8)
        tk.Button(frame, text="Save Job", command=self._save_job_dialog).grid(row=row_btn+1, column=0, padx=6, pady=8)
        tk.Button(frame, text="Load Job", command=self._load_job_dialog).grid(row=row_btn+1, column=1, padx=6, pady=8)
        tk.Button(frame, text="Reset Job", command=self._reset_job_fields).grid(row=row_btn+1, column=2, padx=6, pady=8)

    def _get_field(self, lbl):
        return self.entries[lbl].get()

    def _set_field(self, lbl, val):
        self.entries[lbl].delete(0, tk.END)
        self.entries[lbl].insert(0, val)

    def _update_suggested_clearance(self, *args):
        try:
            thickness = float(self._get_field("Thickness (inches):"))
            percent = float(self._get_field("Clearance %:"))
            suggestion = thickness * (percent / 100)
            self.label_suggested.config(text=f"Suggested: {suggestion:.4f}")
        except:
            self.label_suggested.config(text="Suggested: ---")

    # ========== SUMMARY ==========

    def _setup_summary(self):
        self.spacer_frame = tk.Frame(self.frm_main, bg="white")
        self.spacer_frame.place(relx=0.5, rely=1.0, anchor="s", y=-10)
        tk.Label(self.spacer_frame, text="Spacer Usage Summary:").pack()
        self.spacer_text = tk.Text(self.spacer_frame, height=6, width=60)
        self.spacer_text.pack()
        self.weight_scrap_label = tk.Label(self.spacer_frame, text="", font=("Arial", 10, "bold"), bg="white")
        self.weight_scrap_label.pack(pady=(4,0))

    def _update_spacer_summary(self):
        summary = ""
        for size in sorted(self.used_spacers):
            count = self.used_spacers[size]
            mat = "Plastic" if size in self.inventory.plastic else "Metal"
            summary += f"{size:.4f}\" ({mat}): {count}\n"
        self.spacer_text.delete("1.0", tk.END)
        self.spacer_text.insert(tk.END, summary)

    # ========== PREVIEW TAB ==========

    def _setup_preview_tab(self):
        self.preview_canvas = tk.Canvas(self.frm_preview, bg="white", width=900, height=440, highlightthickness=1, highlightbackground="#a0a0a0")
        h_scroll = tk.Scrollbar(self.frm_preview, orient="horizontal", command=self.preview_canvas.xview)
        v_scroll = tk.Scrollbar(self.frm_preview, orient="vertical", command=self.preview_canvas.yview)
        self.preview_canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        self.preview_canvas.pack(fill="both", expand=True, padx=10, pady=10, side="left")
        h_scroll.pack(side="bottom", fill="x")
        v_scroll.pack(side="right", fill="y")
        self.preview_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.preview_canvas.bind("<ButtonPress-2>", self._on_canvas_pan_start)
        self.preview_canvas.bind("<B2-Motion>", self._on_canvas_pan_move)
        self.preview_canvas.bind("<ButtonPress-3>", self._on_canvas_pan_start)
        self.preview_canvas.bind("<B3-Motion>", self._on_canvas_pan_move)
        btn_frame = tk.Frame(self.frm_preview, bg="white")
        btn_frame.pack(pady=(0, 10))
        tk.Button(btn_frame, text="Save Preview", command=self._save_preview_image).pack(side="left", padx=8)
        tk.Button(btn_frame, text="Print Preview", command=self._print_preview_image).pack(side="left", padx=8)

    def _on_mousewheel(self, event):
        if event.state & 0x0004:  # Ctrl held for zoom
            factor = 1.1 if event.delta > 0 else 0.9
            self.canvas_scale[0] = max(0.3, min(self.canvas_scale[0]*factor, 2.5))
            self._draw_knife_layout(self.top_lines, self.bottom_lines, self.canvas_scale[0], self.canvas_pan[0], self.canvas_pan[1])
        else:
            self.preview_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def _on_canvas_pan_start(self, event):
        self.preview_canvas.scan_mark(event.x, event.y)
    def _on_canvas_pan_move(self, event):
        self.preview_canvas.scan_dragto(event.x, event.y, gain=1)

    # ===== INVENTORY EDITOR =====
    def _open_inventory_editor(self):
        if not self._ask_inventory_password():
            messagebox.showerror("Access Denied", "Incorrect password.")
            return
        inv_win = tk.Toplevel(self)
        inv_win.title("Edit Inventory")
        inv_win.grab_set()
        tk.Label(inv_win, text="Metal Spacers", font=('Arial', 11, 'bold')).grid(row=0, column=0, pady=3, padx=8)
        tk.Label(inv_win, text="Plastic Shims", font=('Arial', 11, 'bold')).grid(row=0, column=2, pady=3, padx=8)
        metal_vars, plastic_vars = {}, {}
        for i, sz in enumerate(sorted(self.inventory.metal)):
            tk.Label(inv_win, text=f"{sz:.4f}\"", width=7).grid(row=i+1, column=0)
            var = tk.IntVar(value=self.inventory.metal[sz])
            metal_vars[sz] = var
            tk.Entry(inv_win, textvariable=var, width=7).grid(row=i+1, column=1)
        for i, sz in enumerate(sorted(self.inventory.plastic)):
            tk.Label(inv_win, text=f"{sz:.4f}\"", width=7).grid(row=i+1, column=2)
            var = tk.IntVar(value=self.inventory.plastic[sz])
            plastic_vars[sz] = var
            tk.Entry(inv_win, textvariable=var, width=7).grid(row=i+1, column=3)
        def save_inventory():
            for sz, var in metal_vars.items():
                self.inventory.metal[sz] = var.get()
            for sz, var in plastic_vars.items():
                self.inventory.plastic[sz] = var.get()
            self.inventory.save()
            inv_win.destroy()
            self._update_spacer_summary()
        btn_frame = tk.Frame(inv_win)
        btn_frame.grid(row=max(len(metal_vars), len(plastic_vars))+2, column=0, columnspan=4, pady=8)
        tk.Button(btn_frame, text="Save", command=save_inventory, width=10).pack(side="left", padx=8)
        tk.Button(btn_frame, text="Cancel", command=inv_win.destroy, width=10).pack(side="left", padx=8)

    def _ask_inventory_password(self):
        pwd = simpledialog.askstring("Password Required", "Enter password to edit inventory:", show='*', parent=self)
        return pwd == PASSWORD

    # ===== JOB SAVE/LOAD/RESET =====
    def _save_job_dialog(self):
        job_data = self._get_job_dict()
        customer = job_data.get("customer", "").replace(" ", "_") or "job"
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("Job Files", "*.json")],
            initialdir=JOBS_DIR,
            initialfile=f"{customer}.json"
        )
        if filename:
            with open(filename, "w") as f:
                json.dump(job_data, f, indent=2)
            with open(LAST_JOB_FILE, "w") as f:
                json.dump({"last_job": filename}, f)
            messagebox.showinfo("Job Saved", f"Job saved to: {filename}")

    def _load_job_dialog(self):
        filename = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("Job Files", "*.json")],
            initialdir=JOBS_DIR
        )
        if filename:
            with open(filename, "r") as f:
                data = json.load(f)
            self._set_job_fields_from_dict(data)
            with open(LAST_JOB_FILE, "w") as f:
                json.dump({"last_job": filename}, f)
            messagebox.showinfo("Job Loaded", f"Job loaded from: {filename}")

    def try_load_last_job(self):
        try:
            if os.path.exists(LAST_JOB_FILE):
                with open(LAST_JOB_FILE, "r") as f:
                    data = json.load(f)
                last_job = data.get("last_job")
                if last_job and os.path.exists(last_job):
                    with open(last_job, "r") as f2:
                        job_data = json.load(f2)
                    self._set_job_fields_from_dict(job_data)
        except Exception:
            pass

    def _reset_job_fields(self):
        for e in self.entries.values():
            e.delete(0, tk.END)
        self.material_var.set("Aluminum")
        self.auto_deflect_var.set(1)
        self._update_suggested_clearance()
        self._update_spacer_summary()

    def _get_job_dict(self):
        return {
            "customer": self._get_field("Customer Name:"),
            "cut": self._get_field("Cut Sizes (e.g. 1x3,3x2):"),
            "thickness": self._get_field("Thickness (inches):"),
            "clearance": self._get_field("Clearance %:"),
            "knife_female": self._get_field("Female Knife Thickness:"),
            "knife_male": self._get_field("Male Knife Thickness:"),
            "coil_width": self._get_field("Master Coil Width:"),
            "coil_weight": self._get_field("Master Coil Weight (lbs):"),
            "tol_plus": self._get_field("Width Tolerance (+):"),
            "tol_minus": self._get_field("Width Tolerance (-):"),
            "material": self.material_var.get(),
            "auto_deflect": self.auto_deflect_var.get()
        }

    def _set_job_fields_from_dict(self, d):
        self._set_field("Customer Name:", d.get("customer", ""))
        self._set_field("Cut Sizes (e.g. 1x3,3x2):", d.get("cut", ""))
        self._set_field("Thickness (inches):", d.get("thickness", ""))
        self._set_field("Clearance %:", d.get("clearance", ""))
        self._set_field("Female Knife Thickness:", d.get("knife_female", ""))
        self._set_field("Male Knife Thickness:", d.get("knife_male", ""))
        self._set_field("Master Coil Width:", d.get("coil_width", ""))
        self._set_field("Master Coil Weight (lbs):", d.get("coil_weight", ""))
        self._set_field("Width Tolerance (+):", d.get("tol_plus", ""))
        self._set_field("Width Tolerance (-):", d.get("tol_minus", ""))
        self.material_var.set(d.get("material", "Aluminum"))
        self.auto_deflect_var.set(d.get("auto_deflect", 1))
        self._update_suggested_clearance()
        self._update_spacer_summary()

    # ====== OPTIMIZED CALCULATION ENGINE ======
    def calculate_spacers(self):
        try:
            self.top_lines.clear()
            self.bottom_lines.clear()
            self.used_spacers.clear()
            cuts, total_cut_width = [], 0
            for entry in self._get_field("Cut Sizes (e.g. 1x3,3x2):").split(','):
                parts = entry.strip().split('x')
                size = float(parts[0])
                count = int(parts[1]) if len(parts) == 2 else 1
                cuts.extend([size] * count)
                total_cut_width += size * count
            thickness = float(self._get_field("Thickness (inches):"))
            clearance = thickness * (float(self._get_field("Clearance %:")) / 100)
            kf = float(self._get_field("Female Knife Thickness:"))
            km = float(self._get_field("Male Knife Thickness:"))
            coil_width = float(self._get_field("Master Coil Width:") or 0)
            coil_weight = float(self._get_field("Master Coil Weight (lbs):") or 0)
            tol_plus = float(self._get_field("Width Tolerance (+):") or 0.005)
            tol_minus = float(self._get_field("Width Tolerance (-):") or 0.005)
            deflect_offset = 0.0
            if self.auto_deflect_var.get():
                deflect_offset = self.get_deflection_offset(self.material_var.get(), thickness)

            job_metal = self.inventory.metal.copy()
            job_plastic = self.inventory.plastic.copy()

            # Shoulder stack (clearance + kf)
            shoulder_clearance = clearance + kf
            s_combo, s_metal = self.find_spacer_combo(
                shoulder_clearance, 0.001, 0.001, job_metal, job_plastic, prefer_metal=True, max_stack=8)
            if not s_combo:
                raise ValueError("No spacers found for shoulder")
            for sz in s_combo:
                if sz in job_metal:
                    job_metal[sz] -= 1
                elif sz in job_plastic:
                    job_plastic[sz] -= 1
            self.used_spacers.update(s_combo)
            self.bottom_lines.append(f"Shoulder ({shoulder_clearance:.3f}): {', '.join(map(str, s_combo))}")

            # Each cut
            for i, cut in enumerate(cuts, 1):
                female_on_top = (i % 2 == 1)
                female_combo, is_metal = self.find_spacer_combo(
                    cut, tol_plus, tol_minus, job_metal, job_plastic, prefer_metal=True, max_stack=8
                )
                if not female_combo:
                    raise ValueError(f"No valid spacer combo found for cut {cut} with current inventory.")
                for sz in female_combo:
                    if sz in job_metal and job_metal[sz] > 0:
                        job_metal[sz] -= 1
                    elif sz in job_plastic and job_plastic[sz] > 0:
                        job_plastic[sz] -= 1
                self.used_spacers.update(female_combo)
                female_sum = sum(female_combo) + deflect_offset
                male_target = female_sum - (kf + km + 2 * clearance)
                male_combo, _ = self.find_spacer_combo(
                    male_target, 0.001, 0.001, job_metal, job_plastic, prefer_metal=True, max_stack=8
                )
                if not male_combo:
                    raise ValueError(
                        f"No valid male spacer combo found for cut {cut} after assigning female stack.\n"
                        f"Try increasing shim inventory or adjust tolerances."
                    )
                for sz in male_combo:
                    if sz in job_metal and job_metal[sz] > 0:
                        job_metal[sz] -= 1
                    elif sz in job_plastic and job_plastic[sz] > 0:
                        job_plastic[sz] -= 1
                self.used_spacers.update(male_combo)
                if female_on_top:
                    self.top_lines.append(f"Cut {i} Female ({female_sum:.3f}): {', '.join(map(str, female_combo))}")
                    self.bottom_lines.append(f"Cut {i} Male ({male_target:.3f}): {', '.join(map(str, male_combo))}")
                else:
                    self.top_lines.append(f"Cut {i} Male ({male_target:.3f}): {', '.join(map(str, male_combo))}")
                    self.bottom_lines.append(f"Cut {i} Female ({female_sum:.3f}): {', '.join(map(str, female_combo))}")
            scrap = coil_width - total_cut_width if coil_width else 0
            self.settings.clear()
            self.settings.update({
                "thickness": thickness, "clearance": float(self._get_field("Clearance %:")),
                "knife_female": kf, "knife_male": km,
                "coil_width": coil_width, "coil_weight": coil_weight,
                "scrap": round(scrap, 3)
            })
            self._update_spacer_summary()
            self._draw_knife_layout(self.top_lines, self.bottom_lines, self.canvas_scale[0], self.canvas_pan[0], self.canvas_pan[1])
            messagebox.showinfo("Done", "Calculation complete. Export setup or view layout preview.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def get_deflection_offset(self, material, thickness):
        try:
            thickness = float(thickness)
            if material == "Aluminum":
                return 0.0005
            elif material in ("Galvanized", "Stainless"):
                return 0.0015 if thickness > 0.030 else 0.0010
        except:
            return 0.0
        return 0.0

    def find_spacer_combo(self, target, tol_plus, tol_minus, metal_inv, plastic_inv, prefer_metal=True, max_stack=8):
        minimize_shims = getattr(self, "minimize_shims_var", tk.IntVar(value=1)).get()
        smart_balance = getattr(self, "smart_balance_var", tk.IntVar(value=1)).get()
        keys_metal = sorted([k for k, v in metal_inv.items() if v > 0], reverse=True)
        keys_all = sorted([k for k, v in (metal_inv + plastic_inv).items() if v > 0], reverse=True)
        if prefer_metal:
            for r in range(1, max_stack+1):
                for combo in combinations_with_replacement(keys_metal, r):
                    total = round(sum(combo), 4)
                    if (target - tol_minus) <= total <= (target + tol_plus):
                        tmp = Counter(combo)
                        if all(tmp[k] <= metal_inv[k] for k in tmp):
                            return list(combo), True
        for r in range(1, max_stack+1):
            for combo in combinations_with_replacement(keys_all, r):
                total = round(sum(combo), 4)
                if (target - tol_minus) <= total <= (target + tol_plus):
                    tmp = Counter(combo)
                    if all(tmp[k] <= (metal_inv + plastic_inv)[k] for k in tmp):
                        return list(combo), False
        return None, None

    # === KNIFE PREVIEW DRAWING (same as before, full-color stacks, scales/zooms, etc.) ===
    def _draw_knife_layout(self, top_lines, bottom_lines, scale=1.0, pan_x=0, pan_y=0):
        self.preview_canvas.delete("all")
        width = int(self.preview_canvas.winfo_width())
        height = int(self.preview_canvas.winfo_height())
        margin = int(40*scale)
        top_space = int(130*scale) + pan_y
        stack_w = int(62*scale)
        stack_h = int(22*scale)
        stack_spacing_x = int(28*scale)
        row_spacing = int(80*scale)
        total_cols = len(bottom_lines)
        n_blocks_per_stack = max(
            [len(self.parse_stack_line_pdf(line)) for line in top_lines + bottom_lines], default=6
        )
        legend_x = width - margin - int(220*scale)
        legend_y = int(18*scale)
        info_x = margin
        info_y = int(18*scale)
        needed_width = margin*2 + total_cols * (stack_w + stack_spacing_x)
        needed_height = top_space + 2*stack_h*n_blocks_per_stack + row_spacing + 60
        self.preview_canvas.config(scrollregion=(0,0,needed_width,needed_height))
        info_lines = [
            f"Customer: {self._get_field('Customer Name:')}",
            f"Material: {self.material_var.get()}",
            f"Suggested Clearance: {self.label_suggested.cget('text').replace('Suggested: ','')}",
            f"Total Scrap: {self.settings.get('scrap','---')}"
        ]
        self.preview_canvas.create_text(
            info_x+pan_x, info_y, anchor="nw", font=("Arial", int(10*scale), "bold"),
            text="\n".join(info_lines)
        )
        leg_box = int(16*scale)
        leg_y = legend_y
        self.preview_canvas.create_text(legend_x, leg_y, text="Legend:", anchor="nw", font=("Arial", int(12*scale), "bold"))
        leg_y += int(18*scale)
        legend = [
            ("Female Knife", "#3a6edc"),
            ("Male Knife", "#d13b2b"),
            ("Metal Spacer", "#b0b0b0"),
            ("Plastic Shim", "#f0e130"),
        ]
        for name, color in legend:
            self.preview_canvas.create_rectangle(legend_x, leg_y, legend_x+leg_box, leg_y+leg_box, fill=color, outline="black")
            self.preview_canvas.create_text(legend_x+leg_box+8, leg_y+leg_box//2, text=name, anchor="w", font=("Arial", int(10*scale)))
            leg_y += leg_box + 6
        self.preview_canvas.create_text(legend_x, leg_y, anchor="nw",
            text='M = Metal, P = Plastic', font=("Arial", int(9*scale), "italic"))
        y_top = top_space
        y_bot = y_top + stack_h * n_blocks_per_stack + row_spacing
        for idx in range(total_cols):
            x = margin + idx * (stack_w + stack_spacing_x) + pan_x
            stack = self.parse_stack_line_pdf(bottom_lines[idx])
            h = 0
            label = "Shoulder" if idx == 0 else f"Cut {idx} (Bot)"
            self.preview_canvas.create_text(x + stack_w//2, y_bot-18, text=label, font=("Arial", int(10*scale), "bold"))
            for block_idx, (lbl, mat) in enumerate(stack):
                color = self.get_tk_color(mat)
                self.preview_canvas.create_rectangle(x, y_bot+h, x+stack_w, y_bot+h+stack_h, fill=color, outline="black")
                self.preview_canvas.create_text(x+stack_w/2, y_bot+h+stack_h/2, text=lbl, font=("Arial", int(9*scale)))
                h += stack_h + 2
            if idx > 0 and (idx-1) < len(top_lines):
                stack = self.parse_stack_line_pdf(top_lines[idx-1])
                h = 0
                label = f"Cut {idx} (Top)"
                self.preview_canvas.create_text(x + stack_w//2, y_top-18, text=label, font=("Arial", int(10*scale), "bold"))
                for block_idx, (lbl, mat) in enumerate(stack):
                    color = self.get_tk_color(mat)
                    self.preview_canvas.create_rectangle(x, y_top+h, x+stack_w, y_top+h+stack_h, fill=color, outline="black")
                    self.preview_canvas.create_text(x+stack_w/2, y_top+h+stack_h/2, text=lbl, font=("Arial", int(9*scale)))
                    h += stack_h + 2

    def parse_stack_line_pdf(self, line):
        out = []
        if ':' not in line: return out
        what, stack = line.split(':', 1)
        if "Female" in what:
            out.append(("FEMALE", "Female Knife"))
        elif "Male" in what:
            out.append(("MALE", "Male Knife"))
        elif "Shoulder" in what:
            pass
        parts = stack.split(',')
        for p in parts:
            val = p.strip()
            try:
                f = float(val)
                mat = "Plastic" if f in self.inventory.plastic else "Metal"
                label = f'{f:.3f}" {"P" if mat == "Plastic" else "M"}'
                out.append((label, mat))
            except:
                pass
        return out
    def get_tk_color(self, mat):
        color_map = {
            "Female Knife": "#3a6edc",
            "Male Knife": "#d13b2b",
            "Metal": "#b0b0b0",
            "Plastic": "#f0e130"
        }
        return color_map.get(mat, "#bbbbbb")

    # === EXPORT/PRINT ===
    
    
    
    
    def _save_preview_image(self):
        from reportlab.lib.pagesizes import landscape, letter
        from reportlab.pdfgen import canvas as pdf_canvas
        from reportlab.lib.units import inch

        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")]
        )
        if not file_path:
            return

        tops = self.top_lines
        bottoms = self.bottom_lines
        PAGE_W, PAGE_H = landscape(letter)
        margin = 0.5 * inch
        stacks_per_page = 4
        stack_width = 6.5 * inch
        stack_height = 0.5 * inch
        spacing_y = 1.8 * inch

        try:
            c = pdf_canvas.Canvas(file_path, pagesize=landscape(letter))
            total = len(bottoms)
            total_pages = (total + stacks_per_page - 1) // stacks_per_page

            for page in range(total_pages):
                c.setFont("Helvetica-Bold", 14)
                c.drawString(margin, PAGE_H - margin, f"Spacer Layout – Page {page + 1} of {total_pages}")
                c.setFont("Helvetica", 10)
                c.drawString(margin, PAGE_H - margin - 20, f"Customer: {self._get_field('Customer Name:')} | Material: {self.material_var.get()} | Suggested Clearance: {self.label_suggested.cget('text').replace('Suggested: ','')}")

                # Legend (top-right)
                legend = [
                    ("Female Knife", (58, 110, 220)),
                    ("Male Knife", (209, 59, 43)),
                    ("Metal Spacer", (176, 176, 176)),
                    ("Plastic Shim", (240, 225, 48)),
                ]
                lx, ly = PAGE_W - margin - 180, PAGE_H - margin - 10
                c.setFont("Helvetica-Bold", 10)
                c.drawString(lx, ly, "Legend:")
                for j, (text, color) in enumerate(legend):
                    r, g, b = [v / 255 for v in color]
                    c.setFillColorRGB(r, g, b)
                    c.rect(lx, ly - (j + 1) * 16, 14, 10, fill=1, stroke=1)
                    c.setFillColorRGB(0, 0, 0)
                    c.setFont("Helvetica", 9)
                    c.drawString(lx + 18, ly - (j + 1) * 16 + 2, text)

                y_start = PAGE_H - margin - 80

                for i in range(stacks_per_page):
                    idx = page * stacks_per_page + i
                    if idx >= total:
                        break

                    y_bottom = y_start - (i * spacing_y)

                    # Draw Top First
                    if idx > 0 and (idx - 1) < len(tops):
                        y_top = y_bottom
                        c.setFont("Helvetica-Bold", 11)
                        c.drawString(margin, y_top, f"Cut {idx} (Top)")
                        self._draw_stack_row(c, margin + 120, y_top - 10, stack_width, stack_height, tops[idx - 1])
                        y_bottom = y_top - stack_height - 20

                    # Bottom Stack
                    label = "Shoulder" if idx == 0 else f"Cut {idx} (Bottom)"
                    c.setFont("Helvetica-Bold", 11)
                    c.drawString(margin, y_bottom, label)
                    self._draw_stack_row(c, margin + 120, y_bottom - 10, stack_width, stack_height, bottoms[idx])

                c.showPage()

            c.save()
            messagebox.showinfo("Saved", f"PDF saved to: {file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save PDF: {e}")


    def _draw_stack_row(self, c, x, y, width, height, line):
        items = self.parse_stack_line_pdf(line)
        n = len(items)
        if n == 0:
            return
        block_w = width / n
        color_map = {
            "Female Knife": (58, 110, 220),
            "Male Knife": (209, 59, 43),
            "Metal": (176,176,176),
            "Plastic": (240, 225, 48)
        }
        for i, (label, mat) in enumerate(items):
            bx = x + i * block_w
            r, g, b = [v / 255 for v in color_map.get(mat, (200, 200, 200))]
            c.setFillColorRGB(r, g, b)
            c.rect(bx, y, block_w - 1.5, height, fill=1, stroke=1)
            c.setFont("Helvetica", 6)
            c.setFillColorRGB(0, 0, 0)
            c.drawCentredString(bx + block_w / 2, y + height / 2 - 3, label)





    
    def _print_preview_image(self):
        import platform
        import subprocess
        import os

        # Get last saved PDF file path (based on save path storage)
        file_path = filedialog.askopenfilename(
            title="Select PDF to Print",
            filetypes=[("PDF Files", "*.pdf")]
        )
        if not file_path:
            return

        try:
            if platform.system() == "Windows":
                os.startfile(file_path, "print")
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["lp", file_path])
            else:  # Linux and others
                subprocess.run(["lp", file_path])
        except Exception as e:
            messagebox.showerror("Print Error", f"Could not print PDF: {e}")

    def _play_snake(self):
        snake_win = tk.Toplevel(self)
        snake_win.title("Spacer Snake! (Easter Egg)")
        snake_win.resizable(False, False)
        cell = 22
        grid_size = 17
        w, h = cell*grid_size, cell*grid_size+32
        canvas = tk.Canvas(snake_win, width=w, height=h, bg="#f8f8fa", highlightthickness=0)
        canvas.pack()
        spacer_sizes = [3, 2, 1, 0.750, 0.500, 0.375, 0.250, 0.129, 0.125, 0.065, 0.063, 0.062, 0.0315, 0.025]
        direction = [1, 0]
        snake = [(5, 5), (4, 5), (3, 5)]
        spacer_labels = random.choices(spacer_sizes, k=len(snake)+200)
        food = [random.randint(0, grid_size-1), random.randint(0, grid_size-1)]
        score = [0]
        running = [True]
        highscore = [self._load_snake_highscore()]
        def draw():
            canvas.delete("all")
            for idx, (x, y) in enumerate(snake):
                spacer = spacer_labels[idx % len(spacer_labels)]
                color = "#b0b0b0" if idx == 0 else "#f0e130" if spacer < 0.050 else "#bbbbbb"
                canvas.create_rectangle(x*cell, y*cell, (x+1)*cell, (y+1)*cell, fill=color, outline="#9d9d9d")
                canvas.create_text(x*cell+cell/2, y*cell+cell/2, text=f"{spacer}", font=("Arial", 7, "bold"))
            fx, fy = food
            canvas.create_oval(fx*cell+2, fy*cell+2, (fx+1)*cell-2, (fy+1)*cell-2, fill="#aee9ff", outline="#2171d1", width=2)
            canvas.create_text(w//2, h-22, text=f"Score: {score[0]}      High Score: {highscore[0]}", font=("Arial", 10, "bold"), fill="#3a6edc")
        def move():
            if not running[0]:
                return
            x, y = snake[0]
            dx, dy = direction
            nx, ny = (x+dx)%grid_size, (y+dy)%grid_size
            if (nx, ny) in snake:
                running[0] = False
                if score[0] > highscore[0]:
                    highscore[0] = score[0]
                    self._save_snake_highscore(score[0])
                canvas.create_text(w//2, h//2, text="Game Over!", font=("Arial", 20, "bold"), fill="#d13b2b")
                canvas.create_text(w//2, h//2+25, text=f"Final Score: {score[0]}", font=("Arial", 13, "bold"), fill="#3a6edc")
                return
            snake.insert(0, (nx, ny))
            if [nx, ny] == food:
                score[0] += 1
                while True:
                    food_new = [random.randint(0, grid_size-1), random.randint(0, grid_size-1)]
                    if tuple(food_new) not in snake:
                        break
                food[0], food[1] = food_new
            else:
                snake.pop()
            draw()
            snake_win.after(110, move)
        def on_key(e):
            key = e.keysym
            if key == "Up" and direction != [0, 1]:
                direction[:] = [0, -1]
            elif key == "Down" and direction != [0, -1]:
                direction[:] = [0, 1]
            elif key == "Left" and direction != [1, 0]:
                direction[:] = [-1, 0]
            elif key == "Right" and direction != [-1, 0]:
                direction[:] = [1, 0]
        snake_win.bind("<Up>", on_key)
        snake_win.bind("<Down>", on_key)
        snake_win.bind("<Left>", on_key)
        snake_win.bind("<Right>", on_key)
        draw()
        move()

    def _load_snake_highscore(self):
        try:
            with open(SNAKE_HIGHSCORE_FILE,"r") as f:
                return int(f.read().strip())
        except Exception:
            return 0

    def _save_snake_highscore(self, score):
        hs = self._load_snake_highscore()
        if score > hs:
            with open(SNAKE_HIGHSCORE_FILE,"w") as f:
                f.write(str(score))

    # === FULL TETRIS GAME ===
    def _play_tetris(self):
        tetris_win = tk.Toplevel(self)
        tetris_win.title("Spacer Stack Tetris! (Easter Egg)")
        tetris_win.resizable(False, False)
        cell = 26
        cols = 10
        rows = 20
        w, h = cell*cols, cell*rows
        canvas = tk.Canvas(tetris_win, width=w, height=h, bg="#f4f7ff", highlightthickness=0)
        canvas.pack()
        shapes = [
            [(0,0), (1,0), (2,0), (3,0)],
            [(0,0), (1,0), (1,1), (2,1)],
            [(1,0), (2,0), (0,1), (1,1)],
            [(0,0), (0,1), (1,1), (2,1)],
            [(2,0), (0,1), (1,1), (2,1)],
            [(0,0), (1,0), (0,1), (1,1)],
            [(1,0), (0,1), (1,1), (2,1)],
        ]
        colors = ["#bbbbbb", "#3a6edc", "#d13b2b", "#f0e130", "#f5b042", "#91d5ed", "#fa85c3"]
        grid = [[0]*cols for _ in range(rows)]
        score = [0]
        running = [True]
        def new_piece():
            shape_idx = random.randint(0, len(shapes)-1)
            color = colors[shape_idx]
            piece = [(x+3, y) for (x,y) in shapes[shape_idx]]
            return {"coords": piece, "color": color, "shape_idx": shape_idx}
        piece = new_piece()
        next_piece = new_piece()
        def draw():
            canvas.delete("all")
            for y in range(rows):
                for x in range(cols):
                    if grid[y][x]:
                        canvas.create_rectangle(x*cell, y*cell, (x+1)*cell, (y+1)*cell, fill=grid[y][x], outline="#c4c4c4")
            for x, y in piece["coords"]:
                if y >= 0:
                    canvas.create_rectangle(x*cell, y*cell, (x+1)*cell, (y+1)*cell, fill=piece["color"], outline="#999999")
            canvas.create_text(50, 15, text=f"Score: {score[0]}", font=("Arial", 11, "bold"))
            canvas.create_text(w-62, 15, text=f"Next:", font=("Arial", 10))
            for x, y in shapes[next_piece["shape_idx"]]:
                canvas.create_rectangle(w-36 + x*cell//2, 35 + y*cell//2, w-36 + (x+1)*cell//2, 35 + (y+1)*cell//2,
                                       fill=colors[next_piece["shape_idx"]], outline="#b0b0b0")
        def can_move(dx, dy):
            for x, y in piece["coords"]:
                nx, ny = x+dx, y+dy
                if nx < 0 or nx >= cols or ny >= rows:
                    return False
                if ny >= 0 and grid[ny][nx]:
                    return False
            return True
        def move_piece(dx, dy):
            if can_move(dx, dy):
                piece["coords"] = [(x+dx, y+dy) for x, y in piece["coords"]]
                return True
            return False
        def rotate_piece():
            if piece["shape_idx"] == 5: return
            px, py = piece["coords"][0]
            new_coords = []
            for x, y in piece["coords"]:
                relx, rely = x - px, y - py
                newx, newy = px - rely, py + relx
                new_coords.append((newx, newy))
            old = piece["coords"]
            piece["coords"] = new_coords
            if not all(0 <= x < cols and y < rows and (y < 0 or not grid[y][x]) for x, y in piece["coords"]):
                piece["coords"] = old
        def freeze_piece():
            for x, y in piece["coords"]:
                if y >= 0:
                    grid[y][x] = piece["color"]
            lines = 0
            for y in reversed(range(rows)):
                if all(grid[y][x] for x in range(cols)):
                    del grid[y]
                    grid.insert(0, [0]*cols)
                    lines += 1
            score[0] += [0, 40, 100, 300, 1200][lines]
            piece.update(next_piece)
            next_piece.clear()
            next_piece.update(new_piece())
            if not can_move(0, 0):
                running[0] = False
        def tick():
            if not running[0]:
                canvas.create_text(w//2, h//2, text="Game Over", font=("Arial", 18, "bold"), fill="#d13b2b")
                canvas.create_text(w//2, h//2+24, text=f"Final Score: {score[0]}", font=("Arial", 12, "bold"), fill="#3a6edc")
                return
            if not move_piece(0,1):
                freeze_piece()
            draw()
            tetris_win.after(280, tick)
        def on_key(event):
            if event.keysym == "Left": move_piece(-1,0); draw()
            elif event.keysym == "Right": move_piece(1,0); draw()
            elif event.keysym == "Down": move_piece(0,1); draw()
            elif event.keysym == "Up": rotate_piece(); draw()
            elif event.char == " ":
                while move_piece(0,1): pass
                freeze_piece()
                draw()
        tetris_win.bind("<Left>", on_key)
        tetris_win.bind("<Right>", on_key)
        tetris_win.bind("<Down>", on_key)
        tetris_win.bind("<Up>", on_key)
        tetris_win.bind("<space>", on_key)
        draw()
        tick()

    def _show_about(self):
        about_win = tk.Toplevel(self)
        about_win.title("About B&K Spacer Calculator")
        about_win.resizable(False, False)
        tk.Label(about_win, text="B&K Spacer Calculator", font=("Arial", 15, "bold")).pack(pady=6)
        tk.Label(about_win, text="Year: 2025", font=("Arial", 10)).pack()
        tk.Label(about_win, text="Created by: Hayden Charles Cantwell", font=("Arial", 10)).pack()
        tk.Label(about_win, text="With assistance from ChatGPT", font=("Arial", 10, "italic")).pack()
        hs = 0
        try:
            with open(SNAKE_HIGHSCORE_FILE,"r") as f:
                hs = int(f.read().strip())
        except Exception:
            pass
        tk.Label(about_win, text=f"\nSpacer Snake High Score: {hs}", font=("Arial", 10, "bold"), fg="#3a6edc").pack()
        tk.Button(about_win, text="OK", width=12, command=about_win.destroy).pack(pady=8)

if __name__ == "__main__":
    app = SpacerCalculatorApp()
    app.mainloop()



