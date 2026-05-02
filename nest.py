"""
NEST — Numerical Evaluation for Strategic Tradeoffs

Requirements:
    pip install customtkinter numpy matplotlib pillow
"""

import math
import copy
import re
from dataclasses import dataclass, field
from typing import Optional

import sys
import os
import numpy as np
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
from PIL import Image


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


# ─────────────────────────────────────────────────────────────
# THEME — Dark Sidebar + Warm Stone Content Area
# ─────────────────────────────────────────────────────────────
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

BG_DEEP    = "#e6e6ed"          # canvas  — cool blue-stone
BG_CARD    = "#f6f6f7"          # cards   — soft periwinkle-white (no pure white)
BG_PANEL   = "#ffffff"          # panel   — one step deeper than card
BG_ENTRY   = "#eaecf5"          # inputs  — slightly cooler
ACCENT     = "#088CC5"          # indigo-600  — primary brand
ACCENT_LIGHT = "#dde3ff"        # indigo-100  — tinted active nav bg
ACCENT2    = "#bebec7"          # indigo-800  — hover / pressed
GOLD       = "#b45309"          # amber-700   — warm highlight
GREEN      = "#0d9488"          # teal-600    — Option B / positive
RED        = "#e11d48"          # rose-600    — error / negative
MUTED      = "#4973bd"          # blue-slate  — legible secondary text
TEXT_PRI   = "#6D85B4"          # near-black  — always legible
TEXT_SEC   = "#687E86"          # dark grey   — legible secondary
BORDER     = "#d1d8e8"          # periwinkle border
BORDER2    = "#cad1df"          # slightly deeper border
PURPLE     = "#b29dd7"          # violet-600  — crossover / special

DEFAULT_TOL      = 1e-8
DEFAULT_MAX_ITER = 200
SCAN_STEPS       = 4000


# ═════════════════════════════════════════════════════════════
# DATA MODEL  (unchanged)
# ═════════════════════════════════════════════════════════════

@dataclass
class CostComponent:
    name: str
    amount: float
    cost_type: str = "fixed"
    category: str = "general"
    notes: str = ""

    def cost_at(self, x: float) -> float:
        if self.cost_type == "fixed":
            return self.amount
        if self.cost_type == "variable":
            return self.amount * x
        return self.amount


@dataclass
class BusinessOption:
    name: str
    revenue_per_unit: float = 0.0
    expected_volume: float = 0.0
    description: str = ""
    cost_components: list = field(default_factory=list)

    def total_revenue(self, x: float) -> float:
        return self.revenue_per_unit * x

    def total_cost(self, x: float) -> float:
        return sum(c.cost_at(x) for c in self.cost_components)

    def profit(self, x: float) -> float:
        return self.total_revenue(x) - self.total_cost(x)

    def cost_per_unit(self, x: float) -> float:
        if x == 0:
            return float("inf")
        return self.total_cost(x) / x

    def margin(self, x: float) -> float:
        rev = self.total_revenue(x)
        if rev == 0:
            return 0.0
        return (self.profit(x) / rev) * 100.0

    def fixed_total(self) -> float:
        return sum(c.amount for c in self.cost_components if c.cost_type == "fixed")

    def variable_rate(self) -> float:
        return sum(c.amount for c in self.cost_components if c.cost_type == "variable")

    def cost_breakdown(self, x: float) -> list:
        total = self.total_cost(x)
        rows = []
        for c in self.cost_components:
            amt = c.cost_at(x)
            pct = (amt / total * 100.0) if total > 0 else 0.0
            rows.append((c.name, c.category, amt, pct))
        return sorted(rows, key=lambda r: r[2], reverse=True)


# ═════════════════════════════════════════════════════════════
# NUMERICAL ENGINE  (unchanged)
# ═════════════════════════════════════════════════════════════

def _safe(val):
    try:
        v = float(val)
        return None if (math.isnan(v) or math.isinf(v)) else v
    except Exception:
        return None


def _normalize_zero(v, eps=1e-14):
    if v is None:
        return None
    return 0.0 if abs(v) < eps else v


def _same_root(a, b, tol=1e-6):
    return abs(a - b) <= tol


def _unique_sorted_roots(roots, tol=1e-6):
    clean = []
    for r in sorted(roots):
        if _safe(r) is None:
            continue
        if not clean or not _same_root(r, clean[-1], tol):
            clean.append(float(r))
    return clean


def _result_better(candidate, best, err_tie_tol=1e-12):
    if candidate is None:
        return False
    if best is None:
        return True
    _, c_itr, c_err, _ = candidate
    _, b_itr, b_err, _ = best
    if c_err < b_err - err_tie_tol:
        return True
    if abs(c_err - b_err) <= err_tie_tol and c_itr < b_itr:
        return True
    return False


def choose_best_method(results, err_tie_tol=1e-12):
    best_name = None
    best_data = None
    for name, data in results.items():
        root, itr, err, status = data
        if status != "Success" or root is None or err is None:
            continue
        if _result_better(data, best_data, err_tie_tol):
            best_name = name
            best_data = data
    return best_name, best_data


def bisection(f, a, b, tol=DEFAULT_TOL, max_iter=DEFAULT_MAX_ITER):
    fa, fb = _normalize_zero(f(a)), _normalize_zero(f(b))
    if fa is None or fb is None:
        return None, 0, None, "Failed"
    if abs(fa) < tol:
        return a, 0, abs(fa), "Success"
    if abs(fb) < tol:
        return b, 0, abs(fb), "Success"
    if fa * fb > 0:
        return None, 0, None, "No bracket"
    c = a
    for i in range(1, max_iter + 1):
        c = (a + b) / 2.0
        fc = _normalize_zero(f(c))
        if fc is None:
            return None, i, None, "Failed"
        if abs(fc) < tol or abs(b - a) < tol:
            return c, i, abs(fc), "Success"
        if fa * fc < 0:
            b, fb = c, fc
        else:
            a, fa = c, fc
    last = _normalize_zero(f(c))
    return c, max_iter, abs(last) if last is not None else None, "Max iter"


def _numerical_derivative(f, x, h=1e-5):
    fph = _normalize_zero(f(x + h))
    fmh = _normalize_zero(f(x - h))
    if fph is None or fmh is None:
        return None
    return (fph - fmh) / (2 * h)


def newton(f, x0, tol=DEFAULT_TOL, max_iter=DEFAULT_MAX_ITER):
    if x0 is None:
        return None, 0, None, "No start"
    curr = float(x0)
    for i in range(1, max_iter + 1):
        fv = _normalize_zero(f(curr))
        if fv is None:
            return None, i, None, "Failed"
        dfv = _numerical_derivative(f, curr)
        if dfv is None or abs(dfv) < 1e-14:
            return None, i, None, "Zero deriv"
        nxt = curr - fv / dfv
        if _safe(nxt) is None or abs(nxt) > 1e9:
            return None, i, None, "Diverged"
        fnxt = _normalize_zero(f(nxt))
        if fnxt is None:
            return None, i, None, "Failed"
        if abs(nxt - curr) < tol and abs(fnxt) < tol:
            return nxt, i, abs(fnxt), "Success"
        curr = nxt
    fv = _normalize_zero(f(curr))
    return curr, max_iter, abs(fv) if fv is not None else None, "Max iter"


def secant(f, x0, x1, tol=DEFAULT_TOL, max_iter=DEFAULT_MAX_ITER):
    if x0 is None or x1 is None:
        return None, 0, None, "No start"
    x0 = float(x0)
    x1 = float(x1)
    fx0 = _normalize_zero(f(x0))
    fx1 = _normalize_zero(f(x1))
    if fx0 is None or fx1 is None:
        return None, 0, None, "Failed"
    for i in range(1, max_iter + 1):
        denom = fx1 - fx0
        if abs(denom) < 1e-15:
            return None, i, None, "Zero denom"
        nxt = x1 - fx1 * (x1 - x0) / denom
        if _safe(nxt) is None or abs(nxt) > 1e9:
            return None, i, None, "Diverged"
        fnxt = _normalize_zero(f(nxt))
        if fnxt is None:
            return None, i, None, "Failed"
        if abs(nxt - x1) < tol and abs(fnxt) < tol:
            return nxt, i, abs(fnxt), "Success"
        x0, fx0 = x1, fx1
        x1, fx1 = nxt, fnxt
    return x1, max_iter, abs(fx1) if fx1 is not None else None, "Max iter"


def brent(f, a, b, tol=DEFAULT_TOL, max_iter=DEFAULT_MAX_ITER):
    fa, fb = _normalize_zero(f(a)), _normalize_zero(f(b))
    if fa is None or fb is None:
        return None, 0, None, "Failed"
    if abs(fa) < tol:
        return a, 0, abs(fa), "Success"
    if abs(fb) < tol:
        return b, 0, abs(fb), "Success"
    if fa * fb > 0:
        return None, 0, None, "No bracket"
    if abs(fa) < abs(fb):
        a, b = b, a
        fa, fb = fb, fa
    c, fc = a, fa
    mflag = True
    d = None
    s = b
    for i in range(1, max_iter + 1):
        if abs(b - a) < tol or abs(fb) < tol:
            return b, i, abs(fb), "Success"
        if fa != fc and fb != fc:
            s = (
                a * fb * fc / ((fa - fb) * (fa - fc))
                + b * fa * fc / ((fb - fa) * (fb - fc))
                + c * fa * fb / ((fc - fa) * (fc - fb))
            )
        else:
            if abs(fb - fa) < 1e-15:
                s = (a + b) / 2
            else:
                s = b - fb * (b - a) / (fb - fa)
        cond1 = not (min(a, b) < s < max(a, b))
        cond2 = mflag and abs(s - b) >= abs(b - c) / 2
        cond3 = (not mflag) and (d is not None) and abs(s - b) >= abs(c - d) / 2
        cond4 = mflag and abs(b - c) < tol
        cond5 = (not mflag) and (d is not None) and abs(c - d) < tol
        if cond1 or cond2 or cond3 or cond4 or cond5:
            s = (a + b) / 2
            mflag = True
        else:
            mflag = False
        fs = _normalize_zero(f(s))
        if fs is None:
            return None, i, None, "Failed"
        d = c
        c, fc = b, fb
        if fa * fs < 0:
            b, fb = s, fs
        else:
            a, fa = s, fs
        if abs(fa) < abs(fb):
            a, b = b, a
            fa, fb = fb, fa
    return b, max_iter, abs(fb), "Max iter"


