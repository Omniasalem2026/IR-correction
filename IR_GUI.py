# -*- coding: utf-8 -*-
"""
IR correction  -  simple GUI program
Developed by Omnia M. Salem

Calculates the IR-corrected potential from an Excel/CSV file of potential and current.
    Half-cell / applied potential (CV, LSV):  E_IR-corrected = E_measured - i * Rs
    Full cell (fuel cell discharge, DMFC):    E_IR-corrected = E_measured + i * Rs

Use Rs only (ohmic resistance from EIS), NOT Rct.
Your original file is never changed.

Requirements:  pip install pandas openpyxl matplotlib numpy
Run:           python IR_correction.py
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
import pandas as pd

APP_NAME = "IR correction"
AUTHOR = "Omnia M. Salem"

UNITS = ["A", "mA", "A/cm2  (current density)", "mA/cm2  (current density)"]
MODES = [
    "Half-cell / applied potential (CV, LSV):   E - i*Rs",
    "Full cell / fuel cell discharge (DMFC):   E + i*Rs",
]


# ======================= calculation part (no GUI) ==========================

def to_float(text, name):
    """Convert text to a number (accepts comma or dot)."""
    try:
        return float(str(text).strip().replace(",", "."))
    except ValueError:
        raise ValueError(f"'{name}' must be a number.")


def calculate(df, e_idx, i_idx, unit_idx, area, Rs, mode_idx,
              tafel=False, forward_only=True, lo=None, hi=None):
    """
    Do the IR correction. Returns a dictionary with all results.
    unit_idx : 0 = A, 1 = mA, 2 = A/cm2, 3 = mA/cm2
    mode_idx : 0 = half-cell (E - i*Rs), 1 = full cell (E + i*Rs)
    """
    E_all = pd.to_numeric(df.iloc[:, e_idx], errors="coerce")
    I_all = pd.to_numeric(df.iloc[:, i_idx], errors="coerce")
    ok = E_all.notna() & I_all.notna()
    data = df[ok].reset_index(drop=True)
    E = E_all[ok].to_numpy(dtype=float)
    I = I_all[ok].to_numpy(dtype=float)
    if len(E) < 2:
        raise ValueError("Not enough valid data rows. Check the columns you selected.")

    if unit_idx in (2, 3) and not area:
        raise ValueError("The active area is required when the current is a current density.")

    if unit_idx == 0:
        i_amp = I
    elif unit_idx == 1:
        i_amp = I / 1000.0
    elif unit_idx == 2:
        i_amp = I * area
    else:
        i_amp = I * area / 1000.0

    drop = i_amp * Rs                                   # V
    E_corr = E - drop if mode_idx == 0 else E + drop
    j_mA = i_amp * 1000.0 / area if area else None      # mA/cm2

    out = data.copy()
    out["i (A)"] = i_amp
    if j_mA is not None:
        out["j (mA/cm2)"] = j_mA
    out["IR drop (V)"] = drop
    out["E IR-corrected (V)"] = E_corr

    res = {
        "out": out, "E": E, "E_corr": E_corr, "i_amp": i_amp, "j_mA": j_mA,
        "drop": drop, "mode": mode_idx, "area": area, "Rs": Rs, "tafel": None,
        "n": len(E),
    }

    # Tafel slope (half-cell only)
    if tafel and mode_idx == 0:
        x = np.abs(j_mA) if j_mA is not None else np.abs(i_amp) * 1000.0   # |j|, works for cathodic (negative) current too
        use = np.ones(len(E), dtype=bool)
        if forward_only:
            use[int(np.argmax(np.abs(E - E[0]))) + 1:] = False   # forward scan = from the start up to the vertex potential
        sel = use & (x >= lo) & (x <= hi) & (x > 0)
        if sel.sum() < 3:
            res["tafel"] = {"error": "Fewer than 3 points in this window. Try a wider window."}
        else:
            logx = np.log10(x[sel])
            fits = {}
            for label, y in (("IR-corrected", E_corr[sel]), ("measured", E[sel])):
                slope, intercept = np.polyfit(logx, y, 1)
                fit = slope * logx + intercept
                ss_tot = np.sum((y - y.mean()) ** 2)
                r2 = 1 - np.sum((y - fit) ** 2) / ss_tot if ss_tot > 0 else float("nan")
                fits[label] = (slope * 1000.0, r2)
            res["tafel"] = {
                "fits": fits, "points": int(sel.sum()),
                "x": x[sel], "E_corr": E_corr[sel], "E": E[sel],
                "unit": "mA/cm2" if j_mA is not None else "mA",
            }
    return res


def summary_text(res):
    """Build the text that is shown in the results box."""
    E, Ec, i_amp, j_mA = res["E"], res["E_corr"], res["i_amp"], res["j_mA"]
    area = res["area"]
    L = []
    L.append(f"Rs = {res['Rs']} ohm" + (f",   area = {area} cm2" if area else ""))
    L.append(f"Data points used: {res['n']}")
    L.append("-" * 52)
    if res["mode"] == 0:
        k = int(np.argmax(np.abs(i_amp)))
        unit = "mA/cm2" if j_mA is not None else "mA"
        peak = j_mA[k] if j_mA is not None else i_amp[k] * 1000
        L.append(f"Largest current (abs.)     : {peak:.3f} {unit}")
        L.append(f"  Potential (measured)     : {E[k]:.4f} V")
        L.append(f"  Potential (IR-corrected) : {Ec[k]:.4f} V")
        L.append(f"  IR drop there            : {abs(res['drop'][k]):.4f} V")
        L.append("")
        L.append("Note: the current value does not change with IR")
        L.append("correction, only the potential changes. For a CV,")
        L.append("use the forward-scan peak.")
    else:
        scale = 1000.0 / area if area else 1000.0
        pu = "mW/cm2" if area else "mW"
        L.append(f"Peak power (measured)      : {(i_amp * E * scale).max():.3f} {pu}")
        L.append(f"Peak power (IR-corrected)  : {(i_amp * Ec * scale).max():.3f} {pu}")

    t = res["tafel"]
    if t is not None:
        L.append("-" * 52)
        if "error" in t:
            L.append("Tafel: " + t["error"])
        else:
            f = t["fits"]
            L.append(f"Tafel slope (IR-corrected) : {abs(f['IR-corrected'][0]):.1f} mV/dec  (R2 = {f['IR-corrected'][1]:.4f})")
            L.append(f"Tafel slope (measured)     : {abs(f['measured'][0]):.1f} mV/dec  (R2 = {f['measured'][1]:.4f})")
            L.append(f"Points used in fit: {t['points']}")
            L.append("Report the IR-corrected slope in your paper.")
    return "\n".join(L)


# ================================ GUI part ==================================

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("720x820")
        self.minsize(680, 760)

        self.path = None
        self.xl = None
        self.df = None
        self.result = None

        self.build_widgets()

    # ---------------------------- layout ------------------------------------
    def build_widgets(self):
        pad = {"padx": 12, "pady": 4}

        head = ttk.Frame(self)
        head.pack(fill="x", padx=12, pady=(12, 2))
        ttk.Label(head, text=APP_NAME, font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(head, text=f"Developed by {AUTHOR}",
                  font=("Segoe UI", 10, "italic")).pack(anchor="w")

        # 1) File
        f1 = ttk.LabelFrame(self, text="1. Data file (Excel or CSV)")
        f1.pack(fill="x", **pad)
        row = ttk.Frame(f1)
        row.pack(fill="x", padx=8, pady=6)
        self.file_var = tk.StringVar(value="No file selected")
        ttk.Button(row, text="Browse...", command=self.browse).pack(side="left")
        ttk.Label(row, textvariable=self.file_var, wraplength=520).pack(side="left", padx=10)

        row2 = ttk.Frame(f1)
        row2.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Label(row2, text="Sheet:", width=18).pack(side="left")
        self.sheet_box = ttk.Combobox(row2, state="readonly", width=30)
        self.sheet_box.pack(side="left")
        self.sheet_box.bind("<<ComboboxSelected>>", lambda e: self.load_sheet())

        # 2) Columns and units
        f2 = ttk.LabelFrame(self, text="2. Columns and units")
        f2.pack(fill="x", **pad)
        self.e_box = self.add_row(f2, "Potential column (V):", ttk.Combobox, width=38, state="readonly")
        self.i_box = self.add_row(f2, "Current column:", ttk.Combobox, width=38, state="readonly")
        self.unit_box = self.add_row(f2, "Current unit:", ttk.Combobox, width=38,
                                     state="readonly", values=UNITS)
        self.unit_box.current(3)

        # 3) Values
        f3 = ttk.LabelFrame(self, text="3. Values")
        f3.pack(fill="x", **pad)
        self.area_entry = self.add_row(f3, "Active area (cm2):", ttk.Entry, width=20)
        self.rs_entry = self.add_row(f3, "Rs from EIS (ohm):", ttk.Entry, width=20)
        ttk.Label(f3, text="Use Rs only, not Rct.  The area can be left empty if the current is in A or mA.",
                  foreground="#555").pack(anchor="w", padx=8, pady=(0, 6))

        # 4) Type
        f4 = ttk.LabelFrame(self, text="4. Type of measurement")
        f4.pack(fill="x", **pad)
        self.mode_var = tk.IntVar(value=0)
        for k, text in enumerate(MODES):
            ttk.Radiobutton(f4, text=text, variable=self.mode_var, value=k,
                            command=self.update_tafel_state).pack(anchor="w", padx=8, pady=2)

        # 5) Tafel
        f5 = ttk.LabelFrame(self, text="5. Tafel slope (optional, half-cell only)")
        f5.pack(fill="x", **pad)
        self.tafel_var = tk.IntVar(value=0)
        self.fwd_var = tk.IntVar(value=1)
        self.tafel_check = ttk.Checkbutton(f5, text="Calculate Tafel slope from IR-corrected data",
                                           variable=self.tafel_var, command=self.update_tafel_state)
        self.tafel_check.pack(anchor="w", padx=8, pady=2)
        self.fwd_check = ttk.Checkbutton(f5, text="Use the forward scan only (recommended for CV)",
                                         variable=self.fwd_var)
        self.fwd_check.pack(anchor="w", padx=8, pady=2)
        row = ttk.Frame(f5)
        row.pack(fill="x", padx=8, pady=(2, 6))
        ttk.Label(row, text="Fit window, from").pack(side="left")
        self.lo_entry = ttk.Entry(row, width=10)
        self.lo_entry.pack(side="left", padx=4)
        ttk.Label(row, text="to").pack(side="left")
        self.hi_entry = ttk.Entry(row, width=10)
        self.hi_entry.pack(side="left", padx=4)
        ttk.Label(row, text="mA/cm2  (mA if no area)").pack(side="left")
        self.update_tafel_state()

        # Buttons
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=12, pady=8)
        ttk.Button(bar, text="Calculate", command=self.on_calculate).pack(side="left")
        self.save_btn = ttk.Button(bar, text="Save Excel", command=self.on_save, state="disabled")
        self.save_btn.pack(side="left", padx=8)
        self.plot_btn = ttk.Button(bar, text="Show plots", command=self.on_plot, state="disabled")
        self.plot_btn.pack(side="left")

        # Results
        f6 = ttk.LabelFrame(self, text="Results")
        f6.pack(fill="both", expand=True, **pad)
        self.text = tk.Text(f6, height=12, font=("Consolas", 10), state="disabled", wrap="none")
        self.text.pack(fill="both", expand=True, padx=6, pady=6)

        ttk.Label(self, text=f"{APP_NAME}  -  {AUTHOR}", foreground="#777").pack(pady=(0, 6))

    def add_row(self, parent, label, widget_cls, width, **kw):
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=8, pady=3)
        ttk.Label(row, text=label, width=22).pack(side="left")
        w = widget_cls(row, width=width, **kw)
        w.pack(side="left")
        return w

    def update_tafel_state(self):
        half = self.mode_var.get() == 0
        if not half:
            self.tafel_var.set(0)
        self.tafel_check.state(["!disabled"] if half else ["disabled"])
        on = half and self.tafel_var.get() == 1
        st = ["!disabled"] if on else ["disabled"]
        self.fwd_check.state(st)
        self.lo_entry.state(st)
        self.hi_entry.state(st)

    # ---------------------------- file loading -------------------------------
    def browse(self):
        path = filedialog.askopenfilename(
            title="Select your data file",
            filetypes=[("Excel / CSV", "*.xlsx *.xls *.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            self.path = path
            if path.lower().endswith(".csv"):
                self.xl = None
                self.sheet_box.configure(values=["(CSV file)"], state="disabled")
                self.sheet_box.set("(CSV file)")
                self.df = pd.read_csv(path)
                self.fill_columns()
            else:
                self.xl = pd.ExcelFile(path)
                self.sheet_box.configure(values=self.xl.sheet_names, state="readonly")
                self.sheet_box.current(0)
                self.load_sheet()
            self.file_var.set(path)
        except Exception as ex:
            messagebox.showerror(APP_NAME, f"Could not read the file:\n{ex}")

    def load_sheet(self):
        try:
            self.df = self.xl.parse(self.sheet_box.get())
            self.fill_columns()
        except Exception as ex:
            messagebox.showerror(APP_NAME, f"Could not read the sheet:\n{ex}")

    def fill_columns(self):
        names = [str(c) for c in self.df.columns]
        self.e_box.configure(values=names)
        self.i_box.configure(values=names)
        self.e_box.current(0)
        self.i_box.current(1 if len(names) > 1 else 0)

    # ----------------------------- actions -----------------------------------
    def show_text(self, text):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", text)
        self.text.configure(state="disabled")

    def on_calculate(self):
        try:
            if self.df is None:
                raise ValueError("Please select a data file first.")
            if self.e_box.current() < 0 or self.i_box.current() < 0:
                raise ValueError("Please select the potential and current columns.")
            if self.e_box.current() == self.i_box.current():
                raise ValueError("Potential and current must be different columns.")

            area_txt = self.area_entry.get().strip()
            area = to_float(area_txt, "Active area") if area_txt else None
            if area is not None and area <= 0:
                raise ValueError("The active area must be greater than zero.")
            Rs = to_float(self.rs_entry.get(), "Rs")

            tafel = bool(self.tafel_var.get()) and self.mode_var.get() == 0
            lo = hi = None
            if tafel:
                lo = to_float(self.lo_entry.get(), "Fit window (from)")
                hi = to_float(self.hi_entry.get(), "Fit window (to)")
                if lo >= hi:
                    raise ValueError("In the fit window, 'from' must be smaller than 'to'.")

            self.result = calculate(
                self.df, self.e_box.current(), self.i_box.current(),
                self.unit_box.current(), area, Rs, self.mode_var.get(),
                tafel=tafel, forward_only=bool(self.fwd_var.get()), lo=lo, hi=hi)

            self.show_text(summary_text(self.result))
            self.save_btn.configure(state="normal")
            self.plot_btn.configure(state="normal")
        except ValueError as ex:
            messagebox.showwarning(APP_NAME, str(ex))
        except Exception as ex:
            messagebox.showerror(APP_NAME, f"Something went wrong:\n{ex}")

    def on_save(self):
        if self.result is None:
            return
        base = os.path.splitext(os.path.basename(self.path))[0]
        target = filedialog.asksaveasfilename(
            title="Save corrected data", defaultextension=".xlsx",
            initialdir=os.path.dirname(self.path), initialfile=base + "_IR_corrected.xlsx",
            filetypes=[("Excel file", "*.xlsx")])
        if not target:
            return
        try:
            self.result["out"].to_excel(target, index=False)
            messagebox.showinfo(APP_NAME, f"Saved:\n{target}")
        except Exception as ex:
            messagebox.showerror(APP_NAME, f"Could not save the file.\nIs it open in Excel?\n\n{ex}")

    def on_plot(self):
        if self.result is None:
            return
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        except ImportError:
            messagebox.showerror(APP_NAME, "matplotlib is not installed.\nRun:  pip install matplotlib")
            return

        r = self.result
        xs = r["j_mA"] if r["j_mA"] is not None else r["i_amp"] * 1000.0
        ylab = "j (mA/cm²)" if r["j_mA"] is not None else "i (mA)"
        t = r["tafel"] if (r["tafel"] and "fits" in r["tafel"]) else None

        win = tk.Toplevel(self)
        win.title(f"{APP_NAME} - plots")
        fig = Figure(figsize=(10 if t else 6, 4.6), dpi=100)
        ax = fig.add_subplot(1, 2 if t else 1, 1)
        if r["mode"] == 0:
            ax.plot(r["E"], xs, "-", color="tab:blue", label="Measured")
            ax.plot(r["E_corr"], xs, "--", color="tab:red", label="IR-corrected")
            ax.set_xlabel("Potential (V)")
            ax.set_ylabel(ylab)
        else:
            ax.plot(xs, r["E"], "o-", color="tab:blue", label="Measured")
            ax.plot(xs, r["E_corr"], "s--", color="tab:red", label="IR-corrected")
            ax.set_xlabel(ylab)
            ax.set_ylabel("Cell voltage (V)")
        ax.legend()

        if t:
            ax2 = fig.add_subplot(1, 2, 2)
            lx = np.log10(t["x"])
            ax2.plot(lx, t["E_corr"], "o", color="tab:red", label="IR-corrected")
            ax2.plot(lx, t["E"], "o", color="tab:blue", alpha=0.5, label="Measured")
            ax2.set_xlabel(f"log |j| ({t['unit']})")
            ax2.set_ylabel("Potential (V)")
            ax2.set_title(f"Tafel slope (IR-corrected) = {abs(t['fits']['IR-corrected'][0]):.1f} mV/dec")
            ax2.legend()

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        toolbar = NavigationToolbar2Tk(canvas, win)  # has a Save button for PNG
        toolbar.update()
        canvas.get_tk_widget().pack(fill="both", expand=True)


if __name__ == "__main__":
    App().mainloop()
