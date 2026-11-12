import flet as ft
import re
import sqlite3
import os
import shutil
import zlib
import base64
import threading
import time
from datetime import datetime, timedelta
import inspect

# --- سازگارکننده خودکار کدهای فلت 0.24 با فلت نسخه جدید (1.0+) ---
if not hasattr(ft, "app") and hasattr(ft, "run"):
    ft.app = lambda target=None, *a, **kw: ft.run(target or a[0], **kw)

if not hasattr(ft, "ElevatedButton"):
    ft.ElevatedButton = getattr(ft, "Button", getattr(ft, "FilledButton", None))

if hasattr(ft, "Icons"):
    class _CompatIcons:
        def __getattr__(self, name):
            if hasattr(ft.Icons, name):
                return getattr(ft.Icons, name)
            for fb in (
                name.replace("_OUTLINE_", "_"),
                name.replace("_OUTLINED", ""),
                name.replace("_ROUNDED", ""),
                "RESTAURANT",
                "CIRCLE",
            ):
                if hasattr(ft.Icons, fb):
                    return getattr(ft.Icons, fb)
            return getattr(ft.Icons, "INFO", None)
    ft.icons = _CompatIcons()

if hasattr(ft, "Colors"):
    class _CompatColors:
        def __getattr__(self, name):
            if hasattr(ft.Colors, name):
                return getattr(ft.Colors, name)
            return "#9C623E"
        @staticmethod
        def with_opacity(opacity, color):
            if hasattr(ft.Colors, "with_opacity"):
                return ft.Colors.with_opacity(opacity, color)
            return color
    ft.colors = _CompatColors()

class _CompatPadding:
    @staticmethod
    def symmetric(vertical=0, horizontal=0):
        if hasattr(ft, "Padding"):
            if hasattr(ft.Padding, "symmetric"):
                return ft.Padding.symmetric(vertical=vertical, horizontal=horizontal)
            return ft.Padding(left=horizontal, top=vertical, right=horizontal, bottom=vertical)
        return vertical

    @staticmethod
    def all(value=0):
        if hasattr(ft, "Padding"):
            if hasattr(ft.Padding, "all"):
                return ft.Padding.all(value)
            return ft.Padding(left=value, top=value, right=value, bottom=value)
        return value

    @staticmethod
    def only(left=0, top=0, right=0, bottom=0):
        if hasattr(ft, "Padding"):
            return ft.Padding(left=left, top=top, right=right, bottom=bottom)
        return 0

ft.padding = _CompatPadding()

class _CompatBorder:
    @staticmethod
    def all(width=1, color="#000000"):
        if hasattr(ft, "Border"):
            if hasattr(ft.Border, "all"):
                return ft.Border.all(width, color)
            if hasattr(ft.Border, "BorderSide") or hasattr(ft, "BorderSide"):
                side = ft.BorderSide(width, color)
                return ft.Border(top=side, bottom=side, left=side, right=side)
        return None

    @staticmethod
    def only(left=None, top=None, right=None, bottom=None):
        if hasattr(ft, "Border"):
            if hasattr(ft.Border, "only"):
                return ft.Border.only(left=left, top=top, right=right, bottom=bottom)
            return ft.Border(left=left, top=top, right=right, bottom=bottom)
        return None

ft.border = _CompatBorder()

class _CompatBorderRadius:
    @staticmethod
    def all(value=0):
        if hasattr(ft, "BorderRadius"):
            if hasattr(ft.BorderRadius, "all"):
                return ft.BorderRadius.all(value)
            return ft.BorderRadius(top_left=value, top_right=value, bottom_left=value, bottom_right=value)
        return value

    @staticmethod
    def only(top_left=0, top_right=0, bottom_left=0, bottom_right=0):
        if hasattr(ft, "BorderRadius"):
            if hasattr(ft.BorderRadius, "only"):
                return ft.BorderRadius.only(
                    top_left=top_left, top_right=top_right,
                    bottom_left=bottom_left, bottom_right=bottom_right
                )
            return ft.BorderRadius(
                top_left=top_left, top_right=top_right,
                bottom_left=bottom_left, bottom_right=bottom_right
            )
        return top_left or bottom_left or 0

ft.border_radius = _CompatBorderRadius()

class _CompatAlignment:
    center = ft.Alignment(0, 0) if hasattr(ft, "Alignment") else None
    top_left = ft.Alignment(-1, -1) if hasattr(ft, "Alignment") else None
    top_center = ft.Alignment(0, -1) if hasattr(ft, "Alignment") else None
    top_right = ft.Alignment(1, -1) if hasattr(ft, "Alignment") else None
    center_left = ft.Alignment(-1, 0) if hasattr(ft, "Alignment") else None
    center_right = ft.Alignment(1, 0) if hasattr(ft, "Alignment") else None
    bottom_left = ft.Alignment(-1, 1) if hasattr(ft, "Alignment") else None
    bottom_center = ft.Alignment(0, 1) if hasattr(ft, "Alignment") else None
    bottom_right = ft.Alignment(1, 1) if hasattr(ft, "Alignment") else None

ft.alignment = _CompatAlignment()

if hasattr(ft, "DropdownOption"):
    if not hasattr(ft, "dropdown"):
        class _CompatDropdownMod:
            Option = ft.DropdownOption
        ft.dropdown = _CompatDropdownMod()
    elif not hasattr(ft.dropdown, "Option"):
        ft.dropdown.Option = ft.DropdownOption

# سازگارکننده ویژه Icon برای فلت 1.0+ (پشتیبانی همزمان از .name و .icon)
if hasattr(ft, "Icon") and not hasattr(ft.Icon, "name"):
    try:
        ft.Icon.name = property(
            lambda self: getattr(self, "icon", None),
            lambda self, val: setattr(self, "icon", val),
        )
    except Exception:
        pass

for _ctrl_name in (
    "Button", "ElevatedButton", "FilledButton", "OutlinedButton", "TextButton",
    "IconButton", "TextField", "Dropdown", "Container", "GestureDetector",
    "AlertDialog", "SnackBar", "NavigationBar", "NavigationBarDestination",
    "ButtonStyle", "TextStyle", "BoxShadow", "Theme", "Icon",
):
    _cls = getattr(ft, _ctrl_name, None)
    if _cls is not None and not getattr(_cls, "_compat_patched", False):
        if _ctrl_name != "Icon" and not hasattr(_cls, "text"):
            try:
                _cls.text = property(
                    lambda self: getattr(self, "content", None),
                    lambda self, val: setattr(self, "content", val),
                )
            except Exception:
                pass
        try:
            _orig_init = _cls.__init__
            def _make_safe_init(orig):
                def _safe_init(self, *a, **kw):
                    tried_swaps = set()
                    while True:
                        try:
                            return orig(self, *a, **kw)
                        except TypeError as ex:
                            m = re.search(r"unexpected keyword argument '(\w+)'", str(ex))
                            if m:
                                bad_key = m.group(1)
                                if bad_key == "text" and "content" not in kw and not a:
                                    kw["content"] = kw.pop("text")
                                elif bad_key == "name" and "icon" not in kw and not a:
                                    kw["icon"] = kw.pop("name")
                                elif bad_key == "on_long_press" and "on_long_press_start" not in kw and "lp1" not in tried_swaps:
                                    tried_swaps.add("lp1")
                                    kw["on_long_press_start"] = kw.pop("on_long_press")
                                elif bad_key == "on_long_press_start" and "on_long_press" not in kw and "lp2" not in tried_swaps:
                                    tried_swaps.add("lp2")
                                    kw["on_long_press"] = kw.pop("on_long_press_start")
                                elif bad_key in kw:
                                    kw.pop(bad_key)
                                else:
                                    raise
                            else:
                                raise
                return _safe_init
            _cls.__init__ = _make_safe_init(_orig_init)
            _cls._compat_patched = True
        except Exception:
            pass
# ------------------------------------------------------------------

def _resolve_storage_dir():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    test_db = os.path.join(base_dir, "cafe_accounting.db")
    if os.path.exists(test_db):
        return base_dir
    try:
        test_file = os.path.join(base_dir, ".write_test")
        with open(test_file, "w") as f:
            f.write("1")
        os.remove(test_file)
        return base_dir
    except Exception:
        return os.environ.get("FLET_APP_STORAGE_DATA", os.path.expanduser("~"))

APP_STORAGE_DIR = _resolve_storage_dir()
DB_NAME = os.path.join(APP_STORAGE_DIR, "cafe_accounting.db")
INTERNAL_BACKUP_DIR = os.path.join(APP_STORAGE_DIR, "backups")
BACKUP_CODE_PREFIX = "VITA_BKP_V1:"

# دسته‌بندی‌های پیش‌فرض کافه (کاملاً دست‌نخورده)
DEFAULT_CATEGORIES = [
    "قهوه‌ها",
    "نوشیدنی‌های گرم بر پایۀ قهوه",
    "نوشیدنی‌های سرد بر پایۀ قهوه",
    "شیک‌ها",
    "ماکتل‌ها",
    "بستنی بار",
    "نوشیدنی‌های گرم",
    "چای‌ها",
    "دمنوش‌ها",
    "کیک و دسر",
]

# دسته‌بندی‌های پیش‌فرض و استاندارد رستوران
DEFAULT_RESTAURANT_CATEGORIES = [
    "کباب و گریل",
    "خورشت و غذای سنتی",
    "پیتزا",
    "برگر و ساندویچ",
    "پاستا و استیک",
    "سوخاری و فینگر فود",
    "پیش‌غذا و سوپ",
    "سالاد و مخلفات",
    "صبحانه و برانچ",
    "نوشیدنی سرد",
]

ADD_CAT_OPTION = "+ افزودن دسته‌بندی جدید"

def get_all_categories(section="cafe"):
    default_list = DEFAULT_CATEGORIES if section == "cafe" else DEFAULT_RESTAURANT_CATEGORIES
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT name FROM categories WHERE section = ? ORDER BY id ASC", (section,))
        rows = [r[0] for r in cur.fetchall()]
        conn.close()
        return rows if rows else list(default_list)
    except Exception:
        return list(default_list)

def get_app_mode() -> str:
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT value FROM app_settings WHERE key = 'app_mode'")
        row = cur.fetchone()
        conn.close()
        if row and row[0] in ("cafe", "restaurant", "both"):
            return row[0]
    except Exception:
        pass
    return "cafe"

def set_app_mode_db(mode_val: str):
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES ('app_mode', ?)",
            (mode_val,)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

JALALI_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"
]

def num_to_persian(n: int) -> str:
    if n <= 0:
        return "صفر"
    ones = ["", "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه"]
    tens = ["", "ده", "بیست", "سی", "چهل", "پنجاه", "شصت", "هفتاد", "هشتاد", "نود"]
    teens = ["ده", "یازده", "دوازده", "سیزده", "چهارده", "پانزده", "شانزده", "هفده", "هجده", "نوزده"]
    huns = ["", "صد", "دویست", "سیصد", "چهارصد", "پانصد", "ششصد", "هفتصد", "هشتصد", "نهصد"]
    scales = ["", "هزار", "میلیون", "میلیارد", "تیلیارد"]

    def c999(num):
        r = []
        h = num // 100
        if h:
            r.append(huns[h])
        num %= 100
        if 10 <= num <= 19:
            r.append(teens[num - 10])
        else:
            t = num // 10
            if t:
                r.append(tens[t])
            o = num % 10
            if o:
                r.append(ones[o])
        return " و ".join(r)

    groups, i = [], 0
    while n > 0:
        rem = n % 1000
        if rem:
            scale_word = f" {scales[i]}" if i > 0 and i < len(scales) else ""
            groups.append(c999(rem) + scale_word)
        n //= 1000
        i += 1
    return " و ".join(reversed(groups))

def gregorian_to_jalali(gy: int, gm: int, gd: int):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (
        355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100)
        + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    )
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd

def jalali_to_gregorian(jy: int, jm: int, jd: int):
    jy += 1595
    days = -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += ((jm - 7) * 30) + 186
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    is_leap = (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)
    sal_a = [0, 31, 29 if is_leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 13 and gd > sal_a[gm]:
        gd -= sal_a[gm]
        gm += 1
    return gy, gm, gd

def get_jalali_month_days(jy: int, jm: int) -> int:
    if jm <= 6:
        return 31
    elif jm <= 11:
        return 30
    else:
        gy, gm, gd = jalali_to_gregorian(jy, 12, 30)
        jy_check, _, _ = gregorian_to_jalali(gy, gm, gd)
        return 30 if jy_check == jy else 29

def format_jalali_datetime(dt_str: str) -> str:
    try:
        date_part = dt_str[:10]
        time_part = dt_str[11:16] if len(dt_str) >= 16 else ""
        gy, gm, gd = map(int, date_part.split("-"))
        jy, jm, jd = gregorian_to_jalali(gy, gm, gd)
        return f"{jy}/{jm:02d}/{jd:02d}" + (f" ساعت {time_part}" if time_part else "")
    except Exception:
        return dt_str

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('app_mode', 'cafe')")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            cost_price REAL NOT NULL,
            sell_price REAL NOT NULL,
            sort_index INTEGER DEFAULT 0,
            section TEXT DEFAULT 'cafe'
        )
    """)
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN sort_index INTEGER DEFAULT 0")
        cursor.execute("UPDATE products SET sort_index = id")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN section TEXT DEFAULT 'cafe'")
        cursor.execute("UPDATE products SET section = 'cafe' WHERE section IS NULL")
    except Exception:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            sell_price REAL NOT NULL,
            profit REAL NOT NULL,
            order_date TEXT NOT NULL,
            section TEXT DEFAULT 'cafe'
        )
    """)
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN section TEXT DEFAULT 'cafe'")
        cursor.execute("UPDATE orders SET section = 'cafe' WHERE section IS NULL")
    except Exception:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            section TEXT NOT NULL DEFAULT 'cafe',
            UNIQUE(name, section)
        )
    """)

    cursor.execute("PRAGMA table_info(categories)")
    cat_cols = [col[1] for col in cursor.fetchall()]
    if "section" not in cat_cols:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                section TEXT NOT NULL DEFAULT 'cafe',
                UNIQUE(name, section)
            )
        """)
        cursor.execute("INSERT OR IGNORE INTO categories_new (id, name, section) SELECT id, name, 'cafe' FROM categories")
        cursor.execute("DROP TABLE categories")
        cursor.execute("ALTER TABLE categories_new RENAME TO categories")

    cursor.execute("SELECT COUNT(*) FROM categories WHERE section = 'cafe'")
    if cursor.fetchone()[0] == 0:
        for cat in DEFAULT_CATEGORIES:
            cursor.execute("INSERT OR IGNORE INTO categories (name, section) VALUES (?, 'cafe')", (cat,))

    cursor.execute("SELECT COUNT(*) FROM categories WHERE section = 'restaurant'")
    if cursor.fetchone()[0] == 0:
        for cat in DEFAULT_RESTAURANT_CATEGORIES:
            cursor.execute("INSERT OR IGNORE INTO categories (name, section) VALUES (?, 'restaurant')", (cat,))

    conn.commit()
    conn.close()

def format_price(val):
    try:
        return f"{int(float(val)):,}"
    except (ValueError, TypeError):
        return "0"

# =====================================================================
# موتور بک‌اند بکاپ، کد پشتیبان فشرده و بازیابی اطلاعات (Restore)
# =====================================================================
def get_public_download_dirs():
    candidates = [
        "/storage/emulated/0/Download",
        "/sdcard/Download",
        os.path.join(os.path.expanduser("~"), "Downloads"),
    ]
    valid = []
    for d in candidates:
        if d and os.path.isdir(d) and d not in valid:
            valid.append(d)
    return valid

def perform_db_backup():
    if not os.path.exists(DB_NAME):
        return False, "فایل پایگاه داده یافت نشد!", None

    os.makedirs(INTERNAL_BACKUP_DIR, exist_ok=True)
    now = datetime.now()
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    timestamp = f"{jy}{jm:02d}{jd:02d}_{now.strftime('%H%M%S')}"
    backup_filename = f"VitaHesab_{timestamp}.db"
    internal_backup_path = os.path.join(INTERNAL_BACKUP_DIR, backup_filename)

    try:
        source_conn = sqlite3.connect(DB_NAME)
        dest_conn = sqlite3.connect(internal_backup_path)
        with dest_conn:
            source_conn.backup(dest_conn)
        dest_conn.close()
        source_conn.close()

        public_saved_path = None
        for pub_dir in get_public_download_dirs():
            try:
                target_pub = os.path.join(pub_dir, backup_filename)
                shutil.copy2(internal_backup_path, target_pub)
                public_saved_path = target_pub
                break
            except Exception:
                continue

        return True, backup_filename, public_saved_path
    except Exception as e:
        return False, str(e), None

def list_available_backups():
    os.makedirs(INTERNAL_BACKUP_DIR, exist_ok=True)
    files_map = {}

    for folder in [INTERNAL_BACKUP_DIR] + get_public_download_dirs():
        try:
            for fname in os.listdir(folder):
                if (fname.startswith("VitaHesab_") or fname.startswith("cafe_backup_")) and fname.endswith(".db"):
                    fpath = os.path.join(folder, fname)
                    if os.path.isfile(fpath) and fname not in files_map:
                        stat = os.stat(fpath)
                        dt = datetime.fromtimestamp(stat.st_mtime)
                        jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
                        j_str = f"{jy}/{jm:02d}/{jd:02d} ساعت {dt.strftime('%H:%M')}"
                        size_kb = max(1, int(stat.st_size / 1024))
                        files_map[fname] = {
                            "name": fname,
                            "path": fpath,
                            "mtime": stat.st_mtime,
                            "jalali_str": j_str,
                            "size_kb": size_kb,
                            "is_public": folder != INTERNAL_BACKUP_DIR,
                        }
        except Exception:
            continue

    return sorted(files_map.values(), key=lambda x: x["mtime"], reverse=True)

def restore_db_from_file(backup_file_path: str):
    if not os.path.exists(backup_file_path):
        return False, "فایل بکاپ یافت نشد!"
    try:
        with open(backup_file_path, "rb") as f:
            header = f.read(16)
        if not header.startswith(b"SQLite format 3"):
            return False, "فایل انتخاب‌شده یک دیتابیس معتبر نیست!"

        src_conn = sqlite3.connect(backup_file_path)
        dst_conn = sqlite3.connect(DB_NAME)
        with dst_conn:
            src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()
        init_db()
        return True, "اطلاعات با موفقیت بازگردانی شد!"
    except Exception as e:
        return False, f"خطا در بازگردانی: {e}"

def export_db_to_text_code():
    try:
        os.makedirs(INTERNAL_BACKUP_DIR, exist_ok=True)
        temp_snap = os.path.join(INTERNAL_BACKUP_DIR, "_temp_snap.db")
        src_conn = sqlite3.connect(DB_NAME)
        dst_conn = sqlite3.connect(temp_snap)
        with dst_conn:
            src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()

        with open(temp_snap, "rb") as f:
            raw_bytes = f.read()
        try:
            os.remove(temp_snap)
        except Exception:
            pass

        compressed = zlib.compress(raw_bytes, level=9)
        b64_str = base64.b64encode(compressed).decode("ascii")
        return True, BACKUP_CODE_PREFIX + b64_str
    except Exception as e:
        return False, str(e)

