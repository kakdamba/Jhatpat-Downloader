import customtkinter as ctk
import yt_dlp
import threading
import pyperclip
import time
import os
import re
import json
import sys
import ctypes
import socket
import requests
import subprocess
import math
import winreg
from io import BytesIO
from tkinter import filedialog, Canvas
from PIL import Image, ImageTk, ImageDraw
import pystray
from pystray import MenuItem as item
from flask import Flask, request, jsonify
from flask_cors import CORS
from queue import Queue

# --- 1. THE BOUNCER (Single Instance Lock) ---
def check_single_instance():
    try:
        global lock_socket
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(('127.0.0.1', 45001))
    except socket.error:
        try: requests.post('http://127.0.0.1:5001/wake_up', timeout=1)
        except: pass
        sys.exit()

if os.name == 'nt':
    try: ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("jhatpat.downloader.final")
    except: pass

APP_DATA_DIR = os.path.join(os.environ.get('LOCALAPPDATA', os.getcwd()), 'JhatpatDownloader')
if not os.path.exists(APP_DATA_DIR): os.makedirs(APP_DATA_DIR)
CONFIG_FILE = os.path.join(APP_DATA_DIR, 'settings.json')

server = Flask(__name__)
CORS(server)
app_instance = None 

@server.route('/send_link', methods=['POST'])
def receive_link():
    data = request.json
    url = data.get('url')
    if url and app_instance:
        type_str = data.get('type', 'video')
        ptitle = data.get('page_title', '')
        app_instance.after(0, lambda: app_instance.catch_from_chrome(url, type_str, ptitle))
        return jsonify({"status": "received"}), 200
    return jsonify({"status": "error"}), 400

@server.route('/wake_up', methods=['POST'])
def wake_up():
    if app_instance:
        app_instance.after(0, app_instance.show_window)
        return jsonify({"status": "awake"}), 200
    return jsonify({"status": "error"}), 400

def run_server():
    try: server.run(host='127.0.0.1', port=5001, debug=False, use_reloader=False)
    except: pass

def resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def is_startup_enabled():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, "JhatpatDownloader")
        winreg.CloseKey(key)
        return True
    except OSError:
        return False

def toggle_startup(enable):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)
        if enable:
            exe_path = os.path.abspath(sys.argv[0])
            cmd = f'"{exe_path}" --startup' if exe_path.endswith('.exe') else f'"{sys.executable}" "{exe_path}" --startup'
            winreg.SetValueEx(key, "JhatpatDownloader", 0, winreg.REG_SZ, cmd)
        else:
            try: winreg.DeleteValue(key, "JhatpatDownloader")
            except FileNotFoundError: pass
        winreg.CloseKey(key)
    except Exception:
        pass

# --- THEME ENGINE ---
THEMES = {
    "Default (Dark)": {
        "C_BG": "#0b0c10",
        "C_PANEL": "#11131c",
        "C_PANEL_SOLID": "#11131c",
        "C_CARD": "#1a1c29",
        "C_CARD_SOLID": "#1a1c29",
        "C_CARD_HOVER": "#22263a",
        "C_PURPLE": "#8b5cf6",
        "C_GREEN": "#10b981",
        "C_TEXT": "#f8f8f2",
        "C_MUTED": "#8b92a5",
        "C_RED": "#ef4444"
    },
    "The Rookery": {
        "C_BG": "#1f2d30",
        "C_PANEL": "#3e3f40",
        "C_PANEL_SOLID": "#3e3f40",
        "C_CARD": "#667578",
        "C_CARD_SOLID": "#667578",
        "C_CARD_HOVER": "#7c8c94",
        "C_PURPLE": "#f79d34",
        "C_GREEN": "#3eb6b0",
        "C_TEXT": "#d9ccb5",
        "C_MUTED": "#b9c0b9",
        "C_RED": "#d7807c"
    }
}

CURRENT_THEME_NAME = "Default (Dark)"
try:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            _data = json.load(f)
            CURRENT_THEME_NAME = _data.get("theme", "Default (Dark)")
except: pass

if CURRENT_THEME_NAME not in THEMES: CURRENT_THEME_NAME = "Default (Dark)"
_t = THEMES[CURRENT_THEME_NAME]

C_BG = _t["C_BG"]
C_PANEL = _t["C_PANEL"]
C_PANEL_SOLID = _t.get("C_PANEL_SOLID", "#0c0822")
C_CARD = _t["C_CARD"]
C_CARD_SOLID = _t.get("C_CARD_SOLID", "#110b29")
C_CARD_HOVER = _t["C_CARD_HOVER"]
C_PURPLE = _t["C_PURPLE"]
C_GREEN = _t["C_GREEN"]
C_TEXT = _t["C_TEXT"]
C_MUTED = _t["C_MUTED"]
C_RED = _t["C_RED"]

ctk.set_appearance_mode("dark")

