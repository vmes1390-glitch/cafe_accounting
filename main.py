import flet as ft
import re
import sqlite3
import os
import shutil
from datetime import datetime, timedelta

# --- سازگارکننده خودکار کدهای فلت 0.24 با فلت نسخه جدید (1.0+) ---
if not hasattr(ft, "app") and hasattr(ft, "run"):
    ft.app = lambda target=None, *a, **kw: ft.run(target or a[0])

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
            return "#4F46E5"
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
            if hasattr(ft, "BorderSide"):
                side = ft.BorderSide(width, color)
                return ft.Border(top=side, bottom=side, left=side, right=side)
        return None

ft.border = _CompatBorder()

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

for _ctrl_name in (
    "Button", "ElevatedButton", "FilledButton", "OutlinedButton", "TextButton",
    "IconButton", "TextField", "Dropdown", "Container",
    "AlertDialog", "SnackBar", "NavigationBar", "NavigationBarDestination",
    "ButtonStyle", "TextStyle", "BoxShadow", "Theme",
):
    _cls = getattr(ft, _ctrl_name, None)
    if _cls is not None and not getattr(_cls, "_compat_patched", False):
        if not hasattr(_cls, "text"):
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
                    while True:
                        try:
                            return orig(self, *a, **kw)
                        except TypeError as ex:
                            m = re.search(r"unexpected keyword argument '(\w+)'", str(ex))
                            if m:
                                bad_key = m.group(1)
                                if bad_key == "text" and "content" not in kw and not a:
                                    kw["content"] = kw.pop("text")
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

DB_NAME = "cafe_accounting.db"

CATEGORIES_LIST = [
    "قهوه",
    "نوشیدنی گرم بر پایۀ قهوه",
    "نوشیدنی سرد بر پایۀ قهوه",
    "شیک",
    "بستنی بار",
    "نوشیدنی گرم",
    "چای",
]

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
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            cost_price REAL NOT NULL,
            sell_price REAL NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            sell_price REAL NOT NULL,
            profit REAL NOT NULL,
            order_date TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def format_price(val):
    try:
        return f"{int(float(val)):,}"
    except (ValueError, TypeError):
        return "0"

def perform_db_backup():
    db_file = DB_NAME
    backup_dir = "backups"
    if not os.path.exists(db_file):
        return False, "فایل پایگاه داده یافت نشد!"
    
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"cafe_backup_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    try:
        source_conn = sqlite3.connect(db_file)
        dest_conn = sqlite3.connect(backup_path)
        with dest_conn:
            source_conn.backup(dest_conn)
        dest_conn.close()
        source_conn.close()
        return True, backup_filename
    except Exception as e:
        return False, str(e)


