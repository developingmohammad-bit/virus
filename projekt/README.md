# SystemLock Pro v4.0
Windows 11 – Single-file Python remote lock

**File:** `blocker.py` (29 KB, 1 file, zero external pip deps)
**Icon:** `app.ico` + `icon_512.png`

---

## on.json – دقیق

URL که برنامه می‌خواند:
```
https://raw.githubusercontent.com/developingmohammad-bit/virus/main/on.json
```

مجاز برای **LOCK = True**:
```
True
true
1
on
yes
enable
{"on":true}
```

مجاز برای **UNLOCK = False**:
```
False
false
0
off
no
disable
{"on":false}
```

توصیه: دقیقا بنویس `True` یا `False` تک خط.

Bug fix v4: cache-buster `?v=timestamp`, debounce 2x, false-first parsing, last_success_remote memory.

---

## پیش‌نیاز

- Windows 11 x64
- Python 3.10+ (tkinter همراه نصب است)
- **هیچ pip لازم نیست** برای اجرا
- برای ساخت exe: `pip install pyinstaller`

---

## اجرا

تست امن:
```
python blocker.py --test
```
- ۲ ثانیه بعد قفل می‌آید
- ۲۰ ثانیه بعد خودکار آزاد
- F12 خروج فوری
- Ctrl+Shift+Q → Mohammad1405

اجرای واقعی:
```
pythonw blocker.py
```
یا
```
python blocker.py --console
```

دستورات:
```
python blocker.py --install      # autostart Registry + Task Scheduler
python blocker.py --uninstall    # حذف کامل
python blocker.py --status
python blocker.py --test         # safe mode
```

خروج اضطراری:
- **Ctrl+Shift+Q → Mohammad1405**
- Kill-switch file: `echo 1 > %USERPROFILE%\.systemlock_kill`
- Safe Mode

لاگ:
```
%TEMP%\systemlock_pro.log
```

---

## ساخت EXE

```
pip install pyinstaller
pyinstaller --onefile --noconsole --icon=app.ico --name SystemLockPro blocker.py
```
خروجی: `dist\SystemLockPro.exe` ~10 MB

حرفه‌ای:
```
pyinstaller --onefile --noconsole --uac-admin --icon=app.ico --name SystemLockPro --version-file version_info.txt blocker.py
```

---

## تغییرات v4.0 vs v3 (باگ‌ها رفع شد)

1. **False گیر می‌کرد** → `fetch_remote_state()` الان `last_success_remote` برمی‌گرداند نه `applied_locked`
2. **Flicker قطع/وصل** → Debounce 2x + TOGGLE_COOLDOWN 2.5s + cache-buster timestamp
3. **Overlay نشتی** → OverlayManager با Lock، create/destroy اتمیک، watchdog 2.2s
4. **دو بار اجرا** → Global Mutex `Global\SystemLockPro_Mohammad_2026`
5. **DPI تار** → SetProcessDpiAwareness V2
6. **Task Manager دوباره باز می‌شد** → هم kill process + هم Registry `DisableTaskMgr`
7. **Emergency گیر** → shutdown_flag، hook uninstall فوری، os._exit(0) تضمینی، 150ms
8. **Thread race** → تمام state ها با `state_lock`
9. **parse on.json گیج** → `parse_remote_payload()` تمیز، false-first
10. **جدید:** mouse auto-center، multi-monitor EnumDisplayMonitors، RotatingFileHandler log، --test / --install / --uninstall داخلی، single-instance، تست F12 فقط در --test

---

فقط ۳ فایل در پروژه:
- blocker.py
- app.ico
- icon_512.png

ساخته شده: 2026-07-03 – Arena.ai
