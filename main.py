import flet as ft
import re
import sqlite3
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

JALALI_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"
]

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
        return f"{jy}/{jm:02d}/{jd:02d}" + (f" - {time_part}" if time_part else "")
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

def main(page: ft.Page):
    init_db()

    page.title = "حسابداری و صندوق کافه"
    page.rtl = True
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = "#F4F6FA"
    page.window.width = 430
    page.window.height = 780
    page.window.resizable = False
    page.padding = 0

    page.fonts = {
        "Vazir": "https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/fonts/ttf/Vazirmatn-Regular.ttf",
        "Vazir-Bold": "https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/fonts/ttf/Vazirmatn-Bold.ttf"
    }
    page.theme = ft.Theme(font_family="Vazir")

    cart = []
    editing_product_id = None

    now_dt = datetime.now()
    init_jy, init_jm, init_jd = gregorian_to_jalali(now_dt.year, now_dt.month, now_dt.day)

    filter_mode = "day"
    selected_date = datetime(now_dt.year, now_dt.month, now_dt.day)
    selected_j_year = init_jy
    selected_j_month = init_jm

    def show_snackbar(message: str, color=ft.colors.TEAL_700):
        snack = ft.SnackBar(
            content=ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(ft.icons.INFO_OUTLINE_ROUNDED, color=ft.colors.WHITE, size=18),
                    ft.Text(message, color=ft.colors.WHITE, font_family="Vazir-Bold", size=12, expand=True),
                ]
            ),
            bgcolor=color,
            behavior=ft.SnackBarBehavior.FLOATING,
            shape=ft.RoundedRectangleBorder(radius=12),
            margin=12,
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
            shape=ft.RoundedRectangleBorder(radius=18),
            bgcolor=ft.colors.WHITE,
            surface_tint_color=ft.colors.WHITE,
            title=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.icons.WARNING_AMBER_ROUNDED, color=ft.colors.RED_600, size=34),
                        bgcolor=ft.colors.RED_50,
                        padding=14,
                        border_radius=50,
                    ),
                    ft.Text(title_text, size=15, font_family="Vazir-Bold", color=ft.colors.BLUE_GREY_900, text_align=ft.TextAlign.CENTER),
                ]
            ),
            content=ft.Text(
                message_text,
                size=12,
                color=ft.colors.BLUE_GREY_600,
                text_align=ft.TextAlign.CENTER,
            ),
            actions=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10,
                    controls=[
                        ft.ElevatedButton(
                            "انصراف",
                            bgcolor=ft.colors.BLUE_GREY_50,
                            color=ft.colors.BLUE_GREY_700,
                            elevation=0,
                            height=38,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                            on_click=handle_no
                        ),
                        ft.ElevatedButton(
                            "بله، حذف شود",
                            icon=ft.icons.DELETE_FOREVER_ROUNDED,
                            bgcolor=ft.colors.RED_600,
                            color=ft.colors.WHITE,
                            elevation=2,
                            height=38,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                            on_click=handle_yes
                        ),
                    ]
                )
            ],
        )
        page.overlay.append(confirm_dlg)
        confirm_dlg.open = True
        page.update()

    today_jy, today_jm, today_jd = gregorian_to_jalali(now_dt.year, now_dt.month, now_dt.day)
    today_badge_str = f"{today_jd} {JALALI_MONTHS[today_jm - 1]} {today_jy}"

    top_app_header = ft.Container(
        padding=ft.padding.symmetric(horizontal=16, vertical=12),
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_right,
            end=ft.alignment.bottom_left,
            colors=["#1E1B4B", "#312E81", "#4338CA"]
        ),
        shadow=ft.BoxShadow(blur_radius=10, color=ft.colors.with_opacity(0.18, ft.colors.BLACK), offset=ft.Offset(0, 3)),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(
                    spacing=10,
                    controls=[
                        ft.Container(
                            content=ft.Icon(ft.icons.LOCAL_CAFE_ROUNDED, color=ft.colors.AMBER_400, size=22),
                            bgcolor=ft.colors.with_opacity(0.15, ft.colors.WHITE),
                            padding=8,
                            border_radius=10,
                        ),
                        ft.Column(
                            spacing=1,
                            controls=[
                                ft.Text("سیستم حسابداری کافه", size=14, font_family="Vazir-Bold", color=ft.colors.WHITE),
                                ft.Text("مدیریت هوشمند فروش و سود", size=10, color=ft.colors.INDIGO_100),
                            ]
                        )
                    ]
                ),
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
                )
            ]
        )
    )

    # 1. صندوق
    cashier_products_col = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
    cart_items_col = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, height=92)
    cart_total_text = ft.Text("0 تومان", font_family="Vazir-Bold", size=15, color=ft.colors.GREEN_800)

    def get_category_style(cat: str):
        styles = {
            "قهوه و اسپرسو": (ft.icons.COFFEE_ROUNDED, ft.colors.BROWN_700, ft.colors.BROWN_50),
            "نوشیدنی گرم": (ft.icons.EMOJI_FOOD_BEVERAGE_ROUNDED, ft.colors.ORANGE_800, ft.colors.ORANGE_50),
            "نوشیدنی سرد": (ft.icons.LOCAL_BAR_ROUNDED, ft.colors.CYAN_800, ft.colors.CYAN_50),
            "کیک و دسر": (ft.icons.CAKE_ROUNDED, ft.colors.PINK_700, ft.colors.PINK_50),
            "غذا و اسنک": (ft.icons.LUNCH_DINING_ROUNDED, ft.colors.INDIGO_700, ft.colors.INDIGO_50),
        }
        return styles.get(cat, (ft.icons.LOCAL_CAFE_ROUNDED, ft.colors.INDIGO_700, ft.colors.INDIGO_50))

    def load_cashier_products():
        cashier_products_col.controls.clear()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, category, cost_price, sell_price FROM products ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            cashier_products_col.controls.append(
                ft.Container(
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                        controls=[
                            ft.Icon(ft.icons.COFFEE_MAKER_OUTLINED, size=40, color=ft.colors.BLUE_GREY_200),
                            ft.Text("هیچ محصولی ثبت نشده است.\nاز تب «مدیریت منو» محصولات کافه را اضافه کنید.",
                                    color=ft.colors.BLUE_GREY_400, size=12, text_align=ft.TextAlign.CENTER),
                        ]
                    ),
                    alignment=ft.alignment.center,
                    padding=35
                )
            )
        else:
            for row in rows:
                p_id, p_name, p_cat, p_cost, p_sell = row
                cat_icon, cat_color, cat_bg = get_category_style(p_cat)

                qty_field = ft.TextField(
                    value="1",
                    width=48,
                    height=36,
                    text_align=ft.TextAlign.CENTER,
                    keyboard_type=ft.KeyboardType.NUMBER,
                    content_padding=ft.padding.all(2),
                    text_size=13,
                    border_radius=8,
                    border_color=ft.colors.INDIGO_100,
                    bgcolor="#F8FAFC",
                )

                def add_to_cart_click(e, prod=(p_id, p_name, p_cost, p_sell), q_tf=qty_field):
                    try:
                        qty = int(q_tf.value)
                        if qty <= 0:
                            show_snackbar("تعداد باید بیشتر از صفر باشد!", ft.colors.ORANGE_700)
                            return
                    except ValueError:
                        show_snackbar("لطفاً تعداد معتبر وارد کنید!", ft.colors.RED_700)
                        return

                    for item in cart:
                        if item["id"] == prod[0]:
                            item["qty"] += qty
                            q_tf.value = "1"
                            update_cart_ui()
                            show_snackbar(f"{qty} عدد «{prod[1]}» به سبد اضافه شد.", ft.colors.INDIGO_600)
                            return

                    cart.append({
                        "id": prod[0],
                        "name": prod[1],
                        "cost_price": prod[2],
                        "sell_price": prod[3],
                        "qty": qty
                    })
                    q_tf.value = "1"
                    update_cart_ui()
                    show_snackbar(f"«{prod[1]}» به سبد خرید اضافه شد.", ft.colors.INDIGO_600)

                card = ft.Container(
                    bgcolor=ft.colors.WHITE,
                    border_radius=12,
                    padding=ft.padding.symmetric(horizontal=12, vertical=9),
                    shadow=ft.BoxShadow(blur_radius=6, color=ft.colors.with_opacity(0.05, ft.colors.BLACK), offset=ft.Offset(0, 2)),
                    border=ft.border.all(1, "#EEF2FF"),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                spacing=10,
                                controls=[
                                    ft.Container(
                                        content=ft.Icon(cat_icon, color=cat_color, size=20),
                                        bgcolor=cat_bg,
                                        padding=9,
                                        border_radius=10
                                    ),
                                    ft.Column(
                                        spacing=2,
                                        controls=[
                                            ft.Text(p_name, font_family="Vazir-Bold", size=13, color=ft.colors.BLUE_GREY_900),
                                            ft.Row(
                                                spacing=6,
                                                controls=[
                                                    ft.Container(
                                                        content=ft.Text(p_cat, size=9, color=cat_color),
                                                        bgcolor=cat_bg,
                                                        padding=ft.padding.symmetric(horizontal=6, vertical=1),
                                                        border_radius=4
                                                    ),
                                                    ft.Text(f"{format_price(p_sell)} تومان", size=11, color=ft.colors.GREEN_700, font_family="Vazir-Bold"),
                                                ]
                                            )
                                        ]
                                    ),
                                ]
                            ),
                            ft.Row(
                                spacing=6,
                                controls=[
                                    qty_field,
                                    ft.IconButton(
                                        icon=ft.icons.ADD_SHOPPING_CART_ROUNDED,
                                        icon_color=ft.colors.WHITE,
                                        bgcolor="#4F46E5",
                                        icon_size=18,
                                        width=36,
                                        height=36,
                                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=9)),
                                        tooltip="افزودن به سبد",
                                        on_click=add_to_cart_click
                                    )
                                ]
                            )
                        ]
                    )
                )
                cashier_products_col.controls.append(card)
        page.update()

    def update_cart_ui():
        cart_items_col.controls.clear()
        total_invoice = 0

        if not cart:
            cart_items_col.controls.append(
                ft.Container(
                    content=ft.Text("سبد خرید فعلاً خالی است", color=ft.colors.BLUE_GREY_300, size=11),
                    alignment=ft.alignment.center,
                    padding=18
                )
            )
        else:
            for idx, item in enumerate(cart):
                row_total = item["sell_price"] * item["qty"]
                total_invoice += row_total

                def remove_item_confirm(e, index=idx):
                    target_name = cart[index]["name"]
                    def do_remove():
                        cart.pop(index)
                        update_cart_ui()
                        show_snackbar(f"«{target_name}» از سبد حذف شد.", ft.colors.ORANGE_700)

                    show_confirm_dialog(
                        "حذف آیتم از سبد خرید",
                        f"آیا مطمئن هستید که می‌خواهید «{target_name}» را از سبد خرید فعلی حذف کنید؟",
                        do_remove
                    )

                cart_items_col.controls.append(
                    ft.Container(
                        bgcolor="#F8FAFC",
                        border=ft.border.all(1, "#E2E8F0"),
                        border_radius=8,
                        padding=ft.padding.symmetric(horizontal=8, vertical=3),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text(f"{item['name']}  ×{item['qty']}", size=11, font_family="Vazir-Bold", color=ft.colors.BLUE_GREY_800, expand=True),
                                ft.Text(f"{format_price(row_total)} ت", size=11, color="#4338CA", font_family="Vazir-Bold"),
                                ft.IconButton(
                                    icon=ft.icons.DELETE_OUTLINE_ROUNDED,
                                    icon_color=ft.colors.RED_500,
                                    icon_size=16,
                                    padding=0,
                                    width=24,
                                    height=24,
                                    tooltip="حذف از سبد",
                                    on_click=remove_item_confirm
                                )
                            ]
                        )
                    )
                )

        cart_total_text.value = f"{format_price(total_invoice)} تومان"
        page.update()

    def clear_cart_confirm(e):
        if not cart:
            return
        def do_clear():
            cart.clear()
            update_cart_ui()
            show_snackbar("سبد خرید خالی شد.", ft.colors.ORANGE_700)

        show_confirm_dialog(
            "خالی کردن سبد خرید",
            "آیا از حذف تمامی آیتم‌های موجود در سبد خرید فعلی مطمئن هستید؟",
            do_clear
        )

    def checkout_order(e):
        if not cart:
            show_snackbar("سبد خرید خالی است!", ft.colors.ORANGE_700)
            return

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        for item in cart:
            unit_profit = item["sell_price"] - item["cost_price"]
            for _ in range(item["qty"]):
                cursor.execute("""
                    INSERT INTO orders (product_name, sell_price, profit, order_date)
                    VALUES (?, ?, ?, ?)
                """, (item["name"], item["sell_price"], unit_profit, now_str))

        conn.commit()
        conn.close()

        cart.clear()
        update_cart_ui()
        show_snackbar("فاکتور با موفقیت در سیستم ثبت شد!", ft.colors.GREEN_700)

    def open_recent_orders_dialog(e):
        orders_list_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=330, width=330)

        def load_recent_orders():
            orders_list_col.controls.clear()
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("SELECT id, product_name, sell_price, order_date FROM orders ORDER BY id DESC LIMIT 25")
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                orders_list_col.controls.append(
                    ft.Container(
                        content=ft.Text("هیچ سفارشی ثبت نشده است.", color=ft.colors.BLUE_GREY_400, size=12),
                        alignment=ft.alignment.center,
                        padding=30
                    )
                )
            else:
                for r in rows:
                    o_id, o_name, o_price, o_date = r
                    jalali_dt = format_jalali_datetime(o_date)

                    def ask_delete_order(e, order_id=o_id, prod_name=o_name):
                        def confirmed_delete():
                            conn_del = sqlite3.connect(DB_NAME)
                            cur_del = conn_del.cursor()
                            cur_del.execute("DELETE FROM orders WHERE id = ?", (order_id,))
                            conn_del.commit()
                            conn_del.close()
                            load_recent_orders()
                            load_dashboard_data()
                            show_snackbar(f"فاکتور #{order_id} ({prod_name}) لغو و حذف شد.", ft.colors.RED_700)

                        show_confirm_dialog(
                            "لغو و حذف فاکتور",
                            f"آیا از لغو و حذف سفارش شماره #{order_id} «{prod_name}» به مبلغ {format_price(o_price)} تومان مطمئن هستید؟",
                            confirmed_delete
                        )

                    orders_list_col.controls.append(
                        ft.Container(
                            bgcolor="#F8FAFC",
                            border=ft.border.all(1, "#E2E8F0"),
                            border_radius=10,
                            padding=10,
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Column(
                                        spacing=2,
                                        controls=[
                                            ft.Text(f"#{o_id} - {o_name}", size=12, font_family="Vazir-Bold", color=ft.colors.BLUE_GREY_900),
                                            ft.Text(f"{format_price(o_price)} تومان  |  {jalali_dt}", size=10, color=ft.colors.BLUE_GREY_500)
                                        ]
                                    ),
                                    ft.IconButton(
                                        icon=ft.icons.DELETE_FOREVER_ROUNDED,
                                        icon_color=ft.colors.RED_600,
                                        bgcolor=ft.colors.RED_50,
                                        icon_size=18,
                                        width=34,
                                        height=34,
                                        tooltip="لغو این سفارش",
                                        on_click=ask_delete_order
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
                    ft.Icon(ft.icons.HISTORY_ROUNDED, color=ft.colors.ORANGE_700, size=22),
                    ft.Text("فاکتورهای اخیر (لغو سفارش)", size=14, font_family="Vazir-Bold"),
                ]
            ),
            content=orders_list_col,
            bgcolor=ft.colors.WHITE,
            surface_tint_color=ft.colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=16),
            actions=[
                ft.TextButton("بستن پنجره", on_click=lambda e: close_dialog(dlg))
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def close_dialog(dlg):
        dlg.open = False
        page.update()

    cashier_view = ft.Container(
        padding=12,
        expand=True,
        content=ft.Column(
            spacing=8,
            expand=True,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=6,
                            controls=[
                                ft.Icon(ft.icons.STOREFRONT_ROUNDED, color="#4338CA", size=21),
                                ft.Text("صندوق فروش", size=15, font_family="Vazir-Bold", color=ft.colors.BLUE_GREY_900),
                            ]
                        ),
                        ft.ElevatedButton(
                            "لغو فاکتورهای پیشین",
                            icon=ft.icons.RESTORE_FROM_TRASH_ROUNDED,
                            bgcolor=ft.colors.RED_50,
                            color=ft.colors.RED_700,
                            elevation=0,
                            height=32,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=8),
                                text_style=ft.TextStyle(size=11, font_family="Vazir-Bold")
                            ),
                            on_click=open_recent_orders_dialog
                        )
                    ]
                ),
                cashier_products_col,
                ft.Container(
                    bgcolor=ft.colors.WHITE,
                    border_radius=14,
                    padding=11,
                    border=ft.border.all(1, "#E0E7FF"),
                    shadow=ft.BoxShadow(blur_radius=12, color=ft.colors.with_opacity(0.08, ft.colors.BLACK), offset=ft.Offset(0, -2)),
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row(
                                        spacing=5,
                                        controls=[
                                            ft.Icon(ft.icons.SHOPPING_CART_CHECKOUT_ROUNDED, size=16, color="#4338CA"),
                                            ft.Text("سبد خرید فعلی", size=12, font_family="Vazir-Bold", color=ft.colors.BLUE_GREY_800),
                                        ]
                                    ),
                                    ft.TextButton(
                                        "خالی کردن سبد",
                                        style=ft.ButtonStyle(color=ft.colors.RED_600, padding=0),
                                        on_click=clear_cart_confirm
                                    )
                                ]
                            ),
                            cart_items_col,
                            ft.Divider(height=1, color=ft.colors.BLUE_GREY_100),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Column(
                                        spacing=0,
                                        controls=[
                                            ft.Text("مبلغ قابل پرداخت:", size=10, color=ft.colors.BLUE_GREY_500),
                                            cart_total_text
                                        ]
                                    ),
                                    ft.ElevatedButton(
                                        "ثبت نهایی فاکتور",
                                        icon=ft.icons.TASK_ALT_ROUNDED,
                                        bgcolor="#059669",
                                        color=ft.colors.WHITE,
                                        height=40,
                                        style=ft.ButtonStyle(
                                            shape=ft.RoundedRectangleBorder(radius=10),
                                            text_style=ft.TextStyle(size=12, font_family="Vazir-Bold")
                                        ),
                                        on_click=checkout_order
                                    )
                                ]
                            )
                        ]
                    )
                )
            ]
        )
    )

    # 2. مدیریت منو
    name_input = ft.TextField(
        label="نام محصول",
        height=44,
        text_size=12,
        content_padding=ft.padding.symmetric(horizontal=10, vertical=6),
        border_radius=9,
        border_color=ft.colors.BLUE_GREY_200,
        expand=1
    )
    category_dropdown = ft.Dropdown(
        label="دسته‌بندی",
        height=44,
        text_size=12,
        content_padding=ft.padding.symmetric(horizontal=10, vertical=6),
        border_radius=9,
        border_color=ft.colors.BLUE_GREY_200,
        expand=1,
        value="قهوه و اسپرسو",
        options=[
            ft.dropdown.Option("قهوه و اسپرسو"),
            ft.dropdown.Option("نوشیدنی گرم"),
            ft.dropdown.Option("نوشیدنی سرد"),
            ft.dropdown.Option("کیک و دسر"),
            ft.dropdown.Option("غذا و اسنک"),
        ]
    )
    cost_input = ft.TextField(
        label="قیمت خرید/مایه (تومان)",
        height=44,
        text_size=12,
        keyboard_type=ft.KeyboardType.NUMBER,
        content_padding=ft.padding.symmetric(horizontal=10, vertical=6),
        border_radius=9,
        border_color=ft.colors.BLUE_GREY_200,
        expand=1
    )
    sell_input = ft.TextField(
        label="قیمت فروش (تومان)",
        height=44,
        text_size=12,
        keyboard_type=ft.KeyboardType.NUMBER,
        content_padding=ft.padding.symmetric(horizontal=10, vertical=6),
        border_radius=9,
        border_color=ft.colors.BLUE_GREY_200,
        expand=1
    )

    submit_product_btn = ft.ElevatedButton(
        "ذخیره محصول",
        icon=ft.icons.CHECK_CIRCLE_ROUNDED,
        bgcolor="#4F46E5",
        color=ft.colors.WHITE,
        expand=True,
        height=42,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=9),
            text_style=ft.TextStyle(size=12, font_family="Vazir-Bold")
        )
    )

    cancel_edit_btn = ft.IconButton(
        icon=ft.icons.CLOSE_ROUNDED,
        icon_color=ft.colors.RED_600,
        bgcolor=ft.colors.RED_50,
        width=42,
        height=42,
        tooltip="بستن فرم / انصراف",
    )

    menu_products_col = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)

    add_form_container = ft.Container(
        visible=False,
        bgcolor=ft.colors.WHITE,
        border_radius=14,
        padding=12,
        border=ft.border.all(1, "#E0E7FF"),
        shadow=ft.BoxShadow(blur_radius=8, color=ft.colors.with_opacity(0.05, ft.colors.BLACK), offset=ft.Offset(0, 2)),
        content=ft.Column(
            spacing=10,
            controls=[
                ft.Row(spacing=8, controls=[name_input, category_dropdown]),
                ft.Row(spacing=8, controls=[cost_input, sell_input]),
                ft.Row(spacing=8, controls=[submit_product_btn, cancel_edit_btn])
            ]
        )
    )

    show_add_form_btn = ft.ElevatedButton(
        "افزودن محصول جدید",
        icon=ft.icons.ADD_ROUNDED,
        bgcolor="#EEF2FF",
        color="#4338CA",
        elevation=0,
        height=40,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            text_style=ft.TextStyle(size=12, font_family="Vazir-Bold")
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
        category_dropdown.value = "قهوه و اسپرسو"
        cost_input.value = ""
        sell_input.value = ""
        submit_product_btn.text = "ذخیره محصول"
        submit_product_btn.icon = ft.icons.CHECK_CIRCLE_ROUNDED
        submit_product_btn.bgcolor = "#4F46E5"
        toggle_form(False)

    cancel_edit_btn.on_click = lambda e: reset_menu_form()

    def save_or_update_product(e):
        nonlocal editing_product_id
        name = name_input.value.strip()
        cat = category_dropdown.value
        cost_str = cost_input.value.strip()
        sell_str = sell_input.value.strip()

        if not name or not cost_str or not sell_str:
            show_snackbar("لطفاً تمام فیلدها را پر کنید!", ft.colors.RED_700)
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
            show_snackbar(f"محصول «{name}» با موفقیت ثبت شد.", ft.colors.GREEN_700)
        else:
            cursor.execute("""
                UPDATE products
                SET name = ?, category = ?, cost_price = ?, sell_price = ?
                WHERE id = ?
            """, (name, cat, cost_val, sell_val, editing_product_id))
            show_snackbar(f"محصول «{name}» بروزرسانی شد.", ft.colors.ORANGE_700)

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

        if not rows:
            menu_products_col.controls.append(
                ft.Container(
                    content=ft.Text("هنوز محصولی در منو ثبت نشده است.", color=ft.colors.BLUE_GREY_400, size=12),
                    alignment=ft.alignment.center,
                    padding=25
                )
            )
        else:
            for r in rows:
                p_id, p_name, p_cat, p_cost, p_sell = r
                cat_icon, cat_color, cat_bg = get_category_style(p_cat)

                def edit_click(e, prod=r):
                    nonlocal editing_product_id
                    editing_product_id = prod[0]
                    name_input.value = prod[1]
                    category_dropdown.value = prod[2]
                    cost_input.value = str(int(prod[3]))
                    sell_input.value = str(int(prod[4]))
                    submit_product_btn.text = "ذخیره تغییرات"
                    submit_product_btn.icon = ft.icons.UPDATE_ROUNDED
                    submit_product_btn.bgcolor = ft.colors.ORANGE_600
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
                    border_radius=12,
                    padding=10,
                    border=ft.border.all(1, "#EEF2FF"),
                    shadow=ft.BoxShadow(blur_radius=5, color=ft.colors.with_opacity(0.04, ft.colors.BLACK), offset=ft.Offset(0, 2)),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                spacing=10,
                                controls=[
                                    ft.Container(
                                        content=ft.Icon(cat_icon, color=cat_color, size=19),
                                        bgcolor=cat_bg,
                                        padding=8,
                                        border_radius=9
                                    ),
                                    ft.Column(
                                        spacing=3,
                                        controls=[
                                            ft.Row(
                                                spacing=6,
                                                controls=[
                                                    ft.Text(p_name, font_family="Vazir-Bold", size=13, color=ft.colors.BLUE_GREY_900),
                                                    ft.Container(
                                                        content=ft.Text(p_cat, size=9, color=cat_color),
                                                        bgcolor=cat_bg,
                                                        padding=ft.padding.symmetric(horizontal=6, vertical=1),
                                                        border_radius=4
                                                    )
                                                ]
                                            ),
                                            ft.Text(
                                                f"مایه: {format_price(p_cost)}  |  فروش: {format_price(p_sell)}  (سود: {format_price(p_sell - p_cost)} ت)",
                                                size=10,
                                                color=ft.colors.BLUE_GREY_600
                                            )
                                        ]
                                    ),
                                ]
                            ),
                            ft.Row(
                                spacing=4,
                                controls=[
                                    ft.IconButton(
                                        icon=ft.icons.EDIT_NOTE_ROUNDED,
                                        icon_color=ft.colors.BLUE_700,
                                        bgcolor=ft.colors.BLUE_50,
                                        icon_size=18,
                                        width=32,
                                        height=32,
                                        tooltip="ویرایش",
                                        on_click=edit_click
                                    ),
                                    ft.IconButton(
                                        icon=ft.icons.DELETE_OUTLINE_ROUNDED,
                                        icon_color=ft.colors.RED_600,
                                        bgcolor=ft.colors.RED_50,
                                        icon_size=18,
                                        width=32,
                                        height=32,
                                        tooltip="حذف",
                                        on_click=delete_click
                                    )
                                ]
                            )
                        ]
                    )
                )
                menu_products_col.controls.append(card)
        page.update()

    menu_view = ft.Container(
        padding=12,
        expand=True,
        content=ft.Column(
            spacing=10,
            expand=True,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=6,
                            controls=[
                                ft.Icon(ft.icons.MENU_BOOK_ROUNDED, color="#4338CA", size=21),
                                ft.Text("مدیریت آیتم‌های منو", size=15, font_family="Vazir-Bold", color=ft.colors.BLUE_GREY_900),
                            ]
                        ),
                        show_add_form_btn
                    ]
                ),
                add_form_container,
                ft.Text("لیست محصولات موجود:", size=12, font_family="Vazir-Bold", color=ft.colors.BLUE_GREY_800),
                menu_products_col
            ]
        )
    )

    # 3. داشبورد و تقویم
    total_revenue_text = ft.Text("0", size=13, font_family="Vazir-Bold", color="#1E40AF")
    total_cost_text = ft.Text("0", size=13, font_family="Vazir-Bold", color="#B45309")
    net_profit_text = ft.Text("0", size=13, font_family="Vazir-Bold", color="#047857")
    period_summary_badge = ft.Text("0 سفارش ثبت‌شده", size=11, font_family="Vazir-Bold", color="#4338CA")

    report_items_col = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
    mode_selector_row = ft.Row(spacing=6, alignment=ft.MainAxisAlignment.CENTER)
    date_navigator_container = ft.Container()

    def create_stat_card(title: str, value_control: ft.Text, icon_name: str, icon_color: str, badge_bg: str, border_col: str):
        return ft.Container(
            expand=1,
            bgcolor=ft.colors.WHITE,
            border_radius=14,
            padding=ft.padding.symmetric(horizontal=6, vertical=10),
            border=ft.border.all(1, border_col),
            shadow=ft.BoxShadow(blur_radius=8, color=ft.colors.with_opacity(0.05, ft.colors.BLACK), offset=ft.Offset(0, 3)),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=5,
                controls=[
                    ft.Container(
                        content=ft.Icon(icon_name, color=icon_color, size=24),
                        bgcolor=badge_bg,
                        padding=9,
                        border_radius=12
                    ),
                    ft.Text(title, size=10, color=ft.colors.BLUE_GREY_600, font_family="Vazir-Bold"),
                    value_control,
                    ft.Text("تومان", size=9, color=ft.colors.BLUE_GREY_400)
                ]
            )
        )

    def open_jalali_calendar_dialog(e):
        nonlocal selected_date
        cur_jy, cur_jm, cur_jd = gregorian_to_jalali(selected_date.year, selected_date.month, selected_date.day)
        cal_state = {"jy": cur_jy, "jm": cur_jm, "jd": cur_jd}

        cal_header_text = ft.Text("", size=14, font_family="Vazir-Bold", color="#312E81")
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

                btn_bg = "#4F46E5" if is_selected else (ft.colors.AMBER_100 if is_today else "#F1F5F9")
                btn_col = ft.colors.WHITE if is_selected else (ft.colors.AMBER_900 if is_today else ft.colors.BLUE_GREY_800)

                row_buttons.append(
                    ft.Container(
                        width=40,
                        height=36,
                        bgcolor=btn_bg,
                        border_radius=8,
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
            shape=ft.RoundedRectangleBorder(radius=18),
            bgcolor=ft.colors.WHITE,
            surface_tint_color=ft.colors.WHITE,
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.IconButton(ft.icons.CHEVRON_RIGHT_ROUNDED, on_click=lambda e: change_cal_month(-1), tooltip="ماه قبل"),
                    cal_header_text,
                    ft.IconButton(ft.icons.CHEVRON_LEFT_ROUNDED, on_click=lambda e: change_cal_month(1), tooltip="ماه بعد"),
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
                            color="#4338CA",
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
            ("day", "روزانه (انتخاب روز)", ft.icons.TODAY_ROUNDED),
            ("month", "ماهانه (آمار ماه)", ft.icons.CALENDAR_MONTH_ROUNDED),
            ("all", "کل تاریخچه", ft.icons.ALL_INCLUSIVE_ROUNDED),
        ]
        mode_selector_row.controls.clear()
        for m_key, m_label, m_icon in modes:
            is_active = (filter_mode == m_key)
            mode_selector_row.controls.append(
                ft.ElevatedButton(
                    m_label,
                    icon=m_icon,
                    bgcolor="#4F46E5" if is_active else ft.colors.WHITE,
                    color=ft.colors.WHITE if is_active else ft.colors.BLUE_GREY_700,
                    elevation=2 if is_active else 0,
                    height=34,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=9),
                        padding=ft.padding.symmetric(horizontal=10, vertical=0),
                        text_style=ft.TextStyle(size=11, font_family="Vazir-Bold")
                    ),
                    on_click=lambda e, k=m_key: switch_filter_mode(k)
                )
            )

        if filter_mode == "day":
            jy, jm, jd = gregorian_to_jalali(selected_date.year, selected_date.month, selected_date.day)
            is_today_selected = (jy == today_jy and jm == today_jm and jd == today_jd)
            day_label = f"امروز، {jd} {JALALI_MONTHS[jm - 1]} {jy}" if is_today_selected else f"{jd} {JALALI_MONTHS[jm - 1]} {jy}"

            date_navigator_container.content = ft.Container(
                bgcolor=ft.colors.WHITE,
                border_radius=12,
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                border=ft.border.all(1, "#E0E7FF"),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.IconButton(
                            icon=ft.icons.CHEVRON_RIGHT_ROUNDED,
                            icon_color="#4338CA",
                            bgcolor="#EEF2FF",
                            icon_size=20,
                            width=32,
                            height=32,
                            tooltip="روز قبل",
                            on_click=lambda e: step_day(-1)
                        ),
                        ft.Container(
                            on_click=open_jalali_calendar_dialog,
                            border_radius=8,
                            padding=ft.padding.symmetric(horizontal=10, vertical=4),
                            content=ft.Row(
                                spacing=6,
                                controls=[
                                    ft.Icon(ft.icons.EDIT_CALENDAR_ROUNDED, color="#4F46E5", size=17),
                                    ft.Text(day_label, size=12, font_family="Vazir-Bold", color=ft.colors.BLUE_GREY_900),
                                    ft.Text("(انتخاب از تقویم)", size=10, color="#4F46E5"),
                                ]
                            )
                        ),
                        ft.IconButton(
                            icon=ft.icons.CHEVRON_LEFT_ROUNDED,
                            icon_color="#4338CA",
                            bgcolor="#EEF2FF",
                            icon_size=20,
                            width=32,
                            height=32,
                            tooltip="روز بعد",
                            on_click=lambda e: step_day(1)
                        ),
                    ]
                )
            )
        elif filter_mode == "month":
            month_title = f"آمار ماه {JALALI_MONTHS[selected_j_month - 1]} {selected_j_year}"
            date_navigator_container.content = ft.Container(
                bgcolor=ft.colors.WHITE,
                border_radius=12,
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                border=ft.border.all(1, "#E0E7FF"),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.IconButton(
                            icon=ft.icons.CHEVRON_RIGHT_ROUNDED,
                            icon_color="#4338CA",
                            bgcolor="#EEF2FF",
                            icon_size=20,
                            width=32,
                            height=32,
                            tooltip="ماه قبل",
                            on_click=lambda e: step_month(-1)
                        ),
                        ft.Row(
                            spacing=6,
                            controls=[
                                ft.Icon(ft.icons.DATE_RANGE_ROUNDED, color="#4F46E5", size=18),
                                ft.Text(month_title, size=13, font_family="Vazir-Bold", color="#1E1B4B"),
                            ]
                        ),
                        ft.IconButton(
                            icon=ft.icons.CHEVRON_LEFT_ROUNDED,
                            icon_color="#4338CA",
                            bgcolor="#EEF2FF",
                            icon_size=20,
                            width=32,
                            height=32,
                            tooltip="ماه بعد",
                            on_click=lambda e: step_month(1)
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
                content=ft.Text("نمایش تجمیعی تمام تراکنش‌های ثبت‌شده از ابتدا", size=11, font_family="Vazir-Bold", color="#4338CA")
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

        total_revenue_text.value = format_price(total_rev)
        total_cost_text.value = format_price(total_cost)
        net_profit_text.value = format_price(total_prof)
        period_summary_badge.value = f"{total_count} عدد فروش در این بازه"

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
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                        controls=[
                            ft.Icon(ft.icons.EVENT_BUSY_ROUNDED, size=36, color=ft.colors.BLUE_GREY_200),
                            ft.Text("در این بازه زمانی هیچ سفارشی ثبت نشده است.", color=ft.colors.BLUE_GREY_400, size=12),
                        ]
                    ),
                    alignment=ft.alignment.center,
                    padding=30
                )
            )
        else:
            for r in rows:
                p_name, p_qty, p_sale, p_prof = r
                card = ft.Container(
                    bgcolor=ft.colors.WHITE,
                    border_radius=12,
                    padding=12,
                    border=ft.border.all(1, "#EEF2FF"),
                    shadow=ft.BoxShadow(blur_radius=5, color=ft.colors.with_opacity(0.04, ft.colors.BLACK), offset=ft.Offset(0, 2)),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                spacing=10,
                                controls=[
                                    ft.Container(
                                        content=ft.Text(f"{p_qty}×", color=ft.colors.WHITE, font_family="Vazir-Bold", size=12),
                                        bgcolor="#4F46E5",
                                        padding=ft.padding.symmetric(horizontal=9, vertical=6),
                                        border_radius=9
                                    ),
                                    ft.Column(
                                        spacing=2,
                                        controls=[
                                            ft.Text(p_name, font_family="Vazir-Bold", size=13, color=ft.colors.BLUE_GREY_900),
                                            ft.Text(f"فروش کل: {format_price(p_sale)} تومان", size=11, color=ft.colors.BLUE_GREY_500)
                                        ]
                                    )
                                ]
                            ),
                            ft.Container(
                                bgcolor="#ECFDF5",
                                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                                border_radius=8,
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
                    )
                )
                report_items_col.controls.append(card)
        page.update()

    dashboard_view = ft.Container(
        padding=12,
        expand=True,
        content=ft.Column(
            spacing=10,
            expand=True,
            controls=[
                mode_selector_row,
                date_navigator_container,
                ft.Row(
                    spacing=8,
                    controls=[
                        create_stat_card("درآمد کل", total_revenue_text, ft.icons.MONETIZATION_ON_ROUNDED, "#2563EB", "#DBEAFE", "#BFDBFE"),
                        create_stat_card("هزینه مایه", total_cost_text, ft.icons.INVENTORY_2_ROUNDED, "#D97706", "#FEF3C7", "#FDE68A"),
                        create_stat_card("سود خالص", net_profit_text, ft.icons.DIAMOND_ROUNDED, "#059669", "#D1FAE5", "#A7F3D0"),
                    ]
                ),
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("تفکیک فروش هر محصول:", size=12, font_family="Vazir-Bold", color=ft.colors.BLUE_GREY_800),
                        ft.Container(
                            bgcolor="#EEF2FF",
                            padding=ft.padding.symmetric(horizontal=8, vertical=3),
                            border_radius=12,
                            content=period_summary_badge
                        )
                    ]
                ),
                report_items_col
            ]
        )
    )

    body_container = ft.Container(content=cashier_view, expand=True)

    def on_nav_change(e):
        idx = e.control.selected_index
        if idx == 0:
            load_cashier_products()
            body_container.content = cashier_view
        elif idx == 1:
            load_menu_products()
            body_container.content = menu_view
        elif idx == 2:
            update_dashboard_controls()
            load_dashboard_data()
            body_container.content = dashboard_view
        page.update()

    page.navigation_bar = ft.NavigationBar(
        selected_index=0,
        height=65,
        bgcolor=ft.colors.WHITE,
        surface_tint_color=ft.colors.WHITE,
        indicator_color="#E0E7FF",
        elevation=10,
        on_change=on_nav_change,
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.icons.STOREFRONT_OUTLINED,
                selected_icon=ft.icons.STOREFRONT_ROUNDED,
                label="صندوق فروش"
            ),
            ft.NavigationBarDestination(
                icon=ft.icons.MENU_BOOK_OUTLINED,
                selected_icon=ft.icons.MENU_BOOK_ROUNDED,
                label="مدیریت منو"
            ),
            ft.NavigationBarDestination(
                icon=ft.icons.PIE_CHART_OUTLINE_ROUNDED,
                selected_icon=ft.icons.PIE_CHART_ROUNDED,
                label="داشبورد و تقویم"
            ),
        ]
    )

    load_cashier_products()
    update_cart_ui()
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