def main(page: ft.Page):
    init_db()

    page.title = "حسابداری و صندوق کافه"
    page.rtl = True
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = "#F1F5F9"
    page.window.width = 435
    page.window.height = 820
    page.window.resizable = False
    page.padding = 0

    page.fonts = {
        "Vazir": "https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/fonts/ttf/Vazirmatn-Regular.ttf",
        "Vazir-Bold": "https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/fonts/ttf/Vazirmatn-Bold.ttf"
    }
    page.theme = ft.Theme(font_family="Vazir")

    editing_product_id = None
    selected_cashier_category = "همه"
    cashier_search_query = ""

    now_dt = datetime.now()
    init_jy, init_jm, init_jd = gregorian_to_jalali(now_dt.year, now_dt.month, now_dt.day)

    filter_mode = "day"
    selected_date = datetime(now_dt.year, now_dt.month, now_dt.day)
    selected_j_year = init_jy
    selected_j_month = init_jm

    def show_snackbar(message: str, bg_color="#0F172A"):
        snack = ft.SnackBar(
            content=ft.Row(
                spacing=10,
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.icons.NOTIFICATIONS_ACTIVE_ROUNDED, color="#FBBF24", size=18),
                        bgcolor=ft.colors.with_opacity(0.15, ft.colors.WHITE),
                        padding=6,
                        border_radius=8,
                    ),
                    ft.Text(message, color=ft.colors.WHITE, font_family="Vazir-Bold", size=12, expand=True),
                ]
            ),
            bgcolor=bg_color,
            behavior=ft.SnackBarBehavior.FLOATING,
            shape=ft.RoundedRectangleBorder(radius=14),
            margin=14,
            duration=2000,
        )
        page.overlay.append(snack)
        snack.open = True
        page.update()

    def show_confirm_dialog(title_text: str, message_text: str, on_confirm_callback):
        def handle_yes(e):
            confirm_dlg.open = False
            page.update()
            on_confirm_callback()

        def handle_no(e):
            confirm_dlg.open = False
            page.update()

        confirm_dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=22),
            bgcolor=ft.colors.WHITE,
            surface_tint_color=ft.colors.WHITE,
            title=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.icons.DELETE_SWEEP_ROUNDED, color="#DC2626", size=32),
                        bgcolor="#FEF2F2",
                        padding=16,
                        border_radius=50,
                        border=ft.border.all(1, "#FECACA"),
                    ),
                    ft.Text(title_text, size=15, font_family="Vazir-Bold", color="#0F172A", text_align=ft.TextAlign.CENTER),
                ]
            ),
            content=ft.Text(
                message_text,
                size=12,
                color="#475569",
                text_align=ft.TextAlign.CENTER,
            ),
            actions=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10,
                    controls=[
                        ft.ElevatedButton(
                            "انصراف",
                            bgcolor="#F1F5F9",
                            color="#334155",
                            elevation=0,
                            height=40,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
                            on_click=handle_no
                        ),
                        ft.ElevatedButton(
                            "بله، حذف شود",
                            icon=ft.icons.CHECK_ROUNDED,
                            bgcolor="#DC2626",
                            color=ft.colors.WHITE,
                            elevation=2,
                            height=40,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
                            on_click=handle_yes
                        ),
                    ]
                )
            ],
        )
        page.overlay.append(confirm_dlg)
        confirm_dlg.open = True
        page.update()

    def close_dialog(dlg):
        dlg.open = False
        page.update()

    def handle_backup_click(e):
        success, res = perform_db_backup()
        if success:
            show_snackbar(f"بکاپ با موفقیت در پوشه backups ذخیره شد:\n{res}", "#059669")
        else:
            show_snackbar(f"خطا در ایجاد بکاپ: {res}", "#DC2626")


    # --- هدر لوکس بالای برنامه ---
    today_jy, today_jm, today_jd = gregorian_to_jalali(now_dt.year, now_dt.month, now_dt.day)
    today_badge_str = f"{today_jd} {JALALI_MONTHS[today_jm - 1]} {today_jy}"
    header_today_sales_text = ft.Text("0 تومان", size=9, font_family="Vazir-Bold", color=ft.colors.GREEN_400)

    def refresh_header_today_sales():
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        today_prefix = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("SELECT COALESCE(SUM(sell_price), 0) FROM orders WHERE substr(order_date, 1, 10) = ?", (today_prefix,))
        val = cursor.fetchone()[0]
        conn.close()
        header_today_sales_text.value = f"{format_price(val)} تومان"
        
    backup_btn = ft.Container(
        content=ft.Row(
            spacing=4,
            controls=[
                ft.Icon(ft.icons.BACKUP_ROUNDED, color=ft.colors.WHITE, size=15),
                ft.Text("بکاپ", size=10, color=ft.colors.WHITE, font_family="Vazir-Bold"),
            ]
        ),
        bgcolor=ft.colors.with_opacity(0.18, ft.colors.WHITE),
        padding=ft.padding.symmetric(horizontal=8, vertical=4),
        border_radius=12,
        on_click=handle_backup_click,
        tooltip="ایجاد نسخه پشتیبان از دیتابیس",
    )

    top_app_header = ft.Container(
        padding=ft.padding.only(top=44, bottom=14, left=16, right=16),
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_right,
            end=ft.alignment.bottom_left,
            colors=["#090D16", "#1E1B4B", "#312E81"]
        ),
        shadow=ft.BoxShadow(blur_radius=16, color=ft.colors.with_opacity(0.22, ft.colors.BLACK), offset=ft.Offset(0, 4)),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(
                    spacing=10,
                    controls=[
                        ft.Container(
                            content=ft.Icon(ft.icons.LOCAL_CAFE_ROUNDED, color="#FBBF24", size=24),
                            bgcolor=ft.colors.with_opacity(0.12, ft.colors.WHITE),
                            padding=10,
                            border_radius=14,
                            border=ft.border.all(1, ft.colors.with_opacity(0.2, ft.colors.WHITE)),
                        ),
                        ft.Column(
                            spacing=2,
                            controls=[
                                ft.Text("کافه حساب", size=15, font_family="Vazir-Bold", color=ft.colors.WHITE),
                                ft.Text("صندوق فروش و حسابداری هوشمند", size=10, color="#A5B4FC"),
                            ]
                        )
                    ]
                ),
                ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.END,
                    spacing=4,
                    controls=[
                        ft.Container(
                            bgcolor=ft.colors.with_opacity(0.15, ft.colors.WHITE),
                            padding=ft.padding.symmetric(horizontal=10, vertical=5),
                            border_radius=20,
                            content=ft.Row(
                                spacing=5,
                                controls=[
                                    ft.Icon(ft.icons.CALENDAR_TODAY_ROUNDED, color=ft.colors.AMBER_300, size=13),
                                    ft.Text(today_badge_str, size=11, color=ft.colors.WHITE, font_family="Vazir-Bold"),
                                ]
                            )
                        ),
                        ft.Row(
                            spacing=4,
                            controls=[
                                ft.Text("فروش امروز:", size=9, color=ft.colors.INDIGO_100),
                                header_today_sales_text,
                            ]
                        )
                    ]
                )
            ]
        )
    )

    # =========================================================================
    # 1. تب صندوق فروش (POS)
    # =========================================================================
    cashier_categories_row = ft.Row(spacing=6, scroll=ft.ScrollMode.HIDDEN)
    cashier_products_col = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)

    def select_cashier_category(cat_name: str):
        nonlocal selected_cashier_category
        selected_cashier_category = cat_name
        render_cashier_category_chips()
        load_cashier_products()

    def render_cashier_category_chips():
        cashier_categories_row.controls.clear()
        all_cats = ["همه"] + CATEGORIES_LIST
        for c in all_cats:
            is_sel = (selected_cashier_category == c)
            cashier_categories_row.controls.append(
                ft.Container(
                    bgcolor="#4F46E5" if is_sel else ft.colors.WHITE,
                    border=ft.border.all(1, "#4F46E5" if is_sel else ft.colors.BLUE_GREY_200),
                    border_radius=20,
                    padding=ft.padding.symmetric(horizontal=12, vertical=6),
                    on_click=lambda e, cat=c: select_cashier_category(cat),
                    shadow=ft.BoxShadow(blur_radius=6, color=ft.colors.with_opacity(0.15 if is_sel else 0.03, "#4F46E5"), offset=ft.Offset(0, 2)),
                    content=ft.Text(
                        c,
                        size=11,
                        font_family="Vazir-Bold" if is_sel else "Vazir",
                        color=ft.colors.WHITE if is_sel else "#475569"
                    )
                )
            )
        page.update()

    def on_search_change(e):
        nonlocal cashier_search_query
        cashier_search_query = e.control.value.strip()
        load_cashier_products()

    search_input = ft.TextField(
        hint_text="جستجوی سریع نام محصول...",
        prefix_icon=ft.icons.SEARCH_ROUNDED,
        height=38,
        expand=True, # با این دستور، سرچ‌باکس تمام فضای خالی را به زیبایی پر می‌کند
        text_size=11,
        content_padding=ft.padding.symmetric(horizontal=10, vertical=0),
        border_radius=12,
        border_color=ft.colors.BLUE_GREY_200,
        bgcolor=ft.colors.WHITE,
        on_change=on_search_change
    )

    def get_category_style(cat: str):
        styles = {
            "قهوه": (ft.icons.COFFEE_ROUNDED, "#78350F", "#FEF3C7", "#FDE68A"),
            "نوشیدنی گرم بر پایۀ قهوه": (ft.icons.LOCAL_CAFE_ROUNDED, "#9A3412", "#FFEDD5", "#FED7AA"),
            "نوشیدنی سرد بر پایۀ قهوه": (ft.icons.AC_UNIT_ROUNDED, "#0369A1", "#E0F2FE", "#BAE6FD"),
            "شیک": (ft.icons.BLENDER_ROUNDED, "#6D28D9", "#EDE9FE", "#DDD6FE"),
            "بستنی بار": (ft.icons.ICE_CREAM_ROUNDED, "#BE185D", "#FCE7F3", "#FBCFE8"),
            "نوشیدنی گرم": (ft.icons.EMOJI_FOOD_BEVERAGE_ROUNDED, "#B91C1C", "#FEE2E2", "#FECACA"),
            "چای": (ft.icons.LOCAL_DRINK_ROUNDED, "#047857", "#D1FAE5", "#A7F3D0"),
        }
        return styles.get(cat, (ft.icons.LOCAL_CAFE_ROUNDED, "#4338CA", "#EEF2FF", "#C7D2FE"))

    def load_cashier_products():
        cashier_products_col.controls.clear()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, category, cost_price, sell_price FROM products ORDER BY id DESC")
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
            cashier_products_col.controls.append(
                ft.Container(
                    bgcolor=ft.colors.WHITE,
                    border_radius=16,
                    border=ft.border.all(1, "#E2E8F0"),
                    padding=30,
                    alignment=ft.alignment.center,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                        controls=[
                            ft.Container(
                                content=ft.Icon(ft.icons.COFFEE_MAKER_OUTLINED, size=36, color="#94A3B8"),
                                bgcolor="#F8FAFC",
                                padding=14,
                                border_radius=50,
                            ),
                            ft.Text(
                                "محصولی در این بخش یافت نشد!",
                                color="#475569", size=12, font_family="Vazir-Bold", text_align=ft.TextAlign.CENTER
                            ),
                            ft.Text(
                                "از تب «مدیریت منو» آیتم‌های جدید کافه را ثبت کنید.",
                                color="#94A3B8", size=10, text_align=ft.TextAlign.CENTER
                            ),
                        ]
                    )
                )
            )
        else:
            for row in filtered_rows:
                p_id, p_name, p_cat, p_cost, p_sell = row
                cat_icon, cat_color, cat_bg, cat_border = get_category_style(p_cat)

                qty_state = {"val": 1}
                qty_label = ft.Text("1", size=12, font_family="Vazir-Bold", color="#1E293B", text_align=ft.TextAlign.CENTER, width=22)

                def make_step_handlers(state_dict, lbl_ctrl):
                    def dec_click(e):
                        if state_dict["val"] > 1:
                            state_dict["val"] -= 1
                            lbl_ctrl.value = str(state_dict["val"])
                            page.update()

                    def inc_click(e):
                        state_dict["val"] += 1
                        lbl_ctrl.value = str(state_dict["val"])
                        page.update()

                    return dec_click, inc_click

                dec_fn, inc_fn = make_step_handlers(qty_state, qty_label)

                def direct_checkout_click(e, prod=(p_id, p_name, p_cost, p_sell), st=qty_state, lbl=qty_label):
                    qty = st["val"]
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                    unit_profit = prod[3] - prod[2]

                    for _ in range(qty):
                        cursor.execute("""
                            INSERT INTO orders (product_name, sell_price, profit, order_date)
                            VALUES (?, ?, ?, ?)
                        """, (prod[1], prod[3], unit_profit, now_str))

                    conn.commit()
                    conn.close()

                    st["val"] = 1
                    lbl.value = "1"
                    refresh_header_today_sales()
                    load_cashier_products()
                    show_snackbar(f"{qty} عدد «{prod[1]}» با موفقیت در فاکتور ثبت شد.", "#059669")

                card = ft.Container(
                    bgcolor=ft.colors.WHITE,
                    border_radius=16,
                    padding=ft.padding.symmetric(horizontal=12, vertical=10),
                    shadow=ft.BoxShadow(blur_radius=10, color=ft.colors.with_opacity(0.04, ft.colors.BLACK), offset=ft.Offset(0, 3)),
                    border=ft.border.all(1, "#E2E8F0"),
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
                                            ft.Text(p_name, font_family="Vazir-Bold", size=13, color="#0F172A"),
                                            ft.Row(
                                                spacing=6,
                                                controls=[
                                                    ft.Container(
                                                        content=ft.Text(p_cat, size=9, color=cat_color, font_family="Vazir-Bold"),
                                                        bgcolor=cat_bg,
                                                        padding=ft.padding.symmetric(horizontal=6, vertical=2),
                                                        border_radius=6
                                                    ),
                                                    ft.Text(f"{format_price(p_sell)} تومان", size=11, color="#059669", font_family="Vazir-Bold"),
                                                ]
                                            )
                                        ]
                                    ),
                                ]
                            ),
                            ft.Row(
                                spacing=6,
                                controls=[
                                    ft.Container(
                                        bgcolor="#F8FAFC",
                                        border=ft.border.all(1, "#E2E8F0"),
                                        border_radius=10,
                                        padding=ft.padding.symmetric(horizontal=4, vertical=2),
                                        content=ft.Row(
                                            spacing=2,
                                            controls=[
                                                ft.Container(
                                                    content=ft.Icon(ft.icons.ADD_ROUNDED, size=15, color="#4F46E5"),
                                                    width=26, height=26, bgcolor="#EEF2FF", border_radius=7, alignment=ft.alignment.center,
                                                    on_click=inc_fn,
                                                ),
                                                qty_label,
                                                ft.Container(
                                                    content=ft.Icon(ft.icons.REMOVE_ROUNDED, size=15, color="#64748B"),
                                                    width=26, height=26, bgcolor="#F1F5F9", border_radius=7, alignment=ft.alignment.center,
                                                    on_click=dec_fn,
                                                ),
                                            ]
                                        )
                                    ),
                                    ft.Container(
                                        gradient=ft.LinearGradient(colors=["#4F46E5", "#6366F1"]),
                                        width=38, height=36, border_radius=10, alignment=ft.alignment.center,
                                        on_click=direct_checkout_click,
                                        shadow=ft.BoxShadow(blur_radius=6, color=ft.colors.with_opacity(0.25, "#4F46E5"), offset=ft.Offset(0, 2)),
                                        content=ft.Icon(ft.icons.POINT_OF_SALE_ROUNDED, color=ft.colors.WHITE, size=18),
                                    )
                                ]
                            )
                        ]
                    )
                )
                cashier_products_col.controls.append(card)
        page.update()

    def open_recent_orders_dialog(e):
        orders_list_col = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, height=340, width=330)

        def load_recent_orders():
            orders_list_col.controls.clear()
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM orders")
            total_orders = cursor.fetchone()[0]
            
            cursor.execute("SELECT id, product_name, sell_price, order_date FROM orders ORDER BY id DESC LIMIT 25")
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                orders_list_col.controls.append(
                    ft.Container(
                        content=ft.Text("هیچ سفارشی ثبت نشده است.", color="#94A3B8", size=12),
                        alignment=ft.alignment.center,
                        padding=30
                    )
                )
            else:
                for idx, r in enumerate(rows):
                    o_id, o_name, o_price, o_date = r
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
                            show_snackbar(f"فاکتور شماره {d_num} ({prod_name}) لغو و حذف شد.", "#DC2626")

                        show_confirm_dialog(
                            "لغو و حذف فاکتور",
                            f"آیا از لغو و حذف سفارش شماره {d_num} «{prod_name}» به مبلغ {format_price(o_price)} تومان مطمئن هستید؟",
                            confirmed_delete
                        )

                    orders_list_col.controls.append(
                        ft.Container(
                            bgcolor="#F8FAFC",
                            border=ft.border.all(1, "#E2E8F0"),
                            border_radius=12,
                            padding=10,
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row(
                                        spacing=8,
                                        controls=[
                                            ft.Container(
                                                content=ft.Text(f"#{display_num}", size=11, font_family="Vazir-Bold", color="#4F46E5"),
                                                bgcolor="#EEF2FF",
                                                padding=ft.padding.symmetric(horizontal=8, vertical=5),
                                                border_radius=8,
                                            ),
                                            ft.Column(
                                                spacing=2,
                                                controls=[
                                                    ft.Text(f"سفارش {display_num} - {o_name}", size=12, font_family="Vazir-Bold", color="#0F172A"),
                                                    ft.Text(f"{format_price(o_price)} تومان  |  {jalali_dt}", size=10, color="#64748B")
                                                ]
                                            ),
                                        ]
                                    ),
                                    ft.Container(
                                        content=ft.Icon(ft.icons.DELETE_FOREVER_ROUNDED, color=ft.colors.RED_600, size=18),
                                        bgcolor=ft.colors.RED_50,
                                        width=34, height=34, border_radius=8, alignment=ft.alignment.center,
                                        on_click=ask_delete_order,
                                        tooltip="لغو این سفارش"
                                    )
                                ]
                            )
                        )
                    )
            page.update()

        load_recent_orders()

        dlg = ft.AlertDialog(
            title=ft.Row(
                spacing=8,
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.icons.HISTORY_ROUNDED, color="#D97706", size=20),
                        bgcolor="#FEF3C7",
                        padding=7,
                        border_radius=10,
                    ),
                    ft.Text("فاکتورهای اخیر (لغو سفارش)", size=14, font_family="Vazir-Bold", color="#0F172A"),
                ]
            ),
            content=orders_list_col,
            bgcolor=ft.colors.WHITE,
            surface_tint_color=ft.colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=20),
            actions=[
                ft.TextButton("بستن پنجره", on_click=lambda e: close_dialog(dlg))
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    cashier_view = ft.Container(
        padding=16, # افزایش فضای تنفس برای ظاهر مدرن‌تر
        expand=True,
        content=ft.Column(
            spacing=12,
            expand=True,
            controls=[
                ft.Row(
                    spacing=10,
                    controls=[
                        search_input,
                        ft.ElevatedButton(
                            "لغو فاکتور",
                            icon=ft.icons.RESTORE_FROM_TRASH_ROUNDED,
                            bgcolor=ft.colors.RED_50,
                            color=ft.colors.RED_700,
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
    # 2. تب مدیریت منو (با نمایش زنده حروف فارسی و سود خالص)
    # =========================================================================
    name_input = ft.TextField(
        label="نام محصول (مثلاً اسپرسو دبل)",
        height=44,
        text_size=12,
        content_padding=ft.padding.symmetric(horizontal=12, vertical=8),
        border_radius=10,
        border_color="#CBD5E1",
        bgcolor="#F8FAFC",
        expand=1
    )
    category_dropdown = ft.Dropdown(
        label="دسته‌بندی منو",
        height=44,
        text_size=12,
        content_padding=ft.padding.symmetric(horizontal=12, vertical=8),
        border_radius=10,
        border_color="#CBD5E1",
        bgcolor="#F8FAFC",
        expand=1,
        value="قهوه",
        options=[ft.dropdown.Option(c) for c in CATEGORIES_LIST]
    )

    cost_words_text = ft.Text("صفر تومان", size=10, color="#B45309", font_family="Vazir-Bold")
    sell_words_text = ft.Text("صفر تومان", size=10, color="#047857", font_family="Vazir-Bold")
    live_profit_preview_text = ft.Text("سود خالص هر واحد: 0 تومان", size=11, color="#4338CA", font_family="Vazir-Bold")

    def update_live_profit_preview():
        c_raw = (cost_input.value or "").replace(",", "").strip()
        s_raw = (sell_input.value or "").replace(",", "").strip()
        c_num = int(c_raw) if c_raw.isdigit() else 0
        s_num = int(s_raw) if s_raw.isdigit() else 0
        diff = s_num - c_num
        margin_pct = int((diff / s_num) * 100) if s_num > 0 else 0
        if diff >= 0:
            live_profit_preview_text.value = f"سود خالص هر فروش: {format_price(diff)} تومان ({margin_pct}٪ سود)"
            live_profit_preview_text.color = "#047857"
        else:
            live_profit_preview_text.value = f"زیان هر فروش: {format_price(abs(diff))} تومان (قیمت فروش کمتر از خرید است!)"
            live_profit_preview_text.color = "#DC2626"

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
        label="قیمت خرید / مایه (تومان)",
        height=44,
        text_size=12,
        keyboard_type=ft.KeyboardType.NUMBER,
        content_padding=ft.padding.symmetric(horizontal=12, vertical=8),
        border_radius=10,
        border_color="#CBD5E1",
        bgcolor="#F8FAFC",
        on_change=on_cost_price_change
    )
    sell_input = ft.TextField(
        label="قیمت فروش به مشتری (تومان)",
        height=44,
        text_size=12,
        keyboard_type=ft.KeyboardType.NUMBER,
        content_padding=ft.padding.symmetric(horizontal=12, vertical=8),
        border_radius=10,
        border_color="#CBD5E1",
        bgcolor="#F8FAFC",
        on_change=on_sell_price_change
    )

    submit_product_btn = ft.ElevatedButton(
        "ذخیره در منوی کافه",
        icon=ft.icons.CHECK_CIRCLE_ROUNDED,
        bgcolor="#4F46E5",
        color=ft.colors.WHITE,
        expand=True,
        height=42,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            text_style=ft.TextStyle(size=12, font_family="Vazir-Bold")
        )
    )

    cancel_edit_btn = ft.Container(
        content=ft.Icon(ft.icons.CLOSE_ROUNDED, color=ft.colors.RED_600, size=20),
        bgcolor=ft.colors.RED_50,
        width=42, height=42, border_radius=10, alignment=ft.alignment.center,
        tooltip="بستن فرم",
    )

    menu_products_col = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
    menu_count_badge = ft.Text("0 محصول", size=11, font_family="Vazir-Bold", color="#4F46E5")

    add_form_container = ft.Container(
        visible=False,
        bgcolor=ft.colors.WHITE,
        border_radius=16,
        padding=14,
        border=ft.border.all(1.5, "#C7D2FE"),
        shadow=ft.BoxShadow(blur_radius=14, color=ft.colors.with_opacity(0.07, "#1E1B4B"), offset=ft.Offset(0, 4)),
        content=ft.Column(
            spacing=10,
            controls=[
                ft.Row(spacing=8, controls=[name_input, category_dropdown]),
                ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        ft.Column(
                            spacing=4,
                            expand=1,
                            controls=[
                                cost_input,
                                ft.Container(
                                    bgcolor="#FFFBEB",
                                    border=ft.border.all(1, "#FDE68A"),
                                    border_radius=8,
                                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                                    content=ft.Row(
                                        spacing=4,
                                        controls=[
                                            ft.Icon(ft.icons.SUBDIRECTORY_ARROW_LEFT_ROUNDED, size=12, color="#D97706"),
                                            ft.Container(content=cost_words_text, expand=True),
                                        ]
                                    )
                                )
                            ]
                        ),
                        ft.Column(
                            spacing=4,
                            expand=1,
                            controls=[
                                sell_input,
                                ft.Container(
                                    bgcolor="#ECFDF5",
                                    border=ft.border.all(1, "#A7F3D0"),
                                    border_radius=8,
                                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                                    content=ft.Row(
                                        spacing=4,
                                        controls=[
                                            ft.Icon(ft.icons.SUBDIRECTORY_ARROW_LEFT_ROUNDED, size=12, color="#059669"),
                                            ft.Container(content=sell_words_text, expand=True),
                                        ]
                                    )
                                )
                            ]
                        )
                    ]
                ),
                ft.Container(
                    bgcolor="#F8FAFC",
                    border=ft.border.all(1, "#E2E8F0"),
                    border_radius=10,
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    alignment=ft.alignment.center,
                    content=live_profit_preview_text
                ),
                ft.Row(spacing=8, controls=[submit_product_btn, cancel_edit_btn])
            ]
        )
    )

    show_add_form_btn = ft.ElevatedButton(
        "افزودن آیتم جدید",
        icon=ft.icons.ADD_CIRCLE_OUTLINE_ROUNDED,
        bgcolor="#4F46E5",
        color=ft.colors.WHITE,
        elevation=2,
        height=38,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            text_style=ft.TextStyle(size=11, font_family="Vazir-Bold")
        )
    )

    def toggle_form(show: bool):
        add_form_container.visible = show
        show_add_form_btn.visible = not show
        page.update()

    show_add_form_btn.on_click = lambda e: toggle_form(True)

    def reset_menu_form():
        nonlocal editing_product_id
        editing_product_id = None
        name_input.value = ""
        category_dropdown.value = "قهوه"
        cost_input.value = ""
        sell_input.value = ""
        cost_words_text.value = "صفر تومان"
        sell_words_text.value = "صفر تومان"
        live_profit_preview_text.value = "سود خالص هر واحد: 0 تومان"
        live_profit_preview_text.color = "#4338CA"
        submit_product_btn.text = "ذخیره در منوی کافه"
        submit_product_btn.icon = ft.icons.CHECK_CIRCLE_ROUNDED
        submit_product_btn.bgcolor = "#4F46E5"
        toggle_form(False)

    cancel_edit_btn.on_click = lambda e: reset_menu_form()

    def save_or_update_product(e):
        nonlocal editing_product_id
        name = name_input.value.strip()
        cat = category_dropdown.value
        cost_str = cost_input.value.strip().replace(",", "")
        sell_str = sell_input.value.strip().replace(",", "")

        if not name or not cost_str or not sell_str:
            show_snackbar("لطفاً نام محصول و هر دو قیمت را وارد کنید!", ft.colors.RED_700)
            return

        try:
            cost_val = float(cost_str)
            sell_val = float(sell_str)
        except ValueError:
            show_snackbar("قیمت خرید و فروش باید عدد باشند!", ft.colors.RED_700)
            return

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        if editing_product_id is None:
            cursor.execute("""
                INSERT INTO products (name, category, cost_price, sell_price)
                VALUES (?, ?, ?, ?)
            """, (name, cat, cost_val, sell_val))
            show_snackbar(f"محصول «{name}» با موفقیت به منو اضافه شد.", "#059669")
        else:
            cursor.execute("SELECT name FROM products WHERE id = ?", (editing_product_id,))
            old_name_row = cursor.fetchone()
            
            cursor.execute("""
                UPDATE products
                SET name = ?, category = ?, cost_price = ?, sell_price = ?
                WHERE id = ?
            """, (name, cat, cost_val, sell_val, editing_product_id))
            
            if old_name_row:
                old_name = old_name_row[0]
                if old_name != name:
                    cursor.execute("""
                        UPDATE orders
                        SET product_name = ?
                        WHERE product_name = ?
                    """, (name, old_name))

            show_snackbar(f"اطلاعات «{name}» بروزرسانی شد.", "#D97706")

        conn.commit()
        conn.close()
        reset_menu_form()
        load_menu_products()
        load_cashier_products()

    submit_product_btn.on_click = save_or_update_product

    def load_menu_products():
        menu_products_col.controls.clear()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, category, cost_price, sell_price FROM products ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()

        menu_count_badge.value = f"{len(rows)} محصول ثبت‌شده"

        if not rows:
            menu_products_col.controls.append(
                ft.Container(
                    bgcolor=ft.colors.WHITE,
                    border_radius=16,
                    border=ft.border.all(1, "#E2E8F0"),
                    content=ft.Text("هنوز محصولی در منو ثبت نشده است.", color="#94A3B8", size=12),
                    alignment=ft.alignment.center,
                    padding=30
                )
            )
        else:
            for r in rows:
                p_id, p_name, p_cat, p_cost, p_sell = r
                
                styles = {
                    "قهوه": (ft.icons.COFFEE_ROUNDED, "#78350F", "#FEF3C7", "#FDE68A"),
                    "نوشیدنی گرم بر پایۀ قهوه": (ft.icons.LOCAL_CAFE_ROUNDED, "#9A3412", "#FFEDD5", "#FED7AA"),
                    "نوشیدنی سرد بر پایۀ قهوه": (ft.icons.AC_UNIT_ROUNDED, "#0369A1", "#E0F2FE", "#BAE6FD"),
                    "شیک": (ft.icons.BLENDER_ROUNDED, "#6D28D9", "#EDE9FE", "#DDD6FE"),
                    "بستنی بار": (ft.icons.ICE_CREAM_ROUNDED, "#BE185D", "#FCE7F3", "#FBCFE8"),
                    "نوشیدنی گرم": (ft.icons.EMOJI_FOOD_BEVERAGE_ROUNDED, "#B91C1C", "#FEE2E2", "#FECACA"),
                    "چای": (ft.icons.LOCAL_DRINK_ROUNDED, "#047857", "#D1FAE5", "#A7F3D0"),
                }
                cat_icon, cat_color, cat_bg, cat_border = styles.get(p_cat, (ft.icons.LOCAL_CAFE_ROUNDED, "#4338CA", "#EEF2FF", "#C7D2FE"))
                unit_prof = p_sell - p_cost
                margin_pct = int((unit_prof / p_sell) * 100) if p_sell > 0 else 0

                def edit_click(e, prod=r):
                    nonlocal editing_product_id
                    editing_product_id = prod[0]
                    name_input.value = prod[1]
                    category_dropdown.value = prod[2]

                    c_val = int(prod[3])
                    s_val = int(prod[4])

                    cost_input.value = f"{c_val:,}"
                    cost_words_text.value = f"{num_to_persian(c_val)} تومان" if c_val > 0 else "صفر تومان"

                    sell_input.value = f"{s_val:,}"
                    sell_words_text.value = f"{num_to_persian(s_val)} تومان" if s_val > 0 else "صفر تومان"

                    update_live_profit_preview()
                    submit_product_btn.text = "ذخیره تغییرات"
                    submit_product_btn.icon = ft.icons.UPDATE_ROUNDED
                    submit_product_btn.bgcolor = "#D97706"
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
                        show_snackbar(f"محصول «{prod_name}» از منو حذف شد.", ft.colors.RED_700)

                    show_confirm_dialog(
                        "حذف محصول از منو",
                        f"آیا از حذف دائمی آیتم «{prod_name}» از منوی کافه مطمئن هستید؟",
                        confirmed_del_product
                    )

                card = ft.Container(
                    bgcolor=ft.colors.WHITE,
                    border_radius=14,
                    padding=12,
                    border=ft.border.all(1, "#E2E8F0"),
                    shadow=ft.BoxShadow(blur_radius=6, color=ft.colors.with_opacity(0.03, ft.colors.BLACK), offset=ft.Offset(0, 2)),
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
                                                    ft.Text(p_name, font_family="Vazir-Bold", size=13, color=ft.colors.BLUE_GREY_900),
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
                                                content=ft.Icon(ft.icons.EDIT_NOTE_ROUNDED, color=ft.colors.BLUE_700, size=18),
                                                bgcolor=ft.colors.BLUE_50,
                                                width=34, height=34, border_radius=8, alignment=ft.alignment.center,
                                                on_click=edit_click,
                                                tooltip="ویرایش"
                                            ),
                                            ft.Container(
                                                content=ft.Icon(ft.icons.DELETE_OUTLINE_ROUNDED, color=ft.colors.RED_600, size=18),
                                                bgcolor=ft.colors.RED_50,
                                                width=34, height=34, border_radius=8, alignment=ft.alignment.center,
                                                on_click=delete_click,
                                                tooltip="حذف"
                                            )
                                        ]
                                    )
                                ]
                            ),
                            ft.Container(
                                bgcolor="#F8FAFC",
                                border_radius=10,
                                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                                content=ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text(f"مایه: {format_price(p_cost)} ت", size=10, color="#64748B"),
                                        ft.Text(f"فروش: {format_price(p_sell)} ت", size=10, color="#0F172A", font_family="Vazir-Bold"),
                                        ft.Container(
                                            bgcolor="#DCFCE7",
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
        content=ft.Column(
            spacing=10,
            expand=True,
            controls=[
                ft.Row(
                    # دستور alignment حذف شد تا باگ راست‌چین برطرف شود
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Container(
                                    content=ft.Icon(ft.icons.MENU_BOOK_ROUNDED, color="#4338CA", size=20),
                                    bgcolor="#EEF2FF",
                                    padding=8,
                                    border_radius=10,
                                ),
                                ft.Text("مدیریت منو", size=15, font_family="Vazir-Bold", color="#0F172A"),
                                ft.Container(
                                    bgcolor="#EEF2FF",
                                    padding=ft.padding.symmetric(horizontal=8, vertical=3),
                                    border_radius=8,
                                    content=menu_count_badge
                                )
                            ]
                        ),
                        ft.Container(expand=True), # این باکس نامرئی و کشسان، نقش هل‌دهنده را بازی می‌کند
                        show_add_form_btn
                    ]
                ),
                add_form_container,
                ft.Text("لیست محصولات موجود:", size=12, font_family="Vazir-Bold", color=ft.colors.BLUE_GREY_800),
                menu_products_col
            ]
        )
    )

    # =========================================================================
    # 3. تب داشبورد و گزارش مالی پیشرفته
    # =========================================================================
    total_revenue_text = ft.Text("0", size=14, font_family="Vazir-Bold", color="#1D4ED8")
    total_cost_text = ft.Text("0", size=14, font_family="Vazir-Bold", color="#B45309")
    net_profit_text = ft.Text("0 تومان", size=20, font_family="Vazir-Bold", color=ft.colors.WHITE)
    net_profit_words_text = ft.Text("صفر تومان", size=10, color="#A7F3D0")
    profit_margin_badge_text = ft.Text("حاشیه سود: 0٪", size=10, font_family="Vazir-Bold", color="#064E3B")
    period_summary_badge = ft.Text("0 فروش", size=10, font_family="Vazir-Bold", color=ft.colors.WHITE)

    report_items_col = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
    mode_selector_row = ft.Row(spacing=6, alignment=ft.MainAxisAlignment.CENTER)
    date_navigator_container = ft.Container()

    def open_jalali_calendar_dialog(e):
        nonlocal selected_date
        cur_jy, cur_jm, cur_jd = gregorian_to_jalali(selected_date.year, selected_date.month, selected_date.day)
        cal_state = {"jy": cur_jy, "jm": cur_jm, "jd": cur_jd}

        cal_header_text = ft.Text("", size=14, font_family="Vazir-Bold", color="#1E1B4B")
        days_grid_col = ft.Column(spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        def render_calendar_grid():
            jy, jm = cal_state["jy"], cal_state["jm"]
            cal_header_text.value = f"{JALALI_MONTHS[jm - 1]} {jy}"
            days_grid_col.controls.clear()

            max_days = get_jalali_month_days(jy, jm)
            row_buttons = []

            for d in range(1, max_days + 1):
                is_selected = (jy == cur_jy and jm == cur_jm and d == cur_jd)
                is_today = (jy == today_jy and jm == today_jm and d == today_jd)

                def pick_day(e, day_num=d):
                    nonlocal selected_date
                    gy, gm, gd = jalali_to_gregorian(cal_state["jy"], cal_state["jm"], day_num)
                    selected_date = datetime(gy, gm, gd)
                    cal_dlg.open = False
                    update_dashboard_controls()
                    load_dashboard_data()

                btn_bg = "#4F46E5" if is_selected else ("#FEF3C7" if is_today else "#F1F5F9")
                btn_col = ft.colors.WHITE if is_selected else ("#92400E" if is_today else "#334155")

                row_buttons.append(
                    ft.Container(
                        width=40,
                        height=36,
                        bgcolor=btn_bg,
                        border_radius=10,
                        alignment=ft.alignment.center,
                        on_click=pick_day,
                        content=ft.Text(str(d), size=12, font_family="Vazir-Bold", color=btn_col)
                    )
                )
                if len(row_buttons) == 6 or d == max_days:
                    days_grid_col.controls.append(
                        ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=6, controls=row_buttons)
                    )
                    row_buttons = []
            page.update()

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
            cal_dlg.open = False
            update_dashboard_controls()
            load_dashboard_data()

        render_calendar_grid()

        cal_dlg = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=20),
            bgcolor=ft.colors.WHITE,
            surface_tint_color=ft.colors.WHITE,
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.icons.CHEVRON_RIGHT_ROUNDED, color="#4F46E5", size=20),
                        bgcolor="#EEF2FF", width=34, height=34, border_radius=8, alignment=ft.alignment.center,
                        on_click=lambda e: change_cal_month(1)
                    ),
                    cal_header_text,
                    ft.Container(
                        content=ft.Icon(ft.icons.CHEVRON_LEFT_ROUNDED, color="#4F46E5", size=20),
                        bgcolor="#EEF2FF", width=34, height=34, border_radius=8, alignment=ft.alignment.center,
                        on_click=lambda e: change_cal_month(-1)
                    ),
                ]
            ),
            content=ft.Container(
                width=300,
                height=260,
                content=days_grid_col
            ),
            actions=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.ElevatedButton(
                            "برو به امروز",
                            icon=ft.icons.TODAY_ROUNDED,
                            bgcolor="#EEF2FF",
                            color="#4F46E5",
                            elevation=0,
                            on_click=go_to_today
                        ),
                        ft.TextButton("بستن", on_click=lambda e: close_dialog(cal_dlg))
                    ]
                )
            ]
        )
        page.overlay.append(cal_dlg)
        cal_dlg.open = True
        page.update()

    def switch_filter_mode(new_mode: str):
        nonlocal filter_mode
        filter_mode = new_mode
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
                    bgcolor="#4F46E5" if is_active else ft.colors.WHITE,
                    border=ft.border.all(1, "#4F46E5" if is_active else "#E2E8F0"),
                    border_radius=12,
                    padding=ft.padding.symmetric(horizontal=8, vertical=8),
                    alignment=ft.alignment.center,
                    on_click=lambda e, k=m_key: switch_filter_mode(k),
                    shadow=ft.BoxShadow(blur_radius=8, color=ft.colors.with_opacity(0.2 if is_active else 0.03, "#4F46E5"), offset=ft.Offset(0, 2)),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=5,
                        controls=[
                            ft.Icon(m_icon, size=15, color=ft.colors.WHITE if is_active else "#64748B"),
                            ft.Text(m_label, size=11, font_family="Vazir-Bold", color=ft.colors.WHITE if is_active else "#475569"),
                        ]
                    )
                )
            )

        if filter_mode == "day":
            jy, jm, jd = gregorian_to_jalali(selected_date.year, selected_date.month, selected_date.day)
            is_today_selected = (jy == today_jy and jm == today_jm and jd == today_jd)
            day_label = f"امروز، {jd} {JALALI_MONTHS[jm - 1]} {jy}" if is_today_selected else f"{jd} {JALALI_MONTHS[jm - 1]} {jy}"

            date_navigator_container.content = ft.Container(
                bgcolor=ft.colors.WHITE,
                border_radius=14,
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                border=ft.border.all(1, "#E2E8F0"),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Container(
                            content=ft.Icon(ft.icons.CHEVRON_RIGHT_ROUNDED, color="#4338CA", size=20),
                            bgcolor="#EEF2FF", width=32, height=32, border_radius=8, alignment=ft.alignment.center,
                            tooltip="روز بعد",
                            on_click=lambda e: step_day(1)
                        ),
                        ft.Container(
                            on_click=open_jalali_calendar_dialog,
                            border_radius=8,
                            padding=ft.padding.symmetric(horizontal=10, vertical=4),
                            content=ft.Row(
                                spacing=6,
                                controls=[
                                    ft.Icon(ft.icons.EDIT_CALENDAR_ROUNDED, color="#4F46E5", size=17),
                                    ft.Text(day_label, size=12, font_family="Vazir-Bold", color="#0F172A"),
                                    ft.Text("(تقویم)", size=10, color="#4F46E5", font_family="Vazir-Bold"),
                                ]
                            )
                        ),
                        ft.Container(
                            content=ft.Icon(ft.icons.CHEVRON_LEFT_ROUNDED, color="#4338CA", size=20),
                            bgcolor="#EEF2FF", width=32, height=32, border_radius=8, alignment=ft.alignment.center,
                            tooltip="روز قبل",
                            on_click=lambda e: step_day(-1)
                        ),
                    ]
                )
            )
        elif filter_mode == "month":
            month_title = f"آمار ماه {JALALI_MONTHS[selected_j_month - 1]} {selected_j_year}"
            date_navigator_container.content = ft.Container(
                bgcolor=ft.colors.WHITE,
                border_radius=14,
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                border=ft.border.all(1, "#E2E8F0"),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Container(
                            content=ft.Icon(ft.icons.CHEVRON_RIGHT_ROUNDED, color="#4338CA", size=20),
                            bgcolor="#EEF2FF", width=32, height=32, border_radius=8, alignment=ft.alignment.center,
                            tooltip="ماه بعد",
                            on_click=lambda e: step_month(1)
                        ),
                        ft.Row(
                            spacing=6,
                            controls=[
                                ft.Icon(ft.icons.DATE_RANGE_ROUNDED, color="#4F46E5", size=18),
                                ft.Text(month_title, size=13, font_family="Vazir-Bold", color="#0F172A"),
                            ]
                        ),
                        ft.Container(
                            content=ft.Icon(ft.icons.CHEVRON_LEFT_ROUNDED, color="#4338CA", size=20),
                            bgcolor="#EEF2FF", width=32, height=32, border_radius=8, alignment=ft.alignment.center,
                            tooltip="ماه قبل",
                            on_click=lambda e: step_month(-1)
                        ),
                    ]
                )
            )
        else:
            date_navigator_container.content = ft.Container(
                bgcolor="#EEF2FF",
                border_radius=10,
                padding=8,
                alignment=ft.alignment.center,
                content=ft.Text("نمایش تجمیعی تمام تراکنش‌های ثبت‌شده از ابتدا", size=11, font_family="Vazir-Bold", color="#4F46E5")
            )
        page.update()

    def load_dashboard_data():
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        where_sql = ""
        params = ()

        if filter_mode == "day":
            day_prefix = selected_date.strftime("%Y-%m-%d")
            where_sql = "WHERE substr(order_date, 1, 10) = ?"
            params = (day_prefix,)
        elif filter_mode == "month":
            max_d = get_jalali_month_days(selected_j_year, selected_j_month)
            g_start = jalali_to_gregorian(selected_j_year, selected_j_month, 1)
            g_end = jalali_to_gregorian(selected_j_year, selected_j_month, max_d)
            start_str = f"{g_start[0]:04d}-{g_start[1]:02d}-{g_start[2]:02d}"
            end_str = f"{g_end[0]:04d}-{g_end[1]:02d}-{g_end[2]:02d}"
            where_sql = "WHERE substr(order_date, 1, 10) >= ? AND substr(order_date, 1, 10) <= ?"
            params = (start_str, end_str)

        cursor.execute(f"""
            SELECT COALESCE(SUM(sell_price), 0), COALESCE(SUM(profit), 0), COUNT(*)
            FROM orders
            {where_sql}
        """, params)
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
        """, params)
        rows = cursor.fetchall()
        conn.close()

        report_items_col.controls.clear()
        if not rows:
            report_items_col.controls.append(
                ft.Container(
                    bgcolor=ft.colors.WHITE,
                    border_radius=16,
                    border=ft.border.all(1, "#E2E8F0"),
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                        controls=[
                            ft.Icon(ft.icons.INSERT_CHART_OUTLINED_ROUNDED, size=38, color="#94A3B8"),
                            ft.Text("در این بازه زمانی هیچ سفارشی ثبت نشده است.", color="#64748B", size=12, font_family="Vazir-Bold"),
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
                    bgcolor=ft.colors.WHITE,
                    border_radius=14,
                    padding=12,
                    border=ft.border.all(1, "#E2E8F0"),
                    shadow=ft.BoxShadow(blur_radius=6, color=ft.colors.with_opacity(0.03, ft.colors.BLACK), offset=ft.Offset(0, 2)),
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
                                                content=ft.Text(f"{p_qty}×", color=ft.colors.WHITE, font_family="Vazir-Bold", size=12),
                                                gradient=ft.LinearGradient(colors=["#4F46E5", "#6366F1"]),
                                                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                                                border_radius=10
                                            ),
                                            ft.Column(
                                                spacing=2,
                                                controls=[
                                                    ft.Text(f"{rank_idx}. {p_name}", font_family="Vazir-Bold", size=13, color="#0F172A"),
                                                    ft.Text(f"فروش کل: {format_price(p_sale)} تومان ({share_pct}٪ از کل فروش)", size=10, color="#64748B")
                                                ]
                                            )
                                        ]
                                    ),
                                    ft.Container(
                                        bgcolor="#ECFDF5",
                                        border=ft.border.all(1, "#A7F3D0"),
                                        padding=ft.padding.symmetric(horizontal=9, vertical=4),
                                        border_radius=10,
                                        content=ft.Column(
                                            horizontal_alignment=ft.CrossAxisAlignment.END,
                                            spacing=1,
                                            controls=[
                                                ft.Text("سود خالص", size=9, color="#047857"),
                                                ft.Text(f"+{format_price(p_prof)} ت", size=11, font_family="Vazir-Bold", color="#047857")
                                            ]
                                        )
                                    )
                                ]
                            ),
                            # نوار پیشرفت سهم فروش محصول
                            ft.Container(
                                height=5,
                                bgcolor="#F1F5F9",
                                border_radius=5,
                                content=ft.Row(
                                    spacing=0,
                                    controls=[
                                        ft.Container(expand=max(1, share_pct), bgcolor="#4F46E5", border_radius=5),
                                        ft.Container(expand=max(0, 100 - share_pct)),
                                    ]
                                )
                            )
                        ]
                    )
                )
                report_items_col.controls.append(card)
        page.update()

    # کارت هیرو سود خالص در داشبورد
    hero_profit_card = ft.Container(
        border_radius=18,
        padding=14,
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_right,
            end=ft.alignment.bottom_left,
            colors=["#064E3B", "#047857", "#059669"]
        ),
        shadow=ft.BoxShadow(blur_radius=14, color=ft.colors.with_opacity(0.25, "#059669"), offset=ft.Offset(0, 4)),
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
                                    content=ft.Icon(ft.icons.DIAMOND_ROUNDED, color="#34D399", size=18),
                                    bgcolor=ft.colors.with_opacity(0.15, ft.colors.WHITE),
                                    padding=6,
                                    border_radius=8,
                                ),
                                ft.Text("سود خالص دوره انتخابی", size=12, font_family="Vazir-Bold", color="#ECFDF5"),
                            ]
                        ),
                        ft.Container(
                            bgcolor="#A7F3D0",
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
                            bgcolor=ft.colors.with_opacity(0.15, ft.colors.WHITE),
                            padding=ft.padding.symmetric(horizontal=10, vertical=5),
                            border_radius=10,
                            content=period_summary_badge,
                        )
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
                mode_selector_row,
                date_navigator_container,
                hero_profit_card,
                ft.Row(
                    spacing=8,
                    controls=[
                        ft.Container(
                            expand=1,
                            bgcolor=ft.colors.WHITE,
                            border_radius=14,
                            padding=11,
                            border=ft.border.all(1, "#BFDBFE"),
                            content=ft.Row(
                                spacing=10,
                                controls=[
                                    ft.Container(
                                        content=ft.Icon(ft.icons.ACCOUNT_BALANCE_WALLET_ROUNDED, color="#2563EB", size=20),
                                        bgcolor="#DBEAFE",
                                        padding=8,
                                        border_radius=10
                                    ),
                                    ft.Column(
                                        spacing=1,
                                        controls=[
                                            ft.Text("درآمد کل (فروش)", size=10, color="#64748B", font_family="Vazir-Bold"),
                                            total_revenue_text,
                                        ]
                                    )
                                ]
                            )
                        ),
                        ft.Container(
                            expand=1,
                            bgcolor=ft.colors.WHITE,
                            border_radius=14,
                            padding=11,
                            border=ft.border.all(1, "#FDE68A"),
                            content=ft.Row(
                                spacing=10,
                                controls=[
                                    ft.Container(
                                        content=ft.Icon(ft.icons.INVENTORY_2_ROUNDED, color="#D97706", size=20),
                                        bgcolor="#FEF3C7",
                                        padding=8,
                                        border_radius=10
                                    ),
                                    ft.Column(
                                        spacing=1,
                                        controls=[
                                            ft.Text("هزینه مایه (خرید)", size=10, color="#64748B", font_family="Vazir-Bold"),
                                            total_cost_text,
                                        ]
                                    )
                                ]
                            )
                        ),
                    ]
                ),
                ft.Text("رتبه‌بندی پرفروش‌ترین محصولات:", size=12, font_family="Vazir-Bold", color="#0F172A"),
                report_items_col
            ]
        )
    )

    body_container = ft.Container(content=cashier_view, expand=True)

    def on_nav_change(e):
        idx = e.control.selected_index
        if idx == 0:
            load_menu_products()
            body_container.content = menu_view
        elif idx == 1:
            render_cashier_category_chips()
            load_cashier_products()
            body_container.content = cashier_view
        elif idx == 2:
            update_dashboard_controls()
            load_dashboard_data()
            body_container.content = dashboard_view
        page.update()

    page.navigation_bar = ft.NavigationBar(
        selected_index=1,
        height=65,
        bgcolor=ft.colors.WHITE,
        surface_tint_color=ft.colors.WHITE,
        indicator_color="#E0E7FF",
        elevation=12,
        on_change=on_nav_change,
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.icons.MENU_BOOK_OUTLINED,
                selected_icon=ft.icons.MENU_BOOK_ROUNDED,
                label="مدیریت منو"
            ),
            ft.NavigationBarDestination(
                icon=ft.icons.STOREFRONT_OUTLINED,
                selected_icon=ft.icons.STOREFRONT_ROUNDED,
                label="صندوق فروش"
            ),
            ft.NavigationBarDestination(
                icon=ft.icons.ANALYTICS_OUTLINED,
                selected_icon=ft.icons.ANALYTICS_ROUNDED,
                label="داشبورد مالی"
            ),
        ]
    )

    refresh_header_today_sales()
    render_cashier_category_chips()
    load_cashier_products()
    update_dashboard_controls()

    page.add(
        ft.Column(
            spacing=0,
            expand=True,
            controls=[
                top_app_header,
                body_container
            ]
        )
    )

if __name__ == "__main__":
    ft.app(target=main)