def restore_db_from_text_code(code_str: str):
    try:
        clean = (code_str or "").strip()
        if BACKUP_CODE_PREFIX in clean:
            clean = clean.split(BACKUP_CODE_PREFIX, 1)[1].strip()
        clean = re.sub(r"\s+", "", clean)
        if not clean:
            return False, "کد بکاپ وارد نشده است!"

        compressed = base64.b64decode(clean)
        raw_bytes = zlib.decompress(compressed)
        if not raw_bytes.startswith(b"SQLite format 3"):
            return False, "کد واردشده معتبر نیست!"

        os.makedirs(INTERNAL_BACKUP_DIR, exist_ok=True)
        temp_restore = os.path.join(INTERNAL_BACKUP_DIR, "_temp_restore.db")
        with open(temp_restore, "wb") as f:
            f.write(raw_bytes)

        ok, msg = restore_db_from_file(temp_restore)
        try:
            os.remove(temp_restore)
        except Exception:
            pass
        return ok, msg
    except Exception:
        return False, "کد بکاپ ناقص یا نامعتبر است!"


def force_windows_icon(icon_filename: str, window_title: str):
    if os.name != "nt":
        return
    base_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_dir, icon_filename)
    if not os.path.exists(icon_path):
        return

    import ctypes

    def _worker():
        user32 = ctypes.windll.user32
        LR_LOADFROMFILE = 0x0010
        LR_DEFAULTSIZE = 0x0040
        WM_SETICON = 0x0080
        GCLP_HICON = -14
        GCLP_HICONSM = -34

        hicon_big = user32.LoadImageW(0, icon_path, 1, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
        hicon_small = user32.LoadImageW(0, icon_path, 1, 16, 16, LR_LOADFROMFILE)
        if not hicon_small:
            hicon_small = hicon_big
        if not hicon_big:
            return

        set_class_long = getattr(user32, "SetClassLongPtrW", getattr(user32, "SetClassLongW", None))

        for _ in range(15):
            hwnd = user32.FindWindowW(None, window_title)
            if not hwnd:
                hwnd = user32.FindWindowW("FLUTTER_RUNNER_WIN32_WINDOW", None)
            if hwnd:
                user32.SendMessageW(hwnd, WM_SETICON, 1, hicon_big)
                user32.SendMessageW(hwnd, WM_SETICON, 0, hicon_small)
                if set_class_long:
                    try:
                        set_class_long(hwnd, GCLP_HICON, hicon_big)
                        set_class_long(hwnd, GCLP_HICONSM, hicon_small)
                    except Exception:
                        pass
            time.sleep(0.3)

    threading.Thread(target=_worker, daemon=True).start()


def main(page: ft.Page):
    init_db()

    # =========================================================================
    # پالت‌های رنگی کافه (کرم و کاراملی)، رستوران (زعفرانی و سفالی) و حالت ترکیبی
    # =========================================================================
    BOTH_BLEND_MAIN = "#A8542F"   # رنگ میانه متعادل بین کرمی/موکای کافه (#9C623E) و نارنجی رستوران (#B54826)
    BOTH_BLEND_BG = "#FAE6D4"     # پس‌زمینه کرم-کهربایی ملایم مابین کافه و رستوران
    BOTH_BLEND_BORDER = "#E5BFA1" # حاشیه گرم میانه

    THEMES = {
        "cafe": {
            "BG_CREAM": "#F6EFE6",
            "CARD_IVORY": "#FFFDF9",
            "SURFACE_LATTE": "#EFE5D8",
            "CHIP_LATTE": "#E5D3BE",
            "BORDER_SAND": "#E4D5C3",
            "BORDER_WARM": "#D4C0A8",
            "ESPRESSO_DARK": "#4A2E1B",
            "MOCHA_PRIMARY": "#9C623E",
            "CARAMEL_ACCENT": "#C27D48",
            "TEXT_MUTED": "#846752",
            "DISABLED_BG": "#E6D8C8",
            "DISABLED_TEXT": "#A68E77",
            "HEADER_GRAD": ["#8A5434", "#A66B46", "#C2845B"],
            "HEADER_SHADOW": "#8A5434",
            "HEADER_ICON": ft.icons.COFFEE_ROUNDED,
        },
        "restaurant": {
            "BG_CREAM": "#F8EFE6",
            "CARD_IVORY": "#FFFDF9",
            "SURFACE_LATTE": "#F2E3D5",
            "CHIP_LATTE": "#E8CEB8",
            "BORDER_SAND": "#E6CFC0",
            "BORDER_WARM": "#D9B9A3",
            "ESPRESSO_DARK": "#452115",
            "MOCHA_PRIMARY": "#B54826",
            "CARAMEL_ACCENT": "#D97724",
            "TEXT_MUTED": "#875F4A",
            "DISABLED_BG": "#EBD8C8",
            "DISABLED_TEXT": "#A88976",
            "HEADER_GRAD": ["#8F3216", "#B54826", "#D97724"],
            "HEADER_SHADOW": "#8F3216",
            "HEADER_ICON": ft.icons.RESTAURANT_ROUNDED,
        }
    }

    app_mode = get_app_mode()  # 'cafe', 'restaurant', 'both'
    active_section = "restaurant" if app_mode == "restaurant" else "cafe"
    dashboard_section_filter = "all" if app_mode == "both" else active_section

    _initial_theme = THEMES[active_section]
    BG_CREAM = _initial_theme["BG_CREAM"]
    CARD_IVORY = _initial_theme["CARD_IVORY"]
    SURFACE_LATTE = _initial_theme["SURFACE_LATTE"]
    CHIP_LATTE = _initial_theme["CHIP_LATTE"]
    BORDER_SAND = _initial_theme["BORDER_SAND"]
    BORDER_WARM = _initial_theme["BORDER_WARM"]
    ESPRESSO_DARK = _initial_theme["ESPRESSO_DARK"]
    MOCHA_PRIMARY = _initial_theme["MOCHA_PRIMARY"]
    CARAMEL_ACCENT = _initial_theme["CARAMEL_ACCENT"]
    TEXT_MUTED = _initial_theme["TEXT_MUTED"]
    DISABLED_BG = _initial_theme["DISABLED_BG"]
    DISABLED_TEXT = _initial_theme["DISABLED_TEXT"]

    # رنگ‌های اختصاصی سود (سبز زمردی روشن و شاداب)
    PROFIT_DARK = "#047857"
    PROFIT_MAIN = "#059669"
    PROFIT_LIGHT = "#10B981"
    PROFIT_BG = "#DCFCE7"
    PROFIT_SURFACE = "#ECFDF5"
    PROFIT_BORDER = "#86EFAC"

    # رنگ‌های اختصاصی هزینه‌ها، حذف و بستن (قرمز)
    COST_RED_DARK = "#B91C1C"
    COST_RED_MAIN = "#DC2626"
    COST_RED_BG = "#FEE2E2"
    COST_RED_SURFACE = "#FEF2F2"
    COST_RED_BORDER = "#FECACA"

    app_title = "حسابداری کافه"
    page.title = app_title
    page.rtl = True
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = BG_CREAM
    page.window.width = 435
    page.window.height = 820
    page.window.resizable = False

    base_dir = os.path.dirname(os.path.abspath(__file__))
    page.window.icon = os.path.join(base_dir, "icon.ico")
    force_windows_icon("icon.ico", app_title)

    page.padding = 0

    page.fonts = {
        "Vazir": "https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/fonts/ttf/Vazirmatn-Regular.ttf",
        "Vazir-Bold": "https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/fonts/ttf/Vazirmatn-Bold.ttf"
    }
    page.theme = ft.Theme(
        font_family="Vazir",
        color_scheme_seed=MOCHA_PRIMARY
    )

    editing_product_id = None
    selected_cashier_category = "همه"
    cashier_search_query = ""

    now_dt = datetime.now()
    init_jy, init_jm, init_jd = gregorian_to_jalali(now_dt.year, now_dt.month, now_dt.day)

    filter_mode = "day"
    selected_date = datetime(now_dt.year, now_dt.month, now_dt.day)
    selected_j_year = init_jy
    selected_j_month = init_jm

    def refresh_ui(*ctrls):
        for c in ctrls:
            if c is not None:
                try:
                    c.update()
                except Exception:
                    pass
        try:
            page.update()
        except Exception:
            pass

    def set_icon_value(icon_ctrl, new_icon_val):
        try:
            icon_ctrl.icon = new_icon_val
        except Exception:
            pass
        try:
            icon_ctrl.name = new_icon_val
        except Exception:
            pass

    # =========================================================================
    # سیستم مدیریت متمرکز پنجره‌های رویی (وسط‌چین ۱۰۰٪ + قفل کامل دکمه‌های زیرین)
    # =========================================================================
    main_app_col = ft.Column(spacing=0, expand=True)

    def make_centered_modal(card_ctrl):
        layer = ft.Container(
            visible=False,
            top=0,
            bottom=0,
            left=0,
            right=0,
            bgcolor=ft.colors.with_opacity(0.55, "#000000"),
            alignment=ft.alignment.center,
            padding=ft.padding.symmetric(horizontal=18, vertical=10),
            on_click=lambda e: None,
            content=card_ctrl,
        )
        layer.open = False
        return layer

    all_modals = []

    def sync_modal_state():
        confirm_is_open = getattr(confirm_dlg, "visible", False)
        any_modal_open = any(getattr(m, "visible", False) for m in all_modals)

        for m in all_modals:
            if m is not confirm_dlg and getattr(m, "content", None) is not None:
                m.content.disabled = confirm_is_open

        main_app_col.disabled = any_modal_open
        refresh_ui(main_app_col, *all_modals)

    def open_ctrl(ctrl):
        ctrl.open = True
        ctrl.visible = True
        sync_modal_state()

    def close_ctrl(ctrl):
        ctrl.open = False
        ctrl.visible = False
        sync_modal_state()

    # =========================================================================
    # سیستم نوتیفیکیشن هوشمند و ضدباگ (نمایش نامحدود + نمایش روی صفحات باز)
    # =========================================================================
    snack_timer_ref = [None]
    orders_dlg_timer_ref = [None]
    cat_dlg_timer_ref = [None]

    app_snack_text = ft.Text("", color=CARD_IVORY, font_family="Vazir-Bold", size=12, expand=True)
    floating_toast_card = ft.Container(
        visible=False,
        bottom=14,
        left=14,
        right=14,
        bgcolor=MOCHA_PRIMARY,
        border_radius=14,
        padding=ft.padding.symmetric(horizontal=14, vertical=10),
        shadow=ft.BoxShadow(
            blur_radius=16,
            color=ft.colors.with_opacity(0.32, ESPRESSO_DARK),
            offset=ft.Offset(0, 5)
        ),
        content=ft.Row(
            rtl=True,
            spacing=10,
            controls=[
                ft.Container(
                    content=ft.Icon(ft.icons.NOTIFICATIONS_ACTIVE_ROUNDED, color="#FEF3C7", size=18),
                    bgcolor=ft.colors.with_opacity(0.2, CARD_IVORY),
                    padding=6,
                    border_radius=8,
                ),
                app_snack_text,
            ]
        )
    )

    orders_dlg_banner_text = ft.Text("", size=11, font_family="Vazir-Bold", color=CARD_IVORY, expand=True)
    orders_dlg_banner = ft.Container(
        visible=False,
        bgcolor=COST_RED_MAIN,
        border_radius=10,
        padding=ft.padding.symmetric(horizontal=10, vertical=7),
        margin=ft.padding.only(bottom=6),
        content=ft.Row(
            rtl=True,
            spacing=8,
            controls=[
                ft.Icon(ft.icons.NOTIFICATIONS_ACTIVE_ROUNDED, color="#FEF3C7", size=16),
                orders_dlg_banner_text,
            ]
        )
    )

    cat_dlg_banner_text = ft.Text("", size=11, font_family="Vazir-Bold", color=CARD_IVORY, expand=True)
    cat_dlg_banner = ft.Container(
        visible=False,
        bgcolor=COST_RED_MAIN,
        border_radius=10,
        padding=ft.padding.symmetric(horizontal=10, vertical=7),
        margin=ft.padding.only(bottom=6),
        content=ft.Row(
            rtl=True,
            spacing=8,
            controls=[
                ft.Icon(ft.icons.INFO_OUTLINE_ROUNDED, color="#FEF3C7", size=16),
                cat_dlg_banner_text,
            ]
        )
    )

    def show_snackbar(message: str, bg_color=None):
        if bg_color is None:
            bg_color = MOCHA_PRIMARY

        if getattr(cat_dialog, "visible", False):
            if cat_dlg_timer_ref[0] is not None:
                try:
                    cat_dlg_timer_ref[0].cancel()
                except Exception:
                    pass
            cat_dlg_banner_text.value = message
            cat_dlg_banner.bgcolor = bg_color
            cat_dlg_banner.visible = True
            refresh_ui(cat_dlg_banner_text, cat_dlg_banner, cat_dialog)

            def _hide_cat_banner():
                cat_dlg_banner.visible = False
                refresh_ui(cat_dlg_banner, cat_dialog)

            t_cat = threading.Timer(2.2, _hide_cat_banner)
            t_cat.daemon = True
            cat_dlg_timer_ref[0] = t_cat
            t_cat.start()
            return

        if getattr(recent_orders_dlg, "visible", False):
            if orders_dlg_timer_ref[0] is not None:
                try:
                    orders_dlg_timer_ref[0].cancel()
                except Exception:
                    pass
            orders_dlg_banner_text.value = message
            orders_dlg_banner.bgcolor = bg_color
            orders_dlg_banner.visible = True
            refresh_ui(orders_dlg_banner_text, orders_dlg_banner, recent_orders_dlg)

            def _hide_orders_banner():
                orders_dlg_banner.visible = False
                refresh_ui(orders_dlg_banner, recent_orders_dlg)

            t_ord = threading.Timer(2.2, _hide_orders_banner)
            t_ord.daemon = True
            orders_dlg_timer_ref[0] = t_ord
            t_ord.start()
            return

        if snack_timer_ref[0] is not None:
            try:
                snack_timer_ref[0].cancel()
            except Exception:
                pass

        app_snack_text.value = message
        floating_toast_card.bgcolor = bg_color
        floating_toast_card.visible = True
        refresh_ui(app_snack_text, floating_toast_card)

        def _auto_dismiss():
            floating_toast_card.visible = False
            refresh_ui(floating_toast_card)

        t = threading.Timer(2.0, _auto_dismiss)
        t.daemon = True
        snack_timer_ref[0] = t
        t.start()

    # --- سرویس کلیپ‌بورد ---
    _clipboard_service = None
    if hasattr(ft, "Clipboard"):
        try:
            _clipboard_service = ft.Clipboard()
            if hasattr(page, "services"):
                page.services.append(_clipboard_service)
        except Exception:
            pass

    async def copy_to_clipboard_async(text_val: str):
        if os.name == "nt" and not getattr(page, "web", False):
            try:
                import subprocess
                subprocess.run(
                    ["clip"],
                    input=text_val.encode("utf-16-le"),
                    check=True,
                    creationflags=0x08000000
                )
            except Exception:
                pass

        if _clipboard_service is not None:
            try:
                if hasattr(page, "services") and _clipboard_service not in page.services:
                    page.services.append(_clipboard_service)
                    page.update()
                res = _clipboard_service.set(text_val)
                if inspect.iscoroutine(res):
                    await res
                return
            except Exception:
                pass

        if hasattr(page, "set_clipboard"):
            try:
                res = page.set_clipboard(text_val)
                if inspect.iscoroutine(res):
                    await res
            except Exception:
                pass

        targets = []
        if _clipboard_service is not None:
            targets.append(_clipboard_service)
        p_clip = getattr(page, "clipboard", None)
        if p_clip is not None and not isinstance(p_clip, str):
            targets.append(p_clip)
        targets.append(page)

        for target in targets:
            for m_name in ("set", "set_data", "set_clipboard", "set_text"):
                fn = getattr(target, m_name, None)
                if callable(fn):
                    try:
                        res = fn(text_val)
                        if inspect.iscoroutine(res):
                            await res
                    except Exception:
                        continue

    # --- دیالوگ تایید یکتا (وسط صفحه) ---
    confirm_action_ref = [None]
    confirm_icon = ft.Icon(ft.icons.DELETE_SWEEP_ROUNDED, color=COST_RED_MAIN, size=32)
    confirm_icon_box = ft.Container(
        content=confirm_icon,
        bgcolor=COST_RED_SURFACE,
        padding=16,
        border_radius=50,
        border=ft.border.all(1, COST_RED_BORDER),
    )
    confirm_title_label = ft.Text("", size=15, font_family="Vazir-Bold", color=ESPRESSO_DARK, text_align=ft.TextAlign.CENTER)
    confirm_msg_label = ft.Text("", size=12, color=TEXT_MUTED, text_align=ft.TextAlign.CENTER)

    def _on_confirm_yes(e):
        close_ctrl(confirm_dlg)
        cb = confirm_action_ref[0]
        if cb is not None:
            cb()

    def _on_confirm_no(e):
        close_ctrl(confirm_dlg)

    confirm_cancel_btn = ft.ElevatedButton(
        "انصراف",
        bgcolor=SURFACE_LATTE,
        color=ESPRESSO_DARK,
        elevation=0,
        height=40,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
        on_click=_on_confirm_no
    )

    confirm_yes_btn = ft.ElevatedButton(
        "بله، حذف شود",
        icon=ft.icons.CHECK_ROUNDED,
        bgcolor=COST_RED_MAIN,
        color=ft.colors.WHITE,
        elevation=2,
        height=40,
        rtl=True,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
        on_click=_on_confirm_yes
    )

    confirm_card_box = ft.Container(
        width=330,
        bgcolor=CARD_IVORY,
        border_radius=22,
        padding=ft.padding.symmetric(horizontal=20, vertical=18),
        shadow=ft.BoxShadow(
            blur_radius=24,
            color=ft.colors.with_opacity(0.30, "#000000"),
            offset=ft.Offset(0, 8),
        ),
        on_click=lambda e: None,
        rtl=True,
        content=ft.Column(
            rtl=True,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            controls=[
                confirm_icon_box,
                confirm_title_label,
                confirm_msg_label,
                ft.Container(
                    padding=ft.padding.only(top=6),
                    content=ft.Row(
                        rtl=True,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=10,
                        controls=[
                            confirm_cancel_btn,
                            confirm_yes_btn,
                        ]
                    )
                )
            ]
        )
    )
    confirm_dlg = make_centered_modal(confirm_card_box)

    def show_confirm_dialog(
        title_text: str,
        message_text: str,
        on_confirm_callback,
        confirm_btn_text="بله، حذف شود",
        confirm_color=COST_RED_MAIN,
        icon_data=None
    ):
        if icon_data is None:
            icon_data = ft.icons.DELETE_SWEEP_ROUNDED if confirm_color == COST_RED_MAIN else ft.icons.SETTINGS_BACKUP_RESTORE_ROUNDED
        is_danger = (confirm_color == COST_RED_MAIN)

        confirm_action_ref[0] = on_confirm_callback
        confirm_icon_box.content = ft.Icon(icon_data, color=confirm_color, size=32)
        confirm_icon_box.bgcolor = COST_RED_SURFACE if is_danger else BG_CREAM
        confirm_icon_box.border = ft.border.all(1, COST_RED_BORDER if is_danger else BORDER_WARM)
        confirm_title_label.value = title_text
        confirm_title_label.color = ESPRESSO_DARK
        confirm_msg_label.value = message_text
        confirm_msg_label.color = TEXT_MUTED
        confirm_cancel_btn.bgcolor = SURFACE_LATTE
        confirm_cancel_btn.color = ESPRESSO_DARK
        confirm_yes_btn.text = confirm_btn_text
        confirm_yes_btn.bgcolor = confirm_color

        open_ctrl(confirm_dlg)

    def close_dialog(dlg):
        close_ctrl(dlg)

    def refresh_all_views():
        nonlocal app_mode, active_section, dashboard_section_filter
        app_mode = get_app_mode()
        if app_mode == "cafe":
            active_section = "cafe"
            dashboard_section_filter = "cafe"
        elif app_mode == "restaurant":
            active_section = "restaurant"
            dashboard_section_filter = "restaurant"
        else:
            if dashboard_section_filter not in ("all", "cafe", "restaurant"):
                dashboard_section_filter = "all"

        apply_active_theme()
        render_section_switchers()
        refresh_category_dropdown()
        refresh_header_today_sales()
        render_cashier_category_chips()
        load_cashier_products()
        load_menu_products()
        update_dashboard_controls()
        load_dashboard_data()

    # =========================================================================
    # مرکز بکاپ و بازیابی اطلاعات (وسط صفحه + قفل کامل زیرین)
    # =========================================================================
    backups_list_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=130)
    status_timer_ref = [None]
    copy_timer_ref = [None]

    backup_code_field = ft.TextField(
        label="کد پشتیبان (برای بازیابی، کد را اینجا پیست کنید)",
        hint_text="...",
        text_size=11,
        height=44,
        expand=True,
        rtl=True,
        text_align=ft.TextAlign.RIGHT,
        content_padding=ft.padding.symmetric(horizontal=12, vertical=8),
        border_radius=10,
        border_color=BORDER_WARM,
        focused_border_color=MOCHA_PRIMARY,
        bgcolor=SURFACE_LATTE,
    )

    status_info_text = ft.Text(
        "",
        size=11,
        color=MOCHA_PRIMARY,
        font_family="Vazir-Bold",
        text_align=ft.TextAlign.CENTER,
    )
    status_banner = ft.Container(
        visible=False,
        bgcolor=BG_CREAM,
        border=ft.border.all(1, BORDER_WARM),
        border_radius=10,
        padding=ft.padding.symmetric(horizontal=10, vertical=6),
        alignment=ft.alignment.center,
        content=status_info_text,
    )

    copy_btn = ft.ElevatedButton(
        "کپی کد بکاپ",
        icon=ft.icons.CONTENT_COPY_ROUNDED,
        bgcolor=CHIP_LATTE,
        color=ESPRESSO_DARK,
        elevation=0,
        expand=1,
        height=38,
        rtl=True,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            text_style=ft.TextStyle(size=10, font_family="Vazir-Bold")
        )
    )

    def close_bkp_modal(e=None):
        close_ctrl(bkp_dlg)

    def show_dialog_status(msg: str, is_error=False):
        if status_timer_ref[0] is not None:
            try:
                status_timer_ref[0].cancel()
            except Exception:
                pass

        status_info_text.value = msg
        if is_error:
            status_info_text.color = COST_RED_MAIN
            status_banner.bgcolor = COST_RED_SURFACE
            status_banner.border = ft.border.all(1, COST_RED_BORDER)
        else:
            status_info_text.color = MOCHA_PRIMARY
            status_banner.bgcolor = BG_CREAM
            status_banner.border = ft.border.all(1, BORDER_WARM)

        status_banner.visible = True
        refresh_ui(status_info_text, status_banner, bkp_dlg)

        def _clear_status():
            status_banner.visible = False
            status_info_text.value = ""
            refresh_ui(status_info_text, status_banner, bkp_dlg)

        t = threading.Timer(1.8, _clear_status)
        t.daemon = True
        status_timer_ref[0] = t
        t.start()

    def render_backups_list():
        backups_list_col.controls.clear()
        items = list_available_backups()
        if not items:
            backups_list_col.controls.append(
                ft.Container(
                    bgcolor=SURFACE_LATTE,
                    border_radius=12,
                    border=ft.border.all(1, BORDER_SAND),
                    padding=16,
                    alignment=ft.alignment.center,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                        controls=[
                            ft.Icon(ft.icons.FOLDER_OFF_OUTLINED, size=24, color=TEXT_MUTED),
                            ft.Text("هنوز هیچ بکاپی ثبت نشده است.", size=11, color=TEXT_MUTED, font_family="Vazir-Bold"),
                        ]
                    )
                )
            )
        else:
            for item in items:
                b_path = item["path"]
                b_name = item["name"]
                b_date = item["jalali_str"]
                b_loc = "پوشه دانلود" if item["is_public"] else "حافظه برنامه"

                def ask_restore_item(e, path=b_path, dt_str=b_date):
                    def do_restore():
                        ok, msg = restore_db_from_file(path)
                        if ok:
                            close_bkp_modal()
                            refresh_all_views()
                            show_snackbar(f"اطلاعات به بکاپ ({dt_str}) بازگردانی شد.", MOCHA_PRIMARY)
                        else:
                            show_dialog_status(msg, is_error=True)

                    show_confirm_dialog(
                        "بازگردانی اطلاعات",
                        f"آیا مطمئن هستید که اطلاعات فعلی برنامه با بکاپ تاریخ «{dt_str}» جایگزین شود؟",
                        do_restore,
                        confirm_btn_text="بله، بازگردانی شود",
                        confirm_color=MOCHA_PRIMARY
                    )

                def ask_delete_bkp(e, path=b_path, name=b_name):
                    def do_del():
                        paths_to_remove = {
                            path,
                            os.path.join(INTERNAL_BACKUP_DIR, name),
                        }
                        for pub_dir in get_public_download_dirs():
                            paths_to_remove.add(os.path.join(pub_dir, name))

                        for p in paths_to_remove:
                            try:
                                if p and os.path.exists(p):
                                    os.remove(p)
                            except Exception:
                                pass

                        render_backups_list()
                        show_dialog_status("فایل بکاپ با موفقیت حذف شد 🗑", is_error=True)

                    show_confirm_dialog(
                        "حذف فایل بکاپ",
                        "آیا از حذف دائمی این فایل پشتیبان مطمئن هستید؟",
                        do_del
                    )

                backups_list_col.controls.append(
                    ft.Container(
                        bgcolor=SURFACE_LATTE,
                        border=ft.border.all(1, BORDER_SAND),
                        border_radius=12,
                        padding=ft.padding.symmetric(horizontal=10, vertical=8),
                        rtl=True,
                        content=ft.Row(
                            rtl=True,
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Row(
                                    rtl=True,
                                    spacing=8,
                                    controls=[
                                        ft.Container(
                                            content=ft.Icon(ft.icons.STORAGE_ROUNDED, size=18, color=MOCHA_PRIMARY),
                                            bgcolor=CHIP_LATTE,
                                            padding=7,
                                            border_radius=9,
                                        ),
                                        ft.Column(
                                            spacing=2,
                                            horizontal_alignment=ft.CrossAxisAlignment.START,
                                            controls=[
                                                ft.Text(b_date, size=11, font_family="Vazir-Bold", color=ESPRESSO_DARK),
                                                ft.Text(f"{b_loc} | {item['size_kb']} کیلوبایت", size=9, color=TEXT_MUTED),
                                            ]
                                        ),
                                    ]
                                ),
                                ft.Row(
                                    rtl=True,
                                    spacing=5,
                                    controls=[
                                        ft.Container(
                                            bgcolor=CHIP_LATTE,
                                            border=ft.border.all(1, BORDER_WARM),
                                            border_radius=8,
                                            padding=ft.padding.symmetric(horizontal=8, vertical=5),
                                            on_click=ask_restore_item,
                                            tooltip="بازگردانی این بکاپ",
                                            content=ft.Row(
                                                rtl=True,
                                                spacing=3,
                                                controls=[
                                                    ft.Icon(ft.icons.SETTINGS_BACKUP_RESTORE_ROUNDED, size=14, color=ESPRESSO_DARK),
                                                    ft.Text("بازگردانی", size=10, font_family="Vazir-Bold", color=ESPRESSO_DARK),
                                                ]
                                            )
                                        ),
                                        ft.Container(
                                            bgcolor=COST_RED_BG,
                                            border=ft.border.all(1, COST_RED_BORDER),
                                            width=30,
                                            height=30,
                                            border_radius=8,
                                            alignment=ft.alignment.center,
                                            on_click=ask_delete_bkp,
                                            tooltip="حذف بکاپ",
                                            content=ft.Icon(ft.icons.DELETE_OUTLINE_ROUNDED, size=16, color=COST_RED_MAIN),
                                        ),
                                    ]
                                ),
                            ]
                        )
                    )
                )
        refresh_ui(backups_list_col, bkp_dlg)

    def create_new_backup_click(e):
        ok, res, pub_path = perform_db_backup()
        if ok:
            render_backups_list()
            if pub_path:
                show_dialog_status("بکاپ جدید در برنامه و پوشه دانلود ذخیره شد ✔", is_error=False)
            else:
                show_dialog_status("بکاپ جدید با موفقیت ذخیره شد ✔", is_error=False)
        else:
            show_dialog_status(f"خطا: {res}", is_error=True)

    async def generate_and_copy_code_click(e):
        ok, code_or_err = export_db_to_text_code()
        if ok:
            await copy_to_clipboard_async(code_or_err)
            if copy_timer_ref[0] is not None:
                try:
                    copy_timer_ref[0].cancel()
                except Exception:
                    pass

            copy_btn.text = "کد کپی شد ✔"
            copy_btn.icon = ft.icons.CHECK_CIRCLE_ROUNDED
            copy_btn.bgcolor = BORDER_WARM
            copy_btn.color = ESPRESSO_DARK
            refresh_ui(copy_btn, bkp_dlg)

            def _reset_copy_btn():
                copy_btn.text = "کپی کد بکاپ"
                copy_btn.icon = ft.icons.CONTENT_COPY_ROUNDED
                copy_btn.bgcolor = CHIP_LATTE
                copy_btn.color = ESPRESSO_DARK
                refresh_ui(copy_btn, bkp_dlg)

            t = threading.Timer(1.5, _reset_copy_btn)
            t.daemon = True
            copy_timer_ref[0] = t
            t.start()
        else:
            show_dialog_status(f"خطا در ساخت کد: {code_or_err}", is_error=True)

    copy_btn.on_click = generate_and_copy_code_click

    def restore_from_code_click(e):
        code_val = (backup_code_field.value or "").strip()
        if not code_val:
            show_dialog_status("لطفاً ابتدا کد بکاپ را در کادر پیست کنید!", is_error=True)
            return

        def confirmed_code_restore():
            ok, msg = restore_db_from_text_code(code_val)
            if ok:
                backup_code_field.value = ""
                close_bkp_modal()
                refresh_all_views()
                show_snackbar("اطلاعات با موفقیت از کد متنی بازیابی شد!", MOCHA_PRIMARY)
            else:
                show_dialog_status(msg, is_error=True)

        show_confirm_dialog(
            "بازگردانی از کد متنی",
            "آیا مطمئن هستید که اطلاعات فعلی با دیتای داخل این کد جایگزین شود؟",
            confirmed_code_restore,
            confirm_btn_text="بله، بازیابی شود",
            confirm_color=MOCHA_PRIMARY
        )

    bkp_header_icon = ft.Icon(ft.icons.CLOUD_SYNC_ROUNDED, color=MOCHA_PRIMARY, size=20)
    bkp_header_icon_box = ft.Container(
        content=bkp_header_icon,
        bgcolor=CHIP_LATTE,
        padding=7,
        border_radius=10,
    )
    bkp_new_btn = ft.ElevatedButton(
        "ثبت بکاپ جدید (در برنامه + پوشه دانلود)",
        icon=ft.icons.ADD_TASK_ROUNDED,
        bgcolor=MOCHA_PRIMARY,
        color=ft.colors.WHITE,
        height=40,
        expand=True,
        rtl=True,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=11),
            text_style=ft.TextStyle(size=11, font_family="Vazir-Bold")
        ),
        on_click=create_new_backup_click
    )
    bkp_text_label = ft.Text("پشتیبان‌گیری متنی:", size=10, font_family="Vazir-Bold", color=MOCHA_PRIMARY)
    bkp_restore_code_btn = ft.ElevatedButton(
        "بازگردانی از کد",
        icon=ft.icons.DOWNLOAD_DONE_ROUNDED,
        bgcolor=MOCHA_PRIMARY,
        color=ft.colors.WHITE,
        elevation=0,
        expand=1,
        height=38,
        rtl=True,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            text_style=ft.TextStyle(size=10, font_family="Vazir-Bold")
        ),
        on_click=restore_from_code_click
    )

    bkp_close_btn = ft.Container(
        height=34,
        padding=ft.padding.symmetric(horizontal=12, vertical=4),
        border_radius=10,
        alignment=ft.alignment.center,
        on_click=close_bkp_modal,
        content=ft.Text("بستن پنجره", size=12, font_family="Vazir-Bold", color=ESPRESSO_DARK),
    )

    bkp_inner_col = ft.Column(
        rtl=True,
        spacing=8,
        tight=True,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            ft.Row(
                rtl=True,
                alignment=ft.MainAxisAlignment.START,
                spacing=8,
                controls=[
                    bkp_header_icon_box,
                    ft.Text("مرکز بکاپ و بازیابی اطلاعات", size=14, font_family="Vazir-Bold", color=ESPRESSO_DARK),
                ]
            ),
            ft.Row(rtl=True, controls=[bkp_new_btn]),
            status_banner,
            ft.Text("بکاپ‌های موجود (بازگردانی سریع):", size=11, font_family="Vazir-Bold", color=ESPRESSO_DARK),
            backups_list_col,
            ft.Container(height=1, bgcolor=BORDER_SAND, margin=ft.padding.symmetric(vertical=1)),
            bkp_text_label,
            ft.Row(rtl=True, controls=[backup_code_field]),
            ft.Row(
                rtl=True,
                spacing=8,
                controls=[
                    copy_btn,
                    bkp_restore_code_btn,
                ]
            ),
            ft.Row(
                rtl=True,
                alignment=ft.MainAxisAlignment.END,
                controls=[bkp_close_btn]
            ),
        ]
    )

    bkp_card_box = ft.Container(
        width=375,
        bgcolor=CARD_IVORY,
        border_radius=20,
        padding=ft.padding.symmetric(horizontal=16, vertical=12),
        shadow=ft.BoxShadow(
            blur_radius=24,
            color=ft.colors.with_opacity(0.28, "#000000"),
            offset=ft.Offset(0, 8),
        ),
        on_click=lambda e: None,
        rtl=True,
        content=bkp_inner_col,
    )

    def _set_bkp_keyboard_mode(kb_open: bool):
        backups_list_col.height = 68 if kb_open else 112
        bkp_inner_col.spacing = 5 if kb_open else 8
        bkp_card_box.padding = ft.padding.symmetric(horizontal=16, vertical=8 if kb_open else 12)
        if getattr(bkp_dlg, "visible", False):
            refresh_ui(backups_list_col, bkp_inner_col, bkp_card_box, bkp_dlg)

    backup_code_field.on_focus = lambda e: _set_bkp_keyboard_mode(True)
    backup_code_field.on_blur = lambda e: _set_bkp_keyboard_mode(False)

    def _on_page_resize(e):
        if getattr(bkp_dlg, "visible", False) and page.height:
            _set_bkp_keyboard_mode(page.height < 560)

    try:
        page.on_resized = _on_page_resize
    except Exception:
        pass
    try:
        page.on_resize = _on_page_resize
    except Exception:
        pass

    bkp_dlg = make_centered_modal(bkp_card_box)

    def open_backup_manager_dialog(e):
        if status_timer_ref[0] is not None:
            try:
                status_timer_ref[0].cancel()
            except Exception:
                pass
        status_banner.visible = False
        status_info_text.value = ""
        backup_code_field.value = ""
        copy_btn.text = "کپی کد بکاپ"
        copy_btn.icon = ft.icons.CONTENT_COPY_ROUNDED
        copy_btn.bgcolor = CHIP_LATTE
        copy_btn.color = ESPRESSO_DARK
        _set_bkp_keyboard_mode(False)
        render_backups_list()
        open_ctrl(bkp_dlg)

    # =========================================================================
    # پنجره تغییر حالت برنامه (کافه / رستوران / کافه‌رستوران) - بدون حذف اطلاعات
    # =========================================================================
    mode_options_col = ft.Column(spacing=8, tight=True)

    def select_new_app_mode(new_mode: str):
        nonlocal app_mode, active_section, selected_cashier_category, dashboard_section_filter
        app_mode = new_mode
        set_app_mode_db(new_mode)

        if new_mode == "cafe":
            active_section = "cafe"
            dashboard_section_filter = "cafe"
            msg = "حالت برنامه روی «کافه» تنظیم شد."
        elif new_mode == "restaurant":
            active_section = "restaurant"
            dashboard_section_filter = "restaurant"
            msg = "حالت برنامه روی «رستوران» تنظیم شد."
        else:
            dashboard_section_filter = "all"
            msg = "حالت «کافه‌رستوران» (دو منظوره) فعال شد."

        selected_cashier_category = "همه"
        close_ctrl(mode_dlg)
        reset_menu_form()
        refresh_all_views()
        show_snackbar(msg, MOCHA_PRIMARY)

    def render_mode_options():
        mode_options_col.controls.clear()
        modes_info = [
            (
                "cafe",
                "کافه",
                "منو، دسته‌بندی‌ها و تم اختصاصی کافه",
                ft.icons.COFFEE_ROUNDED,
                "#9C623E",
                "#F7EDE2",
            ),
            (
                "restaurant",
                "رستوران",
                "منو، دسته‌بندی‌ها و تم اختصاصی رستوران",
                ft.icons.RESTAURANT_ROUNDED,
                "#B54826",
                "#FFEDD5",
            ),
            (
                "both",
                "کافه رستوران",
                "قابلیت سوئیچ بین کافه و رستوران + گزارش مالی تفکیکی و تجمیعی",
                ft.icons.STOREFRONT_ROUNDED,
                BOTH_BLEND_MAIN,
                BOTH_BLEND_BG,
            ),
        ]

        for m_code, m_title, m_desc, m_icon, m_col, m_bg in modes_info:
            is_curr = (app_mode == m_code)
            card_item = ft.Container(
                bgcolor=SURFACE_LATTE if is_curr else CARD_IVORY,
                border=ft.border.all(2 if is_curr else 1, m_col if is_curr else BORDER_WARM),
                border_radius=14,
                padding=ft.padding.symmetric(horizontal=12, vertical=10),
                on_click=lambda e, code=m_code: select_new_app_mode(code),
                content=ft.Row(
                    rtl=True,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            rtl=True,
                            spacing=10,
                            expand=True,
                            controls=[
                                ft.Container(
                                    content=ft.Icon(m_icon, color=m_col, size=22),
                                    bgcolor=m_bg,
                                    padding=9,
                                    border_radius=12,
                                ),
                                ft.Column(
                                    spacing=2,
                                    expand=True,
                                    controls=[
                                        ft.Text(m_title, size=12, font_family="Vazir-Bold", color=ESPRESSO_DARK),
                                        ft.Text(m_desc, size=10, color=TEXT_MUTED),
                                    ]
                                ),
                            ]
                        ),
                        ft.Icon(
                            ft.icons.CHECK_CIRCLE_ROUNDED if is_curr else ft.icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
                            color=m_col if is_curr else BORDER_WARM,
                            size=20
                        ),
                    ]
                )
            )
            mode_options_col.controls.append(card_item)

    mode_dlg_header_icon_box = ft.Container(
        content=ft.Icon(ft.icons.TUNE_ROUNDED, color=BOTH_BLEND_MAIN, size=20),
        bgcolor=BOTH_BLEND_BG,
        padding=7,
        border_radius=10,
    )

    mode_dlg_info_box = ft.Container(
        bgcolor=BOTH_BLEND_BG,
        border=ft.border.all(1, BOTH_BLEND_BORDER),
        border_radius=10,
        padding=ft.padding.symmetric(horizontal=10, vertical=7),
        content=ft.Row(
            rtl=True,
            spacing=6,
            controls=[
                ft.Icon(ft.icons.VERIFIED_USER_ROUNDED, color=BOTH_BLEND_MAIN, size=16),
                ft.Text(
                    "تغییر حالت باعث حذف محصولات یا فاکتورهای قبلی نمی‌شود.",
                    size=10,
                    font_family="Vazir-Bold",
                    color=ESPRESSO_DARK,
                    expand=True,
                ),
            ]
        )
    )

    mode_card_box = ft.Container(
        width=365,
        bgcolor=CARD_IVORY,
        border_radius=20,
        padding=ft.padding.only(top=16, left=16, right=16, bottom=12),
        shadow=ft.BoxShadow(
            blur_radius=24,
            color=ft.colors.with_opacity(0.28, "#000000"),
            offset=ft.Offset(0, 8),
        ),
        on_click=lambda e: None,
        rtl=True,
        content=ft.Column(
            rtl=True,
            tight=True,
            spacing=10,
            controls=[
                ft.Row(
                    rtl=True,
                    spacing=8,
                    controls=[
                        mode_dlg_header_icon_box,
                        ft.Text("انتخاب حالت برنامه (کافه / رستوران)", size=14, font_family="Vazir-Bold", color=ESPRESSO_DARK),
                    ]
                ),
                mode_options_col,
                mode_dlg_info_box,
                ft.Row(
                    rtl=True,
                    alignment=ft.MainAxisAlignment.END,
                    controls=[
                        ft.TextButton(
                            "بستن",
                            style=ft.ButtonStyle(color=ESPRESSO_DARK),
                            on_click=lambda e: close_ctrl(mode_dlg)
                        )
                    ]
                )
            ]
        )
    )
    mode_dlg = make_centered_modal(mode_card_box)

    def open_mode_selector_dialog(e=None):
        render_mode_options()
        open_ctrl(mode_dlg)

    # --- هدر بالای برنامه ---
    today_jy, today_jm, today_jd = gregorian_to_jalali(now_dt.year, now_dt.month, now_dt.day)
    today_badge_str = f"{today_jd} {JALALI_MONTHS[today_jm - 1]} {today_jy}"
    header_today_sales_text = ft.Text("0 تومان", size=9, font_family="Vazir-Bold", color="#FFFDF9")

    def refresh_header_today_sales():
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        today_prefix = datetime.now().strftime("%Y-%m-%d")
        if app_mode == "cafe":
            cursor.execute(
                "SELECT COALESCE(SUM(sell_price), 0) FROM orders WHERE substr(order_date, 1, 10) = ? AND section = 'cafe'",
                (today_prefix,)
            )
        elif app_mode == "restaurant":
            cursor.execute(
                "SELECT COALESCE(SUM(sell_price), 0) FROM orders WHERE substr(order_date, 1, 10) = ? AND section = 'restaurant'",
                (today_prefix,)
            )
        else:
            cursor.execute(
                "SELECT COALESCE(SUM(sell_price), 0) FROM orders WHERE substr(order_date, 1, 10) = ?",
                (today_prefix,)
            )
        val = cursor.fetchone()[0]
        conn.close()
        header_today_sales_text.value = f"{format_price(val)} تومان"

    backup_btn = ft.Container(
        content=ft.Row(
            spacing=4,
            controls=[
                ft.Icon(ft.icons.BACKUP_ROUNDED, color="#FFFDF9", size=15),
                ft.Text("بکاپ", size=10, color="#FFFDF9", font_family="Vazir-Bold"),
            ]
        ),
        bgcolor=ft.colors.with_opacity(0.22, "#FFFDF9"),
        border=ft.border.all(1, ft.colors.with_opacity(0.35, "#FFFDF9")),
        padding=ft.padding.symmetric(horizontal=8, vertical=4),
        border_radius=12,
        on_click=open_backup_manager_dialog,
        tooltip="مرکز بکاپ و بازیابی اطلاعات",
    )

    mode_btn = ft.Container(
        content=ft.Icon(ft.icons.TUNE_ROUNDED, color="#FFFDF9", size=15),
        bgcolor=ft.colors.with_opacity(0.22, "#FFFDF9"),
        border=ft.border.all(1, ft.colors.with_opacity(0.35, "#FFFDF9")),
        padding=ft.padding.symmetric(horizontal=7, vertical=4),
        border_radius=12,
        on_click=open_mode_selector_dialog,
        tooltip="تغییر حالت (کافه / رستوران / کافه‌رستوران)",
    )

    def _get_header_mode_icon():
        if app_mode == "cafe":
            return ft.icons.COFFEE_ROUNDED
        elif app_mode == "restaurant":
            return ft.icons.RESTAURANT_ROUNDED
        return ft.icons.STOREFRONT_ROUNDED

    header_logo_icon = ft.Icon(_get_header_mode_icon(), color="#FFFDF9", size=22)
    header_logo_box = ft.Container(
        content=header_logo_icon,
        bgcolor=ft.colors.with_opacity(0.2, "#FFFDF9"),
        padding=8,
        border_radius=12,
        border=ft.border.all(1, ft.colors.with_opacity(0.35, "#FFFDF9")),
        on_click=open_mode_selector_dialog,
        tooltip="تغییر حالت (کافه / رستوران / کافه رستوران)",
    )

    header_sub_title = ft.Text(
        "حسابداری کافه" if app_mode == "cafe" else ("حسابداری رستوران" if app_mode == "restaurant" else "حسابداری کافه رستوران"),
        size=9,
        color="#F6EFE6"
    )

    top_app_header = ft.Container(
        padding=ft.padding.only(top=44, bottom=14, left=12, right=12),
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_right,
            end=ft.alignment.bottom_left,
            colors=_initial_theme["HEADER_GRAD"]
        ),
        shadow=ft.BoxShadow(blur_radius=14, color=ft.colors.with_opacity(0.18, _initial_theme["HEADER_SHADOW"]), offset=ft.Offset(0, 4)),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(
                    spacing=8,
                    controls=[
                        header_logo_box,
                        ft.Column(
                            spacing=2,
                            controls=[
                                ft.Text("ویتا حساب", size=14, font_family="Vazir-Bold", color="#FFFDF9"),
                                header_sub_title,
                            ]
                        )
                    ]
                ),
                ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.END,
                    spacing=4,
                    controls=[
                        ft.Row(
                            spacing=5,
                            controls=[
                                ft.Container(
                                    bgcolor=ft.colors.with_opacity(0.2, "#FFFDF9"),
                                    border=ft.border.all(1, ft.colors.with_opacity(0.3, "#FFFDF9")),
                                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                                    border_radius=20,
                                    content=ft.Row(
                                        spacing=4,
                                        controls=[
                                            ft.Icon(ft.icons.CALENDAR_TODAY_ROUNDED, color="#FFFDF9", size=12),
                                            ft.Text(today_badge_str, size=10, color="#FFFDF9", font_family="Vazir-Bold"),
                                        ]
                                    )
                                ),
                                backup_btn,
                                mode_btn,
                            ]
                        ),
                        ft.Row(
                            spacing=4,
                            controls=[
                                ft.Text("فروش امروز:", size=9, color="#F6EFE6"),
                                header_today_sales_text,
                            ]
                        )
                    ]
                )
            ]
        )
    )

    # =========================================================================
    # نوار سوئیچ سریع بین بخش کافه و بخش رستوران (فقط در حالت دو منظوره «کافه‌رستوران»)
    # =========================================================================
    pos_section_switcher_row = ft.Row(spacing=8)
    pos_section_switcher_box = ft.Container(
        visible=(app_mode == "both"),
        content=pos_section_switcher_row,
    )

    menu_section_switcher_row = ft.Row(spacing=8)
    menu_section_switcher_box = ft.Container(
        visible=(app_mode == "both"),
        content=menu_section_switcher_row,
    )

    def switch_active_section(sec_name: str):
        nonlocal active_section, selected_cashier_category
        if active_section == sec_name:
            return
        active_section = sec_name
        selected_cashier_category = "همه"
        close_custom_dropdown()
        reset_menu_form()
        apply_active_theme()
        render_section_switchers()
        refresh_category_dropdown()
        render_cashier_category_chips()
        load_cashier_products()
        load_menu_products()
        page.update()

    def render_section_switchers():
        is_both = (app_mode == "both")
        pos_section_switcher_box.visible = is_both
        menu_section_switcher_box.visible = is_both
        if not is_both:
            return

        def _build_pair():
            items = [
                ("cafe", "بخش کافه", ft.icons.COFFEE_ROUNDED, "#9C623E"),
                ("restaurant", "بخش رستوران", ft.icons.RESTAURANT_ROUNDED, "#B54826"),
            ]
            ctrls = []
            for s_key, s_title, s_icon, s_color in items:
                is_act = (active_section == s_key)
                ctrls.append(
                    ft.Container(
                        expand=1,
                        bgcolor=s_color if is_act else CARD_IVORY,
                        border=ft.border.all(1.5 if is_act else 1, s_color if is_act else BORDER_WARM),
                        border_radius=12,
                        padding=ft.padding.symmetric(horizontal=10, vertical=7),
                        alignment=ft.alignment.center,
                        on_click=lambda e, k=s_key: switch_active_section(k),
                        shadow=ft.BoxShadow(
                            blur_radius=8,
                            color=ft.colors.with_opacity(0.22 if is_act else 0.04, s_color),
                            offset=ft.Offset(0, 2)
                        ),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=6,
                            controls=[
                                ft.Icon(s_icon, size=16, color=CARD_IVORY if is_act else s_color),
                                ft.Text(
                                    s_title,
                                    size=11,
                                    font_family="Vazir-Bold",
                                    color=CARD_IVORY if is_act else ESPRESSO_DARK
                                ),
                            ]
                        )
                    )
                )
            return ctrls

        pos_section_switcher_row.controls = _build_pair()
        menu_section_switcher_row.controls = _build_pair()

    # =========================================================================
    # 1. تب صندوق فروش (POS) - بدون قابلیت حذف دسته‌بندی در این بخش
    # =========================================================================
    cashier_categories_row = ft.Row(spacing=6, scroll=ft.ScrollMode.HIDDEN)
    cashier_products_col = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)

    def select_cashier_category(cat_name: str):
        nonlocal selected_cashier_category
        selected_cashier_category = cat_name
        render_cashier_category_chips()
        load_cashier_products()

    def ask_delete_category(cat_name: str):
        if not cat_name or cat_name == "همه" or cat_name == ADD_CAT_OPTION:
            return

        def confirmed_delete_cat():
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM categories WHERE name = ? AND section = ?", (cat_name, active_section))
            conn.commit()
            conn.close()

            nonlocal selected_cashier_category
            if selected_cashier_category == cat_name:
                selected_cashier_category = "همه"

            refresh_category_dropdown()
            render_cashier_category_chips()
            load_cashier_products()
            show_snackbar(f"دسته‌بندی «{cat_name}» حذف شد.", COST_RED_MAIN)

        show_confirm_dialog(
            "حذف دسته‌بندی",
            f"آیا از حذف دسته‌بندی «{cat_name}» مطمئن هستید؟\n(محصولات ثبت‌شده در این دسته حذف نمی‌شوند)",
            confirmed_delete_cat
        )

    def render_cashier_category_chips():
        cashier_categories_row.controls.clear()
        all_cats = ["همه"] + get_all_categories(active_section)
        for c in all_cats:
            is_sel = (selected_cashier_category == c)
            chip_box = ft.Container(
                bgcolor=MOCHA_PRIMARY if is_sel else CARD_IVORY,
                border=ft.border.all(1, MOCHA_PRIMARY if is_sel else BORDER_WARM),
                border_radius=20,
                padding=ft.padding.symmetric(horizontal=12, vertical=6),
                on_click=lambda e, cat=c: select_cashier_category(cat),
                shadow=ft.BoxShadow(
                    blur_radius=6,
                    color=ft.colors.with_opacity(0.18 if is_sel else 0.04, MOCHA_PRIMARY),
                    offset=ft.Offset(0, 2)
                ),
                content=ft.Text(
                    c,
                    size=11,
                    font_family="Vazir-Bold" if is_sel else "Vazir",
                    color=CARD_IVORY if is_sel else ESPRESSO_DARK
                )
            )
            cashier_categories_row.controls.append(chip_box)
        page.update()

    def on_search_change(e):
        nonlocal cashier_search_query
        cashier_search_query = e.control.value.strip()
        load_cashier_products()

    search_input = ft.TextField(
        hint_text="جستجوی سریع نام محصول...",
        prefix_icon=ft.icons.SEARCH_ROUNDED,
        height=38,
        expand=True,
        text_size=11,
        content_padding=ft.padding.symmetric(horizontal=10, vertical=0),
        border_radius=12,
        border_color=BORDER_WARM,
        focused_border_color=MOCHA_PRIMARY,
        bgcolor=CARD_IVORY,
        on_change=on_search_change
    )

    def get_category_style(cat: str):
        styles = {
            # دسته‌بندی‌های پیش‌فرض کافه (کاملاً دست‌نخورده)
            "قهوه‌ها": (ft.icons.COFFEE_ROUNDED, "#8C532E", "#F7EDE2", "#E2CBB5"),
            "نوشیدنی‌های گرم بر پایۀ قهوه": (ft.icons.LOCAL_CAFE_ROUNDED, "#9A5B13", "#FEF3C7", "#FDE68A"),
            "نوشیدنی‌های سرد بر پایۀ قهوه": (ft.icons.AC_UNIT_ROUNDED, "#0369A1", "#E0F2FE", "#BAE6FD"),
            "شیک‌ها": (ft.icons.BLENDER_ROUNDED, "#6D28D9", "#EDE9FE", "#DDD6FE"),
            "ماکتل‌ها": (ft.icons.LOCAL_BAR_ROUNDED, "#0284C7", "#E0F2FE", "#BAE6FD"),
            "بستنی بار": (ft.icons.ICE_CREAM_ROUNDED, "#BE185D", "#FCE7F3", "#FBCFE8"),
            "نوشیدنی‌های گرم": (ft.icons.LOCAL_DRINK_ROUNDED, "#C2410C", "#FFEDD5", "#FED7AA"),
            "چای‌ها": (ft.icons.EMOJI_FOOD_BEVERAGE_ROUNDED, "#047857", "#D1FAE5", "#A7F3D0"),
            "دمنوش‌ها": (ft.icons.SPA_ROUNDED, "#15803D", "#DCFCE7", "#BBF7D0"),
            "کیک و دسر": (ft.icons.COOKIE_ROUNDED, "#B45309", "#FEF3C7", "#FDE68A"),

            # دسته‌بندی‌های پیش‌فرض رستوران
            "کباب و گریل": (ft.icons.OUTDOOR_GRILL_ROUNDED, "#B43E24", "#FFEDD5", "#FDBA74"),
            "خورشت و غذای سنتی": (ft.icons.RICE_BOWL_ROUNDED, "#B45309", "#FEF3C7", "#FDE68A"),
            "پیتزا": (ft.icons.LOCAL_PIZZA_ROUNDED, "#C2410C", "#FFEDD5", "#FED7AA"),
            "برگر و ساندویچ": (ft.icons.LUNCH_DINING_ROUNDED, "#9A3412", "#FEF3C7", "#FCD34D"),
            "پاستا و استیک": (ft.icons.DINNER_DINING_ROUNDED, "#7C2D12", "#FCE7F3", "#FBCFE8"),
            "سوخاری و فینگر فود": (ft.icons.FASTFOOD_ROUNDED, "#D97706", "#FEF9C3", "#FDE047"),
            "پیش‌غذا و سوپ": (ft.icons.SOUP_KITCHEN_ROUNDED, "#0F766E", "#CCFBF1", "#99F6E4"),
            "سالاد و مخلفات": (ft.icons.ECO_ROUNDED, "#15803D", "#DCFCE7", "#BBF7D0"),
            "صبحانه و برانچ": (ft.icons.EGG_ALT_ROUNDED, "#A16207", "#FEF3C7", "#FDE68A"),
            "نوشیدنی سرد": (ft.icons.LOCAL_DRINK_ROUNDED, "#0284C7", "#E0F2FE", "#BAE6FD"),
        }
        if cat in styles:
            return styles[cat]

        if any(w in cat for w in ("کباب", "جوجه", "بریانی", "گریل", "شیشلیک", "کوبیده")):
            return (ft.icons.OUTDOOR_GRILL_ROUNDED, "#B43E24", "#FFEDD5", "#FDBA74")
        if any(w in cat for w in ("پلو", "چلو", "خورشت", "سنتی", "ایرانی", "دیزی", "آبگوشت", "تهچین")):
            return (ft.icons.RICE_BOWL_ROUNDED, "#B45309", "#FEF3C7", "#FDE68A")
        if any(w in cat for w in ("پیتزا", "کالزونه", "لازانیا")):
            return (ft.icons.LOCAL_PIZZA_ROUNDED, "#C2410C", "#FFEDD5", "#FED7AA")
        if any(w in cat for w in ("برگر", "ساندویچ", "هات‌داگ", "هات داگ", "اسنک", "پنینی", "تست")):
            return (ft.icons.LUNCH_DINING_ROUNDED, "#9A3412", "#FEF3C7", "#FCD34D")
        if any(w in cat for w in ("پاستا", "استیک", "فرنگی", "ماهی", "میگو", "دریایی")):
            return (ft.icons.DINNER_DINING_ROUNDED, "#7C2D12", "#FCE7F3", "#FBCFE8")
        if any(w in cat for w in ("سوخاری", "فینگر", "سیب‌زمینی", "سیب زمینی", "کنتاکی")):
            return (ft.icons.FASTFOOD_ROUNDED, "#D97706", "#FEF9C3", "#FDE047")
        if any(w in cat for w in ("سوپ", "آش", "پیش‌غذا", "پیش غذا", "حمص")):
            return (ft.icons.SOUP_KITCHEN_ROUNDED, "#0F766E", "#CCFBF1", "#99F6E4")
        if any(w in cat for w in ("سالاد", "زیتون", "ماست", "ترشی", "مخلفات", "گیاهی", "عرقیات")):
            return (ft.icons.ECO_ROUNDED, "#15803D", "#DCFCE7", "#BBF7D0")
        if any(w in cat for w in ("صبحانه", "املت", "نیمرو", "برانچ")):
            return (ft.icons.EGG_ALT_ROUNDED, "#A16207", "#FEF3C7", "#FDE68A")
        if any(w in cat for w in ("شیرینی", "کوکی", "کروسان", "وافل", "پنکیک")):
            return (ft.icons.BAKERY_DINING_ROUNDED, "#B45309", "#FEF3C7", "#FDE68A")
        if any(w in cat for w in ("سرد", "آیس", "فراپه", "ماکتیل", "اسموتی", "آب‌میوه", "نوشابه", "دوغ")):
            return (ft.icons.LOCAL_DRINK_ROUNDED, "#0284C7", "#E0F2FE", "#BAE6FD")
        if any(w in cat for w in ("دمی",)):
            return (ft.icons.LOCAL_CAFE_ROUNDED, "#8C532E", "#F7EDE2", "#E2CBB5")
        if any(w in cat for w in ("غذا", "رستوران")):
            return (ft.icons.RESTAURANT_ROUNDED, "#C2410C", "#FFEDD5", "#FED7AA")
        if any(w in cat for w in ("بستنی", "شیک")):
            return (ft.icons.ICE_CREAM_ROUNDED, "#BE185D", "#FCE7F3", "#FBCFE8")

        fallback_palettes = [
            (ft.icons.LOCAL_CAFE_ROUNDED, "#8C532E", "#F7EDE2", "#E2CBB5"),
            (ft.icons.RESTAURANT_MENU_ROUNDED, "#0F766E", "#CCFBF1", "#99F6E4"),
            (ft.icons.COOKIE_ROUNDED, "#B45309", "#FEF3C7", "#FDE68A"),
            (ft.icons.LOCAL_DRINK_ROUNDED, "#C2410C", "#FFEDD5", "#FED7AA"),
            (ft.icons.BAKERY_DINING_ROUNDED, "#BE123C", "#FFE4E6", "#FECDD3"),
            (ft.icons.WINE_BAR_ROUNDED, "#A16207", "#FEF9C3", "#FEF08A"),
        ]
        idx = sum(ord(ch) for ch in cat) % len(fallback_palettes)
        return fallback_palettes[idx]

    def load_cashier_products():
        cashier_products_col.controls.clear()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, category, cost_price, sell_price FROM products WHERE section = ? ORDER BY sort_index ASC",
            (active_section,)
        )
        rows = cursor.fetchall()
        conn.close()

        filtered_rows = []
        for r in rows:
            if selected_cashier_category != "همه" and r[2] != selected_cashier_category:
                continue
            if cashier_search_query and cashier_search_query not in r[1]:
                continue
            filtered_rows.append(r)

        if not filtered_rows:
            empty_icon = ft.icons.COFFEE_ROUNDED if active_section == "cafe" else ft.icons.RESTAURANT_ROUNDED
            cashier_products_col.controls.append(
                ft.Container(
                    bgcolor=CARD_IVORY,
                    border_radius=16,
                    border=ft.border.all(1, BORDER_SAND),
                    padding=30,
                    alignment=ft.alignment.center,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                        controls=[
                            ft.Container(
                                content=ft.Icon(empty_icon, size=36, color=CARAMEL_ACCENT),
                                bgcolor=SURFACE_LATTE,
                                padding=14,
                                border_radius=50,
                            ),
                            ft.Text(
                                "محصولی در این بخش یافت نشد!",
                                color=ESPRESSO_DARK, size=12, font_family="Vazir-Bold", text_align=ft.TextAlign.CENTER
                            ),
                            ft.Text(
                                "از تب «مدیریت منو» آیتم‌های جدید کافه را ثبت کنید.",
                                color=TEXT_MUTED, size=10, text_align=ft.TextAlign.CENTER
                            ),
                        ]
                    )
                )
            )
        else:
            for row in filtered_rows:
                p_id, p_name, p_cat, p_cost, p_sell = row
                cat_icon, cat_color, cat_bg, cat_border = get_category_style(p_cat)

                def direct_checkout_click(e, prod=(p_id, p_name, p_cost, p_sell), sec=active_section):
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                    unit_profit = prod[3] - prod[2]

                    cursor.execute("""
                        INSERT INTO orders (product_name, sell_price, profit, order_date, section)
                        VALUES (?, ?, ?, ?, ?)
                    """, (prod[1], prod[3], unit_profit, now_str, sec))

                    conn.commit()
                    conn.close()

                    refresh_header_today_sales()
                    show_snackbar(f"یک عدد «{prod[1]}» در فاکتور ثبت شد.", MOCHA_PRIMARY)

                card = ft.Container(
                    bgcolor=CARD_IVORY,
                    border_radius=16,
                    padding=ft.padding.symmetric(horizontal=12, vertical=10),
                    shadow=ft.BoxShadow(blur_radius=10, color=ft.colors.with_opacity(0.05, MOCHA_PRIMARY), offset=ft.Offset(0, 3)),
                    border=ft.border.all(1, BORDER_SAND),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                spacing=10,
                                expand=True,
                                controls=[
                                    ft.Container(
                                        content=ft.Icon(cat_icon, color=cat_color, size=22),
                                        bgcolor=cat_bg,
                                        padding=10,
                                        border_radius=12,
                                        border=ft.border.all(1, cat_border),
                                    ),
                                    ft.Column(
                                        spacing=3,
                                        expand=True,
                                        controls=[
                                            ft.Text(p_name, font_family="Vazir-Bold", size=13, color=ESPRESSO_DARK),
                                            ft.Row(
                                                spacing=6,
                                                wrap=True,
                                                controls=[
                                                    ft.Container(
                                                        content=ft.Text(p_cat, size=9, color=cat_color, font_family="Vazir-Bold"),
                                                        bgcolor=cat_bg,
                                                        padding=ft.padding.symmetric(horizontal=6, vertical=2),
                                                        border_radius=6
                                                    ),
                                                    ft.Text(f"{format_price(p_sell)} تومان", size=11, color=MOCHA_PRIMARY, font_family="Vazir-Bold"),
                                                ]
                                            )
                                        ]
                                    ),
                                ]
                            ),
                            ft.Container(
                                gradient=ft.LinearGradient(colors=[MOCHA_PRIMARY, CARAMEL_ACCENT]),
                                width=60, height=44, border_radius=12, alignment=ft.alignment.center,
                                on_click=direct_checkout_click,
                                shadow=ft.BoxShadow(blur_radius=6, color=ft.colors.with_opacity(0.25, MOCHA_PRIMARY), offset=ft.Offset(0, 2)),
                                content=ft.Icon(ft.icons.POINT_OF_SALE_ROUNDED, color="#FFFDF9", size=24),
                            )
                        ]
                    )
                )
                cashier_products_col.controls.append(card)
        page.update()

    # --- دیالوگ یکتای فاکتورهای اخیر (وسط صفحه) ---
    orders_list_col = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, height=310)

    recent_orders_card = ft.Container(
        width=365,
        bgcolor=CARD_IVORY,
        border_radius=20,
        padding=ft.padding.only(top=16, left=16, right=16, bottom=10),
        shadow=ft.BoxShadow(
            blur_radius=24,
            color=ft.colors.with_opacity(0.28, "#000000"),
            offset=ft.Offset(0, 8),
        ),
        on_click=lambda e: None,
        rtl=True,
        content=ft.Column(
            rtl=True,
            tight=True,
            spacing=8,
            controls=[
                ft.Row(
                    rtl=True,
                    alignment=ft.MainAxisAlignment.START,
                    spacing=8,
                    controls=[
                        ft.Container(
                            content=ft.Icon(ft.icons.HISTORY_ROUNDED, color=COST_RED_MAIN, size=20),
                            bgcolor=COST_RED_BG,
                            padding=7,
                            border_radius=10,
                        ),
                        ft.Text("فاکتورهای اخیر (لغو سفارش)", size=14, font_family="Vazir-Bold", color=ESPRESSO_DARK),
                    ]
                ),
                orders_dlg_banner,
                orders_list_col,
                ft.Row(
                    rtl=True,
                    alignment=ft.MainAxisAlignment.END,
                    controls=[
                        ft.TextButton(
                            "بستن پنجره",
                            style=ft.ButtonStyle(color=ESPRESSO_DARK),
                            on_click=lambda e: close_dialog(recent_orders_dlg)
                        )
                    ]
                )
            ]
        )
    )
    recent_orders_dlg = make_centered_modal(recent_orders_card)

    def load_recent_orders():
        orders_list_col.controls.clear()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        if app_mode == "cafe":
            cursor.execute("SELECT COUNT(*) FROM orders WHERE section = 'cafe'")
            total_orders = cursor.fetchone()[0]
            cursor.execute("SELECT id, product_name, sell_price, order_date, section FROM orders WHERE section = 'cafe' ORDER BY id DESC LIMIT 25")
        elif app_mode == "restaurant":
            cursor.execute("SELECT COUNT(*) FROM orders WHERE section = 'restaurant'")
            total_orders = cursor.fetchone()[0]
            cursor.execute("SELECT id, product_name, sell_price, order_date, section FROM orders WHERE section = 'restaurant' ORDER BY id DESC LIMIT 25")
        else:
            cursor.execute("SELECT COUNT(*) FROM orders")
            total_orders = cursor.fetchone()[0]
            cursor.execute("SELECT id, product_name, sell_price, order_date, section FROM orders ORDER BY id DESC LIMIT 25")

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            orders_list_col.controls.append(
                ft.Container(
                    content=ft.Text("هیچ سفارشی ثبت نشده است.", color=TEXT_MUTED, size=12),
                    alignment=ft.alignment.center,
                    padding=30
                )
            )
        else:
            for idx, r in enumerate(rows):
                o_id, o_name, o_price, o_date, o_sec = r
                jalali_dt = format_jalali_datetime(o_date)
                display_num = total_orders - idx

                def ask_delete_order(e, order_id=o_id, prod_name=o_name, d_num=display_num):
                    def confirmed_delete():
                        conn_del = sqlite3.connect(DB_NAME)
                        cur_del = conn_del.cursor()
                        cur_del.execute("DELETE FROM orders WHERE id = ?", (order_id,))

                        cur_del.execute("SELECT COUNT(*) FROM orders")
                        if cur_del.fetchone()[0] == 0:
                            cur_del.execute("DELETE FROM sqlite_sequence WHERE name='orders'")

                        conn_del.commit()
                        conn_del.close()
                        refresh_header_today_sales()
                        load_recent_orders()
                        load_dashboard_data()
                        show_snackbar(f"فاکتور شماره {d_num} ({prod_name}) لغو و حذف شد.", COST_RED_MAIN)

                    show_confirm_dialog(
                        "لغو و حذف فاکتور",
                        f"آیا از لغو و حذف سفارش شماره {d_num} «{prod_name}» به مبلغ {format_price(o_price)} تومان مطمئن هستید؟",
                        confirmed_delete
                    )

                name_row_controls = [
                    ft.Text(o_name, size=12, font_family="Vazir-Bold", color=ESPRESSO_DARK),
                ]
                if app_mode == "both":
                    sec_label = "کافه" if o_sec == "cafe" else "رستوران"
                    sec_col = "#9C623E" if o_sec == "cafe" else "#B54826"
                    name_row_controls.append(
                        ft.Container(
                            bgcolor=CHIP_LATTE,
                            padding=ft.padding.symmetric(horizontal=5, vertical=1),
                            border_radius=5,
                            content=ft.Text(sec_label, size=8, font_family="Vazir-Bold", color=sec_col),
                        )
                    )

                orders_list_col.controls.append(
                    ft.Container(
                        bgcolor=SURFACE_LATTE,
                        border=ft.border.all(1, BORDER_SAND),
                        border_radius=12,
                        padding=10,
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            rtl=True,
                            controls=[
                                ft.Container(
                                    content=ft.Text(f"{display_num}", size=11, font_family="Vazir-Bold", color=MOCHA_PRIMARY),
                                    bgcolor=CHIP_LATTE,
                                    padding=ft.padding.symmetric(horizontal=8, vertical=5),
                                    border_radius=8,
                                ),
                                ft.Row(
                                    rtl=True,
                                    spacing=12,
                                    controls=[
                                        ft.Column(
                                            spacing=2,
                                            horizontal_alignment=ft.CrossAxisAlignment.START,
                                            controls=[
                                                ft.Row(rtl=True, spacing=6, controls=name_row_controls),
                                                ft.Row(
                                                    rtl=True,
                                                    spacing=4,
                                                    controls=[
                                                        ft.Text(f"{format_price(o_price)}", size=10, font_family="Vazir-Bold", color=TEXT_MUTED),
                                                        ft.Text("تومان", size=10, color=TEXT_MUTED),
                                                        ft.Text("|", size=9, color=BORDER_WARM),
                                                        ft.Text(jalali_dt, size=10, color=TEXT_MUTED)
                                                    ]
                                                )
                                            ]
                                        ),
                                        ft.Container(
                                            content=ft.Icon(ft.icons.DELETE_FOREVER_ROUNDED, color=COST_RED_MAIN, size=18),
                                            bgcolor=COST_RED_BG,
                                            border=ft.border.all(1, COST_RED_BORDER),
                                            width=34, height=34, border_radius=8, alignment=ft.alignment.center,
                                            on_click=ask_delete_order,
                                            tooltip="لغو این سفارش"
                                        ),
                                    ]
                                ),
                            ]
                        )
                    )
                )
        refresh_ui(orders_list_col, recent_orders_dlg)

    def open_recent_orders_dialog(e):
        orders_dlg_banner.visible = False
        load_recent_orders()
        open_ctrl(recent_orders_dlg)

    cashier_view = ft.Container(
        padding=16,
        expand=True,
        content=ft.Column(
            spacing=12,
            expand=True,
            controls=[
                pos_section_switcher_box,
                ft.Row(
                    spacing=10,
                    controls=[
                        search_input,
                        ft.ElevatedButton(
                            "لغو فاکتور",
                            icon=ft.icons.RESTORE_FROM_TRASH_ROUNDED,
                            bgcolor=COST_RED_BG,
                            color=COST_RED_DARK,
                            elevation=0,
                            height=38,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=10),
                                text_style=ft.TextStyle(size=11, font_family="Vazir-Bold")
                            ),
                            on_click=open_recent_orders_dialog
                        ),
                    ]
                ),
                ft.Container(
                    content=cashier_categories_row,
                    margin=ft.padding.only(top=-2)
                ),
                cashier_products_col
            ]
        )
    )

    # =========================================================================
    # 2. تب مدیریت منو (منوی کشویی زیر کادر دسته‌بندی + حذف با لانگ‌پرس)
    # =========================================================================
    def move_product(prod_id, current_sort, direction):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        if direction == "up":
            cursor.execute(
                "SELECT id, sort_index FROM products WHERE section = ? AND sort_index < ? ORDER BY sort_index DESC LIMIT 1",
                (active_section, current_sort)
            )
        else:
            cursor.execute(
                "SELECT id, sort_index FROM products WHERE section = ? AND sort_index > ? ORDER BY sort_index ASC LIMIT 1",
                (active_section, current_sort)
            )

        adjacent = cursor.fetchone()
        if adjacent:
            adj_id, adj_sort = adjacent
            cursor.execute("UPDATE products SET sort_index = ? WHERE id = ?", (adj_sort, prod_id))
            cursor.execute("UPDATE products SET sort_index = ? WHERE id = ?", (current_sort, adj_id))
            conn.commit()

        conn.close()
        load_menu_products()
        load_cashier_products()

    name_input = ft.TextField(
        label="نام محصول",
        height=44,
        text_size=12,
        content_padding=ft.padding.symmetric(horizontal=12, vertical=8),
        border_radius=10,
        border_color=BORDER_WARM,
        focused_border_color=MOCHA_PRIMARY,
        bgcolor=SURFACE_LATTE,
        expand=1
    )

    form_category_value = [""]
    form_category_label = ft.Text(
        "انتخاب دسته‌بندی...",
        size=11,
        color=ESPRESSO_DARK,
        font_family="Vazir-Bold",
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
    dropdown_arrow_icon = ft.Icon(ft.icons.ARROW_DROP_DOWN_ROUNDED, color=MOCHA_PRIMARY, size=20)

    custom_dropdown_list = ft.Column(
        spacing=3,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    custom_dropdown_list_container = ft.Container(
        visible=False,
        bgcolor=CARD_IVORY,
        border=ft.border.all(1, BORDER_WARM),
        border_radius=ft.border_radius.only(bottom_left=10, bottom_right=10),
        padding=ft.padding.all(5),
        height=190,
        width=174,
        top=43,
        left=0,
        shadow=ft.BoxShadow(
            blur_radius=12,
            color=ft.colors.with_opacity(0.15, MOCHA_PRIMARY),
            offset=ft.Offset(0, 6)
        ),
        content=custom_dropdown_list
    )

    def close_custom_dropdown(e=None):
        was_open = custom_dropdown_list_container.visible or dropdown_backdrop.visible
        custom_dropdown_list_container.visible = False
        dropdown_backdrop.visible = False
        set_icon_value(dropdown_arrow_icon, ft.icons.ARROW_DROP_DOWN_ROUNDED)
        custom_dropdown_box.border_radius = 10
        if was_open:
            refresh_ui(custom_dropdown_box, custom_dropdown_list_container, dropdown_backdrop)

    dropdown_backdrop = ft.Container(
        visible=False,
        top=0,
        bottom=0,
        left=0,
        right=0,
        on_click=close_custom_dropdown,
    )

    def select_custom_cat(cat_name):
        form_category_value[0] = cat_name
        form_category_label.value = cat_name
        close_custom_dropdown()
        refresh_ui(form_category_label)

    last_long_press_ts = [0.0]

    def trigger_long_press_delete(cat_name: str):
        now_t = time.time()
        if now_t - last_long_press_ts[0] < 0.8:
            return
        last_long_press_ts[0] = now_t
        close_custom_dropdown()
        ask_delete_category(cat_name)

    def refresh_custom_dropdown_list():
        custom_dropdown_list.controls.clear()
        cats = get_all_categories(active_section)
        for c in cats:
            is_sel = (c == form_category_value[0])
            item_box = ft.Container(
                bgcolor=MOCHA_PRIMARY if is_sel else SURFACE_LATTE,
                border_radius=8,
                padding=ft.padding.symmetric(horizontal=10, vertical=9),
                on_click=lambda e, cat=c: select_custom_cat(cat),
                on_long_press=lambda e, cat=c: trigger_long_press_delete(cat),
                content=ft.Row(
                    rtl=True,
                    alignment=ft.MainAxisAlignment.START,
                    controls=[
                        ft.Text(
                            c, size=11,
                            color=CARD_IVORY if is_sel else ESPRESSO_DARK,
                            font_family="Vazir-Bold" if is_sel else "Vazir",
                            expand=True,
                        )
                    ]
                )
            )
            item_gesture = ft.GestureDetector(
                mouse_cursor=ft.MouseCursor.CLICK,
                on_tap=lambda e, cat=c: select_custom_cat(cat),
                on_long_press_start=lambda e, cat=c: trigger_long_press_delete(cat),
                on_secondary_tap=lambda e, cat=c: trigger_long_press_delete(cat),
                content=item_box
            )
            custom_dropdown_list.controls.append(item_gesture)

        custom_dropdown_list.controls.append(
            ft.Container(
                bgcolor=CHIP_LATTE,
                border_radius=8,
                padding=ft.padding.symmetric(horizontal=10, vertical=9),
                on_click=lambda e: open_new_cat_dialog(),
                content=ft.Row(
                    rtl=True, alignment=ft.MainAxisAlignment.START, spacing=5,
                    controls=[
                        ft.Icon(ft.icons.ADD_ROUNDED, size=15, color=MOCHA_PRIMARY),
                        ft.Text("افزودن دسته‌بندی جدید", size=11, color=MOCHA_PRIMARY, font_family="Vazir-Bold", expand=True)
                    ]
                )
            )
        )
        refresh_ui(custom_dropdown_list)

    def toggle_custom_dropdown(e=None):
        is_open = custom_dropdown_list_container.visible
        if not is_open:
            page_w = page.width if (page.width and page.width > 0) else 419
            calc_w = int((page_w - 71) / 2)
            if calc_w > 100:
                custom_dropdown_list_container.width = calc_w

            custom_dropdown_list_container.visible = True
            dropdown_backdrop.visible = True
            set_icon_value(dropdown_arrow_icon, ft.icons.ARROW_DROP_UP_ROUNDED)
            custom_dropdown_box.border_radius = ft.border_radius.only(top_left=10, top_right=10)
            refresh_custom_dropdown_list()
            refresh_ui(custom_dropdown_box, custom_dropdown_list_container, dropdown_backdrop)
        else:
            close_custom_dropdown()

    custom_dropdown_box = ft.Container(
        height=44,
        expand=1,
        border=ft.border.all(1, BORDER_WARM),
        border_radius=10,
        bgcolor=SURFACE_LATTE,
        padding=ft.padding.symmetric(horizontal=10, vertical=4),
        on_click=toggle_custom_dropdown,
        content=ft.Row(
            rtl=True,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Column(
                    spacing=0, alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.START, expand=True,
                    controls=[
                        ft.Text("دسته‌بندی", size=8, color=TEXT_MUTED),
                        form_category_label,
                    ]
                ),
                dropdown_arrow_icon,
            ]
        )
    )

    def refresh_category_dropdown(selected: str = None):
        cats = get_all_categories(active_section)
        if selected and selected in cats:
            form_category_value[0] = selected
        elif form_category_value[0] not in cats:
            form_category_value[0] = cats[0] if cats else ""
        form_category_label.value = form_category_value[0]
        close_custom_dropdown()
        refresh_ui(form_category_label, custom_dropdown_list_container, custom_dropdown_box)

    new_cat_input = ft.TextField(
        label="نام دسته‌بندی جدید",
        text_size=12, height=44, border_radius=10, border_color=BORDER_WARM,
        focused_border_color=MOCHA_PRIMARY, bgcolor=SURFACE_LATTE, rtl=True, text_align=ft.TextAlign.RIGHT,
    )

    def submit_new_category(e):
        c_name = (new_cat_input.value or "").strip()
        if not c_name or c_name == ADD_CAT_OPTION or c_name == "همه":
            show_snackbar("لطفاً یک نام معتبر برای دسته‌بندی وارد کنید!", COST_RED_MAIN)
            return
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO categories (name, section) VALUES (?, ?)", (c_name, active_section))
            conn.commit()
            conn.close()
            new_cat_input.value = ""
            close_ctrl(cat_dialog)
            refresh_category_dropdown(selected=c_name)
            render_cashier_category_chips()
            show_snackbar(f"دسته‌بندی «{c_name}» با موفقیت اضافه شد.", MOCHA_PRIMARY)
        except sqlite3.IntegrityError:
            show_snackbar("این دسته‌بندی از قبل در لیست وجود دارد!", COST_RED_MAIN)

    new_cat_input.on_submit = submit_new_category

    def open_new_cat_dialog(e=None):
        cat_dlg_banner.visible = False
        new_cat_input.value = ""
        close_custom_dropdown()
        open_ctrl(cat_dialog)

    cat_dlg_icon = ft.Icon(ft.icons.CREATE_NEW_FOLDER_ROUNDED, color=MOCHA_PRIMARY, size=20)
    cat_dlg_icon_box = ft.Container(content=cat_dlg_icon, bgcolor=CHIP_LATTE, padding=7, border_radius=10)
    cat_dlg_add_btn = ft.ElevatedButton(
        "افزودن",
        icon=ft.icons.ADD_ROUNDED,
        bgcolor=MOCHA_PRIMARY,
        color=ft.colors.WHITE,
        height=38,
        rtl=True,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
        on_click=submit_new_category
    )

    cat_dialog_card = ft.Container(
        width=325,
        bgcolor=CARD_IVORY,
        border_radius=18,
        padding=ft.padding.symmetric(horizontal=18, vertical=16),
        shadow=ft.BoxShadow(
            blur_radius=24,
            color=ft.colors.with_opacity(0.28, "#000000"),
            offset=ft.Offset(0, 8),
        ),
        on_click=lambda e: None,
        rtl=True,
        content=ft.Column(
            rtl=True,
            tight=True,
            spacing=12,
            controls=[
                ft.Row(
                    rtl=True, alignment=ft.MainAxisAlignment.START, spacing=8,
                    controls=[
                        cat_dlg_icon_box,
                        ft.Text("افزودن دسته‌بندی جدید", size=14, font_family="Vazir-Bold", color=ESPRESSO_DARK),
                    ]
                ),
                cat_dlg_banner,
                new_cat_input,
                ft.Row(
                    rtl=True, alignment=ft.MainAxisAlignment.END, spacing=8,
                    controls=[
                        ft.TextButton("انصراف", style=ft.ButtonStyle(color=ESPRESSO_DARK), on_click=lambda e: close_ctrl(cat_dialog)),
                        cat_dlg_add_btn,
                    ]
                )
            ]
        )
    )
    cat_dialog = make_centered_modal(cat_dialog_card)

    cost_words_text = ft.Text("صفر تومان", size=10, color=COST_RED_MAIN, font_family="Vazir-Bold")
    sell_words_text = ft.Text("صفر تومان", size=10, color=MOCHA_PRIMARY, font_family="Vazir-Bold")
    live_profit_preview_text = ft.Text("لطفاً قیمت پایه و فروش را وارد کنید", size=11, color=MOCHA_PRIMARY, font_family="Vazir-Bold")
    live_profit_preview_box = ft.Container(
        bgcolor=SURFACE_LATTE, border=ft.border.all(1, BORDER_SAND), border_radius=10,
        padding=ft.padding.symmetric(horizontal=10, vertical=6), alignment=ft.alignment.center,
        content=live_profit_preview_text
    )

    submit_product_btn = ft.ElevatedButton(
        "ذخیره در منوی کافه",
        icon=ft.icons.CHECK_CIRCLE_ROUNDED,
        bgcolor=DISABLED_BG, color=DISABLED_TEXT, expand=True, height=42, disabled=False,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), text_style=ft.TextStyle(size=12, font_family="Vazir-Bold")),
        on_click=lambda e: None
    )

    def update_live_profit_preview():
        c_raw = (cost_input.value or "").replace(",", "").strip()
        s_raw = (sell_input.value or "").replace(",", "").strip()
        c_num = int(c_raw) if c_raw.isdigit() else 0
        s_num = int(s_raw) if s_raw.isdigit() else 0
        diff = s_num - c_num

        if s_raw == "" or c_raw == "":
            live_profit_preview_text.value = "لطفاً قیمت پایه و فروش را وارد کنید"
            live_profit_preview_text.color = MOCHA_PRIMARY
            live_profit_preview_box.bgcolor = SURFACE_LATTE
            live_profit_preview_box.border = ft.border.all(1, BORDER_SAND)
            submit_product_btn.bgcolor = DISABLED_BG
            submit_product_btn.color = DISABLED_TEXT
            submit_product_btn.on_click = lambda e: None
        elif diff > 0:
            margin_pct = int((diff / s_num) * 100) if s_num > 0 else 0
            live_profit_preview_text.value = f"سود خالص هر فروش: {format_price(diff)} تومان ({margin_pct}٪ سود)"
            live_profit_preview_text.color = PROFIT_DARK
            live_profit_preview_box.bgcolor = PROFIT_SURFACE
            live_profit_preview_box.border = ft.border.all(1, PROFIT_BORDER)
            submit_product_btn.bgcolor = CARAMEL_ACCENT if editing_product_id else MOCHA_PRIMARY
            submit_product_btn.color = ft.colors.WHITE
            submit_product_btn.on_click = save_or_update_product
        else:
            live_profit_preview_text.value = f"زیان یا بدون سود: {format_price(abs(diff))} تومان (غیرقابل ثبت!)"
            live_profit_preview_text.color = COST_RED_MAIN
            live_profit_preview_box.bgcolor = COST_RED_SURFACE
            live_profit_preview_box.border = ft.border.all(1, COST_RED_BORDER)
            submit_product_btn.bgcolor = DISABLED_BG
            submit_product_btn.color = DISABLED_TEXT
            submit_product_btn.on_click = lambda e: None

    def on_cost_price_change(e):
        digits = "".join([c for c in (e.control.value or "") if c.isdigit()])
        if digits:
            num_val = int(digits)
            e.control.value = f"{num_val:,}"
            cost_words_text.value = f"{num_to_persian(num_val)} تومان"
        else:
            e.control.value = ""
            cost_words_text.value = "صفر تومان"
        update_live_profit_preview()
        page.update()

    def on_sell_price_change(e):
        digits = "".join([c for c in (e.control.value or "") if c.isdigit()])
        if digits:
            num_val = int(digits)
            e.control.value = f"{num_val:,}"
            sell_words_text.value = f"{num_to_persian(num_val)} تومان"
        else:
            e.control.value = ""
            sell_words_text.value = "صفر تومان"
        update_live_profit_preview()
        page.update()

    cost_input = ft.TextField(
        label="قیمت پایه (هزینه)",
        height=44,
        text_size=12,
        keyboard_type=ft.KeyboardType.NUMBER,
        content_padding=ft.padding.symmetric(horizontal=12, vertical=8),
        border_radius=10,
        border_color=BORDER_WARM,
        focused_border_color=MOCHA_PRIMARY,
        bgcolor=SURFACE_LATTE,
        on_change=on_cost_price_change
    )

    sell_input = ft.TextField(
        label="قیمت فروش", height=44, text_size=12, keyboard_type=ft.KeyboardType.NUMBER,
        content_padding=ft.padding.symmetric(horizontal=12, vertical=8), border_radius=10,
        border_color=BORDER_WARM, focused_border_color=MOCHA_PRIMARY, bgcolor=SURFACE_LATTE,
        on_change=on_sell_price_change
    )

    cancel_edit_btn = ft.Container(
        content=ft.Icon(ft.icons.CLOSE_ROUNDED, color=COST_RED_MAIN, size=20),
        bgcolor=COST_RED_BG, border=ft.border.all(1, COST_RED_BORDER),
        width=42, height=42, border_radius=10, alignment=ft.alignment.center, tooltip="بستن فرم",
    )

    menu_products_col = ft.Column(spacing=8)
    menu_count_badge = ft.Text("0 محصول", size=11, font_family="Vazir-Bold", color=MOCHA_PRIMARY)
    menu_count_badge_box = ft.Container(
        bgcolor=CHIP_LATTE,
        padding=ft.padding.symmetric(horizontal=7, vertical=3),
        border_radius=8,
        content=menu_count_badge
    )
    menu_header_icon = ft.Icon(ft.icons.MENU_BOOK_ROUNDED, color=MOCHA_PRIMARY, size=18)
    menu_header_icon_box = ft.Container(
        content=menu_header_icon,
        bgcolor=CHIP_LATTE,
        padding=7,
        border_radius=10,
    )

    sell_words_icon = ft.Icon(ft.icons.SUBDIRECTORY_ARROW_LEFT_ROUNDED, size=12, color=MOCHA_PRIMARY)
    sell_words_box = ft.Container(
        bgcolor=BG_CREAM, border=ft.border.all(1, BORDER_SAND),
        border_radius=8, padding=ft.padding.symmetric(horizontal=8, vertical=4),
        content=ft.Row(spacing=4, controls=[sell_words_icon, ft.Container(content=sell_words_text, expand=True)])
    )

    add_form_content = ft.Column(
        spacing=10,
        controls=[
            ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[name_input, custom_dropdown_box]
            ),
            ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    ft.Column(
                        spacing=4, expand=1,
                        controls=[
                            cost_input,
                            ft.Container(
                                bgcolor=COST_RED_SURFACE, border=ft.border.all(1, COST_RED_BORDER),
                                border_radius=8, padding=ft.padding.symmetric(horizontal=8, vertical=4),
                                content=ft.Row(spacing=4, controls=[ft.Icon(ft.icons.SUBDIRECTORY_ARROW_LEFT_ROUNDED, size=12, color=COST_RED_MAIN), ft.Container(content=cost_words_text, expand=True)])
                            )
                        ]
                    ),
                    ft.Column(
                        spacing=4, expand=1,
                        controls=[
                            sell_input,
                            sell_words_box,
                        ]
                    )
                ]
            ),
            live_profit_preview_box,
            ft.Row(spacing=8, controls=[submit_product_btn, cancel_edit_btn])
        ]
    )

    add_form_stack = ft.Stack(
        controls=[
            add_form_content,
            dropdown_backdrop,
            custom_dropdown_list_container
        ]
    )
    try:
        add_form_stack.clip_behavior = ft.ClipBehavior.NONE
    except Exception:
        pass

    add_form_container = ft.Container(
        visible=False,
        bgcolor=CARD_IVORY,
        border_radius=16,
        padding=14,
        border=ft.border.all(1.5, BORDER_WARM),
        shadow=ft.BoxShadow(blur_radius=14, color=ft.colors.with_opacity(0.08, MOCHA_PRIMARY), offset=ft.Offset(0, 4)),
        content=add_form_stack
    )

    show_add_form_btn = ft.ElevatedButton(
        "افزودن آیتم",
        icon=ft.icons.ADD_CIRCLE_OUTLINE_ROUNDED,
        bgcolor=MOCHA_PRIMARY,
        color=ft.colors.WHITE,
        elevation=2,
        height=36,
        style=ft.ButtonStyle(
            padding=ft.padding.symmetric(horizontal=10, vertical=0),
            shape=ft.RoundedRectangleBorder(radius=10),
            text_style=ft.TextStyle(size=11, font_family="Vazir-Bold")
        )
    )

    def toggle_form(show: bool):
        add_form_container.visible = show
        show_add_form_btn.visible = not show
        if not show:
            close_custom_dropdown()
        page.update()

    show_add_form_btn.on_click = lambda e: toggle_form(True)

    def reset_menu_form():
        nonlocal editing_product_id
        editing_product_id = None
        name_input.value = ""
        refresh_category_dropdown()
        cost_input.value = ""
        sell_input.value = ""
        cost_words_text.value = "صفر تومان"
        sell_words_text.value = "صفر تومان"
        live_profit_preview_text.value = "لطفاً قیمت پایه و فروش را وارد کنید"
        live_profit_preview_text.color = MOCHA_PRIMARY
        live_profit_preview_box.bgcolor = SURFACE_LATTE
        live_profit_preview_box.border = ft.border.all(1, BORDER_SAND)
        submit_product_btn.text = "ذخیره در منوی کافه"
        submit_product_btn.icon = ft.icons.CHECK_CIRCLE_ROUNDED
        submit_product_btn.bgcolor = DISABLED_BG
        submit_product_btn.color = DISABLED_TEXT
        submit_product_btn.on_click = lambda e: None
        toggle_form(False)

    cancel_edit_btn.on_click = lambda e: reset_menu_form()

    def save_or_update_product(e):
        nonlocal editing_product_id
        name = name_input.value.strip()
        cat = form_category_value[0]
        cost_str = cost_input.value.strip().replace(",", "")
        sell_str = sell_input.value.strip().replace(",", "")

        if not name or not cost_str or not sell_str or not cat or cat == ADD_CAT_OPTION:
            show_snackbar("لطفاً نام محصول، دسته‌بندی و هر دو قیمت را وارد کنید!", COST_RED_MAIN)
            return

        try:
            cost_val = float(cost_str)
            sell_val = float(sell_str)
        except ValueError:
            show_snackbar("قیمت خرید و فروش باید عدد باشند!", COST_RED_MAIN)
            return

        if sell_val <= cost_val:
            show_snackbar("خطا: قیمت فروش باید حتماً بیشتر از قیمت پایه باشد!", COST_RED_MAIN)
            return

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        if editing_product_id is None:
            cursor.execute("SELECT MAX(sort_index) FROM products WHERE section = ?", (active_section,))
            max_sort = cursor.fetchone()[0]
            new_sort = (max_sort or 0) + 1

            cursor.execute("""
                INSERT INTO products (name, category, cost_price, sell_price, sort_index, section)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, cat, cost_val, sell_val, new_sort, active_section))
            show_snackbar(f"محصول «{name}» با موفقیت به منو اضافه شد.", MOCHA_PRIMARY)
        else:
            cursor.execute("SELECT name, section FROM products WHERE id = ?", (editing_product_id,))
            old_row = cursor.fetchone()

            cursor.execute("""
                UPDATE products
                SET name = ?, category = ?, cost_price = ?, sell_price = ?
                WHERE id = ?
            """, (name, cat, cost_val, sell_val, editing_product_id))

            if old_row:
                old_name, old_sec = old_row[0], old_row[1]
                if old_name != name:
                    cursor.execute("""
                        UPDATE orders
                        SET product_name = ?
                        WHERE product_name = ? AND section = ?
                    """, (name, old_name, old_sec))

            show_snackbar(f"اطلاعات «{name}» بروزرسانی شد.", CARAMEL_ACCENT)

        conn.commit()
        conn.close()
        reset_menu_form()
        load_menu_products()
        load_cashier_products()

    def load_menu_products():
        menu_products_col.controls.clear()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, category, cost_price, sell_price, sort_index FROM products WHERE section = ? ORDER BY sort_index ASC",
            (active_section,)
        )
        rows = cursor.fetchall()
        conn.close()

        menu_count_badge.value = f"{len(rows)} محصول"

        if not rows:
            menu_products_col.controls.append(
                ft.Container(
                    bgcolor=CARD_IVORY,
                    border_radius=16,
                    border=ft.border.all(1, BORDER_SAND),
                    content=ft.Text("هنوز محصولی در منو ثبت نشده است.", color=TEXT_MUTED, size=12),
                    alignment=ft.alignment.center,
                    padding=30
                )
            )
        else:
            for r in rows:
                p_id, p_name, p_cat, p_cost, p_sell, p_sort = r
                cat_icon, cat_color, cat_bg, cat_border = get_category_style(p_cat)
                unit_prof = p_sell - p_cost
                margin_pct = int((unit_prof / p_sell) * 100) if p_sell > 0 else 0

                def edit_click(e, prod=r):
                    nonlocal editing_product_id
                    editing_product_id = prod[0]
                    name_input.value = prod[1]
                    refresh_category_dropdown(selected=prod[2])

                    c_val = int(prod[3])
                    s_val = int(prod[4])

                    cost_input.value = f"{c_val:,}"
                    cost_words_text.value = f"{num_to_persian(c_val)} تومان" if c_val > 0 else "صفر تومان"

                    sell_input.value = f"{s_val:,}"
                    sell_words_text.value = f"{num_to_persian(s_val)} تومان" if s_val > 0 else "صفر تومان"

                    submit_product_btn.text = "ذخیره تغییرات"
                    submit_product_btn.icon = ft.icons.UPDATE_ROUNDED
                    update_live_profit_preview()
                    toggle_form(True)
                    page.update()

                def delete_click(e, prod_id=p_id, prod_name=p_name):
                    def confirmed_del_product():
                        conn_del = sqlite3.connect(DB_NAME)
                        cur_del = conn_del.cursor()
                        cur_del.execute("DELETE FROM products WHERE id = ?", (prod_id,))
                        conn_del.commit()
                        conn_del.close()
                        load_menu_products()
                        load_cashier_products()
                        show_snackbar(f"محصول «{prod_name}» از منو حذف شد.", COST_RED_MAIN)

                    show_confirm_dialog(
                        "حذف محصول از منو",
                        f"آیا از حذف دائمی آیتم «{prod_name}» از منوی کافه مطمئن هستید؟",
                        confirmed_del_product
                    )

                card = ft.Container(
                    bgcolor=CARD_IVORY,
                    border_radius=14,
                    padding=12,
                    border=ft.border.all(1, BORDER_SAND),
                    shadow=ft.BoxShadow(blur_radius=6, color=ft.colors.with_opacity(0.04, MOCHA_PRIMARY), offset=ft.Offset(0, 2)),
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row(
                                        spacing=10,
                                        controls=[
                                            ft.Container(
                                                content=ft.Icon(cat_icon, color=cat_color, size=20),
                                                bgcolor=cat_bg,
                                                padding=9,
                                                border_radius=11,
                                                border=ft.border.all(1, cat_border),
                                            ),
                                            ft.Column(
                                                spacing=2,
                                                controls=[
                                                    ft.Text(p_name, font_family="Vazir-Bold", size=13, color=ESPRESSO_DARK),
                                                    ft.Container(
                                                        content=ft.Text(p_cat, size=9, color=cat_color, font_family="Vazir-Bold"),
                                                        bgcolor=cat_bg,
                                                        padding=ft.padding.symmetric(horizontal=7, vertical=2),
                                                        border_radius=6
                                                    )
                                                ]
                                            ),
                                        ]
                                    ),
                                    ft.Row(
                                        spacing=4,
                                        controls=[
                                            ft.Container(
                                                content=ft.Icon(ft.icons.KEYBOARD_ARROW_UP_ROUNDED, color=MOCHA_PRIMARY, size=18),
                                                bgcolor=SURFACE_LATTE, width=34, height=34, border_radius=8, alignment=ft.alignment.center,
                                                on_click=lambda e, pid=p_id, s=p_sort: move_product(pid, s, "up"),
                                                tooltip="یک پله به بالا"
                                            ),
                                            ft.Container(
                                                content=ft.Icon(ft.icons.KEYBOARD_ARROW_DOWN_ROUNDED, color=MOCHA_PRIMARY, size=18),
                                                bgcolor=SURFACE_LATTE, width=34, height=34, border_radius=8, alignment=ft.alignment.center,
                                                on_click=lambda e, pid=p_id, s=p_sort: move_product(pid, s, "down"),
                                                tooltip="یک پله به پایین"
                                            ),
                                            ft.Container(
                                                content=ft.Icon(ft.icons.EDIT_NOTE_ROUNDED, color=MOCHA_PRIMARY, size=18),
                                                bgcolor=BG_CREAM,
                                                border=ft.border.all(1, BORDER_WARM),
                                                width=34, height=34, border_radius=8, alignment=ft.alignment.center,
                                                on_click=edit_click,
                                                tooltip="ویرایش"
                                            ),
                                            ft.Container(
                                                content=ft.Icon(ft.icons.DELETE_OUTLINE_ROUNDED, color=COST_RED_MAIN, size=18),
                                                bgcolor=COST_RED_BG,
                                                border=ft.border.all(1, COST_RED_BORDER),
                                                width=34, height=34, border_radius=8, alignment=ft.alignment.center,
                                                on_click=delete_click,
                                                tooltip="حذف"
                                            )
                                        ]
                                    )
                                ]
                            ),
                            ft.Container(
                                bgcolor=BG_CREAM,
                                border_radius=10,
                                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                                content=ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Container(
                                            bgcolor=COST_RED_SURFACE,
                                            border=ft.border.all(1, COST_RED_BORDER),
                                            padding=ft.padding.symmetric(horizontal=7, vertical=2),
                                            border_radius=6,
                                            content=ft.Text(f"پایه: {format_price(p_cost)} ت", size=10, color=COST_RED_MAIN, font_family="Vazir-Bold")
                                        ),
                                        ft.Text(f"فروش: {format_price(p_sell)} ت", size=10, color=ESPRESSO_DARK, font_family="Vazir-Bold"),
                                        ft.Container(
                                            bgcolor=PROFIT_BG,
                                            border=ft.border.all(1, PROFIT_BORDER),
                                            padding=ft.padding.symmetric(horizontal=7, vertical=2),
                                            border_radius=6,
                                            content=ft.Text(f"سود: {format_price(unit_prof)} ت ({margin_pct}٪)", size=10, color="#15803D", font_family="Vazir-Bold")
                                        )
                                    ]
                                )
                            )
                        ]
                    )
                )
                menu_products_col.controls.append(card)
        page.update()

    menu_view = ft.Container(
        padding=16,
        expand=True,
        on_click=lambda e: close_custom_dropdown(),
        content=ft.Column(
            spacing=10,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                menu_section_switcher_box,
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=6,
                            controls=[
                                menu_header_icon_box,
                                ft.Text("مدیریت منو", size=14, font_family="Vazir-Bold", color=ESPRESSO_DARK),
                                menu_count_badge_box,
                            ]
                        ),
                        show_add_form_btn
                    ]
                ),
                add_form_container,
                ft.Text("لیست محصولات موجود:", size=12, font_family="Vazir-Bold", color=ESPRESSO_DARK),
                menu_products_col
            ]
        )
    )

    # =========================================================================
    # 3. تب داشبورد و گزارش مالی پیشرفته
    # =========================================================================
    total_revenue_text = ft.Text("0", size=14, font_family="Vazir-Bold", color=MOCHA_PRIMARY)
    total_cost_text = ft.Text("0", size=14, font_family="Vazir-Bold", color=COST_RED_MAIN)
    net_profit_text = ft.Text("0 تومان", size=20, font_family="Vazir-Bold", color="#FFFDF9")
    net_profit_words_text = ft.Text("صفر تومان", size=10, color="#ECFDF5")
    profit_margin_badge_text = ft.Text("حاشیه سود: 0٪", size=10, font_family="Vazir-Bold", color=PROFIT_DARK)
    period_summary_badge = ft.Text("0 فروش", size=10, font_family="Vazir-Bold", color="#FFFDF9")

    report_items_col = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
    dashboard_sec_filter_row = ft.Row(spacing=6, alignment=ft.MainAxisAlignment.CENTER)
    dashboard_sec_filter_box = ft.Container(visible=(app_mode == "both"), content=dashboard_sec_filter_row)
    mode_selector_row = ft.Row(spacing=6, alignment=ft.MainAxisAlignment.CENTER)
    date_navigator_container = ft.Container()

    cal_state = {"jy": today_jy, "jm": today_jm, "jd": today_jd}
    cal_header_text = ft.Text("", size=13, font_family="Vazir-Bold", color=ESPRESSO_DARK)
    days_grid_col = ft.Column(spacing=5, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def render_calendar_grid():
        CELL_W = 34
        CELL_H = 34
        ROW_SPACING = 5

        cur_jy, cur_jm, cur_jd = gregorian_to_jalali(selected_date.year, selected_date.month, selected_date.day)
        jy, jm = cal_state["jy"], cal_state["jm"]

        max_days = get_jalali_month_days(jy, jm)
        if cal_state["jd"] > max_days:
            cal_state["jd"] = max_days
        jd = cal_state["jd"]

        gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
        target_date = datetime(gy, gm, gd)
        weekday_idx = (target_date.weekday() + 2) % 7
        weekdays_names = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]
        day_name = weekdays_names[weekday_idx]

        cal_header_text.value = f"{day_name}، {jd} {JALALI_MONTHS[jm - 1]} {jy}"
        days_grid_col.controls.clear()

        weekdays_chars = ["ش", "ی", "د", "س", "چ", "پ", "ج"]
        header_buttons = []
        for w in weekdays_chars:
            header_buttons.append(
                ft.Container(
                    width=CELL_W, height=28, bgcolor=CHIP_LATTE, border_radius=8,
                    alignment=ft.alignment.center,
                    content=ft.Text(w, size=11, color=MOCHA_PRIMARY, font_family="Vazir-Bold")
                )
            )

        days_grid_col.controls.append(
            ft.Container(
                margin=ft.padding.only(bottom=6),
                content=ft.Row(rtl=True, alignment=ft.MainAxisAlignment.CENTER, spacing=ROW_SPACING, controls=header_buttons)
            )
        )

        gy_first, gm_first, gd_first = jalali_to_gregorian(jy, jm, 1)
        first_day_date = datetime(gy_first, gm_first, gd_first)
        offset = (first_day_date.weekday() + 2) % 7

        row_buttons = []
        for _ in range(offset):
            row_buttons.append(ft.Container(width=CELL_W, height=CELL_H))

        for d in range(1, max_days + 1):
            is_selected = (jy == cur_jy and jm == cur_jm and d == cur_jd)
            is_today = (jy == today_jy and jm == today_jm and d == today_jd)
            is_future = (jy, jm, d) > (today_jy, today_jm, today_jd)

            def pick_day(e, day_num=d):
                nonlocal selected_date
                gy_pick, gm_pick, gd_pick = jalali_to_gregorian(cal_state["jy"], cal_state["jm"], day_num)
                selected_date = datetime(gy_pick, gm_pick, gd_pick)
                close_ctrl(cal_dlg)
                update_dashboard_controls()
                load_dashboard_data()

            if is_future:
                btn_bg, btn_col, btn_border, click_action = BG_CREAM, "#C9B8A6", None, None
            else:
                btn_bg = MOCHA_PRIMARY if is_selected else (CHIP_LATTE if is_today else SURFACE_LATTE)
                btn_col = CARD_IVORY if is_selected else ESPRESSO_DARK
                btn_border = ft.border.all(1.5, MOCHA_PRIMARY) if is_today and not is_selected else None
                click_action = pick_day

            row_buttons.append(
                ft.Container(
                    width=CELL_W, height=CELL_H, bgcolor=btn_bg, border=btn_border, border_radius=9,
                    alignment=ft.alignment.center, on_click=click_action,
                    content=ft.Text(str(d), size=11, font_family="Vazir-Bold", color=btn_col)
                )
            )

            if len(row_buttons) == 7:
                days_grid_col.controls.append(
                    ft.Row(rtl=True, alignment=ft.MainAxisAlignment.CENTER, spacing=ROW_SPACING, controls=row_buttons)
                )
                row_buttons = []

        if row_buttons:
            while len(row_buttons) < 7:
                row_buttons.append(ft.Container(width=CELL_W, height=CELL_H))
            days_grid_col.controls.append(
                ft.Row(rtl=True, alignment=ft.MainAxisAlignment.CENTER, spacing=ROW_SPACING, controls=row_buttons)
            )

        refresh_ui(cal_header_text, days_grid_col, cal_dlg)

    def change_cal_month(delta: int):
        m = cal_state["jm"] + delta
        y = cal_state["jy"]
        if m > 12:
            m = 1
            y += 1
        elif m < 1:
            m = 12
            y -= 1
        cal_state["jy"], cal_state["jm"] = y, m
        render_calendar_grid()

    def go_to_today(e):
        nonlocal selected_date
        now_t = datetime.now()
        selected_date = datetime(now_t.year, now_t.month, now_t.day)
        close_ctrl(cal_dlg)
        update_dashboard_controls()
        load_dashboard_data()

    cal_next_btn = ft.Container(
        content=ft.Icon(ft.icons.CHEVRON_RIGHT_ROUNDED, color=MOCHA_PRIMARY, size=20),
        bgcolor=CHIP_LATTE, width=34, height=34, border_radius=8, alignment=ft.alignment.center,
        tooltip="ماه بعد",
        on_click=lambda e: change_cal_month(1)
    )
    cal_prev_btn = ft.Container(
        content=ft.Icon(ft.icons.CHEVRON_LEFT_ROUNDED, color=MOCHA_PRIMARY, size=20),
        bgcolor=CHIP_LATTE, width=34, height=34, border_radius=8, alignment=ft.alignment.center,
        tooltip="ماه قبل",
        on_click=lambda e: change_cal_month(-1)
    )
    cal_today_btn = ft.ElevatedButton(
        "برو به امروز", icon=ft.icons.TODAY_ROUNDED,
        bgcolor=CHIP_LATTE, color=ESPRESSO_DARK, elevation=0, on_click=go_to_today
    )

    cal_card_box = ft.Container(
        width=325,
        bgcolor=CARD_IVORY,
        border_radius=20,
        padding=ft.padding.symmetric(horizontal=18, vertical=16),
        shadow=ft.BoxShadow(
            blur_radius=24,
            color=ft.colors.with_opacity(0.28, "#000000"),
            offset=ft.Offset(0, 8),
        ),
        on_click=lambda e: None,
        rtl=True,
        content=ft.Column(
            rtl=True,
            tight=True,
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    rtl=True,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        cal_next_btn,
                        cal_header_text,
                        cal_prev_btn,
                    ]
                ),
                ft.Container(
                    width=276,
                    height=285,
                    alignment=ft.alignment.center,
                    content=days_grid_col
                ),
                ft.Row(
                    rtl=True,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.TextButton(
                            "بستن",
                            style=ft.ButtonStyle(color=ESPRESSO_DARK),
                            on_click=lambda e: close_dialog(cal_dlg)
                        ),
                        cal_today_btn
                    ]
                )
            ]
        )
    )
    cal_dlg = make_centered_modal(cal_card_box)

    def open_jalali_calendar_dialog(e):
        cur_jy, cur_jm, cur_jd = gregorian_to_jalali(selected_date.year, selected_date.month, selected_date.day)
        cal_state["jy"], cal_state["jm"], cal_state["jd"] = cur_jy, cur_jm, cur_jd
        render_calendar_grid()
        open_ctrl(cal_dlg)

    def switch_filter_mode(new_mode: str):
        nonlocal filter_mode
        filter_mode = new_mode
        update_dashboard_controls()
        load_dashboard_data()

    def switch_dashboard_section_filter(sec_key: str):
        nonlocal dashboard_section_filter
        dashboard_section_filter = sec_key
        update_dashboard_controls()
        load_dashboard_data()

    def step_day(delta: int):
        nonlocal selected_date
        selected_date = selected_date + timedelta(days=delta)
        update_dashboard_controls()
        load_dashboard_data()

    def step_month(delta: int):
        nonlocal selected_j_year, selected_j_month
        m = selected_j_month + delta
        y = selected_j_year
        if m > 12:
            m = 1
            y += 1
        elif m < 1:
            m = 12
            y -= 1
        selected_j_year, selected_j_month = y, m
        update_dashboard_controls()
        load_dashboard_data()

    def update_dashboard_controls():
        dashboard_sec_filter_box.visible = (app_mode == "both")
        if app_mode == "both":
            sec_opts = [
                ("all", "کل مجموعه", ft.icons.STOREFRONT_ROUNDED, BOTH_BLEND_MAIN),
                ("cafe", "بخش کافه", ft.icons.COFFEE_ROUNDED, "#9C623E"),
                ("restaurant", "بخش رستوران", ft.icons.RESTAURANT_ROUNDED, "#B54826"),
            ]
            dashboard_sec_filter_row.controls.clear()
            for s_key, s_label, s_icon, s_col in sec_opts:
                is_s_act = (dashboard_section_filter == s_key)
                dashboard_sec_filter_row.controls.append(
                    ft.Container(
                        expand=1,
                        bgcolor=s_col if is_s_act else CARD_IVORY,
                        border=ft.border.all(1, s_col if is_s_act else BORDER_SAND),
                        border_radius=10,
                        padding=ft.padding.symmetric(horizontal=6, vertical=6),
                        alignment=ft.alignment.center,
                        on_click=lambda e, k=s_key: switch_dashboard_section_filter(k),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=4,
                            controls=[
                                ft.Icon(s_icon, size=14, color=CARD_IVORY if is_s_act else s_col),
                                ft.Text(s_label, size=10, font_family="Vazir-Bold", color=CARD_IVORY if is_s_act else ESPRESSO_DARK),
                            ]
                        )
                    )
                )

        modes = [
            ("day", "گزارش روزانه", ft.icons.TODAY_ROUNDED),
            ("month", "گزارش ماهانه", ft.icons.CALENDAR_MONTH_ROUNDED),
            ("all", "کل تاریخچه", ft.icons.ALL_INCLUSIVE_ROUNDED),
        ]
        mode_selector_row.controls.clear()
        for m_key, m_label, m_icon in modes:
            is_active = (filter_mode == m_key)
            mode_selector_row.controls.append(
                ft.Container(
                    expand=1,
                    bgcolor=MOCHA_PRIMARY if is_active else CARD_IVORY,
                    border=ft.border.all(1, MOCHA_PRIMARY if is_active else BORDER_SAND),
                    border_radius=12,
                    padding=ft.padding.symmetric(horizontal=8, vertical=8),
                    alignment=ft.alignment.center,
                    on_click=lambda e, k=m_key: switch_filter_mode(k),
                    shadow=ft.BoxShadow(blur_radius=8, color=ft.colors.with_opacity(0.2 if is_active else 0.03, MOCHA_PRIMARY), offset=ft.Offset(0, 2)),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=5,
                        controls=[
                            ft.Icon(m_icon, size=15, color=CARD_IVORY if is_active else TEXT_MUTED),
                            ft.Text(m_label, size=11, font_family="Vazir-Bold", color=CARD_IVORY if is_active else ESPRESSO_DARK),
                        ]
                    )
                )
            )

        if filter_mode == "day":
            jy, jm, jd = gregorian_to_jalali(selected_date.year, selected_date.month, selected_date.day)
            is_today_selected = (jy == today_jy and jm == today_jm and jd == today_jd)
            day_label = f"امروز، {jd} {JALALI_MONTHS[jm - 1]} {jy}" if is_today_selected else f"{jd} {JALALI_MONTHS[jm - 1]} {jy}"

            date_navigator_container.content = ft.Container(
                bgcolor=CARD_IVORY,
                border_radius=14,
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                border=ft.border.all(1, BORDER_SAND),
                content=ft.Row(
                    rtl=True,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Container(
                            content=ft.Icon(ft.icons.CHEVRON_RIGHT_ROUNDED, color=MOCHA_PRIMARY, size=20),
                            bgcolor=SURFACE_LATTE, width=32, height=32, border_radius=8, alignment=ft.alignment.center,
                            tooltip="روز بعد",
                            on_click=lambda e: step_day(1)
                        ),
                        ft.Container(
                            on_click=open_jalali_calendar_dialog,
                            border_radius=8,
                            padding=ft.padding.symmetric(horizontal=10, vertical=4),
                            content=ft.Row(
                                rtl=True,
                                spacing=6,
                                controls=[
                                    ft.Icon(ft.icons.EDIT_CALENDAR_ROUNDED, color=MOCHA_PRIMARY, size=17),
                                    ft.Text(day_label, size=12, font_family="Vazir-Bold", color=ESPRESSO_DARK),
                                    ft.Text("(تقویم)", size=10, color=CARAMEL_ACCENT, font_family="Vazir-Bold"),
                                ]
                            )
                        ),
                        ft.Container(
                            content=ft.Icon(ft.icons.CHEVRON_LEFT_ROUNDED, color=MOCHA_PRIMARY, size=20),
                            bgcolor=SURFACE_LATTE, width=32, height=32, border_radius=8, alignment=ft.alignment.center,
                            tooltip="روز قبل",
                            on_click=lambda e: step_day(-1)
                        ),
                    ]
                )
            )
        elif filter_mode == "month":
            month_title = f"آمار ماه {JALALI_MONTHS[selected_j_month - 1]} {selected_j_year}"
            date_navigator_container.content = ft.Container(
                bgcolor=CARD_IVORY,
                border_radius=14,
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                border=ft.border.all(1, BORDER_SAND),
                content=ft.Row(
                    rtl=True,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Container(
                            content=ft.Icon(ft.icons.CHEVRON_RIGHT_ROUNDED, color=MOCHA_PRIMARY, size=20),
                            bgcolor=SURFACE_LATTE, width=32, height=32, border_radius=8, alignment=ft.alignment.center,
                            tooltip="ماه بعد",
                            on_click=lambda e: step_month(1)
                        ),
                        ft.Row(
                            rtl=True,
                            spacing=6,
                            controls=[
                                ft.Icon(ft.icons.DATE_RANGE_ROUNDED, color=MOCHA_PRIMARY, size=18),
                                ft.Text(month_title, size=13, font_family="Vazir-Bold", color=ESPRESSO_DARK),
                            ]
                        ),
                        ft.Container(
                            content=ft.Icon(ft.icons.CHEVRON_LEFT_ROUNDED, color=MOCHA_PRIMARY, size=20),
                            bgcolor=SURFACE_LATTE, width=32, height=32, border_radius=8, alignment=ft.alignment.center,
                            tooltip="ماه قبل",
                            on_click=lambda e: step_month(-1)
                        ),
                    ]
                )
            )
        else:
            date_navigator_container.content = ft.Container(
                bgcolor=SURFACE_LATTE,
                border=ft.border.all(1, BORDER_SAND),
                border_radius=10,
                padding=8,
                alignment=ft.alignment.center,
                content=ft.Text("نمایش تجمیعی تمام تراکنش‌های ثبت‌شده از ابتدا", size=11, font_family="Vazir-Bold", color=MOCHA_PRIMARY)
            )
        page.update()

    def load_dashboard_data():
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        conditions = []
        params = []

        if filter_mode == "day":
            day_prefix = selected_date.strftime("%Y-%m-%d")
            conditions.append("substr(order_date, 1, 10) = ?")
            params.append(day_prefix)
        elif filter_mode == "month":
            max_d = get_jalali_month_days(selected_j_year, selected_j_month)
            g_start = jalali_to_gregorian(selected_j_year, selected_j_month, 1)
            g_end = jalali_to_gregorian(selected_j_year, selected_j_month, max_d)
            start_str = f"{g_start[0]:04d}-{g_start[1]:02d}-{g_start[2]:02d}"
            end_str = f"{g_end[0]:04d}-{g_end[1]:02d}-{g_end[2]:02d}"
            conditions.append("substr(order_date, 1, 10) >= ? AND substr(order_date, 1, 10) <= ?")
            params.extend([start_str, end_str])

        eff_sec = active_section if app_mode in ("cafe", "restaurant") else dashboard_section_filter
        if eff_sec in ("cafe", "restaurant"):
            conditions.append("section = ?")
            params.append(eff_sec)

        where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        cursor.execute(f"""
            SELECT COALESCE(SUM(sell_price), 0), COALESCE(SUM(profit), 0), COUNT(*)
            FROM orders
            {where_sql}
        """, tuple(params))
        total_rev, total_prof, total_count = cursor.fetchone()
        total_cost = total_rev - total_prof
        margin_pct = int((total_prof / total_rev) * 100) if total_rev > 0 else 0

        total_revenue_text.value = f"{format_price(total_rev)} ت"
        total_cost_text.value = f"{format_price(total_cost)} ت"
        net_profit_text.value = f"{format_price(total_prof)} تومان"
        net_profit_words_text.value = f"{num_to_persian(int(max(0, total_prof)))} تومان"
        profit_margin_badge_text.value = f"حاشیه سود: {margin_pct}٪"
        period_summary_badge.value = f"{total_count} فروش ثبت‌شده"

        cursor.execute(f"""
            SELECT product_name, COUNT(*) as qty, SUM(sell_price) as total_sale, SUM(profit) as total_profit
            FROM orders
            {where_sql}
            GROUP BY product_name
            ORDER BY qty DESC
        """, tuple(params))
        rows = cursor.fetchall()
        conn.close()

        report_items_col.controls.clear()
        if not rows:
            report_items_col.controls.append(
                ft.Container(
                    bgcolor=CARD_IVORY,
                    border_radius=16,
                    border=ft.border.all(1, BORDER_SAND),
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                        controls=[
                            ft.Icon(ft.icons.INSERT_CHART_OUTLINED_ROUNDED, size=38, color=CARAMEL_ACCENT),
                            ft.Text("در این بازه زمانی هیچ سفارشی ثبت نشده است.", color=TEXT_MUTED, size=12, font_family="Vazir-Bold"),
                        ]
                    ),
                    alignment=ft.alignment.center,
                    padding=30
                )
            )
        else:
            for rank_idx, r in enumerate(rows, start=1):
                p_name, p_qty, p_sale, p_prof = r
                share_pct = int((p_sale / total_rev) * 100) if total_rev > 0 else 0

                card = ft.Container(
                    bgcolor=CARD_IVORY,
                    border_radius=14,
                    padding=12,
                    border=ft.border.all(1, BORDER_SAND),
                    shadow=ft.BoxShadow(blur_radius=6, color=ft.colors.with_opacity(0.04, MOCHA_PRIMARY), offset=ft.Offset(0, 2)),
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row(
                                        spacing=10,
                                        controls=[
                                            ft.Container(
                                                content=ft.Text(f"{p_qty}×", color="#FFFDF9", font_family="Vazir-Bold", size=12),
                                                gradient=ft.LinearGradient(colors=[MOCHA_PRIMARY, CARAMEL_ACCENT]),
                                                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                                                border_radius=10
                                            ),
                                            ft.Column(
                                                spacing=2,
                                                controls=[
                                                    ft.Text(f"{rank_idx}. {p_name}", font_family="Vazir-Bold", size=13, color=ESPRESSO_DARK),
                                                    ft.Text(f"فروش کل: {format_price(p_sale)} تومان ({share_pct}٪ از کل فروش)", size=10, color=TEXT_MUTED)
                                                ]
                                            )
                                        ]
                                    ),
                                    ft.Container(
                                        bgcolor=PROFIT_SURFACE,
                                        border=ft.border.all(1, PROFIT_BORDER),
                                        padding=ft.padding.symmetric(horizontal=9, vertical=4),
                                        border_radius=10,
                                        content=ft.Column(
                                            horizontal_alignment=ft.CrossAxisAlignment.END,
                                            spacing=1,
                                            controls=[
                                                ft.Text("سود خالص", size=9, color=PROFIT_DARK),
                                                ft.Text(f"+{format_price(p_prof)} ت", size=11, font_family="Vazir-Bold", color=PROFIT_DARK)
                                            ]
                                        )
                                    )
                                ]
                            ),
                            ft.Container(
                                height=5,
                                bgcolor=SURFACE_LATTE,
                                border_radius=5,
                                content=ft.Row(
                                    spacing=0,
                                    controls=[
                                        ft.Container(expand=max(1, share_pct), bgcolor=CARAMEL_ACCENT, border_radius=5),
                                        ft.Container(expand=max(0, 100 - share_pct)),
                                    ]
                                )
                            )
                        ]
                    )
                )
                report_items_col.controls.append(card)
        page.update()

    hero_profit_card = ft.Container(
        border_radius=18,
        padding=14,
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_right,
            end=ft.alignment.bottom_left,
            colors=["#059669", "#10B981", "#34D399"]
        ),
        shadow=ft.BoxShadow(blur_radius=14, color=ft.colors.with_opacity(0.22, "#059669"), offset=ft.Offset(0, 4)),
        content=ft.Column(
            spacing=8,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=6,
                            controls=[
                                ft.Container(
                                    content=ft.Icon(ft.icons.TRENDING_UP_ROUNDED, color="#FFFDF9", size=18),
                                    bgcolor=ft.colors.with_opacity(0.22, "#FFFFFF"),
                                    padding=6,
                                    border_radius=8,
                                ),
                                ft.Text("سود خالص دوره انتخابی", size=12, font_family="Vazir-Bold", color="#FFFDF9"),
                            ]
                        ),
                        ft.Container(
                            bgcolor="#ECFDF5",
                            padding=ft.padding.symmetric(horizontal=8, vertical=3),
                            border_radius=20,
                            content=profit_margin_badge_text,
                        )
                    ]
                ),
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.END,
                    controls=[
                        ft.Column(
                            spacing=2,
                            controls=[
                                net_profit_text,
                                net_profit_words_text,
                            ]
                        ),
                        ft.Container(
                            bgcolor=ft.colors.with_opacity(0.2, ft.colors.WHITE),
                            padding=ft.padding.symmetric(horizontal=10, vertical=5),
                            border_radius=10,
                            content=period_summary_badge,
                        )
                    ]
                )
            ]
        )
    )

    revenue_icon = ft.Icon(ft.icons.ACCOUNT_BALANCE_WALLET_ROUNDED, color=MOCHA_PRIMARY, size=20)
    revenue_icon_box = ft.Container(
        content=revenue_icon,
        bgcolor=SURFACE_LATTE,
        padding=8,
        border_radius=10
    )
    revenue_card = ft.Container(
        expand=1,
        bgcolor=CARD_IVORY,
        border_radius=14,
        padding=11,
        border=ft.border.all(1, BORDER_WARM),
        content=ft.Row(
            spacing=10,
            controls=[
                revenue_icon_box,
                ft.Column(
                    spacing=1,
                    controls=[
                        ft.Text("درآمد کل", size=10, color=TEXT_MUTED, font_family="Vazir-Bold"),
                        total_revenue_text,
                    ]
                )
            ]
        )
    )

    dashboard_view = ft.Container(
        padding=16,
        expand=True,
        content=ft.Column(
            spacing=9,
            expand=True,
            controls=[
                dashboard_sec_filter_box,
                mode_selector_row,
                date_navigator_container,
                hero_profit_card,
                ft.Row(
                    spacing=8,
                    controls=[
                        revenue_card,
                        ft.Container(
                            expand=1,
                            bgcolor=CARD_IVORY,
                            border_radius=14,
                            padding=11,
                            border=ft.border.all(1, COST_RED_BORDER),
                            content=ft.Row(
                                spacing=10,
                                controls=[
                                    ft.Container(
                                        content=ft.Icon(ft.icons.INVENTORY_2_ROUNDED, color=COST_RED_MAIN, size=20),
                                        bgcolor=COST_RED_BG,
                                        border=ft.border.all(1, COST_RED_BORDER),
                                        padding=8,
                                        border_radius=10
                                    ),
                                    ft.Column(
                                        spacing=1,
                                        controls=[
                                            ft.Text("هزینه پایه", size=10, color=COST_RED_DARK, font_family="Vazir-Bold"),
                                            total_cost_text,
                                        ]
                                    )
                                ]
                            )
                        ),
                    ]
                ),
                ft.Text("رتبه‌بندی پرفروش‌ترین محصولات:", size=12, font_family="Vazir-Bold", color=ESPRESSO_DARK),
                report_items_col
            ]
        )
    )

    body_container = ft.Container(content=cashier_view, expand=True)

    current_nav_index = [1]
    nav_items_row = ft.Row(spacing=8, expand=True)

    def switch_nav_tab(idx: int):
        if current_nav_index[0] == idx:
            return
        current_nav_index[0] = idx
        close_custom_dropdown()
        render_nav_bar()
        if idx == 0:
            render_section_switchers()
            refresh_category_dropdown()
            load_menu_products()
            body_container.content = menu_view
        elif idx == 1:
            render_section_switchers()
            render_cashier_category_chips()
            load_cashier_products()
            body_container.content = cashier_view
        elif idx == 2:
            update_dashboard_controls()
            load_dashboard_data()
            body_container.content = dashboard_view
        page.update()

    def render_nav_bar():
        tabs_data = [
            (0, "مدیریت منو", ft.icons.MENU_BOOK_OUTLINED, ft.icons.MENU_BOOK_ROUNDED),
            (1, "صندوق فروش", ft.icons.STOREFRONT_OUTLINED, ft.icons.STOREFRONT_ROUNDED),
            (2, "داشبورد مالی", ft.icons.ANALYTICS_OUTLINED, ft.icons.ANALYTICS_ROUNDED),
        ]
        nav_items_row.controls.clear()
        for t_idx, t_label, t_icon_out, t_icon_sel in tabs_data:
            is_sel = (current_nav_index[0] == t_idx)
            nav_items_row.controls.append(
                ft.Container(
                    expand=1,
                    height=54,
                    bgcolor=CHIP_LATTE if is_sel else ft.colors.with_opacity(0, CARD_IVORY),
                    border=ft.border.all(1, BORDER_WARM) if is_sel else None,
                    border_radius=14,
                    alignment=ft.alignment.center,
                    on_click=lambda e, i=t_idx: switch_nav_tab(i),
                    content=ft.Column(
                        spacing=2,
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(
                                t_icon_sel if is_sel else t_icon_out,
                                size=22,
                                color=MOCHA_PRIMARY if is_sel else TEXT_MUTED,
                            ),
                            ft.Text(
                                t_label,
                                size=11,
                                font_family="Vazir-Bold" if is_sel else "Vazir",
                                color=ESPRESSO_DARK if is_sel else TEXT_MUTED,
                            ),
                        ]
                    )
                )
            )

    nav_bar = ft.Container(
        height=68,
        bgcolor=CARD_IVORY,
        padding=ft.padding.symmetric(horizontal=10, vertical=7),
        shadow=ft.BoxShadow(
            blur_radius=12,
            color=ft.colors.with_opacity(0.08, ESPRESSO_DARK),
            offset=ft.Offset(0, -3)
        ),
        content=nav_items_row,
    )

    def apply_active_theme():
        nonlocal BG_CREAM, CARD_IVORY, SURFACE_LATTE, CHIP_LATTE, BORDER_SAND, BORDER_WARM
        nonlocal ESPRESSO_DARK, MOCHA_PRIMARY, CARAMEL_ACCENT, TEXT_MUTED, DISABLED_BG, DISABLED_TEXT

        th = THEMES[active_section]
        BG_CREAM = th["BG_CREAM"]
        CARD_IVORY = th["CARD_IVORY"]
        SURFACE_LATTE = th["SURFACE_LATTE"]
        CHIP_LATTE = th["CHIP_LATTE"]
        BORDER_SAND = th["BORDER_SAND"]
        BORDER_WARM = th["BORDER_WARM"]
        ESPRESSO_DARK = th["ESPRESSO_DARK"]
        MOCHA_PRIMARY = th["MOCHA_PRIMARY"]
        CARAMEL_ACCENT = th["CARAMEL_ACCENT"]
        TEXT_MUTED = th["TEXT_MUTED"]
        DISABLED_BG = th["DISABLED_BG"]
        DISABLED_TEXT = th["DISABLED_TEXT"]

        page.bgcolor = BG_CREAM
        top_app_header.gradient = ft.LinearGradient(
            begin=ft.alignment.top_right,
            end=ft.alignment.bottom_left,
            colors=th["HEADER_GRAD"]
        )
        top_app_header.shadow = ft.BoxShadow(
            blur_radius=14,
            color=ft.colors.with_opacity(0.18, th["HEADER_SHADOW"]),
            offset=ft.Offset(0, 4)
        )

        if app_mode == "cafe":
            target_hdr_icon = ft.icons.COFFEE_ROUNDED
            header_sub_title.value = "حسابداری کافه"
            header_logo_box.bgcolor = ft.colors.with_opacity(0.2, "#FFFDF9")
            header_logo_box.border = ft.border.all(1, ft.colors.with_opacity(0.35, "#FFFDF9"))
            header_logo_box.content = ft.Icon(target_hdr_icon, color="#FFFDF9", size=22)
        elif app_mode == "restaurant":
            target_hdr_icon = ft.icons.RESTAURANT_ROUNDED
            header_sub_title.value = "حسابداری رستوران"
            header_logo_box.bgcolor = ft.colors.with_opacity(0.2, "#FFFDF9")
            header_logo_box.border = ft.border.all(1, ft.colors.with_opacity(0.35, "#FFFDF9"))
            header_logo_box.content = ft.Icon(target_hdr_icon, color="#FFFDF9", size=22)
        else:
            target_hdr_icon = ft.icons.STOREFRONT_ROUNDED
            header_sub_title.value = "حسابداری کافه رستوران"
            header_logo_box.bgcolor = BOTH_BLEND_BG
            header_logo_box.border = ft.border.all(1, BOTH_BLEND_BORDER)
            header_logo_box.content = ft.Icon(target_hdr_icon, color=BOTH_BLEND_MAIN, size=22)

        render_nav_bar()

        search_input.border_color = BORDER_WARM
        search_input.focused_border_color = MOCHA_PRIMARY

        show_add_form_btn.bgcolor = MOCHA_PRIMARY
        menu_header_icon.color = MOCHA_PRIMARY
        menu_header_icon_box.bgcolor = CHIP_LATTE
        menu_count_badge.color = MOCHA_PRIMARY
        menu_count_badge_box.bgcolor = CHIP_LATTE
        add_form_container.border = ft.border.all(1.5, BORDER_WARM)

        for inp in (name_input, cost_input, sell_input, new_cat_input, backup_code_field):
            inp.border_color = BORDER_WARM
            inp.focused_border_color = MOCHA_PRIMARY
            inp.bgcolor = SURFACE_LATTE

        custom_dropdown_box.border = ft.border.all(1, BORDER_WARM)
        custom_dropdown_box.bgcolor = SURFACE_LATTE
        dropdown_arrow_icon.color = MOCHA_PRIMARY
        custom_dropdown_list_container.border = ft.border.all(1, BORDER_WARM)

        sell_words_text.color = MOCHA_PRIMARY
        sell_words_icon.color = MOCHA_PRIMARY
        sell_words_box.bgcolor = BG_CREAM
        sell_words_box.border = ft.border.all(1, BORDER_SAND)

        cat_dlg_icon.color = MOCHA_PRIMARY
        cat_dlg_icon_box.bgcolor = CHIP_LATTE
        cat_dlg_add_btn.bgcolor = MOCHA_PRIMARY

        bkp_header_icon.color = MOCHA_PRIMARY
        bkp_header_icon_box.bgcolor = CHIP_LATTE
        bkp_new_btn.bgcolor = MOCHA_PRIMARY
        bkp_text_label.color = MOCHA_PRIMARY
        bkp_restore_code_btn.bgcolor = MOCHA_PRIMARY
        copy_btn.bgcolor = CHIP_LATTE
        copy_btn.color = ESPRESSO_DARK

        cal_next_btn.bgcolor = CHIP_LATTE
        cal_prev_btn.bgcolor = CHIP_LATTE
        cal_today_btn.bgcolor = CHIP_LATTE
        cal_today_btn.color = ESPRESSO_DARK

        total_revenue_text.color = MOCHA_PRIMARY
        revenue_icon.color = MOCHA_PRIMARY
        revenue_icon_box.bgcolor = SURFACE_LATTE
        revenue_card.border = ft.border.all(1, BORDER_WARM)

        update_live_profit_preview()

    # ثبت تمام لایه‌های مودال برای قفل خودکار دکمه‌های زیرین
    all_modals.extend([bkp_dlg, mode_dlg, recent_orders_dlg, cat_dialog, cal_dlg, confirm_dlg])

    main_app_col.controls.extend([
        top_app_header,
        body_container,
        nav_bar,
    ])

    apply_active_theme()
    render_section_switchers()
    refresh_category_dropdown()
    refresh_header_today_sales()
    render_cashier_category_chips()
    load_cashier_products()
    update_dashboard_controls()

    page.add(
        ft.Stack(
            expand=True,
            controls=[
                main_app_col,
                bkp_dlg,
                mode_dlg,
                recent_orders_dlg,
                cat_dialog,
                cal_dlg,
                confirm_dlg,
                floating_toast_card,
            ]
        )
    )

if __name__ == "__main__":
    ft.app(target=main, assets_dir=os.path.dirname(os.path.abspath(__file__)))