def bisection_newton(f, a, b, tol=DEFAULT_TOL, max_iter=DEFAULT_MAX_ITER):
    fa, fb = _normalize_zero(f(a)), _normalize_zero(f(b))
    if fa is None or fb is None:
        return None, 0, None, "Failed"
    if abs(fa) < tol:
        return a, 0, abs(fa), "Success"
    if abs(fb) < tol:
        return b, 0, abs(fb), "Success"
    if fa * fb > 0:
        return None, 0, None, "No bracket"
    BISECT_PHASES = max_iter // 3
    curr = (a + b) / 2.0
    for i in range(1, BISECT_PHASES + 1):
        curr = (a + b) / 2.0
        fc = _normalize_zero(f(curr))
        if fc is None:
            return None, i, None, "Failed"
        if abs(fc) < tol or abs(b - a) < tol:
            return curr, i, abs(fc), "Success"
        if fa * fc < 0:
            b, fb = curr, fc
        else:
            a, fa = curr, fc
    total_itr = BISECT_PHASES
    for j in range(1, max_iter - BISECT_PHASES + 1):
        fv = _normalize_zero(f(curr))
        if fv is None:
            return None, total_itr + j, None, "Failed"
        dfv = _numerical_derivative(f, curr)
        if dfv is None or abs(dfv) < 1e-14:
            curr = (a + b) / 2.0
            continue
        nxt = curr - fv / dfv
        if nxt < a or nxt > b:
            nxt = (a + b) / 2.0
        fnxt = _normalize_zero(f(nxt))
        if fnxt is None:
            return None, total_itr + j, None, "Failed"
        if abs(nxt - curr) < tol and abs(fnxt) < tol:
            return nxt, total_itr + j, abs(fnxt), "Success"
        if fa * fnxt < 0:
            b, fb = nxt, fnxt
        else:
            a, fa = nxt, fnxt
        curr = nxt
    fv = _normalize_zero(f(curr))
    return curr, max_iter, abs(fv) if fv is not None else None, "Max iter"


def find_brackets(f, lo, hi, steps=SCAN_STEPS, zero_tol=1e-10):
    xs = np.linspace(lo, hi, steps)
    brackets = []
    exact = []
    prev_x = xs[0]
    prev_f = _normalize_zero(f(prev_x))
    if prev_f is not None and abs(prev_f) < zero_tol:
        exact.append(prev_x)
    for x in xs[1:]:
        fx = _normalize_zero(f(x))
        if fx is None:
            prev_x, prev_f = x, fx
            continue
        if abs(fx) < zero_tol:
            exact.append(x)
        if prev_f is not None:
            if prev_f * fx < 0:
                brackets.append((prev_x, x))
        prev_x, prev_f = x, fx
    brackets_clean = []
    for a, b in brackets:
        add_it = True
        for aa, bb in brackets_clean:
            if abs(a - aa) < 1e-6 and abs(b - bb) < 1e-6:
                add_it = False
                break
        if add_it:
            brackets_clean.append((a, b))
    return brackets_clean, _unique_sorted_roots(exact)


def run_all_methods(f, lo, hi):
    brackets, exact = find_brackets(f, lo, hi)
    results = {}
    all_roots = []

    best_bis = None
    if brackets:
        for a, b in brackets:
            candidate = bisection(f, a, b)
            r, itr, err, status = candidate
            if status == "Success" and r is not None:
                all_roots.append(r)
                if _result_better(candidate, best_bis):
                    best_bis = candidate
        results["Bisection"] = best_bis if best_bis is not None else (None, 0, None, "No bracket")
    else:
        results["Bisection"] = (None, 0, None, "No bracket")

    best_brent = None
    if brackets:
        for a, b in brackets:
            candidate = brent(f, a, b)
            r, itr, err, status = candidate
            if status == "Success" and r is not None:
                all_roots.append(r)
                if _result_better(candidate, best_brent):
                    best_brent = candidate
        results["Brent"] = best_brent if best_brent is not None else (None, 0, None, "No bracket")
    else:
        results["Brent"] = (None, 0, None, "No bracket")

    best_newton = None
    newton_starts = [(a + b) / 2 for a, b in brackets] if brackets else [(lo + hi) / 2]
    for x0 in newton_starts:
        candidate = newton(f, x0)
        r, itr, err, status = candidate
        if status == "Success" and r is not None and lo <= r <= hi:
            all_roots.append(r)
            if _result_better(candidate, best_newton):
                best_newton = candidate
    results["Newton"] = best_newton if best_newton is not None else (None, 0, None, "Failed")

    best_secant = None
    secant_pairs = brackets if brackets else [((lo + hi) / 2 - 1.0, (lo + hi) / 2 + 1.0)]
    for x0, x1 in secant_pairs:
        candidate = secant(f, x0, x1)
        r, itr, err, status = candidate
        if status == "Success" and r is not None and lo <= r <= hi:
            all_roots.append(r)
            if _result_better(candidate, best_secant):
                best_secant = candidate
    results["Secant"] = best_secant if best_secant is not None else (None, 0, None, "Failed")

    best_hybrid = None
    if brackets:
        for a, b in brackets:
            candidate = bisection_newton(f, a, b)
            r, itr, err, status = candidate
            if status == "Success" and r is not None:
                all_roots.append(r)
                if _result_better(candidate, best_hybrid):
                    best_hybrid = candidate
        results["Bisection-Newton"] = best_hybrid if best_hybrid is not None else (None, 0, None, "No bracket")
    else:
        results["Bisection-Newton"] = (None, 0, None, "No bracket")

    all_roots.extend(exact)
    unique_roots = _unique_sorted_roots(all_roots, tol=1e-6)
    best_name, best = choose_best_method(results)
    return results, unique_roots, best_name, best


# ═════════════════════════════════════════════════════════════
# COMPARISON / SENSITIVITY / RECOMMENDATION  (unchanged)
# ═════════════════════════════════════════════════════════════

class ComparisonEngine:
    def __init__(self, option_a: BusinessOption, option_b: BusinessOption):
        self.a = option_a
        self.b = option_b

    def profit_diff(self, x):
        return self.a.profit(x) - self.b.profit(x)

    def _scan_range(self):
        vol = max(self.a.expected_volume, self.b.expected_volume, 100)
        return 0.1, vol * 2.5

    def find_breakeven_a(self):
        lo, hi = self._scan_range()
        _, roots, _, _ = run_all_methods(self.a.profit, lo, hi)
        return roots[0] if roots else None

    def find_breakeven_b(self):
        lo, hi = self._scan_range()
        _, roots, _, _ = run_all_methods(self.b.profit, lo, hi)
        return roots[0] if roots else None

    def find_crossover(self):
        lo, hi = self._scan_range()
        return run_all_methods(self.profit_diff, lo, hi)

    def summary_at_volumes(self, vol_a, vol_b):
        pa = self.a.profit(vol_a)
        pb = self.b.profit(vol_b)
        better = self.a.name if pa >= pb else self.b.name
        return {
            "vol_a": vol_a, "vol_b": vol_b,
            "profit_a": pa, "profit_b": pb,
            "margin_a": self.a.margin(vol_a),
            "margin_b": self.b.margin(vol_b),
            "cost_per_unit_a": self.a.cost_per_unit(vol_a),
            "cost_per_unit_b": self.b.cost_per_unit(vol_b),
            "better": better,
        }


class SensitivityEngine:
    def __init__(self, option: BusinessOption):
        self.option = option

    def test_component(self, component_name: str, pct_change: float, x: float):
        opt_copy = copy.deepcopy(self.option)
        for c in opt_copy.cost_components:
            if c.name == component_name:
                c.amount *= (1 + pct_change / 100.0)
        return opt_copy.profit(x)

    def rank_sensitivity(self, x: float, pct_change: float = 10.0):
        base_profit = self.option.profit(x)
        impacts = []
        for c in self.option.cost_components:
            new_profit = self.test_component(c.name, pct_change, x)
            delta = new_profit - base_profit
            impacts.append((c.name, c.category, delta, abs(delta)))
        return sorted(impacts, key=lambda r: r[3], reverse=True)


class RecommendationEngine:
    def __init__(self, engine: ComparisonEngine):
        self.eng = engine

    def generate(self, crossover_roots, be_a, be_b, vol_a, vol_b):
        a, b = self.eng.a, self.eng.b
        s = self.eng.summary_at_volumes(vol_a, vol_b)
        pa, pb = s["profit_a"], s["profit_b"]
        lines = []
        better_name = a.name if pa >= pb else b.name
        worse_name  = b.name if pa >= pb else a.name
        lines.append(
            f"{a.name} at volume {vol_a:,.1f}: profit ${pa:,.2f}. "
            f"{b.name} at volume {vol_b:,.1f}: profit ${pb:,.2f}."
        )
        lines.append(f"→ {better_name} shows higher profit at its expected volume.")
        if be_a:
            lines.append(f"{a.name} breaks even at {be_a:,.1f} units.")
        else:
            lines.append(f"{a.name} does not break even in the modelled range.")
        if be_b:
            lines.append(f"{b.name} breaks even at {be_b:,.1f} units.")
        else:
            lines.append(f"{b.name} does not break even in the modelled range.")
        ref_vol = max(vol_a, vol_b)
        if crossover_roots:
            r = crossover_roots[0]
            if r < ref_vol:
                lines.append(
                    f"The options cross at {r:,.1f} units — below expected volume. "
                    f"{better_name} is superior at the current scale."
                )
            else:
                lines.append(
                    f"Options cross at {r:,.1f} units — above expected volume. "
                    f"At lower volumes {worse_name} may be safer."
                )
        else:
            lines.append(f"{better_name} is dominant across the entire modelled range.")
        bd_a = a.cost_breakdown(vol_a)
        if bd_a:
            top = bd_a[0]
            lines.append(
                f"Biggest cost driver for {a.name}: {top[0]} "
                f"(${top[2]:,.2f}, {top[3]:.1f}% of total cost)."
            )
        bd_b = b.cost_breakdown(vol_b)
        if bd_b:
            top = bd_b[0]
            lines.append(
                f"Biggest cost driver for {b.name}: {top[0]} "
                f"(${top[2]:,.2f}, {top[3]:.1f}% of total cost)."
            )
        lines.append(f"Profit margins — {a.name}: {s['margin_a']:.1f}%  |  {b.name}: {s['margin_b']:.1f}%.")
        lines.append(f"\nRecommendation: choose {better_name}.")
        return "\n".join(lines)


