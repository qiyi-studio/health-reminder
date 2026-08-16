# -*- coding: utf-8 -*-
"""
健康提醒程式 (Health Reminder) — 動物森林風格
--------------------------------------------------
每隔固定時間（預設每小時）跳出一個「必須處理完才能關閉」的提醒視窗：
  - 視窗置中出現、可拖曳移動（若電腦連接多台螢幕，也可以拖曳到另一台螢幕上），
    但在停留的那個螢幕上，視窗最下緣不能碰到工作列上緣（無法往下藏起來）
  - 沒有系統標題列，因此沒有關閉鈕、也沒有縮小鈕
  - 每個項目需手動按「完成」；需要持續一段時間的項目要先「開始」計時，
    時間到才能按「完成」，計時中可「暫停 / 繼續」
  - 若跳出後 10 分鐘內沒有全部完成，會另外跳出一個不同色調的「尚未完成」補提醒視窗，
    之後每 10 分鐘再跳一個，直到所有項目完成，所有相關視窗才會一起自動關閉
  - 每天隨機挑一種日式傳統色當主題色，同一天固定、隔天重新挑選
  - 全站字型使用 Arial（不加粗），介面走圓角卡片、柔和的「動物森林」風格，不使用裝飾性小圖示

僅使用 Python 標準函式庫（tkinter），無需額外安裝套件。

執行方式：
    python3 health_reminder.py
"""

import json
import os
import random
import datetime
import tkinter as tk
from tkinter import messagebox, simpledialog

# ----------------------------------------------------------------------
# 基本設定 / 資料存放路徑
# ----------------------------------------------------------------------

APP_DIR = os.path.join(os.path.expanduser("~"), ".health_reminder")
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
STATE_FILE = os.path.join(APP_DIR, "state.json")
os.makedirs(APP_DIR, exist_ok=True)

FONT_FAMILY = "Arial"
NAG_INTERVAL_MS = 10 * 60 * 1000  # 補提醒間隔：10 分鐘

# 動物森林風格的中性配色（用於一般視窗，不隨日期改變）
LEAF_GREEN = "#8FBF7F"
CREAM = "#FBF3E3"
CARD_WHITE = "#FFFDF6"
TEXT_BROWN = "#5B4636"

# 日式傳統色票（名稱, (R, G, B)）—— 用於每日提醒彈窗主題
PALETTE = [
    ("一斤染", (240, 143, 144)),
    ("桜色", (252, 201, 185)),
    ("淡萌黄", (141, 178, 85)),
    ("水浅葱", (116, 159, 141)),
    ("花浅葱", (29, 105, 124)),
    ("藤紫", (135, 95, 154)),
    ("竜胆色", (105, 103, 171)),
    ("鳥之子色", (226, 190, 159)),
    ("薄柿", (252, 164, 116)),
    ("紅碧", (120, 119, 155)),
    ("卯之花色", (251, 251, 246)),
]

DEFAULT_REMINDERS = [
    {"id": 1, "text": "離開椅子起身，站立兩分鐘", "timed": True, "duration_min": 2},
    {"id": 2, "text": "喝水 100ML", "timed": False, "duration_min": 0},
    {"id": 3, "text": "注意情緒管理，以高效率且得體回應對話", "timed": False, "duration_min": 0},
]

DEFAULT_CONFIG = {
    "reminders": DEFAULT_REMINDERS,
    "interval_minutes": 60,
    "next_id": 4,
}


# ----------------------------------------------------------------------
# 設定檔讀寫
# ----------------------------------------------------------------------

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                cfg.setdefault("reminders", DEFAULT_REMINDERS)
                cfg.setdefault("interval_minutes", 60)
                cfg.setdefault("next_id", (max([r["id"] for r in cfg["reminders"]], default=0) + 1))
                return cfg
        except Exception:
            pass
    save_config(DEFAULT_CONFIG)
    return json.loads(json.dumps(DEFAULT_CONFIG))


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_today_color():
    """取得（並視需要更新）今天的主題色。同一天固定，跨日自動重新隨機。"""
    today = datetime.date.today().isoformat()
    state = load_state()
    if state.get("date") == today and "color_name" in state and "color_rgb" in state:
        return state["color_name"], tuple(state["color_rgb"])
    name, rgb = random.choice(PALETTE)
    state["date"] = today
    state["color_name"] = name
    state["color_rgb"] = list(rgb)
    save_state(state)
    return name, rgb


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % rgb