class DownloadRow(ctk.CTkFrame):
    def __init__(self, master, title, file_type, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.stop_flag = False
        
        self.info_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.info_frame.pack(fill="x", padx=5, pady=(5,0))
        
        icon = "🎬" if file_type == "video" else "🎵"
        self.title_lbl = ctk.CTkLabel(self.info_frame, text=f"{icon} {title[:30]}...", font=("Inter", 12), text_color=C_TEXT, anchor="w")
        self.title_lbl.pack(side="left")
        
        self.pct_lbl = ctk.CTkLabel(self.info_frame, text="0%", font=("Inter", 11, "bold"), text_color=C_PURPLE)
        self.pct_lbl.pack(side="right", padx=10)
        
        self.size_lbl = ctk.CTkLabel(self.info_frame, text="-- / --", font=("Inter", 11), text_color=C_MUTED)
        self.size_lbl.pack(side="right", padx=10)
        
        self.bar_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bar_frame.pack(fill="x", padx=5, pady=(2,5))
        
        self.bar = ctk.CTkProgressBar(self.bar_frame, height=8, progress_color=C_GREEN, fg_color=C_CARD_SOLID)
        self.bar.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.bar.set(0)
        
        self.cancel_btn = ctk.CTkButton(self.bar_frame, text="⏸", width=30, height=24, fg_color=C_CARD, hover_color=C_CARD_HOVER, text_color=C_TEXT, command=self.cancel)
        self.cancel_btn.pack(side="right")

    def cancel(self):
        self.stop_flag = True
        self.title_lbl.configure(text=f"❌ {self.title_lbl.cget('text')[2:]}")
        self.pct_lbl.configure(text="Cancelled", text_color=C_RED)
        self.bar.configure(progress_color=C_RED)
        self.after(1000, self.remove_self)

    def complete(self):
        self.pct_lbl.configure(text="Completed", text_color=C_GREEN)
        self.bar.set(1)
        self.cancel_btn.configure(text="✅", state="disabled")
        self.after(1000, self.remove_self)
        
    def remove_self(self):
        try:
            self.pack_forget()
            self.destroy()
            if app_instance:
                rows = [w for w in app_instance.queue_container.winfo_children() if isinstance(w, DownloadRow)]
                if not rows:
                    app_instance.empty_q.pack(pady=20)
        except: pass

class JhatpatDownloader(ctk.CTk):
    def __init__(self):
        super().__init__()
        global app_instance
        app_instance = self

        self.title("Jhatpat Downloader")
        self.geometry("900x950") 
        self.configure(fg_color=C_BG)
        self.protocol('WM_DELETE_WINDOW', self.minimize_to_tray)
        try: self.iconbitmap(resource_path("icon.ico"))
        except: pass

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.dl_queue = Queue()
        self.pending_list = []
        self.pending_lock = threading.Lock()
        self.total_scouted = 0
        self.save_path = ""
        self.history_db = []
        self.log_messages = []
        self.load_settings()
        self.current_meta = None

        self.setup_sidebar()
        self.setup_main_area()

        self.radar_angle = 0
        self.update_radar()

        threading.Thread(target=self.update_engine, daemon=True).start()
        threading.Thread(target=self.listen_to_clipboard, daemon=True).start()
        threading.Thread(target=run_server, daemon=True).start()
        for _ in range(5):
            threading.Thread(target=self.download_worker, daemon=True).start()
        threading.Thread(target=self.create_tray, daemon=True).start()

        if "--startup" in sys.argv:
            self.withdraw()
            self.after(0, self.withdraw)
            self.after(100, self.withdraw)
            self.after(500, self.withdraw)

    def setup_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=220, fg_color=C_PANEL, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(9, weight=1)
        self.sidebar.grid_columnconfigure(0, weight=1)

        # Logo
        try:
            t_img = Image.open(resource_path("text_logo.png"))
            
            # Maintain aspect ratio while fitting into a reasonable width (e.g., 180px)
            w, h = t_img.size
            new_w = 180
            new_h = int(h * (new_w / w))
            t_img = t_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            t_ctk_img = ctk.CTkImage(t_img, size=(new_w, new_h))
            self.logo_img_lbl = ctk.CTkLabel(self.sidebar, image=t_ctk_img, text="")
            self.logo_img_lbl.grid(row=0, column=0, rowspan=2, pady=(20, 0))
        except Exception:
            self.logo_lbl = ctk.CTkLabel(self.sidebar, text="JHATPAT", font=("Inter", 20, "bold", "italic"), text_color=C_PURPLE)
            self.logo_lbl.grid(row=0, column=0, pady=(20, 0))
            self.logo_lbl2 = ctk.CTkLabel(self.sidebar, text="DOWNLOADER", font=("Inter", 14, "bold", "italic"), text_color=C_GREEN)
            self.logo_lbl2.grid(row=1, column=0, pady=(0, 10))

        # Radar in sidebar
        self.radar_canvas = Canvas(self.sidebar, width=100, height=100, bg=C_PANEL_SOLID, highlightthickness=0)
        self.radar_canvas.grid(row=2, column=0, pady=(5, 15))
        
        self.radar_bg_img = None
        try:
            r_img = Image.open(resource_path("logo.png")).resize((80, 80), Image.Resampling.LANCZOS)
            self.radar_bg_img = ImageTk.PhotoImage(r_img)
        except Exception:
            pass

        # Navigation
        menus = [
            ("⌂", "Home", 3, ""), 
            ("⤓", "Downloads", 4, ""), 
            ("▤", "Queue", 5, ""), 
            ("⚙", "Settings", 6, ""), 
            ("ⓘ", "About", 7, "")
        ]
        self.nav_buttons = {}
        for icon, text, row, badge in menus:
            is_active = (text == "Home")
            btn_color = "#2e1065" if is_active else "transparent"
            txt_color = "#ffffff" if is_active else "#d1d5db"
            hover = "#4c1d95" if is_active else C_CARD_HOVER
            
            btn = ctk.CTkButton(self.sidebar, text=f"  {icon}    {text}", fg_color=btn_color, 
                                text_color=txt_color, hover_color=hover, font=("Inter", 13), 
                                anchor="w", height=42, corner_radius=10, command=lambda t=text: self.switch_page(t))
            btn.grid(row=row, column=0, sticky="ew", padx=15, pady=4)
            self.nav_buttons[text] = btn
            
            if badge:
                badge_lbl = ctk.CTkLabel(btn, text=badge, fg_color="#7c3aed", text_color="#ffffff", 
                                         width=22, height=22, corner_radius=11, font=("Inter", 10, "bold"))
                badge_lbl.place(relx=0.90, rely=0.5, anchor="e")
                badge_lbl.bind("<Button-1>", lambda e, t=text: self.switch_page(t))

        # Buy me a Kheer
        self.kheer_frame = ctk.CTkFrame(self.sidebar, fg_color=C_CARD, corner_radius=12, border_width=1, border_color=C_PURPLE)
        self.kheer_frame.grid(row=10, column=0, padx=15, pady=20, sticky="ew")
        
        try:
            kheer_img = Image.open(resource_path("support_logo.png")).resize((120, 120), Image.Resampling.LANCZOS)
            kheer_ctk_img = ctk.CTkImage(kheer_img, size=(120, 120))
            self.kheer_img_lbl = ctk.CTkLabel(self.kheer_frame, image=kheer_ctk_img, text="")
            self.kheer_img_lbl.pack(pady=(15, 5))
        except Exception:
            ctk.CTkLabel(self.kheer_frame, text="🍲", font=("Arial", 40)).pack(pady=(15, 5))

        ctk.CTkLabel(self.kheer_frame, text="Love Jhatpat?", font=("Inter", 14, "bold"), text_color=C_TEXT).pack()
        ctk.CTkLabel(self.kheer_frame, text="Support the project\nwith a bowl of happiness!", font=("Inter", 10), text_color=C_MUTED).pack(pady=(2, 10))
        ctk.CTkButton(self.kheer_frame, text="Buy me a Kheer! 🥣", fg_color=C_PURPLE, hover_color="#7c3aed", corner_radius=6, height=32, font=("Inter", 12, "bold"), command=lambda: self.switch_page("Support")).pack(pady=(0, 15), padx=15, fill="x")

    def setup_main_area(self):
        # HOME PAGE
        self.main_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.main_scroll.grid(row=0, column=1, sticky="nsew", padx=20, pady=10)
        self.main_scroll.grid_columnconfigure(0, weight=1)
        
        try:
            self.main_scroll._scrollbar.configure(width=0)
            self.main_scroll._scrollbar.grid_forget()
        except: pass

        self.status_panel = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        self.status_panel.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        
        self.active_badge = ctk.CTkLabel(self.status_panel, text="🛡️ SCOUT ACTIVE", font=("Inter", 12, "bold"), text_color=C_GREEN)
        self.active_badge.pack(anchor="w")
        self.status_desc = ctk.CTkLabel(self.status_panel, text="Monitoring browser for videos...", font=("Inter", 11), text_color=C_MUTED)
        self.status_desc.pack(anchor="w", pady=(0, 10))

        stats_frame = ctk.CTkFrame(self.status_panel, fg_color="transparent")
        stats_frame.pack(fill="x")
        
        self.stat_box_1 = ctk.CTkFrame(stats_frame, fg_color=C_CARD, corner_radius=8, border_width=1, border_color=C_PANEL_SOLID)
        self.stat_box_1.pack(side="left", padx=(0, 10), ipadx=10, ipady=5)
        ctk.CTkLabel(self.stat_box_1, text="Scouted\n0", font=("Inter", 10), justify="left", text_color=C_TEXT).pack()
        self.scout_count_lbl = self.stat_box_1.winfo_children()[0]

        stat_box_2 = ctk.CTkFrame(stats_frame, fg_color=C_CARD, corner_radius=8, border_width=1, border_color=C_PANEL_SOLID)
        stat_box_2.pack(side="left", padx=10, ipadx=10, ipady=5)
        ctk.CTkLabel(stat_box_2, text="Status\nAll Systems Go", font=("Inter", 10), justify="left", text_color=C_GREEN).pack()

        stat_box_3 = ctk.CTkFrame(stats_frame, fg_color=C_CARD, corner_radius=8, border_width=1, border_color=C_PANEL_SOLID)
        stat_box_3.pack(side="left", padx=10, ipadx=10, ipady=5)
        self.speed_lbl = ctk.CTkLabel(stat_box_3, text="0.0 MB/s\nDownload Speed", font=("Inter", 10), justify="left", text_color=C_PURPLE)
        self.speed_lbl.pack()

        self.link_lbl = ctk.CTkLabel(self.main_scroll, text="🔗 LINK DETECTED", font=("Inter", 11, "bold"), text_color=C_GREEN)
        self.link_lbl.grid(row=1, column=0, sticky="w", pady=(5, 5))
        
        self.url_frame = ctk.CTkFrame(self.main_scroll, fg_color=C_PANEL, corner_radius=8, border_width=1, border_color=C_PURPLE)
        self.url_frame.grid(row=2, column=0, sticky="ew")
        self.url_frame.grid_columnconfigure(0, weight=1)
        
        self.url_entry = ctk.CTkEntry(self.url_frame, fg_color="transparent", border_width=0, font=("Inter", 12), text_color=C_TEXT)
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
        
        self.detect_btn = ctk.CTkButton(self.url_frame, text="Detect Again", fg_color=C_PURPLE, hover_color="#7c3aed", width=90, height=28, font=("Inter", 11), command=lambda: self.fetch_metadata(self.url_entry.get()))
        self.detect_btn.grid(row=0, column=1, padx=8)

        self.thumb_frame = ctk.CTkFrame(self.main_scroll, fg_color=C_PANEL, corner_radius=12)
        self.thumb_frame.grid(row=3, column=0, sticky="ew", pady=15)
        self.thumb_frame.grid_columnconfigure(1, weight=1)

        self.thumb_lbl = ctk.CTkLabel(self.thumb_frame, text="Waiting...", font=("Inter", 11), fg_color=C_CARD, width=240, height=135, corner_radius=8)
        self.thumb_lbl.grid(row=0, column=0, rowspan=4, padx=15, pady=15)

        self.platform_lbl = ctk.CTkLabel(self.thumb_frame, text="📺 Platform", font=("Inter", 11, "bold"), text_color=C_MUTED)
        self.platform_lbl.grid(row=0, column=1, sticky="w", pady=(15, 0))
        
        self.video_title = ctk.CTkLabel(self.thumb_frame, text="Ready for scout detection.", font=("Inter", 15, "bold"), text_color=C_TEXT, wraplength=350, justify="left")
        self.video_title.grid(row=1, column=1, sticky="nw", pady=(5, 5))
        
        self.video_meta = ctk.CTkLabel(self.thumb_frame, text="-- • -- • --", font=("Inter", 11), text_color=C_MUTED)
        self.video_meta.grid(row=2, column=1, sticky="nw")

        self.opt_lbl = ctk.CTkLabel(self.main_scroll, text="CHOOSE DOWNLOAD OPTION", font=("Inter", 11, "bold"), text_color=C_PURPLE)
        self.opt_lbl.grid(row=4, column=0, sticky="w", pady=(5, 5))

        self.cards_frame = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        self.cards_frame.grid(row=5, column=0, sticky="ew")
        self.cards_frame.grid_columnconfigure(0, weight=1)
        self.cards_frame.grid_columnconfigure(1, weight=1)

        self.mp4_card = ctk.CTkFrame(self.cards_frame, fg_color=C_PANEL, corner_radius=12, border_width=1, border_color=C_PURPLE)
        self.mp4_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.build_option_card(self.mp4_card, "MP4", "★ Best Quality", C_PURPLE, "video")

        self.mp3_card = ctk.CTkFrame(self.cards_frame, fg_color=C_PANEL, corner_radius=12, border_width=1, border_color=C_GREEN)
        self.mp3_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.build_option_card(self.mp3_card, "MP3", "🎵 Extract Audio", C_GREEN, "audio")

        # DOWNLOAD PROGRESS HEADER
        self.prog_header = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        self.prog_header.grid(row=6, column=0, sticky="ew", pady=(20, 5))
        self.prog_header.grid_columnconfigure(0, weight=1)
        
        self.prog_lbl = ctk.CTkLabel(self.prog_header, text="DOWNLOAD PROGRESS", font=("Inter", 11, "bold"), text_color=C_PURPLE)
        self.prog_lbl.grid(row=0, column=0, sticky="w")
        
        ctk.CTkButton(self.prog_header, text="📂 Open Folder", command=self.open_destination, height=24, width=100, font=("Inter", 11), fg_color="transparent", border_width=1, border_color=C_GREEN, text_color=C_GREEN, hover_color="#064e3b").grid(row=0, column=1, padx=(0, 10), sticky="e")
        ctk.CTkButton(self.prog_header, text="🛑 Stop All", command=self.cancel_all, height=24, width=80, font=("Inter", 11), fg_color="transparent", border_width=1, border_color=C_RED, text_color=C_RED, hover_color="#451a1a").grid(row=0, column=2, sticky="e")

        self.queue_container = ctk.CTkFrame(self.main_scroll, fg_color=C_PANEL, corner_radius=12)
        self.queue_container.grid(row=7, column=0, sticky="ew")
        self.queue_container.grid_columnconfigure(0, weight=1)
        
        self.empty_q = ctk.CTkLabel(self.queue_container, text="No active downloads", font=("Inter", 11), text_color=C_MUTED)
        self.empty_q.pack(pady=20)
        
        self.pending_lbl = ctk.CTkLabel(self.main_scroll, text="", font=("Inter", 11), text_color=C_MUTED, justify="left")
        self.pending_lbl.grid(row=8, column=0, sticky="w", pady=(0, 10), padx=5)

        # QUEUE PAGE
        self.page_queue = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.page_queue.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.page_queue, text="📜 UPCOMING QUEUE", font=("Inter", 16, "bold"), text_color=C_PURPLE).grid(row=0, column=0, sticky="w", pady=(10,20))
        self.queue_list_container = ctk.CTkFrame(self.page_queue, fg_color="transparent")
        self.queue_list_container.grid(row=1, column=0, sticky="nsew")
        self.queue_list_container.grid_columnconfigure(0, weight=1)
        try:
            self.page_queue._scrollbar.configure(width=0)
            self.page_queue._scrollbar.grid_forget()
        except: pass

        # SETTINGS PAGE
        self.page_settings = ctk.CTkFrame(self, fg_color="transparent")
        self.page_settings.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.page_settings, text="⚙️ SETTINGS", font=("Inter", 16, "bold"), text_color=C_PURPLE).grid(row=0, column=0, sticky="w", pady=(10,20))
        
        set_card = ctk.CTkFrame(self.page_settings, fg_color=C_PANEL, corner_radius=12)
        set_card.grid(row=1, column=0, sticky="ew")
        set_card.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(set_card, text="Download Destination", font=("Inter", 14, "bold"), text_color=C_TEXT).pack(anchor="w", padx=20, pady=(20, 5))
        self.path_lbl = ctk.CTkLabel(set_card, text=self.save_path, font=("Inter", 12), text_color=C_MUTED, wraplength=400, justify="left")
        self.path_lbl.pack(anchor="w", padx=20, pady=(0, 15))
        ctk.CTkButton(set_card, text="⚙️ Change Path", command=self.change_destination, height=35, font=("Inter", 12), fg_color=C_CARD, text_color=C_TEXT, hover_color=C_CARD_HOVER).pack(anchor="w", padx=20, pady=(0, 20))
        
        ctk.CTkLabel(set_card, text="Advanced Configuration", font=("Inter", 14, "bold"), text_color=C_TEXT).pack(anchor="w", padx=20, pady=(10, 5))
        
        self.startup_var = ctk.BooleanVar(value=is_startup_enabled())
        self.startup_switch = ctk.CTkSwitch(set_card, text="Run on Windows Startup (Minimized)", variable=self.startup_var, font=("Inter", 12), command=lambda: toggle_startup(self.startup_var.get()))
        self.startup_switch.pack(anchor="w", padx=20, pady=(0, 15))

        ctk.CTkLabel(set_card, text="Appearance", font=("Inter", 14, "bold"), text_color=C_TEXT).pack(anchor="w", padx=20, pady=(10, 5))
        self.theme_var = ctk.StringVar(value=CURRENT_THEME_NAME)
        theme_menu = ctk.CTkOptionMenu(set_card, values=list(THEMES.keys()), variable=self.theme_var, font=("Inter", 12), fg_color=C_CARD_SOLID, button_color=C_CARD_HOVER, button_hover_color=C_PURPLE, command=self.handle_theme_change)
        theme_menu.pack(anchor="w", padx=20, pady=(0, 5))
        self.theme_warn_lbl = ctk.CTkLabel(set_card, text="", font=("Inter", 11, "italic"), text_color=C_RED)
        self.theme_warn_lbl.pack(anchor="w", padx=20, pady=(0, 15))

        ctk.CTkButton(set_card, text="🛠️ Black Box (Filter)", command=self.open_black_box, height=35, font=("Inter", 12), fg_color="transparent", border_width=1, border_color=C_PURPLE, text_color=C_PURPLE, hover_color="#4c1d95").pack(anchor="w", padx=20, pady=(0, 20))

        # HISTORY PAGE
        self.page_history = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.page_history.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.page_history, text="🕒 DOWNLOAD HISTORY", font=("Inter", 16, "bold"), text_color=C_GREEN).grid(row=0, column=0, sticky="w", pady=(10,20))
        self.history_container = ctk.CTkFrame(self.page_history, fg_color="transparent")
        self.history_container.grid(row=1, column=0, sticky="nsew")
        self.history_container.grid_columnconfigure(0, weight=1)
        try:
            self.page_history._scrollbar.configure(width=0)
            self.page_history._scrollbar.grid_forget()
        except: pass

        # ABOUT PAGE
        self.page_about = ctk.CTkFrame(self, fg_color="transparent")
        self.page_about.grid_columnconfigure(0, weight=1)
        
        about_card = ctk.CTkFrame(self.page_about, fg_color=C_PANEL, corner_radius=15)
        about_card.pack(pady=50, padx=50, fill="both", expand=True)
        
        ctk.CTkLabel(about_card, text="JHATPAT", font=("Inter", 24, "bold", "italic"), text_color=C_PURPLE).pack(pady=(40, 0))
        ctk.CTkLabel(about_card, text="DOWNLOADER", font=("Inter", 16, "bold", "italic"), text_color=C_GREEN).pack()
        ctk.CTkLabel(about_card, text="Version 5.5 Premium", font=("Inter", 12), text_color=C_MUTED).pack(pady=(5, 20))
        
        ctk.CTkLabel(about_card, text="A lightning-fast, beautifully designed video & audio extractor.\nCreated to make downloading seamless and organized.", font=("Inter", 14), text_color=C_TEXT, justify="center").pack(pady=20)
        
        gh_btn = ctk.CTkButton(about_card, text="⭐ GitHub", fg_color="#333", hover_color="#555", font=("Inter", 13, "bold"), 
                               command=lambda: __import__('webbrowser').open("https://github.com/kakdamba"))
        gh_btn.pack(pady=(10, 10))

        bug_btn = ctk.CTkButton(about_card, text="🐞 Bug Report", fg_color="#b91c1c", hover_color="#991b1b", font=("Inter", 13, "bold"), 
                               command=lambda: __import__('webbrowser').open("mailto:ombhatswaha@duck.com"))
        bug_btn.pack(pady=(0, 10))

        contact_btn = ctk.CTkButton(about_card, text="✉️ Contact Developer", fg_color="#1d4ed8", hover_color="#1e40af", font=("Inter", 13, "bold"), 
                               command=lambda: __import__('webbrowser').open("mailto:ombhatswaha@duck.com"))
        contact_btn.pack(pady=(0, 30))

        # SUPPORT PAGE
        self.page_support = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.page_support.grid_columnconfigure(0, weight=1)
        try:
            self.page_support._scrollbar.configure(width=0)
            self.page_support._scrollbar.grid_forget()
        except: pass
        
        sup_card = ctk.CTkFrame(self.page_support, fg_color=C_PANEL, corner_radius=15)
        sup_card.pack(pady=20, padx=20, fill="both", expand=True)
        
        ctk.CTkLabel(sup_card, text="Support", font=("Inter", 24, "bold"), text_color=C_TEXT).pack(pady=(30, 5))
        ctk.CTkLabel(sup_card, text="Thank you for using our software ❤️\nIf you'd like to support development, you can contribute below.", font=("Inter", 13), text_color=C_MUTED, justify="center").pack(pady=(0, 20))
        
        # UPI Section
        upi_frame = ctk.CTkFrame(sup_card, fg_color=C_CARD, corner_radius=12)
        upi_frame.pack(fill="x", padx=40, pady=10)
        ctk.CTkLabel(upi_frame, text="UPI Support", font=("Inter", 14, "bold"), text_color=C_PURPLE).pack(pady=(15, 5))
        
        try:
            qr_img = Image.open(resource_path("upi_qr.png")).resize((180, 180), Image.Resampling.LANCZOS)
            qr_ctk_img = ctk.CTkImage(qr_img, size=(180, 180))
            qr_lbl = ctk.CTkLabel(upi_frame, image=qr_ctk_img, text="")
            qr_lbl.pack(pady=(5, 5))
        except Exception as e:
            err_msg = f"[ QR Code Error ]\n{type(e).__name__}: {str(e)}"
            ctk.CTkLabel(upi_frame, text=err_msg, font=("Inter", 10), text_color=C_RED).pack(pady=(5, 5))

        ctk.CTkLabel(upi_frame, text="Scan to pay with any UPI app", font=("Inter", 12), text_color=C_MUTED).pack(pady=(0, 15))

        # Connect with us
        conn_frame = ctk.CTkFrame(sup_card, fg_color=C_CARD, corner_radius=12)
        conn_frame.pack(fill="x", padx=40, pady=10)
        ctk.CTkLabel(conn_frame, text="Connect With Us", font=("Inter", 14, "bold"), text_color=C_GREEN).pack(pady=(15, 10))
        
        yt_frame = ctk.CTkFrame(conn_frame, fg_color="transparent")
        yt_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(yt_frame, text="YouTube Channels", font=("Inter", 13, "bold"), text_color=C_TEXT).pack(anchor="w")
        ctk.CTkButton(yt_frame, text="🎥 Travel & Creative Content", fg_color="transparent", text_color=C_PURPLE, hover_color=C_CARD_HOVER, anchor="w", command=lambda: __import__('webbrowser').open("https://www.youtube.com/@AlpeshMac")).pack(fill="x", pady=2)
        ctk.CTkButton(yt_frame, text="🎮 Gaming Content", fg_color="transparent", text_color=C_PURPLE, hover_color=C_CARD_HOVER, anchor="w", command=lambda: __import__('webbrowser').open("https://www.youtube.com/@KAKDAMBAA")).pack(fill="x", pady=2)

        ig_frame = ctk.CTkFrame(conn_frame, fg_color="transparent")
        ig_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(ig_frame, text="Instagram", font=("Inter", 13, "bold"), text_color=C_TEXT).pack(anchor="w")
        ctk.CTkButton(ig_frame, text="📸 @alpesh__mac", fg_color="transparent", text_color=C_PURPLE, hover_color=C_CARD_HOVER, anchor="w", command=lambda: __import__('webbrowser').open("https://instagram.com/alpesh__mac")).pack(fill="x", pady=2)
        ctk.CTkButton(ig_frame, text="📸 @kakdamba", fg_color="transparent", text_color=C_PURPLE, hover_color=C_CARD_HOVER, anchor="w", command=lambda: __import__('webbrowser').open("https://instagram.com/kakdamba")).pack(fill="x", pady=2)
        
        # Tiny Footer
        footer_frame = ctk.CTkFrame(sup_card, fg_color="transparent")
        footer_frame.pack(fill="x", padx=40, pady=(20, 20))
        ctk.CTkLabel(footer_frame, text="Made with ❤️ by Kakdamba\n©2026 jhatpat downloader", font=("Inter", 10), text_color=C_MUTED, justify="center").pack()

    def switch_page(self, name):
        for txt, btn in self.nav_buttons.items():
            if txt == name:
                btn.configure(fg_color="#2e1065", text_color="#ffffff")
            else:
                btn.configure(fg_color="transparent", text_color="#d1d5db")
                
        self.main_scroll.grid_forget()
        self.page_history.grid_forget()
        self.page_about.grid_forget()
        self.page_queue.grid_forget()
        try: self.page_settings.grid_forget()
        except: pass
        try: self.page_support.grid_forget()
        except: pass
        
        if name == "Home":
            self.main_scroll.grid(row=0, column=1, sticky="nsew", padx=20, pady=10)
        elif name == "Queue":
            self.refresh_queue()
            self.page_queue.grid(row=0, column=1, sticky="nsew", padx=20, pady=10)
        elif name == "Downloads":
            self.refresh_history()
            self.page_history.grid(row=0, column=1, sticky="nsew", padx=20, pady=10)
        elif name == "Settings":
            self.page_settings.grid(row=0, column=1, sticky="nsew", padx=20, pady=10)
        elif name == "About":
            self.page_about.grid(row=0, column=1, sticky="nsew", padx=20, pady=10)
        elif name == "Support":
            self.page_support.grid(row=0, column=1, sticky="nsew", padx=20, pady=10)

    def refresh_history(self, limit=10):
        for widget in self.history_container.winfo_children():
            widget.destroy()
            
        top_frame = ctk.CTkFrame(self.history_container, fg_color="transparent")
        top_frame.pack(fill="x", pady=(0,10))
        ctk.CTkButton(top_frame, text="🗑️ Clear All History", width=120, fg_color=C_CARD, text_color=C_RED, hover_color="#451a1a", 
                      command=self.clear_all_history).pack(side="right", padx=15)
                      
        if not self.history_db:
            ctk.CTkLabel(self.history_container, text="No download history yet.", font=("Inter", 12), text_color=C_MUTED).pack(pady=20)
            return
            
        display_list = self.history_db[:limit]
        for item in display_list:
            row = ctk.CTkFrame(self.history_container, fg_color=C_PANEL, corner_radius=8)
            row.pack(fill="x", pady=5)
            
            thumb_lbl = ctk.CTkLabel(row, text="🎬", font=("Inter", 18), width=60, height=40, fg_color=C_CARD, corner_radius=6)
            thumb_lbl.pack(side="left", padx=(10, 5), pady=10)
            
            thumb_url = item.get("thumb")
            if thumb_url:
                def load_thumb(lbl=thumb_lbl, url=thumb_url):
                    try:
                        res = requests.get(url, timeout=3)
                        img = Image.open(BytesIO(res.content)).resize((60, 40), Image.Resampling.LANCZOS)
                        ctk_img = ctk.CTkImage(img, size=(60, 40))
                        app_instance.after(0, lambda: lbl.configure(image=ctk_img, text=""))
                    except: pass
                threading.Thread(target=load_thumb, daemon=True).start()
                
            ctk.CTkLabel(row, text=item["name"][:45] + ("..." if len(item["name"])>45 else ""), font=("Inter", 12), text_color=C_TEXT).pack(side="left", padx=10, pady=12)
            
            ctk.CTkButton(row, text="Remove", width=60, fg_color="transparent", text_color=C_RED, hover_color="#451a1a", 
                          command=lambda i=item: self.remove_from_history(i)).pack(side="right", padx=(0, 15), pady=12)
            ctk.CTkButton(row, text="Open", width=60, fg_color=C_CARD, hover_color=C_GREEN, 
                          command=lambda p=item["path"]: self.open_file_safe(p)).pack(side="right", padx=10, pady=12)

        if len(self.history_db) > limit:
            ctk.CTkButton(self.history_container, text="See More", height=35, font=("Inter", 12), fg_color="transparent", border_width=1, border_color=C_PURPLE, text_color=C_PURPLE, hover_color="#4c1d95", command=lambda: self.refresh_history(limit=limit+10)).pack(pady=(15, 30))

    def clear_all_history(self):
        self.history_db = []
        self.save_settings()
        self.refresh_history()
        
    def remove_from_history(self, item):
        if item in self.history_db:
            self.history_db.remove(item)
            self.save_settings()
            self.refresh_history()
            
    def open_file_safe(self, path):
        if os.path.exists(path):
            os.startfile(path)
        else:
            self.add_log(f"File not found: {path}")

    def add_to_history(self, filepath, thumb_url=None):
        for item in self.history_db:
            if item.get("path") == filepath:
                return
        basename = os.path.basename(filepath)
        self.history_db.insert(0, {"name": basename, "path": filepath, "thumb": thumb_url})
        self.save_settings()

    def build_option_card(self, parent, title, subtitle, color, mode):
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.pack(fill="x", padx=15, pady=15)
        
        icon = "▶" if mode == "video" else "🎵"
        icon_lbl = ctk.CTkLabel(top, text=icon, font=("Arial", 22), width=45, height=45, fg_color=C_CARD, corner_radius=10, text_color=C_TEXT)
        icon_lbl.pack(side="left")
        
        t_frame = ctk.CTkFrame(top, fg_color="transparent")
        t_frame.pack(side="left", padx=10)
        ctk.CTkLabel(t_frame, text=f"Download", font=("Inter", 10), text_color=C_MUTED).pack(anchor="w")
        ctk.CTkLabel(t_frame, text=title, font=("Inter", 18, "bold"), text_color=C_TEXT).pack(anchor="w")
        
        if subtitle == "🎵 Extract Audio":
            sub_btn = ctk.CTkButton(t_frame, text=subtitle, font=("Inter", 11, "bold"), fg_color=color, text_color="#000", corner_radius=6, height=28, hover_color="#059669", command=self.handle_local_audio_picker)
            sub_btn.pack(anchor="w", pady=(2,0))
        else:
            ctk.CTkLabel(t_frame, text=subtitle, font=("Inter", 9), fg_color=color, text_color="#000", corner_radius=4, padx=4).pack(anchor="w", pady=(2,0))

        drop_frame = ctk.CTkFrame(parent, fg_color="transparent")
        drop_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        if mode == "video":
            self.res_var = ctk.StringVar(value="1080p")
            ctk.CTkOptionMenu(drop_frame, values=["4K", "1080p", "720p", "480p"], variable=self.res_var, font=("Inter", 11), fg_color=C_CARD_SOLID, button_color=C_CARD_HOVER, button_hover_color=color).pack(side="left", fill="x", expand=True, padx=(0,5))
            saved_vid_fmt = getattr(self, 'saved_video_fmt', 'MP4')
            self.vid_fmt_var = ctk.StringVar(value=saved_vid_fmt)
            ctk.CTkOptionMenu(drop_frame, values=["MP4", "MOV", "MKV"], variable=self.vid_fmt_var, font=("Inter", 11), fg_color=C_CARD_SOLID, button_color=C_CARD_HOVER, button_hover_color=color, command=lambda _: self.save_settings()).pack(side="left", fill="x", expand=True, padx=(5,0))
        else:
            self.aud_var = ctk.StringVar(value="320kbps")
            self.aud_menu = ctk.CTkOptionMenu(drop_frame, values=["320kbps", "256kbps", "128kbps"], variable=self.aud_var, font=("Inter", 11), fg_color=C_CARD_SOLID, button_color=C_CARD_HOVER, button_hover_color=color)
            self.aud_menu.pack(side="left", fill="x", expand=True, padx=(0,5))
            
            saved_fmt = getattr(self, 'saved_audio_fmt', 'MP3')
            self.fmt_var = ctk.StringVar(value=saved_fmt)
            
            def handle_aud_fmt(choice):
                if choice == "WAV":
                    self.aud_menu.configure(state="disabled")
                else:
                    self.aud_menu.configure(state="normal")
                self.save_settings()
                
            ctk.CTkOptionMenu(drop_frame, values=["MP3", "WAV"], variable=self.fmt_var, font=("Inter", 11), fg_color=C_CARD_SOLID, button_color=C_CARD_HOVER, button_hover_color=color, command=handle_aud_fmt).pack(side="left", fill="x", expand=True, padx=(5,0))
            
            if saved_fmt == "WAV":
                self.aud_menu.configure(state="disabled")

        btn = ctk.CTkButton(parent, text=f"↓ Download {title}", height=38, fg_color=color, hover_color="#7c3aed" if mode=="video" else "#059669", text_color="#000" if color==C_GREEN else C_TEXT, font=("Inter", 12, "bold"), command=lambda: self.add_to_logic(mode))
        btn.pack(fill="x", padx=15, pady=(0, 15))

    def update_radar(self):
        try:
            self.radar_canvas.delete("all")
            cx, cy, r = 50, 50, 42
            
            if hasattr(self, 'radar_bg_img') and self.radar_bg_img:
                self.radar_canvas.create_image(cx, cy, image=self.radar_bg_img)
            
            for i in range(1, 4):
                self.radar_canvas.create_oval(cx - r*i/3, cy - r*i/3, cx + r*i/3, cy + r*i/3, outline="#2a2d3e", width=1)
            
            self.radar_canvas.create_arc(cx-r, cy-r, cx+r, cy+r, start=self.radar_angle, extent=60, fill="", outline=C_PURPLE, width=2)
            self.radar_canvas.create_line(cx, cy, cx + r * math.cos(math.radians(self.radar_angle)), cy - r * math.sin(math.radians(self.radar_angle)), fill=C_PURPLE)

            self.radar_angle = (self.radar_angle - 5) % 360
            self.after(40, self.update_radar)
        except: pass

    def update_engine(self):
        try: subprocess.run([sys.executable, "-m", "pip", "install", "-U", "yt-dlp"], capture_output=True)
        except: pass

    def fetch_metadata(self, url):
        if not url or "http" not in url: return
        self.current_meta = None
        self.url_entry.delete(0, 'end'); self.url_entry.insert(0, url)
        self.active_badge.configure(text="🔍 SCANNING BROWSER", text_color=C_PURPLE)
        self.status_desc.configure(text="Extracting metadata...", text_color=C_PURPLE)
        self.video_title.configure(text="Loading metadata...")
        
        def worker():
            try:
                opts = {'quiet': True, 'noplaylist': True}
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    
                self.current_meta = info
                title = info.get('title', 'Unknown Title')
                res = info.get('resolution', 'Unknown Res')
                ext = info.get('ext', 'mp4')
                dur = info.get('duration_string', '--:--')
                extractor = info.get('extractor_key', 'Unknown')
                thumb_url = info.get('thumbnail')

                self.after(0, lambda: self.update_thumb_ui(title, extractor, f"{res} • {dur} • {ext.upper()}", thumb_url))
            except Exception as e:
                self.add_log(f"Meta Error: {e}")
                self.after(0, lambda: self.video_title.configure(text="Failed to extract metadata. Ready to download anyway."))
                self.after(0, lambda: self.reset_status())

        threading.Thread(target=worker, daemon=True).start()

    def update_thumb_ui(self, title, platform, meta, thumb_url):
        self.video_title.configure(text=title)
        self.platform_lbl.configure(text=f"📺 {platform}")
        self.video_meta.configure(text=meta)
        self.active_badge.configure(text="🎯 LINK CAPTURED", text_color=C_GREEN)
        self.status_desc.configure(text="Ready to download", text_color=C_MUTED)

        if thumb_url:
            def load_img():
                try:
                    res = requests.get(thumb_url, timeout=5)
                    img = Image.open(BytesIO(res.content))
                    img = img.resize((240, 135), Image.Resampling.LANCZOS)
                    ctk_img = ctk.CTkImage(img, size=(240, 135))
                    self.after(0, lambda: self.thumb_lbl.configure(image=ctk_img, text=""))
                except: pass
            threading.Thread(target=load_img, daemon=True).start()

    def reset_status(self):
        self.active_badge.configure(text="🛡️ SCOUT ACTIVE", text_color=C_GREEN)
        self.status_desc.configure(text="Monitoring browser for videos...", text_color=C_MUTED)

    def listen_to_clipboard(self):
        last = pyperclip.paste().strip()
        while True:
            c = pyperclip.paste().strip()
            if c != last and "http" in c and len(c) < 500:
                self.after(0, lambda: self.fetch_metadata(c))
                last = c
            time.sleep(1)

    def catch_from_chrome(self, url, mtype="video", ptitle=""): 
        self.show_window()
        if mtype in ["video", "audio"]:
            self.fetch_metadata(url)
        self.add_to_logic(mtype, auto_url=url, ptitle=ptitle)

    def handle_local_audio_picker(self):
        filepath = filedialog.askopenfilename(title="Select Video File", filetypes=[("Video Files", "*.mp4 *.mkv *.webm *.avi *.mov *.flv")])
        if filepath:
            title = os.path.basename(filepath)
            self.dl_queue.put((title, filepath, "local_audio", ""))
            with self.pending_lock:
                self.pending_list.append(title)
            self.update_pending_ui()
            self.switch_page("Home")
            self.after(100, lambda: self.main_scroll._parent_canvas.yview_moveto(1.0))

    def add_to_logic(self, mode, auto_url=None, ptitle=""):
        u = auto_url if auto_url else self.url_entry.get().strip()
        if not u: return
        
        if not auto_url or self.url_entry.get().strip() == auto_url:
            self.url_entry.delete(0, 'end')
            
        self.active_badge.configure(text="⚡ PREPARING...", text_color=C_PURPLE)
        self.status_desc.configure(text="Fetching queue details...", text_color=C_MUTED)
        
        self.switch_page("Home")
        self.after(100, lambda: self.main_scroll._parent_canvas.yview_moveto(1.0))
        
        threading.Thread(target=self._process_url_for_queue, args=(u, mode, ptitle), daemon=True).start()

    def cancel_all(self):
        with self.pending_lock:
            self.pending_list.clear()
        self.update_pending_ui()
        for widget in self.queue_container.winfo_children():
            if isinstance(widget, DownloadRow):
                widget.cancel()

    def _process_url_for_queue(self, url, mode, ptitle=""):
        if mode in ["image", "subtitle"]:
            filename = url.split('/')[-1].split('?')[0] or "downloaded_file"
            with self.pending_lock:
                self.pending_list.append(filename)
                self.dl_queue.put((filename, url, mode, ptitle))
            self.after(0, self.update_pending_ui)
            self.after(0, self.reset_status)
            return

        if mode in ["video", "audio"] and 'youtube' in url.lower() and 'list=' in url and 'watch' in url.lower():
            try:
                list_id = url.split('list=')[1].split('&')[0]
                if list_id and not list_id.startswith('RD'):
                    url = f"https://www.youtube.com/playlist?list={list_id}"
            except: pass

        try:
            opts = {'quiet': True, 'extract_flat': True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
            if 'entries' in info:
                entries = list(info['entries'])
                playlist_title = info.get('title')
                if not playlist_title: playlist_title = "Playlist"
            else:
                entries = [info]
                playlist_title = ptitle
                
            with self.pending_lock:
                for entry in entries:
                    title = entry.get('title', 'Unknown File')
                    entry_url = entry.get('url', url)
                    if not entry_url.startswith('http'):
                        if 'youtube' in url.lower() or 'youtu.be' in url.lower():
                            entry_url = f"https://www.youtube.com/watch?v={entry_url}"
                        else:
                            entry_url = url
                    self.pending_list.append(title)
                    self.dl_queue.put((title, entry_url, mode, playlist_title))
                    
            self.after(0, self.update_pending_ui)
            self.after(0, self.reset_status)
        except Exception as e:
            self.add_log(f"Queue Error: {e}")
            self.after(0, self.reset_status)

    def update_pending_ui(self):
        with self.pending_lock:
            count = len(self.pending_list)
            if count == 0:
                self.pending_lbl.configure(text="")
            else:
                self.pending_lbl.configure(text=f"⏳ {count} upcoming items waiting (Check Queue tab)")
                
        if self.page_queue.winfo_ismapped():
            self.refresh_queue()

    def refresh_queue(self):
        for widget in self.queue_list_container.winfo_children():
            widget.destroy()
            
        with self.pending_lock:
            if not self.pending_list:
                ctk.CTkLabel(self.queue_list_container, text="No upcoming downloads.", font=("Inter", 12), text_color=C_MUTED).pack(pady=20)
                return
                
            display_list = self.pending_list[:10]
            for i, title in enumerate(display_list):
                row = ctk.CTkFrame(self.queue_list_container, fg_color=C_PANEL, corner_radius=8)
                row.pack(fill="x", pady=5)
                
                num_lbl = ctk.CTkLabel(row, text=str(i+1), font=("Inter", 12, "bold"), text_color=C_PURPLE, width=30)
                num_lbl.pack(side="left", padx=10, pady=12)
                
                ctk.CTkLabel(row, text=title[:60] + ("..." if len(title)>60 else ""), font=("Inter", 12), text_color=C_TEXT).pack(side="left", padx=5, pady=12)
                
                ctk.CTkButton(row, text="Cancel", width=60, fg_color="transparent", text_color=C_RED, hover_color="#451a1a", 
                              command=lambda t=title: self.cancel_pending(t)).pack(side="right", padx=15, pady=12)
                              
            remaining = len(self.pending_list) - 10
            if remaining > 0:
                ctk.CTkLabel(self.queue_list_container, text=f"...and {remaining} more items in queue.", font=("Inter", 12, "italic"), text_color=C_MUTED).pack(pady=20)

    def cancel_pending(self, title):
        with self.pending_lock:
            if title in self.pending_list:
                self.pending_list.remove(title)
        self.update_pending_ui()

    def download_worker(self):
        while True: 
            title, url, mode, pt = self.dl_queue.get()
            
            should_download = False
            with self.pending_lock:
                if title in self.pending_list:
                    self.pending_list.remove(title)
                    should_download = True
            
            if not should_download:
                self.dl_queue.task_done()
                continue
                
            self.after(0, self.update_pending_ui)
            
            row_ui = [None]
            def create_ui():
                self.empty_q.pack_forget()
                r = DownloadRow(self.queue_container, title, mode)
                r.pack(fill="x", padx=10, pady=5)
                row_ui[0] = r
            
            self.after(0, create_ui)
            
            while row_ui[0] is None: time.sleep(0.1)
            self.run_dl(url, mode, row_ui[0], pt)
            self.dl_queue.task_done()

    def run_dl(self, url, mode, row_ui, playlist_title):
        if mode == "local_audio":
            self.run_local_ffmpeg(url, row_ui)
            return

        base_folders = {"video": "Videos", "audio": "Audio", "image": "Images", "subtitle": "Subtitles"}
        folder_name = base_folders.get(mode, "Downloads")
        
        target_dir = os.path.join(self.save_path, folder_name)
        if playlist_title:
            pt_clean = "".join([c for c in playlist_title if c.isalnum() or c in ' -_']).strip()
            if not pt_clean: pt_clean = "Playlist_Folder"
            target_dir = os.path.join(target_dir, pt_clean)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
            
        if mode in ["image", "subtitle"]:
            self.run_direct_dl(url, mode, row_ui, target_dir)
            return

        ff = os.path.join(resource_path("ffmpeg"), "bin")
        q = {"4K":"2160","1080p":"1080","720p":"720","480p":"480"}.get(self.res_var.get(), "1080")
        
        def hook(d):
            if row_ui.stop_flag: raise Exception("USER_STOP")
            if d['status'] == 'downloading':
                try:
                    p = d.get('_percent_str', '0%')
                    ansi = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                    p_clean = float(ansi.sub('', p).strip().replace('%',''))
                    speed = ansi.sub('', d.get('_speed_str', '0MiB/s')).strip()
                    total = ansi.sub('', d.get('_total_bytes_str', d.get('_estimate_bytes_str', '--'))).strip()
                    
                    self.after(0, lambda: row_ui.bar.set(p_clean/100))
                    self.after(0, lambda: row_ui.pct_lbl.configure(text=f"{p_clean}%"))
                    self.after(0, lambda: row_ui.size_lbl.configure(text=f"{speed}   {total}"))
                    
                    filename = d.get('filename')
                    if filename and "Unknown" in row_ui.title_lbl.cget("text"):
                        basename = os.path.basename(filename)
                        name_no_ext = os.path.splitext(basename)[0]
                        icon = "🎥 " if mode == "video" else "🎵 "
                        self.after(0, lambda n=name_no_ext: row_ui.title_lbl.configure(text=f"{icon}{n[:30]}..."))
                    
                    self.after(0, lambda: self.speed_lbl.configure(text=f"{speed}\nDownload Speed"))
                except: pass
            elif d['status'] == 'finished':
                filename = d.get('filename')
                info = d.get('info_dict', {})
                thumb = info.get('thumbnail')
                if filename:
                    self.after(0, lambda f=filename, t=thumb: self.add_to_history(f, t))

        outtmpl = os.path.join(target_dir, '%(title)s.%(ext)s')
            
        opts = {'ffmpeg_location': ff, 'outtmpl': outtmpl, 'progress_hooks': [hook], 'quiet': True, 'noplaylist': True}
        
        if mode == "video":
            v_fmt = self.vid_fmt_var.get().lower() if hasattr(self, 'vid_fmt_var') else 'mp4'
            opts.update({'format': f'bestvideo[height<={q}]+bestaudio/best[height<={q}]/best', 'merge_output_format': v_fmt})
        else:
            fmt = self.fmt_var.get().lower()
            opts.update({'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': fmt,'preferredquality': '320'}]})

        try:
            with yt_dlp.YoutubeDL(opts) as ydl: ydl.download([url])
            self.total_scouted += 1
            self.after(0, lambda: self.scout_count_lbl.configure(text=f"Scouted\n{self.total_scouted}"))
            self.after(0, row_ui.complete)
        except Exception as e:
            self.add_log(f"FFmpeg Error: {e}")
            self.after(0, lambda: row_ui.pct_lbl.configure(text="Error", text_color=C_RED))
            self.after(1000, row_ui.remove_self)

    def run_direct_dl(self, url, mode, row_ui, target_dir):
        try:
            self.after(0, lambda: row_ui.title_lbl.configure(text=f"⬇️ {row_ui.title_lbl.cget('text')}"))
            self.after(0, lambda: row_ui.bar.set(0.5))
            self.after(0, lambda: row_ui.pct_lbl.configure(text="Downloading..."))
            
            res = requests.get(url, stream=True, timeout=10)
            res.raise_for_status()
            
            filename = url.split('/')[-1].split('?')[0] or f"downloaded_{mode}"
            if '.' not in filename: filename += ".png" if mode == "image" else ".srt"
            
            out_path = os.path.join(target_dir, filename)
            with open(out_path, 'wb') as f:
                for chunk in res.iter_content(chunk_size=8192):
                    if row_ui.stop_flag: raise Exception("USER_STOP")
                    if chunk: f.write(chunk)
            
            self.after(0, lambda: row_ui.bar.set(1.0))
            self.after(0, lambda: row_ui.pct_lbl.configure(text="100%"))
            self.total_scouted += 1
            self.after(0, lambda: self.scout_count_lbl.configure(text=f"Scouted\n{self.total_scouted}"))
            self.after(0, row_ui.complete)
            self.after(0, lambda f=out_path: self.add_to_history(f, None))
        except Exception as e:
            if "USER_STOP" not in str(e):
                self.add_log(f"Direct DL Error: {e}")
                self.after(0, lambda: row_ui.pct_lbl.configure(text="Error", text_color=C_RED))
                self.after(1000, row_ui.remove_self)

    def run_local_ffmpeg(self, filepath, row_ui):
        ff_dir = os.path.join(resource_path("ffmpeg"), "bin")
        ff = os.path.join(ff_dir, "ffmpeg.exe") if os.name == 'nt' else os.path.join(ff_dir, "ffmpeg")
        if not os.path.exists(ff): ff = "ffmpeg"
        
        name_no_ext = os.path.splitext(os.path.basename(filepath))[0]
        fmt = self.fmt_var.get().lower()
        out_path = os.path.join(self.save_path, f"{name_no_ext}.{fmt}")
        
        q = self.aud_var.get()
        kbps = q.replace("kbps", "k") if q else "320k"
        
        try:
            self.after(0, lambda: row_ui.pct_lbl.configure(text="Converting..."))
            self.after(0, lambda: row_ui.bar.configure(mode="indeterminate"))
            self.after(0, lambda: row_ui.bar.start())
            
            if fmt == "wav":
                cmd = [ff, "-y", "-i", filepath, "-vn", out_path]
            else:
                cmd = [ff, "-y", "-i", filepath, "-vn", "-b:a", kbps, out_path]
                
            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags)
            
            while proc.poll() is None:
                if row_ui.stop_flag:
                    proc.kill()
                    raise Exception("USER_STOP")
                time.sleep(0.1)
                
            if proc.returncode != 0:
                raise Exception("Conversion Failed")
                
            self.after(0, lambda: row_ui.bar.stop())
            self.after(0, lambda: row_ui.bar.configure(mode="determinate"))
            self.after(0, row_ui.complete)
            self.after(0, lambda: self.add_to_history(out_path, None))
        except Exception as e:
            if "USER_STOP" not in str(e):
                self.add_log(f"FFmpeg Error: {e}")
                self.after(0, lambda: row_ui.pct_lbl.configure(text="Error", text_color=C_RED))
                self.after(0, lambda: row_ui.cancel_btn.configure(text="✖", command=row_ui.remove_self))
                self.after(1000, row_ui.remove_self)

    def cleanup_part_files(self):
        try:
            for root, dirs, files in os.walk(self.save_path):
                for f in files:
                    if f.endswith((".part", ".ytdl")):
                        try: os.remove(os.path.join(root, f))
                        except: pass
        except: pass

    def add_log(self, msg): self.log_messages.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
    def open_black_box(self):
        log_win = ctk.CTkToplevel(self)
        log_win.title("Diagnostics")
        log_win.geometry("600x400")
        box = ctk.CTkTextbox(log_win, width=580, height=380, font=("Consolas", 12))
        box.pack(padx=10, pady=10)
        box.insert("0.0", "\n".join(self.log_messages) if self.log_messages else "No logs recorded.")

    def create_tray(self):
        try:
            image = Image.open(resource_path("icon.ico"))
            self.tray_icon = pystray.Icon("Jhatpat", image, "Jhatpat", (item('Show', self.show_window, default=True), item('Exit', self.quit_app)))
            self.tray_icon.run()
        except: pass
    def quit_app(self, icon=None):
        if icon: icon.stop()
        self.quit(); sys.exit()
    def minimize_to_tray(self): self.withdraw()

    def show_window(self, icon=None, item=None):
        self.after(0, self._show_window_internal)
        
    def _show_window_internal(self):
        self.deiconify()
        self.state('normal')
        self.lift()
        self.focus_force()
    
    def load_settings(self):
        self.save_path = os.path.join(os.path.expanduser("~"), "Downloads")
        self.history_db = []
        if os.path.exists(CONFIG_FILE):
            try:
                data = json.load(open(CONFIG_FILE, "r"))
                self.save_path = data.get("path", self.save_path)
                self.history_db = data.get("history", [])
                self.saved_audio_fmt = data.get("audio_fmt", "MP3")
                self.saved_video_fmt = data.get("video_fmt", "MP4")
            except: pass
            
    def handle_theme_change(self, choice):
        self.save_settings()
        self.theme_warn_lbl.configure(text="Restart app to apply theme changes.")

    def save_settings(self):
        a_fmt = self.fmt_var.get() if hasattr(self, 'fmt_var') else getattr(self, 'saved_audio_fmt', 'MP3')
        v_fmt = self.vid_fmt_var.get() if hasattr(self, 'vid_fmt_var') else getattr(self, 'saved_video_fmt', 'MP4')
        t_name = self.theme_var.get() if hasattr(self, 'theme_var') else CURRENT_THEME_NAME
        with open(CONFIG_FILE, "w") as f: json.dump({"path": self.save_path, "history": self.history_db, "audio_fmt": a_fmt, "video_fmt": v_fmt, "theme": t_name}, f)
        
    def open_destination(self): os.startfile(self.save_path)
    def change_destination(self):
        f = filedialog.askdirectory(initialdir=self.save_path)
        if f:
            self.save_path = f
            self.save_settings()
            try: self.path_lbl.configure(text=self.save_path)
            except: pass
            self.add_log(f"Download path changed to: {self.save_path}")

if __name__ == "__main__":
    check_single_instance()
    app = JhatpatDownloader()
    app.mainloop()