# ═════════════════════════════════════════════════════════════
# GUI HELPERS
# ═════════════════════════════════════════════════════════════
COST_CATEGORIES = ["general", "labor", "transport", "storage", "quality", "overhead", "materials", "utilities"]
COST_TYPES = ["fixed", "variable"]

# Fonts are created lazily after the root window exists
FONT_H1   = None
FONT_H2   = None
FONT_H3   = None
FONT_BODY = None
FONT_SMALL= None
FONT_MONO = None

def _init_fonts():
    global FONT_H1, FONT_H2, FONT_H3, FONT_BODY, FONT_SMALL, FONT_MONO
    FONT_H1    = ctk.CTkFont(size=22, weight="bold")
    FONT_H2    = ctk.CTkFont(size=15, weight="bold")
    FONT_H3    = ctk.CTkFont(size=13, weight="bold")
    FONT_BODY  = ctk.CTkFont(size=12)
    FONT_SMALL = ctk.CTkFont(size=11)
    FONT_MONO  = ctk.CTkFont(family="Segoe UI", size=12)


def _isolate_scroll(widget):
    """Prevent mouse-wheel events on a textbox from bubbling up to the parent scrollable frame."""
    def _block(event):
        widget.tk_widget = widget._textbox if hasattr(widget, "_textbox") else widget
        widget.tk_widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"
    def _bind_recursive(w):
        w.bind("<MouseWheel>", _block, add="+")          # Windows / macOS
        w.bind("<Button-4>",   lambda e: (w.yview_scroll(-1, "units"), "break")[1], add="+")  # Linux scroll up
        w.bind("<Button-5>",   lambda e: (w.yview_scroll( 1, "units"), "break")[1], add="+")  # Linux scroll down
        for child in w.winfo_children():
            _bind_recursive(child)
    _bind_recursive(widget)


def card_frame(parent, **kwargs):
    kw = dict(corner_radius=12, fg_color=BG_CARD, border_width=1, border_color=BORDER)
    kw.update(kwargs)
    return ctk.CTkFrame(parent, **kw)


def section_label(parent, text, color=ACCENT):
    return ctk.CTkLabel(parent, text=text, font=FONT_H3, text_color=color)


def muted_label(parent, text):
    return ctk.CTkLabel(parent, text=text, font=FONT_SMALL, text_color=MUTED)


def _apply_treeview_style():
    style = ttk.Style()
    style.theme_use("default")
    style.configure(
        "Pro.Treeview",
        rowheight=30,
        font=("Segoe UI", 11),
        background=BG_CARD,
        foreground=TEXT_PRI,
        fieldbackground=BG_CARD,
        borderwidth=0,
    )
    style.configure(
        "Pro.Treeview.Heading",
        font=("Segoe UI", 10, "bold"),
        background="#dde3f5",
        foreground="#3730a3",
        relief="flat",
        borderwidth=0,
    )
    style.map(
        "Pro.Treeview",
        background=[("selected", ACCENT)],
        foreground=[("selected", "white")],
    )