def contrast_text_color(rgb):
    r, g, b = rgb
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return "#3a2f28" if luminance > 150 else "#ffffff"


# ----------------------------------------------------------------------
# 圓角繪製工具 / 圓角按鈕 / 圓角卡片
# ----------------------------------------------------------------------

def _rounded_rect_points(x1, y1, x2, y2, r):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]


def draw_rounded_rect(canvas, x1, y1, x2, y2, r=14, **kwargs):
    return canvas.create_polygon(_rounded_rect_points(x1, y1, x2, y2, r), smooth=True, **kwargs)


class RoundedButton(tk.Canvas):
    """圓角按鈕（Canvas 繪製），支援 normal / disabled 兩種狀態與 hover 效果。"""

    def __init__(self, master, text, command=None, width=120, height=36, radius=14,
                 parent_bg=CREAM, bg_color=LEAF_GREEN, fg_color="#ffffff",
                 disabled_bg="#dcdcdc", disabled_fg="#9a9a9a",
                 font=(FONT_FAMILY, 10)):
        super().__init__(master, width=width, height=height, bg=parent_bg,
                          highlightthickness=0, bd=0)
        self.command = command
        self.radius = radius
        self.w = width
        self.h = height
        self.text = text
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.disabled_bg = disabled_bg
        self.disabled_fg = disabled_fg
        self.font = font
        self.state_ = "normal"
        self._draw()
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", lambda e: self._draw(hover=True))
        self.bind("<Leave>", lambda e: self._draw(hover=False))

    def _hover_shade(self, hexcolor, factor=0.9):
        r = int(hexcolor[1:3], 16)
        g = int(hexcolor[3:5], 16)
        b = int(hexcolor[5:7], 16)
        return "#%02x%02x%02x" % (int(r * factor), int(g * factor), int(b * factor))

    def _draw(self, hover=False):
        self.delete("all")
        if self.state_ == "disabled":
            fill, txt = self.disabled_bg, self.disabled_fg
        else:
            fill = self._hover_shade(self.bg_color) if hover else self.bg_color
            txt = self.fg_color
        draw_rounded_rect(self, 1, 1, self.w - 1, self.h - 1, self.radius, fill=fill, outline="")
        self.create_text(self.w // 2, self.h // 2, text=self.text, fill=txt, font=self.font)

    def _on_click(self, event):
        if self.state_ != "disabled" and self.command:
            self.command()

    def set_state(self, state):
        self.state_ = state
        self._draw()

    def set_text(self, text):
        self.text = text
        self._draw()

    def set_colors(self, bg=None, fg=None):
        if bg:
            self.bg_color = bg
        if fg:
            self.fg_color = fg
        self._draw()


def make_card(parent, bg=CARD_WHITE, radius=16, pad=12):
    """建立圓角卡片：回傳 (canvas, inner_frame)。把內容放進 inner_frame 後呼叫 finalize_card()。"""
    canvas = tk.Canvas(parent, bg=parent["bg"], highlightthickness=0, bd=0)
    inner = tk.Frame(canvas, bg=bg)
    canvas._inner = inner
    canvas._bg = bg
    canvas._radius = radius
    canvas._pad = pad
    return canvas, inner


def finalize_card(canvas):
    inner, pad, radius, bg = canvas._inner, canvas._pad, canvas._radius, canvas._bg
    inner.update_idletasks()
    w = inner.winfo_reqwidth()
    h = inner.winfo_reqheight()
    total_w, total_h = w + pad * 2, h + pad * 2
    canvas.config(width=total_w, height=total_h)
    draw_rounded_rect(canvas, 0, 0, total_w, total_h, radius, fill=bg, outline="")
    canvas.create_window(pad, pad, anchor="nw", window=inner, width=w, height=h)
    return canvas


# ----------------------------------------------------------------------
# 強制顯示視窗的共用基底類別
# ----------------------------------------------------------------------

class ForcedWindow(tk.Toplevel):
    """
    無 OS 標題列（因此無關閉/縮小鈕）、持續最上層、可拖曳移動。
    可拖曳到任一台已連接的螢幕上（雙螢幕或多螢幕環境），
    但在停留的那個螢幕上，視窗最下緣不可碰到該螢幕工作列上緣。
    """

    BOTTOM_GAP = 6  # 與工作列上緣保留的最小間距（像素），確保「不碰觸」而非剛好貼齊

    def __init__(self, master, bg_rgb, title_text):
        super().__init__(master)
        self.bg_rgb = bg_rgb
        self.bg_hex = rgb_to_hex(bg_rgb)
        self.fg_hex = contrast_text_color(bg_rgb)
        self._closed = False

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=self.bg_hex)
        self.resizable(False, False)

        self._build_title_bar(title_text)
        self.body = tk.Frame(self, bg=self.bg_hex, padx=18, pady=12)
        self.body.pack(fill="both", expand=True)
        self._build_body(self.body)

        self.monitor_work_areas = self._get_monitor_work_areas()
        self.virtual_bounds = self._get_virtual_screen_bounds()
        self.primary_work_area = self._find_primary_work_area()
        self._center_on_screen()
        self._keep_on_top_loop()

    # -- 標題列（可拖曳） -------------------------------------------------

    def _build_title_bar(self, text):
        bar = tk.Canvas(self, height=44, bg=self.bg_hex, highlightthickness=0, bd=0, cursor="fleur")
        bar.pack(fill="x")
        bar.create_text(18, 22, anchor="w", text=text, fill=self.fg_hex,
                         font=(FONT_FAMILY, 13))
        bar.bind("<ButtonPress-1>", self._start_move)
        bar.bind("<B1-Motion>", self._do_move)

    def _build_body(self, body):
        pass  # 由子類別實作

    # -- 多螢幕偵測（盡力而為；Windows 可精準取得每個螢幕的工作區域，
    #    其他系統則以單一螢幕的估算值為主） -----------------------------

    def _get_monitor_work_areas(self):
        """回傳每個螢幕的工作區域列表 [(left, top, right, bottom), ...]，已扣除工作列。"""
        areas = []
        try:
            import ctypes
            from ctypes import wintypes

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD),
                ]

            MONITORENUMPROC = ctypes.WINFUNCTYPE(
                ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
                ctypes.POINTER(wintypes.RECT), ctypes.c_double
            )

            def _callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
                info = MONITORINFO()
                info.cbSize = ctypes.sizeof(MONITORINFO)
                if ctypes.windll.user32.GetMonitorInfoW(hMonitor, ctypes.byref(info)):
                    r = info.rcWork
                    areas.append((r.left, r.top, r.right, r.bottom))
                return 1

            ctypes.windll.user32.EnumDisplayMonitors(0, 0, MONITORENUMPROC(_callback), 0)
        except Exception:
            pass

        if not areas:
            # 非 Windows，或取得失敗：退回單一螢幕的概略估算
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            estimated_taskbar = 60
            areas = [(0, 0, sw, sh - estimated_taskbar)]
        return areas

    def _get_virtual_screen_bounds(self):
        """回傳涵蓋所有螢幕的整體虛擬桌面範圍 (left, top, right, bottom)，讓視窗可以跨螢幕拖曳。"""
        try:
            import ctypes
            SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
            SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
            user32 = ctypes.windll.user32
            x = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
            y = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
            cx = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
            cy = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
            if cx > 0 and cy > 0:
                return x, y, x + cx, y + cy
        except Exception:
            pass
        # 非 Windows：多數狀況下 winfo_screenwidth/height 已涵蓋整個虛擬螢幕範圍
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        return 0, 0, sw, sh

    def _find_primary_work_area(self):
        for area in self.monitor_work_areas:
            l, t, r, b = area
            if l <= 0 < r and t <= 0 < b:
                return area
        return self.monitor_work_areas[0]

    def _work_area_for_point(self, px, py):
        for area in self.monitor_work_areas:
            l, t, r, b = area
            if l <= px < r and t <= py < b:
                return area
        return self.primary_work_area

    # -- 定位與受限移動（可跨螢幕拖曳，但每個螢幕上仍不可碰到該螢幕工作列上緣） --

    def _center_on_screen(self):
        self.update_idletasks()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        left, top, right, bottom = self.primary_work_area
        x = left + max((right - left - w) // 2, 0)
        y = top + max((bottom - top - h) // 2, 0)
        if y + h > bottom - self.BOTTOM_GAP:
            y = bottom - self.BOTTOM_GAP - h
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _start_move(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _do_move(self, event):
        x = self.winfo_x() + (event.x - self._drag_x)
        y = self.winfo_y() + (event.y - self._drag_y)
        w = self.winfo_width()
        h = self.winfo_height()

        # 先限制在「所有螢幕組成的整體範圍」內，允許視窗被拖到另一個螢幕上
        vleft, vtop, vright, vbottom = self.virtual_bounds
        if x < vleft:
            x = vleft
        if x + w > vright:
            x = vright - w
        if y < vtop:
            y = vtop
        if y + h > vbottom:
            y = vbottom - h

        # 再依視窗中心點目前所在的螢幕，限制不能碰到「該螢幕」工作列上緣
        center_x = x + w // 2
        center_y = y + h // 2
        wleft, wtop, wright, wbottom = self._work_area_for_point(center_x, center_y)
        max_y = wbottom - self.BOTTOM_GAP - h
        if y > max_y:
            y = max_y

        self.geometry(f"+{x}+{y}")

    def _keep_on_top_loop(self):
        if self._closed:
            return
        try:
            self.attributes("-topmost", True)
            self.lift()
        except tk.TclError:
            return
        self.after(400, self._keep_on_top_loop)

    def force_destroy(self):
        self._closed = True
        try:
            self.destroy()
        except tk.TclError:
            pass


# ----------------------------------------------------------------------
# 補提醒視窗（未在時限內完成時，每 10 分鐘跳出一次，色調與主視窗不同）
# ----------------------------------------------------------------------

class NagPopup(ForcedWindow):
    def __init__(self, master, color_rgb, main_popup):
        self.main_popup = main_popup
        super().__init__(master, color_rgb, "提醒")

    def _build_body(self, body):
        remaining = len([1 for st in self.main_popup.item_states.values() if not st["done"]])
        tk.Label(body, text="尚未完成每日注意事項", bg=self.bg_hex, fg=self.fg_hex,
                 font=(FONT_FAMILY, 16)).pack(pady=(6, 8))
        tk.Label(body, text=f"還有 {remaining} 項提醒尚未完成，記得回去完成勾選喔",
                 bg=self.bg_hex, fg=self.fg_hex, font=(FONT_FAMILY, 11),
                 wraplength=280, justify="center").pack(pady=(0, 14))
        btn = RoundedButton(body, text="回到提醒視窗", command=self._go_back,
                             width=150, height=38, radius=16, parent_bg=self.bg_hex,
                             bg_color="#ffffff", fg_color=TEXT_BROWN)
        btn.pack(pady=(0, 4))

    def _go_back(self):
        try:
            self.main_popup.attributes("-topmost", True)
            self.main_popup.lift()
        except tk.TclError:
            pass


# ----------------------------------------------------------------------
# 主要提醒彈窗
# ----------------------------------------------------------------------

class ReminderPopup(ForcedWindow):
    def __init__(self, master, reminders, theme_name, theme_rgb, on_close=None):
        self.reminders = reminders
        self.theme_name = theme_name
        self.item_states = {}
        self.on_close = on_close
        self.nag_windows = []
        self.nag_job = None
        self.status_lbl = None

        candidates = [c for c in PALETTE if c[0] != theme_name]
        self.nag_color_name, self.nag_color_rgb = random.choice(candidates or PALETTE)

        super().__init__(master, theme_rgb, "健康提醒")
        self._schedule_nag()

    # -- UI 建構 ------------------------------------------------------------

    def _build_body(self, body):
        for item in self.reminders:
            self._build_item_row(body, item)
        self.status_lbl = tk.Label(body, text="請完成以下所有項目", bg=self.bg_hex,
                                    fg=self.fg_hex, font=(FONT_FAMILY, 10))
        self.status_lbl.pack(pady=(6, 2))

    def _build_item_row(self, parent, item):
        rid = item["id"]
        timed = item.get("timed", False)
        duration_sec = int(item.get("duration_min", 0) * 60)

        canvas, card = make_card(parent, bg=CARD_WHITE, radius=16, pad=12)

        tk.Label(card, text=item["text"], bg=CARD_WHITE, fg=TEXT_BROWN,
                 font=(FONT_FAMILY, 12), anchor="w", justify="left",
                 wraplength=320).pack(fill="x", anchor="w")

        state = {"remaining": duration_sec, "running": False, "done": False}
        self.item_states[rid] = state

        controls = tk.Frame(card, bg=CARD_WHITE)
        controls.pack(fill="x", pady=(8, 0))

        complete_btn = RoundedButton(controls, text="完成", command=lambda i=rid: self._mark_done(i),
                                      width=90, height=32, radius=12, parent_bg=CARD_WHITE,
                                      bg_color=LEAF_GREEN, fg_color="#ffffff")
        if timed:
            complete_btn.set_state("disabled")

        if timed:
            timer_lbl = tk.Label(controls, text=self._fmt_time(duration_sec), bg=CARD_WHITE,
                                  fg=TEXT_BROWN, font=(FONT_FAMILY, 12), width=6)

            start_btn = RoundedButton(controls, text="開始", width=80, height=32, radius=12,
                                       parent_bg=CARD_WHITE, bg_color="#E8A24C", fg_color="#ffffff")
            pause_btn = RoundedButton(controls, text="暫停", width=80, height=32, radius=12,
                                       parent_bg=CARD_WHITE, bg_color="#B7A6D9", fg_color="#ffffff")
            pause_btn.set_state("disabled")

            def start(i=rid):
                st = self.item_states[i]
                if st["done"] or st["running"]:
                    return
                st["running"] = True
                start_btn.set_state("disabled")
                pause_btn.set_state("normal")
                pause_btn.set_text("暫停")
                self._tick(i, timer_lbl, complete_btn, start_btn, pause_btn)

            def toggle_pause(i=rid):
                st = self.item_states[i]
                if st["done"]:
                    return
                st["running"] = not st["running"]
                pause_btn.set_text("暫停" if st["running"] else "繼續")
                if st["running"]:
                    self._tick(i, timer_lbl, complete_btn, start_btn, pause_btn)

            start_btn.command = start
            pause_btn.command = toggle_pause

            start_btn.pack(side="left", padx=(0, 6))
            pause_btn.pack(side="left", padx=(0, 6))
            timer_lbl.pack(side="left", padx=(0, 10))

        complete_btn.pack(side="right")
        state["complete_btn"] = complete_btn

        finalize_card(canvas)
        canvas.pack(fill="x", pady=6)

    @staticmethod
    def _fmt_time(sec):
        m, s = divmod(max(sec, 0), 60)
        return f"{m:02d}:{s:02d}"

    def _tick(self, rid, timer_lbl, complete_btn, start_btn, pause_btn):
        st = self.item_states[rid]
        if st["done"] or not st["running"]:
            return
        if st["remaining"] <= 0:
            timer_lbl.config(text="00:00")
            complete_btn.set_state("normal")
            start_btn.set_state("disabled")
            pause_btn.set_state("disabled")
            return
        st["remaining"] -= 1
        timer_lbl.config(text=self._fmt_time(st["remaining"]))
        self.after(1000, lambda: self._tick(rid, timer_lbl, complete_btn, start_btn, pause_btn))

    def _mark_done(self, rid):
        st = self.item_states[rid]
        if st["done"]:
            return
        st["done"] = True
        st["complete_btn"].set_text("✔ 已完成")
        st["complete_btn"].set_colors(bg="#CFE8C4", fg="#3a5a34")
        st["complete_btn"].set_state("disabled")
        self._check_all_done()

    def _all_done(self):
        return all(st["done"] for st in self.item_states.values())

    def _check_all_done(self):
        remaining = [rid for rid, st in self.item_states.items() if not st["done"]]
        if remaining:
            self.status_lbl.config(text=f"尚有 {len(remaining)} 項未完成")
        else:
            self.status_lbl.config(text="全部完成，視窗即將關閉")
            self.after(800, self._close_all)

    # -- 每 10 分鐘的補提醒排程 ---------------------------------------------

    def _schedule_nag(self):
        self.nag_job = self.after(NAG_INTERVAL_MS, self._nag_check)

    def _nag_check(self):
        if self._closed or self._all_done():
            return
        nag = NagPopup(self.master, self.nag_color_rgb, self)
        self.nag_windows.append(nag)
        self._schedule_nag()

    def _close_all(self):
        if self.nag_job:
            try:
                self.after_cancel(self.nag_job)
            except Exception:
                pass
            self.nag_job = None
        for nag in self.nag_windows:
            nag.force_destroy()
        self.nag_windows = []
        if self.on_close:
            self.on_close()
        self.force_destroy()


# ----------------------------------------------------------------------
# 管理提醒事項視窗
# ----------------------------------------------------------------------

class ManageRemindersWindow(tk.Toplevel):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.title("管理提醒事項")
        self.configure(bg=CREAM)
        self.geometry("440x440")
        self.resizable(False, False)

        tk.Label(self, text="提醒事項清單", font=(FONT_FAMILY, 14),
                 bg=CREAM, fg=TEXT_BROWN).pack(pady=(14, 6))

        list_canvas, list_card = make_card(self, bg=CARD_WHITE, radius=16, pad=10)
        self.listbox = tk.Listbox(list_card, width=46, height=10, bg=CARD_WHITE,
                                   fg=TEXT_BROWN, font=(FONT_FAMILY, 10), bd=0,
                                   highlightthickness=0, selectbackground=LEAF_GREEN)
        self.listbox.pack()
        finalize_card(list_canvas)
        list_canvas.pack(padx=14, pady=6)
        self._refresh_list()

        btn_row = tk.Frame(self, bg=CREAM)
        btn_row.pack(pady=10)
        RoundedButton(btn_row, text="新增", command=self._add_item, width=100, height=34,
                      radius=14, parent_bg=CREAM, bg_color=LEAF_GREEN).pack(side="left", padx=6)
        RoundedButton(btn_row, text="刪除選取", command=self._remove_item, width=100, height=34,
                      radius=14, parent_bg=CREAM, bg_color="#E08A8A").pack(side="left", padx=6)

        RoundedButton(self, text="關閉", command=self.destroy, width=100, height=34,
                      radius=14, parent_bg=CREAM, bg_color="#C9BFAF", fg_color=TEXT_BROWN).pack(pady=8)

    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        for item in self.app.config["reminders"]:
            tag = f"（計時 {item['duration_min']} 分鐘）" if item["timed"] else "（無需計時）"
            self.listbox.insert(tk.END, f"  {item['text']} {tag}")

    def _add_item(self):
        text = simpledialog.askstring("新增提醒事項", "請輸入提醒內容：", parent=self)
        if not text:
            return
        timed = messagebox.askyesno("是否需要計時", "此項目是否需要持續一段時間才算完成？", parent=self)
        duration_min = 0
        if timed:
            duration_min = simpledialog.askinteger(
                "計時長度", "請輸入需要持續的分鐘數：", parent=self, minvalue=1, maxvalue=180
            )
            if not duration_min:
                return
        new_id = self.app.config["next_id"]
        self.app.config["next_id"] += 1
        self.app.config["reminders"].append(
            {"id": new_id, "text": text, "timed": timed, "duration_min": duration_min}
        )
        save_config(self.app.config)
        self._refresh_list()

    def _remove_item(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        item = self.app.config["reminders"][idx]
        if messagebox.askyesno("確認刪除", f"確定要刪除「{item['text']}」嗎？", parent=self):
            del self.app.config["reminders"][idx]
            save_config(self.app.config)
            self._refresh_list()


# ----------------------------------------------------------------------
# 主控台（一般視窗，可自由關閉/縮小）
# ----------------------------------------------------------------------

class ReminderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("健康提醒程式 - 控制台")
        self.configure(bg=CREAM)
        self.geometry("460x480")
        self.resizable(False, False)

        self.config = load_config()
        self.theme_name, self.theme_rgb = get_today_color()
        self.schedule_job = None
        self.scheduled_running = False

        self._build_ui()
        self.start_schedule()

    def _build_ui(self):
        tk.Label(self, text="健康提醒程式", font=(FONT_FAMILY, 24, "bold"),
                 bg=CREAM, fg=TEXT_BROWN).pack(pady=(18, 6))

        theme_canvas, theme_card = make_card(self, bg=CARD_WHITE, radius=16, pad=12)
        tk.Label(theme_card, text="今日主題色", font=(FONT_FAMILY, 15), bg=CARD_WHITE,
                 fg=TEXT_BROWN).pack(anchor="w")
        row = tk.Frame(theme_card, bg=CARD_WHITE)
        row.pack(anchor="w", pady=(4, 0))
        tk.Frame(row, bg=rgb_to_hex(self.theme_rgb), width=26, height=20,
                 highlightthickness=1, highlightbackground="#bbb").pack(side="left", padx=(0, 8))
        tk.Label(row, text=f"{self.theme_name} {self.theme_rgb}", font=(FONT_FAMILY, 15),
                 bg=CARD_WHITE, fg=TEXT_BROWN).pack(side="left")
        finalize_card(theme_canvas)
        theme_canvas.pack(pady=8)

        interval_frame = tk.Frame(self, bg=CREAM)
        interval_frame.pack(pady=8)
        tk.Label(interval_frame, text="提醒間隔（分鐘）：", font=(FONT_FAMILY, 15),
                 bg=CREAM, fg=TEXT_BROWN).pack(side="left")
        self.interval_var = tk.IntVar(value=self.config["interval_minutes"])
        tk.Spinbox(interval_frame, from_=1, to=240, width=6, textvariable=self.interval_var,
                   command=self._on_interval_change, font=(FONT_FAMILY, 15)).pack(side="left", padx=6)

        self.status_lbl = tk.Label(self, text="", font=(FONT_FAMILY, 15), bg=CREAM, fg=TEXT_BROWN)
        self.status_lbl.pack(pady=6)

        RoundedButton(self, text="立即測試提醒", command=self.trigger_now, width=240, height=44,
                      radius=16, parent_bg=CREAM, bg_color=LEAF_GREEN,
                      font=(FONT_FAMILY, 15)).pack(pady=5)
        self.toggle_btn = RoundedButton(self, text="暫停自動提醒", command=self.toggle_schedule,
                                         width=240, height=44, radius=16, parent_bg=CREAM,
                                         bg_color="#E8A24C", font=(FONT_FAMILY, 15))
        self.toggle_btn.pack(pady=5)
        RoundedButton(self, text="管理提醒事項", command=lambda: ManageRemindersWindow(self, self),
                      width=240, height=44, radius=16, parent_bg=CREAM,
                      bg_color="#B7A6D9", font=(FONT_FAMILY, 15)).pack(pady=5)

        tk.Label(self, text="提醒視窗跳出後，需完成所有項目才會關閉；\n逾時未完成每 10 分鐘會再跳出補提醒視窗。",
                 font=(FONT_FAMILY, 12, "bold"), fg="#8a7a68", bg=CREAM, justify="center").pack(pady=(14, 0))

    def _on_interval_change(self):
        self.config["interval_minutes"] = int(self.interval_var.get())
        save_config(self.config)
        if self.scheduled_running:
            self.start_schedule()

    def start_schedule(self):
        if self.schedule_job:
            self.after_cancel(self.schedule_job)
        self.scheduled_running = True
        self.toggle_btn.set_text("暫停自動提醒")
        minutes = int(self.interval_var.get()) if hasattr(self, "interval_var") else self.config["interval_minutes"]
        ms = max(minutes, 1) * 60 * 1000
        self.schedule_job = self.after(ms, self._scheduled_trigger)
        self.status_lbl.config(text=f"下一次提醒約 {minutes} 分鐘後")

    def pause_schedule(self):
        if self.schedule_job:
            self.after_cancel(self.schedule_job)
            self.schedule_job = None
        self.scheduled_running = False
        self.toggle_btn.set_text("繼續自動提醒")
        self.status_lbl.config(text="自動提醒已暫停")

    def toggle_schedule(self):
        if self.scheduled_running:
            self.pause_schedule()
        else:
            self.start_schedule()

    def _scheduled_trigger(self):
        self.trigger_now()
        if self.scheduled_running:
            self.start_schedule()

    def trigger_now(self):
        self.theme_name, self.theme_rgb = get_today_color()
        reminders = self.config["reminders"]
        if not reminders:
            return
        ReminderPopup(self, reminders, self.theme_name, self.theme_rgb)


if __name__ == "__main__":
    app = ReminderApp()
    app.mainloop()
