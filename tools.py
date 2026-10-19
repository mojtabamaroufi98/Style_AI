import requests
from typing import List

from models import Product


DIGISTYLE_API = "https://api.digistyle.com/v1/search/"

DIGISTYLE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/155.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "X-Client": "web",
    "Referer": "https://www.digistyle.com/",
    "Origin": "https://www.digistyle.com",
}


# -----------------------------------------------------
# Color normalization
# -----------------------------------------------------

COLOR_ALIASES = {

    "مشکی": [
        "مشکی",
        "ذغالی",
        "زغالی",
        "نوک مدادی",
        "دودی",
        "سیاه",
    ],

    "سفید": [
        "سفید",
        "شیری",
        "استخوانی",
        "سفید استخوانی",
        "سفید شیری",
    ],

    "بژ": [
        "بژ",
        "کرم",
        "نخودی",
        "کرم روشن",
        "بژ روشن",
        "بژ تیره",
    ],

    "قهوه‌ای": [
        "قهوه‌ای",
        "قهوه ای",
        "شکلاتی",
        "کاراملی",
        "کاراملی",
        "نسکافه‌ای",
        "نسکافه ای",
    ],

    "زیتونی": [
        "زیتونی",
        "زیتونی روشن",
        "زیتونی تیره",
        "سبز زیتونی",
    ],

    "سرمه‌ای": [
        "سرمه‌ای",
        "سرمه ای",
        "سرمه‌ای تیره",
        "آبی سرمه‌ای",
        "آبی سرمه ای",
    ],

    "قرمز": [
        "قرمز",
        "زرشکی",
        "عنابی",
        "آلبالویی",
        "قرمز تیره",
    ],

    "صورتی": [
        "صورتی",
        "گلبهی",
        "رز",
        "صورتی روشن",
        "صورتی چرک",
        "صورتی پاستلی",
    ],

    "طلایی": [
        "طلایی",
        "طلایی روشن",
        "طلایی تیره",
    ],
}


def normalize_color(color: str) -> str:

    if not color:
        return ""

    normalized = (
        str(color)
        .strip()
        .lower()
    )

    for canonical, aliases in COLOR_ALIASES.items():

        for alias in aliases:

            if alias.lower() in normalized:
                return canonical

    return normalized


def normalize_colors(
    colors: List[str]
) -> List[str]:

    normalized_colors = set()

    for color in colors:

        normalized = normalize_color(
            color
        )

        if normalized:
            normalized_colors.add(
                normalized
            )

    return sorted(
        normalized_colors
    )


# -----------------------------------------------------
# Product validation
# -----------------------------------------------------

def is_relevant_product(
    raw: dict,
    query: str
) -> bool:

    title = raw.get("title_fa") or ""

    category_data = raw.get("category") or {}

    if isinstance(category_data, dict):
        category = (
            category_data.get("title_fa")
            or category_data.get("title")
            or ""
        )
    else:
        category = str(category_data)

    brand_data = raw.get("brand") or {}

    if isinstance(brand_data, dict):
        brand = (
            brand_data.get("title_fa")
            or brand_data.get("title")
            or ""
        )
    else:
        brand = str(brand_data)

    search_text = (
        f"{title} "
        f"{category} "
        f"{brand}"
    ).lower()

    query_text = query.lower()

    # -------------------------------------------------
    # محصولات کاملاً نامرتبط
    # -------------------------------------------------

    forbidden_keywords = [
        "لباس خواب زنانه",
        "لباس خواب",
        "لباس زیر زنانه",
        "سوتین",
        "شورت زنانه",
        "تاپ زنانه",
        "پیراهن زنانه",
        "زنانه",
    ]

    for keyword in forbidden_keywords:

        if keyword in search_text:

            # اگر خود query صراحتاً زنانه باشد،
            # محصول زنانه نباید به خاطر این فیلتر حذف شود.
            if (
                keyword == "زنانه"
                and (
                    "زنانه" in query_text
                    or "زن" in query_text
                )
            ):
                continue

            print(
                f"[PRODUCT FILTER] rejected={title} "
                f"| reason={keyword}"
            )

            return False

    # -------------------------------------------------
    # حذف محصولات کودک و نوزاد
    #
    # این فیلتر مستقل از query است.
    # چون queryهایی مثل «تیشرت مینیمال»
    # ممکن است محصول نوزادی هم برگردانند.
    # -------------------------------------------------

    child_keywords = [
        "نوزادی",
        "نوزاد",
        "بچگانه",
        "بچه‌گانه",
        "بچه گانه",
        "کودک",
        "کودکان",
        "دخترانه",
        "پسرانه",
    ]

    for keyword in child_keywords:

        if keyword in search_text:

            print(
                f"[PRODUCT FILTER] rejected={title} "
                f"| reason={keyword}"
            )

            return False

    # -------------------------------------------------
    # اگر جستجو مردانه است
    # -------------------------------------------------

    if (
        "مردانه" in query_text
        or "مرد" in query_text
    ):

        if "زنانه" in search_text:

            print(
                f"[PRODUCT FILTER] rejected={title} "
                f"| reason=زنانه"
            )

            return False

    # -------------------------------------------------
    # اگر جستجو زنانه است
    # -------------------------------------------------

    if (
        "زنانه" in query_text
        or "زن" in query_text
    ):

        if "مردانه" in search_text:

            print(
                f"[PRODUCT FILTER] rejected={title} "
                f"| reason=مردانه"
            )

            return False

    return True