# ─────────────────────────────────────────────────────────────
# CostRow widget
# ─────────────────────────────────────────────────────────────
class CostRow(ctk.CTkFrame):
    def __init__(self, parent, on_delete, index, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.on_delete = on_delete
        self.index = index
        self.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.name_var   = ctk.StringVar(value="")
        self.amount_var = ctk.StringVar(value="")
        self.type_var   = ctk.StringVar(value="fixed")
        self.cat_var    = ctk.StringVar(value="general")

        e_kw = dict(
            height=32, font=FONT_SMALL,
            fg_color=BG_ENTRY, border_color=BORDER2,
            border_width=1, text_color=TEXT_PRI,
        )

        ctk.CTkEntry(self, textvariable=self.name_var, width=140,
                     placeholder_text="Cost name", **e_kw).grid(
            row=0, column=0, padx=(0, 4), pady=2, sticky="ew")
        ctk.CTkEntry(self, textvariable=self.amount_var, width=80,
                     placeholder_text="Amount", **e_kw).grid(
            row=0, column=1, padx=4, pady=2, sticky="ew")
        ctk.CTkOptionMenu(
            self, variable=self.type_var, values=COST_TYPES,
            width=90, height=32, fg_color=BG_ENTRY,
            button_color=ACCENT, dropdown_fg_color=BG_PANEL,
            text_color=TEXT_PRI, font=FONT_SMALL,
        ).grid(row=0, column=2, padx=4, pady=2, sticky="ew")
        ctk.CTkOptionMenu(
            self, variable=self.cat_var, values=COST_CATEGORIES,
            width=110, height=32, fg_color=BG_ENTRY,
            button_color=ACCENT, dropdown_fg_color=BG_PANEL,
            text_color=TEXT_PRI, font=FONT_SMALL,
        ).grid(row=0, column=3, padx=4, pady=2, sticky="ew")
        ctk.CTkButton(
            self, text="✕", width=30, height=30,
            fg_color="#fef2f2", hover_color="#fecaca",
            text_color="#e11d48", font=FONT_SMALL,
            border_width=1, border_color="#fecaca",
            command=self.delete,
        ).grid(row=0, column=4, padx=(4, 0), pady=2)

    def delete(self):
        self.on_delete(self)

    def to_component(self) -> Optional[CostComponent]:
        try:
            amt = float(self.amount_var.get())
        except ValueError:
            return None
        return CostComponent(
            name=self.name_var.get().strip() or "Unnamed",
            amount=amt,
            cost_type=self.type_var.get(),
            category=self.cat_var.get(),
        )


# ─────────────────────────────────────────────────────────────
# OptionPanel widget
# ─────────────────────────────────────────────────────────────
class OptionPanel(ctk.CTkFrame):
    def __init__(self, parent, label_text, accent_color, **kwargs):
        super().__init__(
            parent, fg_color=BG_CARD, corner_radius=14,
            border_width=1, border_color=BORDER, **kwargs
        )
        self.accent = accent_color
        self.cost_rows = []
        self._build(label_text)

    def _build(self, label_text):
        self.grid_columnconfigure(0, weight=1)

        # Coloured header bar
        hdr = ctk.CTkFrame(self, fg_color=self.accent, corner_radius=0, height=52)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            hdr, text=label_text,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="white",
        ).grid(row=0, column=0, padx=18, pady=14, sticky="w")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=14, pady=10)
        body.grid_columnconfigure((0, 1), weight=1)

        fields = [
            ("Option name",        "name_var", "", "e.g. Option A"),
            ("Revenue / unit ($)", "rev_var",  "", "e.g. 50"),
            ("Expected volume",    "vol_var",  "", "e.g. 500"),
        ]
        for i, (lbl, attr, default, ph) in enumerate(fields):
            muted_label(body, lbl).grid(
                row=i * 2, column=0, columnspan=2, sticky="w", pady=(6, 0))
            var = ctk.StringVar(value=default)
            setattr(self, attr, var)
            ctk.CTkEntry(
                body, textvariable=var, placeholder_text=ph,
                height=34, fg_color=BG_ENTRY, border_color=BORDER2,
                border_width=1, text_color=TEXT_PRI, font=FONT_BODY,
            ).grid(row=i * 2 + 1, column=0, columnspan=2, sticky="ew", pady=(0, 2))

        sep = len(fields) * 2
        ctk.CTkLabel(
            body, text="Cost components",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=ACCENT,
        ).grid(row=sep, column=0, columnspan=2, sticky="w", pady=(12, 4))

        # Column headers for cost rows
        col_hdr = ctk.CTkFrame(body, fg_color="transparent")
        col_hdr.grid(row=sep + 1, column=0, columnspan=2, sticky="ew")
        col_hdr.grid_columnconfigure((0, 1, 2, 3), weight=1)
        for j, lbl in enumerate(["Name", "Amount", "Type", "Category"]):
            muted_label(col_hdr, lbl).grid(row=0, column=j, sticky="w", padx=2)

        self.cost_scroll = ctk.CTkScrollableFrame(
            body, fg_color="transparent", height=170, corner_radius=0,
            scrollbar_button_color=BORDER2,
        )
        self.cost_scroll.grid(row=sep + 2, column=0, columnspan=2, sticky="ew", pady=2)
        self.cost_scroll.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            body, text="＋  Add cost component", height=32,
            fg_color=BG_PANEL, hover_color=BG_ENTRY,
            text_color=ACCENT, font=FONT_SMALL,
            border_width=1, border_color=BORDER2, corner_radius=8,
            command=self.add_cost_row,
        ).grid(row=sep + 3, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        self.add_cost_row()
        self.add_cost_row()

    def add_cost_row(self):
        row = CostRow(self.cost_scroll, on_delete=self._delete_row, index=len(self.cost_rows))
        row.grid(row=len(self.cost_rows), column=0, sticky="ew", pady=1)
        self.cost_rows.append(row)

    def _delete_row(self, row: CostRow):
        if len(self.cost_rows) <= 1:
            return
        self.cost_rows.remove(row)
        row.destroy()
        for i, r in enumerate(self.cost_rows):
            r.grid(row=i)

    def build_option(self) -> Optional[BusinessOption]:
        try:
            rev = float(self.rev_var.get())
            vol = float(self.vol_var.get())
        except ValueError:
            return None
        name = self.name_var.get().strip() or "Option"
        components = []
        for row in self.cost_rows:
            c = row.to_component()
            if c is not None and c.amount != 0:
                components.append(c)
        return BusinessOption(
            name=name, revenue_per_unit=rev,
            expected_volume=vol, cost_components=components,
        )




# ─────────────────────────────────────────────────────────────
# HTML-style content switcher
# Works like CTkTabview for the existing code, but without the top tab bar.
# The sidebar buttons control which content frame is visible.
# ─────────────────────────────────────────────────────────────
class SidebarTabView(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=BG_CARD, corner_radius=12,
                         border_width=1, border_color=BORDER, **kwargs)
        self._tabs = {}
        self._current = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

    def add(self, name: str):
        frame = ctk.CTkScrollableFrame(
            self,
            fg_color=BG_CARD,
            corner_radius=12,
            scrollbar_button_color=BORDER2,
            scrollbar_button_hover_color=MUTED,
        )
        frame.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        frame.grid_remove()
        self._tabs[name] = frame
        if self._current is None:
            self.set(name)
        return frame

    def tab(self, name: str):
        return self._tabs[name]

    def set(self, name: str):
        if name not in self._tabs:
            return
        if self._current and self._current in self._tabs:
            self._tabs[self._current].grid_remove()
        self._tabs[name].grid()
        self._current = name


# ═════════════════════════════════════════════════════════════
# MAIN APP
# ═════════════════════════════════════════════════════════════

class NESTApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Business Decision Analyzer")
        self.geometry("1560x960")
        self.minsize(1280, 800)
        self.configure(fg_color=BG_DEEP)

        try:
            self.iconbitmap(resource_path("logo.ico"))
        except Exception:
            pass

        _init_fonts()
        _apply_treeview_style()

        self._option_a: Optional[BusinessOption] = None
        self._option_b: Optional[BusinessOption] = None
        self._comparison_engine: Optional[ComparisonEngine] = None
        self._crossover_results = {}
        self._crossover_roots = []
        self._best_crossover = None
        self._graph_win = None
        self._eq_motion_cid = None

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()

    # ─── SIDEBAR ───────────────────────────────────────────────

    def _switch_tab(self, name):
        """Switch main content and update sidebar active state."""
        if hasattr(self, "_tabs"):
            self._tabs.set(name)
        key = name.lower().replace(" ", "_")
        if hasattr(self, "_nav_buttons"):
            for k, btn in self._nav_buttons.items():
                if k == key:
                    btn.configure(fg_color="#312e81", text_color="#a5b4fc")
                else:
                    btn.configure(fg_color="transparent", text_color="#94a3b8")

    def _make_nav_button(self, parent, key, text, icon, command, active=False, primary=False):
        if primary:
            btn = ctk.CTkButton(
                parent, text=f"{icon}  {text}", command=command,
                height=38, corner_radius=10, fg_color=ACCENT,
                hover_color=ACCENT2, text_color="white",
                font=ctk.CTkFont(size=13, weight="bold"), anchor="w"
            )
        else:
            btn = ctk.CTkButton(
                parent, text=f"{icon}  {text}", command=command,
                height=36, corner_radius=10,
                fg_color="#312e81" if active else "transparent",
                hover_color="#334155",
                text_color="#a5b4fc" if active else "#94a3b8",
                font=FONT_BODY, anchor="w"
            )
        btn.grid(sticky="ew", pady=2)
        if key:
            self._nav_buttons[key] = btn
        return btn

    def _build_sidebar(self):
        self._nav_buttons = {}

        SB_BG      = "#404d62"
        SB_SECTION = "#94a3b8"
        SB_BORDER  = "#334155"
        SB_HOVER   = "#334155"
        SB_ACTIVE  = "#312e81"
        SB_CARD    = "#4E535F"
        self._SB_BG = SB_BG; self._SB_SECTION = SB_SECTION
        self._SB_BORDER = SB_BORDER; self._SB_HOVER = SB_HOVER
        self._SB_ACTIVE = SB_ACTIVE; self._SB_CARD = SB_CARD

        sb_outer = ctk.CTkFrame(
            self, width=250, corner_radius=0,
            fg_color=SB_BG, border_width=0
        )
        sb_outer.grid(row=0, column=0, sticky="nsew")
        sb_outer.grid_propagate(False)
        sb_outer.grid_columnconfigure(0, weight=1)
        sb_outer.grid_rowconfigure(0, weight=1)

        # Scrollable sidebar so the Method Info card is always reachable on smaller screens.
        sb = ctk.CTkScrollableFrame(
            sb_outer, fg_color=SB_BG, corner_radius=0,
            scrollbar_button_color=SB_BORDER, scrollbar_button_hover_color=SB_SECTION
        )
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_columnconfigure(0, weight=1)

        # Logo area — same structure as the HTML sidebar
        logo = ctk.CTkFrame(sb, fg_color="transparent")
        logo.grid(row=0, column=0, sticky="ew", padx=18, pady=(24, 18))
        logo.grid_columnconfigure(1, weight=1)

        # Brand logo. Uses logo.ico when it is available; otherwise falls back to the indigo icon box.
        try:
            self._sidebar_logo_img = ctk.CTkImage(
                light_image=Image.open(resource_path("logo.ico")),
                dark_image=Image.open(resource_path("logo.ico")),
                size=(44, 44),
            )
            ctk.CTkLabel(logo, text="", image=self._sidebar_logo_img).grid(
                row=0, column=0, sticky="w"
            )
        except Exception:
            icon_box = ctk.CTkFrame(logo, width=44, height=44, fg_color=ACCENT, corner_radius=10)
            icon_box.grid(row=0, column=0, sticky="w")
            icon_box.grid_propagate(False)
            ctk.CTkLabel(icon_box, text="▦", font=ctk.CTkFont(size=22, weight="bold"),
                         text_color="white").place(relx=.5, rely=.5, anchor="center")

        ctk.CTkLabel(logo, text="NEST", font=ctk.CTkFont(size=24, weight="bold"),
                     text_color="#f0f4ff").grid(row=0, column=1, padx=(12, 0), sticky="w")

        ctk.CTkFrame(sb, height=1, fg_color="#334155").grid(row=1, column=0, sticky="ew")

        # Analysis section
        actions = ctk.CTkFrame(sb, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=12, pady=(20, 10))
        actions.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(actions, text="ANALYSIS", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#64748b").grid(row=0, column=0, sticky="w", padx=6, pady=(0, 8))
        self._make_nav_button(actions, None, "Run Analysis", "＋", self._run_analysis, primary=True)
        self._make_nav_button(actions, None, "Sensitivity", "◎", lambda: (self._run_sensitivity(), self._switch_tab("Sensitivity")))
        self._make_nav_button(actions, None, "Reset", "↻", self._reset)

        # Sections navigation — this is the main difference from the old Python version
        nav = ctk.CTkFrame(sb, fg_color="transparent")
        nav.grid(row=3, column=0, sticky="ew", padx=12, pady=(8, 10))
        nav.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(nav, text="SECTIONS", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#64748b").grid(row=0, column=0, sticky="w", padx=6, pady=(0, 8))

        self._make_nav_button(nav, "input", "Input", "＋", lambda: self._switch_tab("Input"), active=True)
        self._make_nav_button(nav, "results", "Results", "⌁", lambda: self._switch_tab("Results"))
        self._make_nav_button(nav, "cost_drivers", "Cost Drivers", "▮", lambda: self._switch_tab("Cost Drivers"))
        self._make_nav_button(nav, "sensitivity", "Sensitivity", "◎", lambda: self._switch_tab("Sensitivity"))
        self._make_nav_button(nav, "numerical_methods", "Num. Methods", "▤", lambda: self._switch_tab("Numerical Methods"))
        self._make_nav_button(nav, "equation_solver", "Equation Solver", "◩", lambda: self._switch_tab("Equation Solver"))

        # Method info box at the bottom, like the HTML card
        info = ctk.CTkFrame(sb, fg_color="#0f172a", corner_radius=12,
                            border_width=1, border_color="#334155", height=260)
        info.grid(row=4, column=0, sticky="ew", padx=12, pady=(10, 18))
        info.grid_propagate(False)
        info.grid_columnconfigure(0, weight=1)
        info.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(info, text="METHOD INFO", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#64748b").grid(row=0, column=0, sticky="w", padx=14, pady=(14, 6))
        self._method_box = ctk.CTkTextbox(
            info, height=205, corner_radius=10, fg_color="#0f172a", text_color="#94a3b8",
            font=FONT_MONO, border_width=0, wrap="word",
            scrollbar_button_color="#334155"
        )
        self._method_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        _isolate_scroll(self._method_box)
        self._method_box.insert("1.0",
            "Run an analysis to see\nhow each numerical method\nperformed on the\ncrossover equation.\n\n"
            "Click a row in the results\ntable to see details.")
        self._method_box.configure(state="disabled")

    # ─── MAIN AREA ─────────────────────────────────────────────

    def _build_main(self):
        main = ctk.CTkFrame(self, fg_color=BG_DEEP)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        # Top bar — closer to the HTML header
        topbar = ctk.CTkFrame(main, height=64, fg_color=BG_CARD,
                              corner_radius=0, border_width=1, border_color=BORDER)
        topbar.grid(row=0, column=0, sticky="ew")
        topbar.grid_columnconfigure(0, weight=1)
        topbar.grid_propagate(False)

        # Indigo accent stripe on left edge of topbar
        stripe = ctk.CTkFrame(topbar, width=4, fg_color=ACCENT, corner_radius=0)
        stripe.place(x=0, y=0, relheight=1.0)

        title_block = ctk.CTkFrame(topbar, fg_color="transparent")
        title_block.grid(row=0, column=0, sticky="w", padx=(18, 28), pady=8)
        ctk.CTkLabel(title_block, text="Business Decision Dashboard",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=TEXT_PRI).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(title_block, text="Enter two options, add cost components, then click Run Analysis.",
                     font=FONT_BODY, text_color=MUTED).grid(row=1, column=0, sticky="w")

        # Top-right buttons removed: Run Analysis and Profit Graph are already available in the sidebar/results area.

        # No top tab bar. Sidebar controls this content switcher.
        self._tabs = SidebarTabView(main)
        self._tabs.grid(row=1, column=0, sticky="nsew", padx=16, pady=12)

        for tab_name in ["Input", "Results", "Cost Drivers",
                         "Sensitivity", "Numerical Methods", "Equation Solver"]:
            self._tabs.add(tab_name)

        self._build_input_tab()
        self._build_results_tab()
        self._build_drivers_tab()
        self._build_sensitivity_tab()
        self._build_methods_tab()
        self._build_equation_solver_tab()

    # ─── INPUT TAB ─────────────────────────────────────────────

    def _build_input_tab(self):
        tab = self._tabs.tab("Input")
        tab.grid_columnconfigure((0, 1), weight=1)
        tab.grid_rowconfigure(0, weight=1)

        self._panel_a = OptionPanel(tab, "  Option A", ACCENT)
        self._panel_a.grid(row=0, column=0, sticky="nsew", padx=(6, 6), pady=8)

        self._panel_b = OptionPanel(tab, "  Option B", GREEN)
        self._panel_b.grid(row=0, column=1, sticky="nsew", padx=(6, 6), pady=8)

    # ─── RESULTS TAB ───────────────────────────────────────────

    def _build_results_tab(self):
        tab = self._tabs.tab("Results")
        tab.grid_columnconfigure((0, 1), weight=1)
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_rowconfigure(2, weight=2)

        # Metric cards row
        metrics_frame = ctk.CTkFrame(tab, fg_color="transparent")
        metrics_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=(6, 4))
        metrics_frame.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

        self._metric_labels = {}
        metrics = [
            ("profit_a",  "Profit A (own vol)",  "—", ACCENT),
            ("profit_b",  "Profit B (own vol)",  "—", GREEN),
            ("better",    "Better option",        "—", GOLD),
            ("crossover", "Crossover point",      "—", PURPLE),
            ("be_a",      "Break-even A",         "—", "#0891b2"),
            ("be_b",      "Break-even B",         "—", "#0891b2"),
        ]
        for col, (key, lbl, default, color) in enumerate(metrics):
            mcard = card_frame(metrics_frame)
            mcard.grid(row=0, column=col, sticky="ew", padx=3)
            mcard.grid_columnconfigure(0, weight=1)
            # Colored left-edge accent stripe
            stripe = ctk.CTkFrame(mcard, width=4, fg_color=color, corner_radius=0)
            stripe.place(x=0, y=0, relheight=1.0)
            muted_label(mcard, lbl).grid(row=0, column=0, padx=(18, 12), pady=(10, 2))
            val = ctk.CTkLabel(mcard, text=default,
                               font=ctk.CTkFont(size=17, weight="bold"), text_color=color)
            val.grid(row=1, column=0, padx=(18, 12), pady=(0, 10))
            self._metric_labels[key] = val

        # Comparison box
        left = card_frame(tab)
        left.grid(row=1, column=0, sticky="nsew", padx=(6, 4), pady=4)
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)
        section_label(left, "Comparison at each option's own expected volume").grid(
            row=0, column=0, padx=14, pady=(12, 4), sticky="w")
        self._comparison_box = ctk.CTkTextbox(
            left, height=220, corner_radius=10, fg_color=BG_PANEL,
            text_color=TEXT_PRI, font=FONT_MONO, border_width=0,
            wrap="none")
        self._comparison_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        _isolate_scroll(self._comparison_box)

        # Recommendation box
        right = card_frame(tab)
        right.grid(row=1, column=1, sticky="nsew", padx=(4, 6), pady=4)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        section_label(right, "Recommendation", GOLD).grid(
            row=0, column=0, padx=14, pady=(12, 4), sticky="w")
        self._reco_box = ctk.CTkTextbox(
            right, height=220, corner_radius=10, fg_color=BG_PANEL,
            text_color=TEXT_PRI, font=FONT_MONO, border_width=0,
            wrap="word")
        self._reco_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        _isolate_scroll(self._reco_box)

        # Profit vs Volume graph directly inside Results tab
        graph_wrap = ctk.CTkFrame(tab, fg_color="transparent")
        graph_wrap.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=6, pady=(10, 6))
        graph_wrap.grid_columnconfigure(0, weight=1)
        graph_wrap.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            graph_wrap, text="PROFIT VS VOLUME",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=MUTED
        ).grid(row=0, column=0, sticky="w", padx=2, pady=(0, 8))

        graph_card = card_frame(graph_wrap)
        graph_card.grid(row=1, column=0, sticky="nsew")
        graph_card.grid_columnconfigure(0, weight=1)
        graph_card.grid_rowconfigure(0, weight=1)

        self._res_fig = Figure(figsize=(8.5, 3.0), dpi=100, facecolor="#e8eaf0")
        self._res_ax = self._res_fig.add_subplot(111)
        self._res_ax.set_facecolor("#eaecf5")
        self._style_ax(self._res_ax)

        self._res_canvas = FigureCanvasTkAgg(self._res_fig, master=graph_card)
        self._res_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=12, pady=12)

    # ─── COST DRIVERS TAB ──────────────────────────────────────

    def _build_drivers_tab(self):
        tab = self._tabs.tab("Cost Drivers")
        tab.grid_columnconfigure((0, 1), weight=1)
        tab.grid_rowconfigure(0, weight=1)

        for col, (key, title) in enumerate([("drivers_a", "Cost Drivers — Option A"),
                                            ("drivers_b", "Cost Drivers — Option B")]):
            f = card_frame(tab)
            f.grid(row=0, column=col, sticky="nsew",
                   padx=(6, 4) if col == 0 else (4, 6), pady=8)
            f.grid_columnconfigure(0, weight=1)
            f.grid_rowconfigure(1, weight=1)
            section_label(f, title).grid(row=0, column=0, padx=14, pady=(12, 4), sticky="w")
            cols = ("Component", "Category", "Amount ($)", "% of Total")
            tree = ttk.Treeview(f, columns=cols, show="headings",
                                style="Pro.Treeview", height=14)
            for c in cols:
                tree.heading(c, text=c)
            tree.column("Component",  width=160, anchor="w")
            tree.column("Category",   width=110, anchor="center")
            tree.column("Amount ($)", width=120, anchor="e")
            tree.column("% of Total", width=90,  anchor="e")
            tree.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
            setattr(self, f"_tree_{key}", tree)

    # ─── SENSITIVITY TAB ───────────────────────────────────────

    def _build_sensitivity_tab(self):
        tab = self._tabs.tab("Sensitivity")
        tab.grid_columnconfigure((0, 1), weight=1)
        tab.grid_rowconfigure(1, weight=1)

        ctrl = card_frame(tab)
        ctrl.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=(8, 4))
        ctrl.grid_columnconfigure((1, 3), weight=1)

        muted_label(ctrl, "What-if analysis:").grid(row=0, column=0, padx=(14, 8), pady=10)
        muted_label(ctrl, "Cost change (%)").grid(row=0, column=2, padx=(16, 4), pady=10)

        self._sens_pct_var = ctk.StringVar(value="10")
        ctk.CTkEntry(ctrl, textvariable=self._sens_pct_var, width=70, height=32,
                     fg_color=BG_ENTRY, border_color=BORDER2, border_width=1,
                     text_color=TEXT_PRI, font=FONT_BODY,
                     ).grid(row=0, column=3, padx=4, pady=10, sticky="w")

        ctk.CTkButton(ctrl, text="Run Sensitivity", command=self._run_sensitivity,
                      height=34, fg_color=ACCENT, hover_color=ACCENT2,
                      font=ctk.CTkFont(size=12, weight="bold"),
                      ).grid(row=0, column=4, padx=(12, 14), pady=10)

        for col, (key, title) in enumerate([("sens_a", "Sensitivity — Option A"),
                                            ("sens_b", "Sensitivity — Option B")]):
            f = card_frame(tab)
            f.grid(row=1, column=col, sticky="nsew",
                   padx=(6, 4) if col == 0 else (4, 6), pady=4)
            f.grid_columnconfigure(0, weight=1)
            f.grid_rowconfigure(1, weight=1)
            section_label(f, title).grid(row=0, column=0, padx=14, pady=(12, 4), sticky="w")
            cols = ("Component", "Category", "Profit impact ($)")
            tree = ttk.Treeview(f, columns=cols, show="headings",
                                style="Pro.Treeview", height=12)
            for c in cols:
                tree.heading(c, text=c)
            tree.column("Component",       width=170, anchor="w")
            tree.column("Category",        width=120, anchor="center")
            tree.column("Profit impact ($)", width=140, anchor="e")
            tree.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
            setattr(self, f"_tree_{key}", tree)

    # ─── NUMERICAL METHODS TAB ─────────────────────────────────

    def _build_methods_tab(self):
        tab = self._tabs.tab("Numerical Methods")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        muted_label(tab,
            "All five methods solving  Profit_A(x) − Profit_B(x) = 0  "
            "(crossover equation) — click a row for details"
        ).grid(row=0, column=0, padx=14, pady=(10, 4), sticky="w")

        f = card_frame(tab)
        f.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(0, weight=1)

        cols = ("Method", "Root found", "Iterations", "Residual error", "Status")
        self._methods_tree = ttk.Treeview(f, columns=cols, show="headings",
                                          style="Pro.Treeview", height=8)
        for c in cols:
            self._methods_tree.heading(c, text=c)
        self._methods_tree.column("Method",         width=160, anchor="w")
        self._methods_tree.column("Root found",     width=170, anchor="center")
        self._methods_tree.column("Iterations",     width=110, anchor="center")
        self._methods_tree.column("Residual error", width=150, anchor="center")
        self._methods_tree.column("Status",         width=110, anchor="center")
        self._methods_tree.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self._methods_tree.bind("<<TreeviewSelect>>", self._on_method_select)

        detail = card_frame(tab)
        detail.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 6))
        detail.grid_columnconfigure(0, weight=1)
        section_label(detail, "Method explanation").grid(
            row=0, column=0, padx=14, pady=(10, 2), sticky="w")
        self._method_detail_box = ctk.CTkTextbox(
            detail, height=110, corner_radius=10, fg_color=BG_PANEL,
            text_color=TEXT_PRI, font=FONT_MONO, border_width=0,
            wrap="word")
        self._method_detail_box.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        _isolate_scroll(self._method_detail_box)
        self._method_detail_box.insert("1.0", "Click a row above to see details.")
        self._method_detail_box.configure(state="disabled")

    # ─── EQUATION SOLVER TAB ───────────────────────────────────

    def _build_equation_solver_tab(self):
        tab = self._tabs.tab("Equation Solver")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        input_card = card_frame(tab)
        input_card.grid(row=0, column=0, sticky="ew", padx=6, pady=(8, 4))
        input_card.grid_columnconfigure(1, weight=1)

        section_label(input_card, "f(x) =").grid(
            row=0, column=0, padx=(16, 8), pady=14)

        self._eq_var = ctk.StringVar(value="x**2+2*x-1")
        ctk.CTkEntry(input_card, textvariable=self._eq_var, height=38,
                     fg_color=BG_ENTRY, border_color=BORDER2, border_width=1,
                     text_color=TEXT_PRI, font=ctk.CTkFont(family="Segoe UI", size=13),
                     ).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=14)

        muted_label(input_card, "x from").grid(row=0, column=2, padx=(8, 4), pady=14)

        self._eq_lo = ctk.StringVar(value="-12")
        ctk.CTkEntry(input_card, textvariable=self._eq_lo, width=72, height=38,
                     fg_color=BG_ENTRY, border_color=BORDER2, border_width=1,
                     text_color=TEXT_PRI, font=FONT_BODY,
                     ).grid(row=0, column=3, padx=4, pady=14)

        muted_label(input_card, "to").grid(row=0, column=4, padx=4, pady=14)

        self._eq_hi = ctk.StringVar(value="13")
        ctk.CTkEntry(input_card, textvariable=self._eq_hi, width=72, height=38,
                     fg_color=BG_ENTRY, border_color=BORDER2, border_width=1,
                     text_color=TEXT_PRI, font=FONT_BODY,
                     ).grid(row=0, column=5, padx=4, pady=14)

        ctk.CTkButton(input_card, text="Solve", height=38, width=100,
                      fg_color=ACCENT, hover_color=ACCENT2,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._solve_equation,
                      ).grid(row=0, column=6, padx=(8, 16), pady=14)

        hint = card_frame(tab)
        hint.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 4))
        hint.grid_columnconfigure(0, weight=1)
        muted_label(hint,
            "Write x as variable. Use ** for powers, * for multiply.  "
            "Examples:  x**3 - 2*x + 1  |  sin(x) - 0.5  |  sqrt(x) - 3",
        ).grid(row=0, column=0, padx=14, pady=8, sticky="w")

        results_frame = ctk.CTkFrame(tab, fg_color="transparent")
        results_frame.grid(row=2, column=0, sticky="nsew", padx=6, pady=4)
        results_frame.grid_columnconfigure(0, weight=3)
        results_frame.grid_columnconfigure(1, weight=2)
        results_frame.grid_rowconfigure(0, weight=1)

        graph_card = card_frame(results_frame)
        graph_card.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        graph_card.grid_columnconfigure(0, weight=1)
        graph_card.grid_rowconfigure(1, weight=1)

        self._eq_best_label = ctk.CTkLabel(
            graph_card,
            text="Best method: —",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=ACCENT,
            anchor="w",
        )
        self._eq_best_label.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 0))

        self._eq_fig = Figure(figsize=(6, 4), dpi=100, facecolor="#e8eaf0")
        self._eq_ax  = self._eq_fig.add_subplot(111)
        self._eq_ax.set_facecolor("#eaecf5")
        self._style_ax(self._eq_ax)
        self._eq_canvas = FigureCanvasTkAgg(self._eq_fig, master=graph_card)
        self._eq_canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

        right = ctk.CTkFrame(results_frame, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        roots_card = card_frame(right)
        roots_card.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        roots_card.grid_columnconfigure(0, weight=1)
        section_label(roots_card, "Roots found", GOLD).grid(
            row=0, column=0, padx=14, pady=(10, 4), sticky="w")
        self._roots_box = ctk.CTkTextbox(
            roots_card, height=90, corner_radius=8,
            fg_color=BG_PANEL, text_color=TEXT_PRI, font=FONT_MONO, border_width=0)
        self._roots_box.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        _isolate_scroll(self._roots_box)
        self._roots_box.insert("1.0", "Solve an equation to see roots.")
        self._roots_box.configure(state="disabled")

        eq_methods_card = card_frame(right)
        eq_methods_card.grid(row=1, column=0, sticky="nsew")
        eq_methods_card.grid_columnconfigure(0, weight=1)
        eq_methods_card.grid_rowconfigure(1, weight=1)
        section_label(eq_methods_card, "Method results").grid(
            row=0, column=0, padx=14, pady=(10, 4), sticky="w")
        cols = ("Method", "Root", "Itr", "Error", "Status")
        self._eq_methods_tree = ttk.Treeview(
            eq_methods_card, columns=cols, show="headings",
            style="Pro.Treeview", height=8)
        for c in cols:
            self._eq_methods_tree.heading(c, text=c)
        self._eq_methods_tree.column("Method", width=120, anchor="w")
        self._eq_methods_tree.column("Root",   width=110, anchor="center")
        self._eq_methods_tree.column("Itr",    width=50,  anchor="center")
        self._eq_methods_tree.column("Error",  width=90,  anchor="center")
        self._eq_methods_tree.column("Status", width=90,  anchor="center")
        self._eq_methods_tree.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

    # ─── STYLE HELPERS ─────────────────────────────────────────

    def _style_ax(self, ax):
        for sp in ax.spines.values():
            sp.set_color("#bec8db")
            sp.set_linewidth(1.2)
        ax.tick_params(colors="#64748b", labelsize=10)
        ax.title.set_color(TEXT_PRI)
        ax.title.set_fontweight("bold")
        ax.xaxis.label.set_color(MUTED)
        ax.yaxis.label.set_color(MUTED)

    # ─── RUN ANALYSIS ──────────────────────────────────────────

    def _analytic_crossover(self, opt_a, opt_b):
        """Exact crossover for the linear profit models used by the business options."""
        slope_a = opt_a.revenue_per_unit - opt_a.variable_rate()
        slope_b = opt_b.revenue_per_unit - opt_b.variable_rate()
        fixed_a = opt_a.fixed_total()
        fixed_b = opt_b.fixed_total()
        denom = slope_a - slope_b
        if abs(denom) < 1e-12:
            return None
        root = (fixed_a - fixed_b) / denom
        if root < 0 or not math.isfinite(root):
            return None
        return float(root)

    def _run_analysis(self):
        opt_a = self._panel_a.build_option()
        opt_b = self._panel_b.build_option()
        if opt_a is None or opt_b is None:
            messagebox.showerror("Input error",
                "Please fill in Revenue/unit and Expected volume for both options.")
            return

        self._option_a = opt_a
        self._option_b = opt_b
        self._comparison_engine = ComparisonEngine(opt_a, opt_b)

        vol_a = max(opt_a.expected_volume, 0.1)
        vol_b = max(opt_b.expected_volume, 0.1)

        cr_results, cr_roots, best_name, best_cross = self._comparison_engine.find_crossover()

        # Numerical scanning can miss a crossover exactly at x=0 or just outside scan grid.
        # Because the business profit functions are linear, also compute the exact crossover.
        exact_cross = self._analytic_crossover(opt_a, opt_b)
        if exact_cross is not None and not any(abs(exact_cross - r) <= 1e-6 for r in cr_roots):
            cr_roots = sorted([*cr_roots, exact_cross])

        self._crossover_results = cr_results
        self._crossover_roots   = cr_roots
        self._best_crossover    = best_cross

        be_a = self._comparison_engine.find_breakeven_a()
        be_b = self._comparison_engine.find_breakeven_b()

        s = self._comparison_engine.summary_at_volumes(vol_a, vol_b)

        # Metric cards
        def fmt(v):
            return f"${v:,.0f}"
        self._metric_labels["profit_a"].configure(text=fmt(s["profit_a"]))
        self._metric_labels["profit_b"].configure(text=fmt(s["profit_b"]))
        self._metric_labels["better"].configure(text=s["better"])
        self._metric_labels["crossover"].configure(
            text=f"{cr_roots[0]:,.1f} units" if cr_roots else "None")
        self._metric_labels["be_a"].configure(
            text=f"{be_a:,.1f} units" if be_a else "None")
        self._metric_labels["be_b"].configure(
            text=f"{be_b:,.1f} units" if be_b else "None")

        # Comparison textbox
        comp_lines = [
            f"{'Metric':<22} {'Option A':>16} {'Option B':>16}",
            "─" * 56,
            f"{'Expected Volume':<22} {vol_a:>16,.1f} {vol_b:>16,.1f}",
            f"{'Revenue/unit':<22} {opt_a.revenue_per_unit:>16,.2f} {opt_b.revenue_per_unit:>16,.2f}",
            f"{'Total Revenue':<22} {opt_a.total_revenue(vol_a):>16,.2f} {opt_b.total_revenue(vol_b):>16,.2f}",
            f"{'Total Cost':<22} {opt_a.total_cost(vol_a):>16,.2f} {opt_b.total_cost(vol_b):>16,.2f}",
            f"{'Net Profit':<22} {s['profit_a']:>16,.2f} {s['profit_b']:>16,.2f}",
            f"{'Margin %':<22} {s['margin_a']:>15.1f}% {s['margin_b']:>15.1f}%",
            f"{'Cost/unit':<22} {s['cost_per_unit_a']:>16,.2f} {s['cost_per_unit_b']:>16,.2f}",
            f"{'Break-even':<22} {str(f'{be_a:,.1f}') if be_a else 'Not found':>16} {str(f'{be_b:,.1f}') if be_b else 'Not found':>16}",
        ]
        self._comparison_box.configure(state="normal")
        self._comparison_box.delete("1.0", "end")
        self._comparison_box.insert("1.0", "\n".join(comp_lines))
        self._comparison_box.configure(state="disabled")

        # Recommendation
        reco_eng = RecommendationEngine(self._comparison_engine)
        reco = reco_eng.generate(cr_roots, be_a, be_b, vol_a, vol_b)
        self._reco_box.configure(state="normal")
        self._reco_box.delete("1.0", "end")
        self._reco_box.insert("1.0", reco)
        self._reco_box.configure(state="disabled")

        self._populate_drivers(opt_a, opt_b, vol_a, vol_b)
        self._populate_methods_table(cr_results)
        self._draw_results_graph()
        self._update_sidebar_info(best_name, best_cross)
        self._switch_tab("Results")

    def _populate_drivers(self, opt_a, opt_b, vol_a, vol_b):
        for tree_key, opt, vol in [("_tree_drivers_a", opt_a, vol_a),
                                   ("_tree_drivers_b", opt_b, vol_b)]:
            tree = getattr(self, tree_key)
            for item in tree.get_children():
                tree.delete(item)
            for name, cat, amt, pct in opt.cost_breakdown(vol):
                tree.insert("", "end", values=(name, cat, f"{amt:,.2f}", f"{pct:.1f}%"))

    def _populate_methods_table(self, results):
        for item in self._methods_tree.get_children():
            self._methods_tree.delete(item)

        method_info = {
            "Bisection": (
                "c = (a+b)/2 — guaranteed convergence inside bracket. "
                "Very safe but slow (linear convergence)."
            ),
            "Brent": (
                "Combines bisection safety with secant/inverse-quadratic interpolation. "
                "Excellent general-purpose bracketed solver — superlinear convergence."
            ),
            "Newton": (
                "x_(n+1) = x_n - f(x_n)/f'(x_n) — quadratic convergence near root, "
                "but can diverge with a poor starting point."
            ),
            "Secant": (
                "Approximates Newton without computing an explicit derivative. "
                "Superlinear convergence; can also diverge."
            ),
            "Bisection-Newton": (
                "Hybrid: Phase 1 uses bisection to safely narrow the bracket to a reliable "
                "region, then Phase 2 switches to Newton's method for fast quadratic "
                "convergence. Combines the safety of bisection with the speed of Newton."
            ),
        }

        self._method_explanations = {}
        for name, (root, itr, err, status) in results.items():
            root_str = f"{root:,.4f}" if root is not None else "—"
            err_str  = f"{err:.2e}"   if err  is not None else "—"
            itr_str  = str(itr)
            tag = "ok" if status == "Success" else "fail"
            iid = self._methods_tree.insert("", "end",
                values=(name, root_str, itr_str, err_str, status), tags=(tag,))
            self._method_explanations[iid] = (
                f"Method: {name}\n\n"
                f"Formula / logic:\n{method_info.get(name, '')}\n\n"
                f"Root found: {root_str}   |   Iterations: {itr_str}   |   "
                f"Residual: {err_str}   |   Status: {status}"
            )

        self._methods_tree.tag_configure("ok",   foreground=GREEN)
        self._methods_tree.tag_configure("fail", foreground=RED)

    def _update_sidebar_info(self, best_name, best):
        if best_name and best:
            root, itr, err, status = best
            txt = (
                f"Best method: {best_name}\n\n"
                f"Crossover root:  {root:,.4f} units\n"
                f"Iterations:      {itr}\n"
                f"Residual error:  {err:.2e}\n"
                f"Status:          {status}\n\n"
                f"The crossover equation\n"
                f"Profit_A(x) − Profit_B(x) = 0\n"
                f"was solved using all five\nnumerical methods.\n\n"
                f"Best method rule:\n"
                f"1) smaller error\n"
                f"2) if tied, fewer iterations\n\n"
                f"Root = volume at which\nboth options earn equal\nprofit."
            )
        else:
            txt = "No crossover found in range.\n\nOne option dominates the\nother across all volumes."

        self._method_box.configure(state="normal")
        self._method_box.delete("1.0", "end")
        self._method_box.insert("1.0", txt)
        self._method_box.configure(state="disabled")

    def _on_method_select(self, event):
        sel = self._methods_tree.selection()
        if not sel:
            return
        explanation = self._method_explanations.get(sel[0], "No details.")
        self._method_detail_box.configure(state="normal")
        self._method_detail_box.delete("1.0", "end")
        self._method_detail_box.insert("1.0", explanation)
        self._method_detail_box.configure(state="disabled")

    # ─── SENSITIVITY ───────────────────────────────────────────

    def _run_sensitivity(self):
        if self._option_a is None or self._option_b is None:
            messagebox.showinfo("Info", "Run an analysis first.")
            return
        try:
            pct = float(self._sens_pct_var.get())
        except ValueError:
            messagebox.showerror("Error", "Enter a valid percentage (e.g. 10).")
            return

        vol_a = max(self._option_a.expected_volume, 0.1)
        vol_b = max(self._option_b.expected_volume, 0.1)

        for tree_key, opt, vol in [("_tree_sens_a", self._option_a, vol_a),
                                   ("_tree_sens_b", self._option_b, vol_b)]:
            tree = getattr(self, tree_key)
            for item in tree.get_children():
                tree.delete(item)
            se = SensitivityEngine(opt)
            for name, cat, delta, _ in se.rank_sensitivity(vol, pct):
                tag = "pos" if delta >= 0 else "neg"
                tree.insert("", "end", values=(name, cat, f"{delta:+,.2f}"), tags=(tag,))
            tree.tag_configure("pos", foreground=GREEN)
            tree.tag_configure("neg", foreground=RED)

        self._switch_tab("Sensitivity")

    def _draw_profit_graph_on_axis(self, ax, canvas):
        if self._comparison_engine is None:
            return

        eng = self._comparison_engine
        max_vol = max(eng.a.expected_volume, eng.b.expected_volume, 100) * 2.5
        xs = np.linspace(0, max_vol, 500)
        ys_a = [eng.a.profit(x) for x in xs]
        ys_b = [eng.b.profit(x) for x in xs]

        ax.clear()
        ax.set_facecolor("#eaecf5")
        self._style_ax(ax)

        ax.plot(xs, ys_a, linewidth=2.5, color=ACCENT, label=eng.a.name)
        ax.plot(xs, ys_b, linewidth=2.5, color=GREEN, label=eng.b.name)
        ax.axhline(0, color="#bec8db", linestyle="--", linewidth=1.2)

        va = max(eng.a.expected_volume, 0.1)
        vb = max(eng.b.expected_volume, 0.1)
        pa = eng.a.profit(va)
        pb = eng.b.profit(vb)

        # Expected-volume markers. They are two different business points:
        # Option A is plotted at A's expected volume, Option B at B's expected volume.
        ax.scatter([va], [pa], s=62, color=ACCENT, edgecolors="white", linewidths=1.2, zorder=6)
        ax.scatter([vb], [pb], s=62, color=GREEN, edgecolors="white", linewidths=1.2, zorder=6)

        # Separate annotations, so both arrows point to their own correct colored point.
        ax.annotate(
            f"{eng.a.name}\n({va:,.0f}, ${pa:,.0f})",
            xy=(va, pa), xytext=(-30, 32), textcoords="offset points",
            ha="right", fontsize=9, color="white",
            bbox=dict(boxstyle="round,pad=0.40", fc=ACCENT, ec=ACCENT, alpha=0.95),
            arrowprops=dict(arrowstyle="->", color=ACCENT, lw=1.2),
            zorder=8,
        )
        ax.annotate(
            f"{eng.b.name}\n({vb:,.0f}, ${pb:,.0f})",
            xy=(vb, pb), xytext=(28, 32), textcoords="offset points",
            ha="left", fontsize=9, color="white",
            bbox=dict(boxstyle="round,pad=0.40", fc=GREEN, ec=GREEN, alpha=0.95),
            arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.2),
            zorder=8,
        )

        for r in self._crossover_roots:
            ya = eng.a.profit(r)
            ax.scatter([r], [ya], s=90, color=GOLD, edgecolors="white", linewidths=1.2, zorder=7)
            ax.axvline(r, color=GOLD, alpha=0.45, linestyle=":", linewidth=1.2)
            ax.annotate(
                f"Crossover\n{r:,.2f} units\nProfit: ${ya:,.0f}",
                xy=(r, ya), xytext=(12, -45), textcoords="offset points",
                fontsize=9, color=GOLD,
                bbox=dict(boxstyle="round,pad=0.35", fc=BG_CARD, ec=GOLD, alpha=0.95),
                arrowprops=dict(arrowstyle="->", color=GOLD, lw=1),
                zorder=9,
            )

        if not self._crossover_roots:
            ax.text(0.01, 0.96, "No crossover in positive volume range",
                    transform=ax.transAxes, ha="left", va="top", fontsize=9, color=MUTED,
                    bbox=dict(boxstyle="round,pad=0.35", fc=BG_CARD, ec=BORDER, alpha=0.95))

        ax.set_title("Profit comparison", color=TEXT_PRI, fontsize=11, pad=8)
        ax.set_xlabel("Volume (units)", color=MUTED)
        ax.set_ylabel("Profit ($)", color=MUTED)
        ax.grid(True, alpha=0.5, color="#d1d8e8", linestyle="-")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x, pos: f"${x:,.0f}"))
        ax.legend(facecolor="#f0f2f8", edgecolor=BORDER, labelcolor=TEXT_PRI, loc="best")

        # Give the chart breathing room so labels/tooltips are not clipped at the edges.
        ax.margins(x=0.06, y=0.18)

        # Live mouse tracker: move the mouse over the chart and see both profits at that volume.
        hover_line = ax.axvline(0, color=MUTED, linestyle="--", linewidth=1.0, alpha=0.0, zorder=5)
        hover_a = ax.scatter([], [], s=70, color=ACCENT, edgecolors="white", linewidths=1.0, zorder=10)
        hover_b = ax.scatter([], [], s=70, color=GREEN, edgecolors="white", linewidths=1.0, zorder=10)
        hover_text = ax.annotate(
            "", xy=(0, 0), xytext=(18, 18), textcoords="offset points",
            fontsize=9, color="white",
            bbox=dict(boxstyle="round,pad=0.45", fc="#2f2f2f", ec="#2f2f2f", alpha=0.95),
            arrowprops=dict(arrowstyle="->", color="#2f2f2f", lw=1),
            visible=False,
            annotation_clip=False,
            zorder=11,
        )

        def on_move(event):
            if event.inaxes != ax or event.xdata is None:
                hover_line.set_alpha(0.0)
                hover_a.set_offsets(np.empty((0, 2)))
                hover_b.set_offsets(np.empty((0, 2)))
                hover_text.set_visible(False)
                canvas.draw_idle()
                return

            x = max(0.0, min(float(event.xdata), max_vol))
            ya = eng.a.profit(x)
            yb = eng.b.profit(x)
            better = eng.a.name if ya >= yb else eng.b.name
            diff = abs(ya - yb)

            hover_line.set_xdata([x, x])
            hover_line.set_alpha(0.55)
            hover_a.set_offsets(np.array([[x, ya]]))
            hover_b.set_offsets(np.array([[x, yb]]))

            top_y = max(ya, yb)
            hover_text.xy = (x, top_y)
            # Keep the live info box inside the visible chart area.
            x_min, x_max = ax.get_xlim()
            y_min, y_max = ax.get_ylim()
            hover_text.set_ha("right" if x > x_min + 0.72 * (x_max - x_min) else "left")
            hover_text.set_va("top" if top_y > y_min + 0.72 * (y_max - y_min) else "bottom")
            hover_text.set_position((-18, -18) if x > x_min + 0.72 * (x_max - x_min) else (18, 18))
            hover_text.set_text(
                f"Volume: {x:,.2f} units\n"
                f"{eng.a.name}: ${ya:,.0f}\n"
                f"{eng.b.name}: ${yb:,.0f}\n"
                f"Better: {better}\n"
                f"Difference: ${diff:,.0f}"
            )
            hover_text.set_visible(True)
            canvas.draw_idle()

        # Avoid stacking multiple motion callbacks after repeated analysis runs.
        if not hasattr(self, "_graph_motion_cids"):
            self._graph_motion_cids = {}
        old_cid = self._graph_motion_cids.get(canvas)
        if old_cid is not None:
            try:
                canvas.mpl_disconnect(old_cid)
            except Exception:
                pass
        self._graph_motion_cids[canvas] = canvas.mpl_connect("motion_notify_event", on_move)

        ax.figure.subplots_adjust(left=0.10, right=0.96, top=0.84, bottom=0.20)
        canvas.draw()

    def _draw_results_graph(self):
        if hasattr(self, "_res_ax") and hasattr(self, "_res_canvas"):
            self._draw_profit_graph_on_axis(self._res_ax, self._res_canvas)

    # ─── GRAPH WINDOW ──────────────────────────────────────────

    def _show_graph(self):
        if self._option_a is None or self._option_b is None:
            messagebox.showinfo("Info", "Run an analysis first.")
            return

        if self._graph_win is None or not self._graph_win.winfo_exists():
            self._graph_win = ctk.CTkToplevel(self)
            self._graph_win.title("NEST — Profit Comparison Graph")
            self._graph_win.geometry("1100x720")
            self._graph_win.configure(fg_color=BG_DEEP)
            self._graph_win.protocol("WM_DELETE_WINDOW", self._graph_win.destroy)

            outer = card_frame(self._graph_win)
            outer.pack(fill="both", expand=True, padx=14, pady=14)
            section_label(outer, "Profit vs Volume — Option A vs Option B").pack(
                anchor="w", padx=18, pady=(14, 4))

            self._fig = Figure(figsize=(11, 6), dpi=100, facecolor="#e8eaf0")
            self._ax  = self._fig.add_subplot(111)
            self._ax.set_facecolor("#eaecf5")
            self._style_ax(self._ax)

            self._canvas = FigureCanvasTkAgg(self._fig, master=outer)
            self._canvas.get_tk_widget().pack(fill="both", expand=True, padx=12, pady=12)

        self._draw_comparison_graph()
        self._graph_win.deiconify()
        self._graph_win.lift()
        self._graph_win.focus_force()

    def _draw_comparison_graph(self):
        if hasattr(self, "_ax") and hasattr(self, "_canvas"):
            self._draw_profit_graph_on_axis(self._ax, self._canvas)

    # ─── EQUATION SOLVER ───────────────────────────────────────

    def _solve_equation(self):
        expr = self._eq_var.get().strip()
        try:
            lo = float(self._eq_lo.get())
            hi = float(self._eq_hi.get())
        except ValueError:
            messagebox.showerror("Error", "Enter valid numeric bounds.")
            return

        safe_names = {k: getattr(__import__("math"), k)
                      for k in dir(__import__("math")) if not k.startswith("_")}
        safe_names["abs"] = abs

        expr_py = re.sub(r'\^', '**', expr)

        def f(x):
            try:
                return float(eval(expr_py, {"__builtins__": {}}, {**safe_names, "x": x}))
            except Exception:
                return None

        try:
            f(0.0)
        except Exception:
            messagebox.showerror("Error", "Could not parse expression.")
            return

        results, roots, best_name, best_data = run_all_methods(f, lo, hi)

        if best_name and best_data:
            best_root, best_itr, best_err, best_status = best_data
            self._eq_best_label.configure(
                text=f"Best method: {best_name}  |  root = {best_root:.6f}  |  iterations = {best_itr}  |  error = {best_err:.2e}",
                text_color=ACCENT,
            )
            sidebar_txt = (
                f"Equation Solver\n\n"
                f"Best method: {best_name}\n"
                f"Root:        {best_root:.8f}\n"
                f"Iterations:  {best_itr}\n"
                f"Error:       {best_err:.2e}\n"
                f"Status:      {best_status}\n\n"
                f"Expression:\n"
                f"f(x) = {expr}\n\n"
                f"The best method is chosen by:\n"
                f"1) smaller residual error\n"
                f"2) if tied, fewer iterations"
            )
        else:
            self._eq_best_label.configure(text="Best method: — no successful method", text_color=RED)
            sidebar_txt = "Equation Solver\n\nNo successful method found in the selected range. Try another interval."

        self._method_box.configure(state="normal")
        self._method_box.delete("1.0", "end")
        self._method_box.insert("1.0", sidebar_txt)
        self._method_box.configure(state="disabled")

        # Roots box
        self._roots_box.configure(state="normal")
        self._roots_box.delete("1.0", "end")
        if roots:
            self._roots_box.insert("1.0",
                "\n".join(f"Root {i+1}: x = {r:.8f}" for i, r in enumerate(roots)))
        else:
            self._roots_box.insert("1.0", "No roots found in the given range.")
        self._roots_box.configure(state="disabled")

        # Methods treeview
        for item in self._eq_methods_tree.get_children():
            self._eq_methods_tree.delete(item)
        for name, (root, itr, err, status) in results.items():
            tag = "ok" if status == "Success" else "fail"
            self._eq_methods_tree.insert("", "end", values=(
                name,
                f"{root:.6f}" if root is not None else "—",
                itr,
                f"{err:.2e}" if err is not None else "—",
                status,
            ), tags=(tag,))
        self._eq_methods_tree.tag_configure("ok",   foreground=GREEN)
        self._eq_methods_tree.tag_configure("fail", foreground=RED)

        # Graph
        n = 400
        xs = np.linspace(lo, hi, n)
        ys = []
        for x in xs:
            try:
                v = f(x)
                ys.append(v if v is not None and math.isfinite(v) else None)
            except Exception:
                ys.append(None)

        self._eq_ax.clear()
        self._eq_ax.set_facecolor("#eaecf5")
        self._style_ax(self._eq_ax)

        # Plot with gap handling
        seg_x, seg_y = [], []
        for x, y in zip(xs, ys):
            if y is None:
                if seg_x:
                    self._eq_ax.plot(seg_x, seg_y, color=ACCENT, linewidth=2.2)
                    seg_x, seg_y = [], []
            else:
                seg_x.append(x); seg_y.append(y)
        if seg_x:
            self._eq_ax.plot(seg_x, seg_y, color=ACCENT, linewidth=2.2, label="f(x)")

        self._eq_ax.axhline(0, color="#bec8db", linestyle="--", linewidth=1.2)
        for r in roots:
            try:
                yr = f(r)
                if yr is not None and math.isfinite(yr):
                    self._eq_ax.scatter([r], [yr], s=80, color=GOLD,
                                        edgecolors="white", linewidths=1.2, zorder=6)
            except Exception:
                pass

        self._eq_ax.set_title(f"f(x) = {expr}", color=TEXT_PRI, fontsize=11, pad=8)
        self._eq_ax.set_xlabel("x", color=MUTED)
        self._eq_ax.set_ylabel("f(x)", color=MUTED)
        self._eq_ax.grid(True, alpha=0.5, color="#d1d8e8", linestyle="-")
        self._eq_ax.margins(x=0.06, y=0.18)

        # Live mouse tracker for Equation Solver: shows x and f(x) while moving over the graph.
        eq_hover_line = self._eq_ax.axvline(lo, color=MUTED, linestyle="--", linewidth=1.0, alpha=0.0, zorder=5)
        eq_hover_point = self._eq_ax.scatter([], [], s=70, color=ACCENT, edgecolors="white", linewidths=1.0, zorder=10)
        eq_hover_text = self._eq_ax.annotate(
            "", xy=(0, 0), xytext=(18, 18), textcoords="offset points",
            fontsize=9, color="white",
            bbox=dict(boxstyle="round,pad=0.45", fc="#2f2f2f", ec="#2f2f2f", alpha=0.95),
            arrowprops=dict(arrowstyle="->", color="#2f2f2f", lw=1),
            visible=False,
            annotation_clip=False,
            zorder=11,
        )

        def on_eq_move(event):
            if event.inaxes != self._eq_ax or event.xdata is None:
                eq_hover_line.set_alpha(0.0)
                eq_hover_point.set_offsets(np.empty((0, 2)))
                eq_hover_text.set_visible(False)
                self._eq_canvas.draw_idle()
                return

            x = max(min(float(event.xdata), hi), lo)
            y = f(x)
            if y is None or not math.isfinite(y):
                eq_hover_line.set_alpha(0.0)
                eq_hover_point.set_offsets(np.empty((0, 2)))
                eq_hover_text.set_visible(False)
                self._eq_canvas.draw_idle()
                return

            eq_hover_line.set_xdata([x, x])
            eq_hover_line.set_alpha(0.55)
            eq_hover_point.set_offsets(np.array([[x, y]]))
            eq_hover_text.xy = (x, y)

            x_min, x_max = self._eq_ax.get_xlim()
            y_min, y_max = self._eq_ax.get_ylim()
            eq_hover_text.set_ha("right" if x > x_min + 0.72 * (x_max - x_min) else "left")
            eq_hover_text.set_va("top" if y > y_min + 0.72 * (y_max - y_min) else "bottom")
            eq_hover_text.set_position((-18, -18) if x > x_min + 0.72 * (x_max - x_min) else (18, 18))
            eq_hover_text.set_text(f"x: {x:,.6f}\nf(x): {y:,.6f}")
            eq_hover_text.set_visible(True)
            self._eq_canvas.draw_idle()

        if hasattr(self, "_eq_motion_cid") and self._eq_motion_cid is not None:
            try:
                self._eq_canvas.mpl_disconnect(self._eq_motion_cid)
            except Exception:
                pass
        self._eq_motion_cid = self._eq_canvas.mpl_connect("motion_notify_event", on_eq_move)

        self._eq_fig.subplots_adjust(left=0.10, right=0.96, top=0.86, bottom=0.16)
        self._eq_canvas.draw()

    # ─── RESET ─────────────────────────────────────────────────

    def _reset(self):
        self.destroy()
        app = NESTApp()
        app.mainloop()


if __name__ == "__main__":
    app = NESTApp()
    app.mainloop()