# -----------------------------------------------------
# Digistyle search
# -----------------------------------------------------

def search_products(
    query: str,
    min_price: int | None = None,
    max_price: int | None = None,
) -> List[Product]:

    print(
        f"[PRODUCT SEARCH] query={query}, "
        f"min_price={min_price}, max_price={max_price}"
    )

    params = {
        "q": query,
        "page": 1,
        "rows": 20,
    }

    response = requests.get(
        DIGISTYLE_API,
        headers=DIGISTYLE_HEADERS,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    widgets = data.get(
        "data",
        {}
    ).get(
        "widgets",
        []
    )

    products = []

    for widget in widgets:

        if widget.get("type") != "products":
            continue

        widget_data = widget.get(
            "data",
            {}
        )

        raw_products = widget_data.get(
            "products",
            []
        )

        for raw in raw_products:

            if raw.get("status") != "marketable":
                continue

            # -------------------------------------------------
            # فیلتر ارتباط محصول با درخواست
            # -------------------------------------------------

            if not is_relevant_product(
                raw,
                query
            ):
                continue

            price_data = raw.get("price") or {}

            price = price_data.get(
                "selling_price"
            )

            old_price = price_data.get(
                "rrp_price"
            )

            if price is None:
                continue

            if (
                min_price is not None
                and price < min_price
            ):
                continue

            if (
                max_price is not None
                and price > max_price
            ):
                continue

            # -------------------------------------------------
            # Variant information
            # -------------------------------------------------

            sizes = set()
            colors = set()

            for variant in raw.get(
                "variants",
                []
            ):

                if variant.get(
                    "status"
                ) != "marketable":
                    continue

                # ---------------------------------------------
                # Size title
                # ---------------------------------------------

                size = variant.get(
                    "size"
                )

                if isinstance(
                    size,
                    dict
                ):

                    size_title = size.get(
                        "title"
                    )

                    if size_title:

                        if " - " in size_title:

                            color_part, size_part = (
                                size_title.rsplit(
                                    " - ",
                                    1
                                )
                            )

                            if color_part:
                                colors.add(
                                    color_part.strip()
                                )

                            if size_part:
                                sizes.add(
                                    size_part.strip()
                                )

                # ---------------------------------------------
                # Themes
                # ---------------------------------------------

                for theme in variant.get(
                    "themes",
                    []
                ):

                    value = theme.get(
                        "value"
                    ) or {}

                    nature = value.get(
                        "nature"
                    )

                    if nature == "alpha":

                        value_title = value.get(
                            "title"
                        )

                        if value_title:
                            sizes.add(
                                value_title.strip()
                            )

                    elif nature == "color":

                        color_title = value.get(
                            "title"
                        )

                        if color_title:
                            colors.add(
                                color_title.strip()
                            )

            # -------------------------------------------------
            # Product URL
            # -------------------------------------------------

            product_url = raw.get(
                "url"
            )

            if isinstance(
                product_url,
                dict
            ):

                product_path = product_url.get(
                    "url"
                )

            else:

                product_path = product_url

            if (
                product_path
                and product_path.startswith("/")
            ):

                product_url = (
                    "https://www.digistyle.com"
                    + product_path
                )

            else:

                product_url = product_path

            # -------------------------------------------------
            # Product
            # -------------------------------------------------

            products.append(
                Product(

                    id=str(
                        raw.get("id")
                    ),

                    name=raw.get(
                        "title_fa",
                        "محصول بدون نام"
                    ),

                    store="Digistyle",

                    price=int(price),

                    old_price=(
                        int(old_price)
                        if old_price is not None
                        else None
                    ),

                    url=product_url,

                    sizes=sorted(
                        sizes
                    ),

                    # توجه:
                    # رنگ واقعی Digistyle را نگه می‌داریم.
                    colors=sorted(
                        colors
                    ),

                    material=None,

                    match=None,

                    body_match=None,

                    note=(
                        f"برند: "
                        f"{(raw.get('brand') or {}).get('title_fa', '')}"
                    ),
                )
            )

    # -----------------------------------------------------
    # جلوگیری از تکرار محصول
    # -----------------------------------------------------

    unique_products = {}

    for product in products:

        unique_products[
            product.id
        ] = product

    result = list(
        unique_products.values()
    )

    print(
        f"[PRODUCT SEARCH] "
        f"found={len(result)} products"
    )

    return result


# -----------------------------------------------------
# Format products for AI
# -----------------------------------------------------

def format_products_for_ai(
    products: List[Product]
) -> str:

    if not products:
        return (
            "هیچ محصول واقعی از فروشگاه متصل "
            "دریافت نشده است.\n"
            "هرگز نام محصول، قیمت، لینک، فروشگاه، "
            "سایز، رنگ یا موجودی اختراع نکن."
        )

    lines = []

    for index, product in enumerate(products, start=1):

        sizes_text = (
            ", ".join(product.sizes)
            if product.sizes
            else "اطلاعات سایز موجود نیست"
        )

        colors_text = (
            ", ".join(product.colors)
            if product.colors
            else "اطلاعات رنگ موجود نیست"
        )

        material_text = (
            product.material
            if product.material
            else "اطلاعات جنس موجود نیست"
        )

        old_price_text = (
            str(product.old_price)
            if product.old_price is not None
            else "ندارد"
        )

        note_text = (
            product.note
            if product.note
            else "توضیح اضافی موجود نیست"
        )

        lines.append(
            f"""
محصول {index}
شناسه محصول: {product.id}

نام دقیق: {product.name}
فروشگاه: {product.store}
قیمت فعلی: {product.price}
قیمت قبلی: {old_price_text}
سایزهای ثبت‌شده: {sizes_text}
رنگ‌های ثبت‌شده: {colors_text}
جنس ثبت‌شده: {material_text}
لینک دقیق: {product.url}
توضیح ثبت‌شده: {note_text}
""".strip()
        )

    return (
        "اطلاعات زیر تنها منبع مجاز برای بیان مشخصات واقعی محصولات است.\n\n"
        + "\n\n".join(lines)
        + """

قوانین بسیار مهم:

1. فقط درباره محصولاتی صحبت کن که در همین فهرست وجود دارند.

2. نام محصول، فروشگاه، قیمت و لینک باید دقیقاً مطابق اطلاعات بالا باشند.

3. هر رنگ فقط زمانی قابل نسبت دادن به یک محصول است که همان رنگ در
«رنگ‌های ثبت‌شده» همان محصول وجود داشته باشد.

4. هر سایز فقط زمانی قابل نسبت دادن به یک محصول است که همان سایز در
«سایزهای ثبت‌شده» همان محصول وجود داشته باشد.

5. اگر رنگ‌های ثبت‌شده یا سایزهای ثبت‌شده خالی باشند، درباره موجود بودن
رنگ یا سایز ادعایی نکن.

6. اگر جنس ثبت‌شده «اطلاعات جنس موجود نیست» باشد، جنس محصول را حدس نزن.

7. مناسب بودن یک رنگ برای استایل کاربر به معنی موجود بودن آن رنگ در محصول نیست.
مثلاً اگر طوسی برای کاربر مناسب است اما طوسی در رنگ‌های ثبت‌شده محصول نیست،
نباید بگویی محصول در رنگ طوسی موجود است.

8. درباره موجودی، تخفیف، رنگ، سایز، جنس یا ویژگی‌ای که در اطلاعات بالا
وجود ندارد، حدس نزن.

9. می‌توانی درباره «پیشنهاد استایل» نظر تخصصی بدهی؛
اما نظر استایلی را با «ویژگی واقعی محصول» اشتباه نگیر.

10. اگر برای یک ویژگی اطلاعات واقعی نداریم، صریحاً بگو اطلاعات آن ویژگی
در داده محصول موجود نیست.

11. قیمت کل ست را فقط با جمع قیمت واقعی محصولات انتخاب‌شده محاسبه کن.
"""
    )