import os
import re
from itertools import product as itertools_product
from statistics import median
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

from models import UserProfile, Product
from tools import (
    search_products,
    format_products_for_ai,
)

load_dotenv()


# =========================================================
# AI CONFIG
# =========================================================

client = OpenAI(
    api_key=os.getenv("AI_API_KEY"),
    base_url=os.getenv("AI_BASE_URL"),
)

MODEL = os.getenv("AI_MODEL")


# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """
تو «StyleAI» هستی؛ یک استایلیست شخصی هوشمند برای کاربران ایرانی.

وظیفه تو:
- پیشنهاد استایل متناسب با پروفایل کاربر
- توجه به جنسیت، فرم بدن، قد، وزن، سایز
- توجه به استایل‌های مورد علاقه
- توجه به رنگ‌های مورد علاقه و رنگ‌های نامطلوب
- توجه به موقعیت استفاده
- توجه جدی به بودجه
- توجه به درخواست دقیق فعلی کاربر
- استفاده از محصولات واقعی فروشگاه‌های مجاز

قوانین بسیار مهم:

1. هرگز محصول، قیمت، لینک، برند، فروشگاه، سایز یا رنگی را اختراع نکن.
2. اطلاعات محصولات فقط از داده‌هایی است که ابزار جستجوی محصول برمی‌گرداند.
3. اگر محصول واقعی پیدا نشد، صادقانه بگو محصول مناسب پیدا نشد.
4. هرگز URL ساختگی تولید نکن.
5. قیمت‌ها را تغییر نده.
6. اگر محصولی فقط در سایز خاصی موجود است، همان را اعلام کن.
7. پاسخ فارسی و روان باشد.
8. پاسخ مربوط به استایل کوتاه و کاربردی باشد.
9. برای دانشگاه، مدرسه، روزمره و موقعیت‌های مشابه، لباس‌های بیش از حد رسمی را پیشنهاد نده مگر اینکه کاربر صراحتاً بخواهد.
10. اگر کاربر بودجه متوسط دارد، محصولات بسیار گران را فقط به دلیل کامل شدن ست انتخاب نکن.
11. اگر چند محصول مشابه وجود دارد، محصولی را ترجیح بده که از نظر قیمت، موقعیت و استایل منطقی‌تر است.
12. اولویت اصلی:
   درخواست دقیق فعلی کاربر
   سپس موقعیت
   سپس استایل
   سپس رنگ
   سپس بودجه
   سپس سایر عوامل.
13. اگر کاربر در پیام فعلی رنگ یا مدل خاصی خواست، همان درخواست فعلی نسبت به رنگ‌ها و ترجیحات عمومی پروفایل اولویت دارد.
14. در پاسخ نهایی مجموع قیمت واقعی محصولات انتخاب‌شده را حساب کن.
قوانین سخت‌گیرانه درباره محصولات واقعی:

- مشخصات هر محصول فقط از Product Context داده‌شده استخراج می‌شود.
- رنگ، سایز، جنس، قیمت، فروشگاه، نام و لینک را هرگز حدس نزن.
- رنگ یا سایز یک محصول فقط در صورتی قابل اعلام است که دقیقاً در داده همان محصول وجود داشته باشد.
- مناسب بودن یک رنگ برای کاربر به معنی موجود بودن آن رنگ در محصول نیست.
- اگر اطلاعات یک ویژگی در Product Context وجود ندارد، درباره آن ویژگی ادعای قطعی نکن.
- می‌توانی درباره هماهنگی و پیشنهاد استایل نظر بدهی، اما نباید نظر استایلی را به‌عنوان ویژگی واقعی محصول معرفی کنی.
- هیچ محصول، برند، قیمت، لینک یا موجودی جدیدی خارج از Product Context اضافه نکن.
"""


# =========================================================
# REQUEST INTENT
# =========================================================

class RequestIntent:
    def __init__(self):
        self.colors = []
        self.categories = []
        self.styles = []
        self.features = []
        self.occasions = []
        self.raw_terms = []

    def is_empty(self):
        return not any([
            self.colors,
            self.categories,
            self.styles,
            self.features,
            self.occasions,
        ])

    def __repr__(self):
        return (
            f"RequestIntent("
            f"colors={self.colors}, "
            f"categories={self.categories}, "
            f"styles={self.styles}, "
            f"features={self.features}, "
            f"occasions={self.occasions}"
            f")"
        )


# =========================================================
# REQUEST INTENT DICTIONARIES
# =========================================================

COLOR_TERMS = {
    "مشکی": ["مشکی", "سیاه", "بلک", "black"],
    "سفید": ["سفید", "سفیدرنگ", "white"],
    "طوسی": ["طوسی", "خاکستری", "gray", "grey"],
    "آبی": ["آبی", "blue"],
    "سرمه‌ای": ["سرمه‌ای", "سرمه ای", "سرمه", "navy"],
    "قرمز": ["قرمز", "red"],
    "سبز": ["سبز", "green"],
    "زیتونی": ["زیتونی", "سبز زیتونی", "olive"],
    "قهوه‌ای": ["قهوه‌ای", "قهوه ای", "قهوه‌یی", "brown"],
    "بژ": ["بژ", "کرم بژ", "beige"],
    "کرم": ["کرم", "cream"],
    "صورتی": ["صورتی", "pink"],
    "بنفش": ["بنفش", "purple"],
    "نارنجی": ["نارنجی", "orange"],
    "زرد": ["زرد", "yellow"],
    "آبی روشن": ["آبی روشن", "آبی کمرنگ"],
    "آبی تیره": ["آبی تیره"],
    "طوسی روشن": ["طوسی روشن", "خاکستری روشن"],
    "طوسی تیره": ["طوسی تیره", "خاکستری تیره"],
}

CATEGORY_TERMS = {
    "تیشرت": [
        "تیشرت",
        "تی‌شرت",
        "تی شرت",
        "t-shirt",
        "tshirt",
    ],
    "پولوشرت": [
        "پولوشرت",
        "پولو شرت",
        "polo",
    ],
    "پیراهن": [
        "پیراهن",
        "shirt",
    ],
    "شلوار": [
        "شلوار",
        "pants",
        "trousers",
    ],
    "هودی": [
        "هودی",
        "hoodie",
    ],
    "کفش": [
        "کفش",
        "کتانی",
        "اسنیکر",
        "sneaker",
        "shoes",
    ],
    "کت": [
        "کت",
        "blazer",
    ],
    "مانتو": [
        "مانتو",
    ],
    "دامن": [
        "دامن",
        "skirt",
    ],
    "شورت": [
        "شورت",
        "shorts",
    ],
    "کاپشن": [
        "کاپشن",
        "jacket",
    ],
}

STYLE_TERMS = {
    "مینیمال": [
        "مینیمال",
        "minimal",
        "minimalist",
    ],
    "کژوال": [
        "کژوال",
        "casual",
    ],
    "اسپرت": [
        "اسپرت",
        "sport",
        "اسپرتی",
    ],
    "رسمی": [
        "رسمی",
        "formal",
    ],
    "اسمارت کژوال": [
        "اسمارت کژوال",
        "smart casual",
    ],
    "خیابانی": [
        "خیابانی",
        "streetwear",
        "street",
    ],
    "کلاسیک": [
        "کلاسیک",
        "classic",
    ],
    "ساده": [
        "ساده",
        "basic",
    ]
}

FEATURE_TERMS = {
    "راسته": [
        "راسته",
        "straight",
        "straight fit",
    ],
    "اسلیم": [
        "اسلیم",
        "slim",
        "slim fit",
    ],
    "اسلیم فیت": [
        "اسلیم فیت",
        "slim fit",
    ],
    "اورسایز": [
        "اورسایز",
        "oversize",
        "oversized",
    ],
    "بگ": [
        "بگ",
        "baggy",
    ],
    "واید": [
        "واید",
        "wide",
        "wide leg",
    ],
    "مام فیت": [
        "مام فیت",
        "mom fit",
    ],
    "لوز": [
        "لوز",
        "loose",
    ],
    "ساده": [
        "ساده",
        "basic",
    ],
    "طرح‌دار": [
        "طرح دار",
        "طرح‌دار",
        "چاپ",
        "printed",
    ],
    "چهارخانه": [
        "چهارخانه",
        "چهارخونه",
        "checkered",
    ],
    "راه‌راه": [
        "راه راه",
        "راه‌راه",
        "راه راهه",
        "striped",
    ],
}

OCCASION_TERMS = {
    "دانشگاه": [
        "دانشگاه",
        "کلاس",
        "دانشجویی",
    ],
    "روزمره": [
        "روزمره",
        "روزانه",
        "everyday",
    ],
    "محل کار": [
        "محل کار",
        "سر کار",
        "محیط کار",
        "اداری",
        "office",
    ],
    "مهمانی": [
        "مهمانی",
        "مهمونی",
        "party",
    ],
    "قرار": [
        "قرار",
        "date",
    ],
    "سفر": [
        "سفر",
        "travel",
    ],
    "ورزش": [
        "ورزش",
        "باشگاه",
        "gym",
        "ورزشی",
    ],
}


# =========================================================
# TEXT NORMALIZATION
# =========================================================

def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = str(text).lower()

    replacements = {
        "ي": "ی",
        "ى": "ی",
        "ك": "ک",
        "ۀ": "ه",
        "ة": "ه",
        "‌": " ",
        "\u200c": " ",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


# =========================================================
# GENERIC TERM EXTRACTOR
# =========================================================

def extract_terms(
    text: str,
    dictionary: dict[str, list[str]],
) -> list[str]:

    normalized = normalize_text(text)

    found = []

    for canonical, aliases in dictionary.items():

        for alias in aliases:

            alias_normalized = normalize_text(alias)

            if alias_normalized in normalized:

                if canonical not in found:
                    found.append(canonical)

                break

    return found


# =========================================================
# REQUEST INTENT EXTRACTION
# =========================================================

def extract_request_intent(message: str) -> RequestIntent:

    intent = RequestIntent()

    normalized = normalize_text(message)

    intent.colors = extract_terms(
        normalized,
        COLOR_TERMS,
    )

    intent.categories = extract_terms(
        normalized,
        CATEGORY_TERMS,
    )

    intent.styles = extract_terms(
        normalized,
        STYLE_TERMS,
    )

    intent.features = extract_terms(
        normalized,
        FEATURE_TERMS,
    )

    intent.occasions = extract_terms(
        normalized,
        OCCASION_TERMS,
    )

    intent.raw_terms = []

    for group in [
        intent.colors,
        intent.categories,
        intent.styles,
        intent.features,
        intent.occasions,
    ]:
        for item in group:
            if item not in intent.raw_terms:
                intent.raw_terms.append(item)

    print("\n[REQUEST INTENT]")

    print(
        f"colors={intent.colors}"
    )

    print(
        f"categories={intent.categories}"
    )

    print(
        f"styles={intent.styles}"
    )

    print(
        f"features={intent.features}"
    )

    print(
        f"occasions={intent.occasions}"
    )

    return intent


# =========================================================
# PROFILE CONTEXT
# =========================================================

def build_profile_context(
    profile: Optional[UserProfile]
) -> str:

    if not profile:
        return "پروفایل کاربر در دسترس نیست."

    parts = []

    if profile.gender:
        parts.append(
            f"جنسیت: {profile.gender}"
        )

    if profile.body_shape:
        parts.append(
            f"فرم بدن: {profile.body_shape}"
        )

    if profile.height_cm:
        parts.append(
            f"قد: {profile.height_cm} سانتی‌متر"
        )

    if profile.weight_kg:
        parts.append(
            f"وزن: {profile.weight_kg} کیلوگرم"
        )

    if profile.size:
        parts.append(
            f"سایز: {profile.size}"
        )

    if profile.chest:
        parts.append(
            f"دور سینه: {profile.chest}"
        )

    if profile.waist:
        parts.append(
            f"دور کمر: {profile.waist}"
        )

    if profile.hip:
        parts.append(
            f"دور باسن: {profile.hip}"
        )

    if profile.shoulder:
        parts.append(
            f"عرض شانه: {profile.shoulder}"
        )

    if profile.styles:
        parts.append(
            f"استایل‌های مورد علاقه: "
            f"{', '.join(profile.styles)}"
        )

    if profile.liked_colors:
        parts.append(
            f"رنگ‌های مورد علاقه: "
            f"{', '.join(profile.liked_colors)}"
        )

    if profile.disliked_colors:
        parts.append(
            f"رنگ‌های نامطلوب: "
            f"{', '.join(profile.disliked_colors)}"
        )

    if profile.occasions:
        parts.append(
            f"موقعیت‌ها: "
            f"{', '.join(profile.occasions)}"
        )

    if profile.budget:
        parts.append(
            f"نوع بودجه: {profile.budget}"
        )

    if profile.min_price is not None:
        parts.append(
            f"حداقل قیمت: {profile.min_price}"
        )

    if profile.max_price is not None:
        parts.append(
            f"حداکثر قیمت: {profile.max_price}"
        )

    if profile.budget_type:
        parts.append(
            f"نوع بودجه قدیمی: "
            f"{profile.budget_type}"
        )

    if profile.budget_amount is not None:
        parts.append(
            f"مقدار بودجه: "
            f"{profile.budget_amount}"
        )

    return "\n".join(parts)


# =========================================================
# SEARCH DECISION
# =========================================================

def should_search_products(message: str) -> bool:

    keywords = [
        "لباس",
        "استایل",
        "ست",
        "پوشاک",
        "شلوار",
        "پیراهن",
        "تیشرت",
        "تی‌شرت",
        "تی شرت",
        "پولوشرت",
        "هودی",
        "کفش",
        "کت",
        "مانتو",
        "دامن",
        "خرید",
        "بخر",
        "پیشنهاد بده",
        "کتانی",
        "اسنیکر",
        "سرچ",
        "جستجو",
        "پیدا کن",
        "محصول",
        "محصول واقعی",
    ]

    text = normalize_text(message)

    return any(
        keyword in text
        for keyword in keywords
    )


# =========================================================
# PRODUCT SEARCH QUERIES
# =========================================================

def build_product_search_queries(
    message: str,
    profile: Optional[UserProfile],
    intent: Optional[RequestIntent] = None,
) -> list[str]:

    if intent is None:
        intent = extract_request_intent(message)

    queries = []

    gender = profile.gender if profile else None

    gender_text = ""

    if gender:

        gender_lower = normalize_text(
            str(gender)
        )

        if (
            "مرد" in gender_lower
            or "male" in gender_lower
        ):
            gender_text = "مردانه"

        elif (
            "زن" in gender_lower
            or "female" in gender_lower
        ):
            gender_text = "زنانه"

    categories = list(
        intent.categories
    )

    if not categories:

        text = normalize_text(message)

        if any(
            word in text
            for word in [
                "ست",
                "استایل",
                "لباس کامل",
                "دانشگاه",
            ]
        ):

            categories = [
                "تیشرت",
                "پولوشرت",
                "پیراهن",
                "شلوار",
                "هودی",
                "کفش",
            ]

        else:

            categories = [
                "تیشرت",
                "پولوشرت",
                "پیراهن",
                "شلوار",
                "کفش",
            ]

    for category in categories:

        query_parts = [
            category
        ]

        if gender_text:
            query_parts.append(
                gender_text
            )

        if intent.colors:

            query_parts.append(
                intent.colors[0]
            )

        if intent.features:

            for feature in intent.features[:2]:

                if feature not in query_parts:
                    query_parts.append(
                        feature
                    )

        if intent.styles:

            for style in intent.styles[:1]:

                if style not in query_parts:
                    query_parts.append(
                        style
                    )

        queries.append(
            " ".join(query_parts)
        )

    for category in categories:

        fallback_query = category

        if gender_text:
            fallback_query += (
                f" {gender_text}"
            )

        if fallback_query not in queries:
            queries.append(
                fallback_query
            )

    unique_queries = []

    for query in queries:

        normalized_query = normalize_text(
            query
        )

        if normalized_query not in [
            normalize_text(item)
            for item in unique_queries
        ]:
            unique_queries.append(
                query
            )

    return unique_queries


# =========================================================
# MULTI PRODUCT SEARCH
# =========================================================

def search_multiple_product_queries(
    queries: list[str],
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
) -> list[Product]:

    all_products = []

    seen_ids = set()

    print("\n[PRODUCT SEARCH QUERIES]")

    for query in queries:

        print(
            f"[SEARCH] {query}"
        )

        products = search_products(
            query=query,
            min_price=min_price,
            max_price=max_price,
        )

        for product in products:

            if product.id in seen_ids:
                continue

            seen_ids.add(
                product.id
            )

            all_products.append(
                product
            )

    print(
        f"[MULTI SEARCH] "
        f"queries={len(queries)}, "
        f"unique_products={len(all_products)}"
    )

    return all_products


# =========================================================
# CATEGORY
# =========================================================

def get_product_category(
    product: Product
) -> str:

    text = normalize_text(
        f"{product.name} "
        f"{product.note or ''} "
        f"{product.material or ''}"
    )

    # -----------------------------------------------------
    # Shoes first
    # -----------------------------------------------------

    if any(
        word in text
        for word in [
            "کفش",
            "کتانی",
            "اسنیکر",
            "صندل",
            "بوت",
            "نیم بوت",
        ]
    ):
        return "shoe"

    # -----------------------------------------------------
    # Bottoms
    # -----------------------------------------------------

    if any(
        word in text
        for word in [
            "شلوار",
            "دامن",
            "شورت",
        ]
    ):
        return "bottom"

    # -----------------------------------------------------
    # Tops
    #
    # IMPORTANT:
    # "تی شرت" was previously missing here.
    # Also check tops BEFORE outerwear so that a product
    # with a top-related name is not accidentally classified
    # as outer.
    # -----------------------------------------------------

    if any(
        word in text
        for word in [
            "تیشرت",
            "تی شرت",
            "تی‌شرت",
            "پولوشرت",
            "پولو شرت",
            "پیراهن",
            "بلوز",
            "تاپ",
        ]
    ):
        return "top"

    # -----------------------------------------------------
    # Outerwear
    # -----------------------------------------------------

    if any(
        word in text
        for word in [
            "هودی",
            "سویشرت",
            "کاپشن",
            "کت",
            "ژاکت",
            "پالتو",
            "بارانی",
        ]
    ):
        return "outer"

    return "other"


# =========================================================
# OUTFIT REQUEST
# =========================================================

def is_outfit_request(
    message: str
) -> bool:

    text = normalize_text(
        message
    )

    keywords = [
        "ست",
        "استایل",
        "لباس کامل",
        "outfit",
        "برای دانشگاه",
        "برای مهمانی",
        "برای محل کار",
        "برای روزمره",
    ]

    return any(
        keyword in text
        for keyword in keywords
    )


# =========================================================
# REQUEST MATCH SCORE
# =========================================================

def score_request_match(
    product: Product,
    intent: Optional[RequestIntent],
) -> int:

    if not intent:
        return 0

    score = 0

    product_text = normalize_text(
        f"{product.name} "
        f"{product.note or ''} "
        f"{product.material or ''} "
        f"{' '.join(product.colors or [])}"
    )

    # =====================================================
    # Color
    # =====================================================

    if intent.colors:

        color_found = False

        for color in intent.colors:

            color_normalized = normalize_text(
                color
            )

            if color_normalized in product_text:
                score += 25
                color_found = True
                break

            aliases = COLOR_TERMS.get(
                color,
                []
            )

            if any(
                normalize_text(alias)
                in product_text
                for alias in aliases
            ):
                score += 25
                color_found = True
                break

        if not color_found:
            score -= 8

    # =====================================================
    # Category
    # =====================================================

    category = get_product_category(
        product
    )

    category_map = {
        "تیشرت": "top",
        "پولوشرت": "top",
        "پیراهن": "top",
        "بلوز": "top",
        "تاپ": "top",
        "شلوار": "bottom",
        "دامن": "bottom",
        "شورت": "bottom",
        "کفش": "shoe",
        "کاپشن": "outer",
        "هودی": "outer",
        "کت": "outer",
    }

    for requested_category in intent.categories:

        requested_type = category_map.get(
            requested_category
        )

        if requested_type == category:

            score += 30

    # =====================================================
    # Style
    # =====================================================

    for style in intent.styles:

        style_normalized = normalize_text(
            style
        )

        aliases = STYLE_TERMS.get(
            style,
            []
        )

        if (
            style_normalized in product_text
            or any(
                normalize_text(alias)
                in product_text
                for alias in aliases
            )
        ):
            score += 12

    # =====================================================
    # Features
    # =====================================================

    for feature in intent.features:

        aliases = FEATURE_TERMS.get(
            feature,
            []
        )

        feature_found = (
            normalize_text(feature)
            in product_text
        )

        if not feature_found:

            feature_found = any(
                normalize_text(alias)
                in product_text
                for alias in aliases
            )

        if feature_found:
            score += 25

        else:
            score -= 5

    # =====================================================
    # Occasion
    # =====================================================

    for occasion in intent.occasions:

        occasion_normalized = normalize_text(
            occasion
        )

        if occasion_normalized in [
            "دانشگاه",
            "روزمره",
        ]:

            casual_keywords = [
                "روزمره",
                "کژوال",
                "اسپرت",
                "کتانی",
                "اسنیکر",
                "راحت",
            ]

            if any(
                keyword in product_text
                for keyword in casual_keywords
            ):
                score += 8

    return score


# =========================================================
# OCCASION / STYLE / BODY PRODUCT SCORE
# =========================================================

def score_outfit_product(
    product: Product,
    profile: Optional[UserProfile],
    message: str = "",
    intent: Optional[RequestIntent] = None,
) -> int:

    score = 0

    product_text = normalize_text(
        f"{product.name} "
        f"{product.note or ''} "
        f"{product.material or ''} "
        f"{' '.join(product.colors or [])}"
    )

    category = get_product_category(
        product
    )

    # =====================================================
    # Current request has highest priority
    # =====================================================

    score += score_request_match(
        product=product,
        intent=intent,
    )

    # =====================================================
    # Occasion compatibility
    # =====================================================

    if profile and profile.occasions:

        for occasion in profile.occasions:

            occasion_text = normalize_text(
                str(occasion)
            )

            if any(
                word in occasion_text
                for word in [
                    "دانشگاه",
                    "روزمره",
                    "سفر",
                    "کژوال",
                ]
            ):

                if category == "shoe":

                    formal_keywords = [
                        "رسمی",
                        "مجلس",
                        "اداری",
                        "چرم طبیعی",
                        "کلاسیک",
                        "dress",
                    ]

                    casual_keywords = [
                        "روزمره",
                        "کژوال",
                        "راحت",
                        "اسپرت",
                        "کتانی",
                        "اسنیکر",
                        "رانینگ",
                        "سلیپ آن",
                    ]

                    if any(
                        keyword in product_text
                        for keyword in formal_keywords
                    ):
                        score -= 35

                    elif any(
                        keyword in product_text
                        for keyword in casual_keywords
                    ):
                        score += 12

            if any(
                word in occasion_text
                for word in [
                    "محل کار",
                    "اداری",
                    "جلسه",
                    "محیط کار",
                ]
            ):

                if category == "shoe":

                    formal_keywords = [
                        "رسمی",
                        "اداری",
                        "کلاسیک",
                        "چرم طبیعی",
                    ]

                    casual_keywords = [
                        "اسپرت",
                        "کتانی",
                        "اسنیکر",
                    ]

                    if any(
                        keyword in product_text
                        for keyword in formal_keywords
                    ):
                        score += 12

                    elif any(
                        keyword in product_text
                        for keyword in casual_keywords
                    ):
                        score -= 15

    # =====================================================
    # Body shape
    # =====================================================

    if profile and profile.body_shape:

        body_shape = normalize_text(
            str(profile.body_shape)
        )

        if body_shape in [
            "مستطیل",
            "rectangle",
        ]:

            if category == "top":

                if any(
                    word in product_text
                    for word in [
                        "regular",
                        "regular fit",
                        "یقه",
                        "پولوشرت",
                    ]
                ):
                    score += 5

    # =====================================================
    # Profile preferred colors
    # =====================================================

    if (
        profile
        and profile.liked_colors
        and not (
            intent
            and intent.colors
        )
    ):

        for color in profile.liked_colors:

            color_text = normalize_text(
                str(color)
            )

            if color_text in product_text:
                score += 5

    # =====================================================
    # Disliked colors
    # =====================================================

    if profile and profile.disliked_colors:

        for color in profile.disliked_colors:

            color_text = normalize_text(
                str(color)
            )

            if color_text in product_text:

                explicitly_requested = (
                    intent
                    and color_text
                    in [
                        normalize_text(
                            item
                        )
                        for item in intent.colors
                    ]
                )

                if not explicitly_requested:
                    score -= 15

    # =====================================================
    # Profile style
    # =====================================================

    if (
        profile
        and profile.styles
        and not (
            intent
            and intent.styles
        )
    ):

        for style in profile.styles:

            style_text = normalize_text(
                str(style)
            )

            if "مینیمال" in style_text:

                minimal_keywords = [
                    "ساده",
                    "مینیمال",
                    "basic",
                    "basic fit",
                    "regular fit",
                    "پولوشرت",
                    "تیشرت",
                    "تی شرت",
                    "تی‌شرت",
                ]

                if any(
                    keyword in product_text
                    for keyword in minimal_keywords
                ):
                    score += 5

    return score


# =========================================================
# BUDGET
# =========================================================

def normalize_budget(
    profile: Optional[UserProfile]
) -> tuple[Optional[int], Optional[int]]:

    if not profile:
        return None, None

    if profile.budget_type:

        budget_type = str(
            profile.budget_type
        ).lower()

        if budget_type in [
            "economic",
            "اقتصادی",
        ]:
            return None, None

        if budget_type in [
            "medium",
            "متوسط",
        ]:
            return None, None

        if budget_type in [
            "free",
            "آزاد",
        ]:
            return None, None

        if budget_type in [
            "custom",
            "دلخواه",
        ]:
            return (
                profile.min_price,
                profile.max_price,
            )

    if (
        profile.min_price is not None
        or profile.max_price is not None
    ):
        return (
            profile.min_price,
            profile.max_price,
        )

    if profile.budget:

        budget = str(
            profile.budget
        ).strip().lower()

        if budget in [
            "اقتصادی",
            "economic",
        ]:
            return None, None

        if budget in [
            "متوسط",
            "medium",
        ]:
            return None, None

        if budget in [
            "آزاد",
            "free",
        ]:
            return None, None

    return None, None


def get_budget_type(
    profile: Optional[UserProfile]
) -> Optional[str]:

    if not profile:
        return None

    if profile.budget_type:

        value = str(
            profile.budget_type
        ).strip().lower()

        if value in [
            "economic",
            "اقتصادی",
        ]:
            return "economic"

        if value in [
            "medium",
            "متوسط",
        ]:
            return "medium"

        if value in [
            "free",
            "آزاد",
        ]:
            return "free"

        if value in [
            "custom",
            "دلخواه",
        ]:
            return "custom"

    if profile.budget:

        value = str(
            profile.budget
        ).strip().lower()

        if value in [
            "اقتصادی",
            "economic",
        ]:
            return "economic"

        if value in [
            "متوسط",
            "medium",
        ]:
            return "medium"

        if value in [
            "آزاد",
            "free",
        ]:
            return "free"

    if (
        profile.min_price is not None
        or profile.max_price is not None
    ):
        return "custom"

    return None


def get_total_outfit_range(
    profile: Optional[UserProfile]
) -> tuple[Optional[int], Optional[int]]:

    if not profile:
        return None, None

    min_price = profile.min_price
    max_price = profile.max_price

    if (
        min_price is not None
        or max_price is not None
    ):
        return min_price, max_price

    return None, None


def get_total_outfit_budget(
    profile: Optional[UserProfile]
) -> Optional[int]:

    if not profile:
        return None

    if profile.budget_amount is not None:
        return profile.budget_amount

    return None


def get_total_outfit_minimum(
    profile: Optional[UserProfile]
) -> Optional[int]:

    if not profile:
        return None

    if profile.min_price is not None:
        return profile.min_price

    return None


# =========================================================
# BUDGET SCORE
# =========================================================

def score_budget_preference(
    total_price: int,
    profile: Optional[UserProfile],
    reference_price: Optional[float] = None,
) -> int:

    budget_type = get_budget_type(
        profile
    )

    if not budget_type:
        return 0

    # -----------------------------------------------------
    # Economic
    # -----------------------------------------------------

    if budget_type == "economic":

        if (
            reference_price
            and reference_price > 0
        ):

            difference_ratio = (
                reference_price
                - total_price
            ) / reference_price

            score = (
                30
                + int(
                    difference_ratio * 60
                )
            )

            return max(
                0,
                min(90, score),
            )

        return 30

    # -----------------------------------------------------
    # Medium
    #
    # The reference is now based on realistic category
    # prices, not the median of arbitrary combinations.
    # -----------------------------------------------------

    if budget_type == "medium":

        if (
            reference_price
            and reference_price > 0
        ):

            distance_ratio = (
                abs(
                    total_price
                    - reference_price
                )
                / reference_price
            )

            score = (
                60
                - int(
                    distance_ratio * 80
                )
            )

            return max(
                0,
                min(60, score),
            )

        return 30

    # -----------------------------------------------------
    # Free
    # -----------------------------------------------------

    if budget_type == "free":
        return 0

    return 0


# =========================================================
# CATEGORY BUDGET PREFERENCE
# =========================================================

def score_category_budget_preference(
    combination: list[Product],
    profile: Optional[UserProfile],
    category_reference_prices: Optional[
        dict[str, float]
    ],
) -> int:

    if (
        not profile
        or not category_reference_prices
    ):
        return 0

    budget_type = get_budget_type(
        profile
    )

    if budget_type not in [
        "economic",
        "medium",
    ]:
        return 0

    score = 0

    for item in combination:

        category = get_product_category(
            item
        )

        reference_price = (
            category_reference_prices.get(
                category
            )
        )

        if (
            not reference_price
            or reference_price <= 0
        ):
            continue

        ratio = (
            item.price
            / reference_price
        )

        # =================================================
        # Economic
        # =================================================

        if budget_type == "economic":

            if ratio <= 1.0:

                score += min(
                    30,
                    15
                    + int(
                        (1.0 - ratio)
                        * 30
                    ),
                )

            elif ratio <= 1.5:

                score -= int(
                    (ratio - 1.0)
                    * 35
                )

            elif ratio <= 2.5:

                score -= int(
                    (ratio - 1.0)
                    * 45
                )

            else:

                score -= 60

        # =================================================
        # Medium
        #
        # This is the important fix.
        #
        # <= 1.25x reference:
        #     good
        #
        # <= 1.75x:
        #     acceptable
        #
        # <= 2.5x:
        #     expensive
        #
        # <= 4x:
        #     very expensive
        #
        # > 4x:
        #     extreme outlier
        # =================================================

        elif budget_type == "medium":

            if ratio <= 1.25:

                score += 30

            elif ratio <= 1.75:

                score += 10

            elif ratio <= 2.5:

                score -= 15

            elif ratio <= 4.0:

                score -= 35

            else:

                score -= 60

    return score


# =========================================================
# COMBINATION BUDGET VALIDATION
# =========================================================

def validate_combination_budget(
    combination: list[Product],
    profile: Optional[UserProfile],
) -> tuple[bool, int]:

    if not profile:
        return True, 0

    total_price = sum(
        item.price
        for item in combination
    )

    budget_type = get_budget_type(
        profile
    )

    if budget_type == "custom":

        min_price, max_price = (
            get_total_outfit_range(
                profile
            )
        )

        if (
            min_price is not None
            and total_price < min_price
        ):
            return False, total_price

        if (
            max_price is not None
            and total_price > max_price
        ):
            return False, total_price

        return True, total_price

    if budget_type in [
        "economic",
        "medium",
        "free",
        None,
    ]:
        return True, total_price

    return True, total_price


# =========================================================
# COMBINATION SCORE
# =========================================================

def score_combination(
    combination: list[Product],
    profile: Optional[UserProfile],
    message: str,
    reference_price: Optional[float] = None,
    category_reference_prices: Optional[
        dict[str, float]
    ] = None,
    intent: Optional[RequestIntent] = None,
) -> int:

    score = 0

    # =====================================================
    # Individual product quality
    # =====================================================

    for item in combination:

        score += score_outfit_product(
            product=item,
            profile=profile,
            message=message,
            intent=intent,
        )

    # =====================================================
    # Category budget preference
    # =====================================================

    score += score_category_budget_preference(
        combination=combination,
        profile=profile,
        category_reference_prices=(
            category_reference_prices
        ),
    )

    # =====================================================
    # Total outfit budget preference
    # =====================================================

    total_price = sum(
        item.price
        for item in combination
    )

    score += score_budget_preference(
        total_price=total_price,
        profile=profile,
        reference_price=reference_price,
    )

    # =====================================================
    # Outfit completeness
    # =====================================================

    categories = {
        get_product_category(item)
        for item in combination
    }

    if "top" in categories:
        score += 15

    if "bottom" in categories:
        score += 15

    if "shoe" in categories:
        score += 15

    if {
        "top",
        "bottom",
        "shoe",
    }.issubset(categories):
        score += 25

    return score


# =========================================================
# SELECT OUTFIT
# =========================================================

def select_outfit(
    products: list[Product],
    profile: Optional[UserProfile],
    message: str,
    intent: Optional[RequestIntent] = None,
) -> tuple[list[Product], int]:

    # =====================================================
    # Rank products
    # =====================================================

    ranked = []

    for product_item in products:

        score = score_outfit_product(
            product=product_item,
            profile=profile,
            message=message,
            intent=intent,
        )

        ranked.append(
            (
                score,
                product_item,
            )
        )

    ranked.sort(
        key=lambda item: (
            item[0],
            -item[1].price,
        ),
        reverse=True,
    )

    # =====================================================
    # Separate categories
    # =====================================================

    category_map = {
        "top": [],
        "bottom": [],
        "outer": [],
        "shoe": [],
    }

    for score, product_item in ranked:

        category = get_product_category(
            product_item
        )

        if category in category_map:

            category_map[
                category
            ].append(
                (
                    score,
                    product_item,
                )
            )

    # =====================================================
    # Print ranking
    # =====================================================

    print(
        "\n[OUTFIT SELECTION SCORES]"
    )

    for category, items in category_map.items():

        for score, product_item in items[:5]:

            print(
                f"[{category}] "
                f"score={score} | "
                f"{product_item.name} | "
                f"price={product_item.price}"
            )

    # =====================================================
    # Category price references
    #
    # IMPORTANT FIX:
    #
    # Previously we used the median of only the top 5
    # ranked products.
    #
    # That could make an expensive category look normal.
    #
    # Now we use the cheapest 3 real products from the
    # entire category pool as the realistic price baseline.
    # =====================================================

    category_reference_prices = {}

    for category, items in category_map.items():

        prices = sorted(
            [
                product_item.price
                for _, product_item in items
                if product_item.price > 0
            ]
        )

        if prices:

            sample = prices[
                :min(3, len(prices))
            ]

            category_reference_prices[
                category
            ] = float(
                median(sample)
            )

    print(
        "\n[OUTFIT CATEGORY REFERENCE PRICES]"
    )

    for category, reference in (
        category_reference_prices.items()
    ):

        print(
            f"[{category}] "
            f"reference={reference}"
        )

    # =====================================================
    # Limit candidates
    #
    # Ranking still controls relevance.
    # Budget logic now controls price.
    # =====================================================

    top_candidates = [
        product_item
        for _, product_item
        in category_map["top"][:5]
    ]

    bottom_candidates = [
        product_item
        for _, product_item
        in category_map["bottom"][:5]
    ]

    shoe_candidates = [
        product_item
        for _, product_item
        in category_map["shoe"][:5]
    ]

    outer_candidates = [
        product_item
        for _, product_item
        in category_map["outer"][:3]
    ]

    # =====================================================
    # Generate combinations
    # =====================================================

    combinations = []

    if (
        top_candidates
        and bottom_candidates
        and shoe_candidates
    ):

        combinations = list(
            itertools_product(
                top_candidates,
                bottom_candidates,
                shoe_candidates,
            )
        )

    elif (
        top_candidates
        and bottom_candidates
    ):

        combinations = list(
            itertools_product(
                top_candidates,
                bottom_candidates,
            )
        )

    elif (
        top_candidates
        and shoe_candidates
    ):

        combinations = list(
            itertools_product(
                top_candidates,
                shoe_candidates,
            )
        )

    elif (
        bottom_candidates
        and shoe_candidates
    ):

        combinations = list(
            itertools_product(
                bottom_candidates,
                shoe_candidates,
            )
        )

    else:

        if ranked:

            best = [
                item
                for _, item in ranked[:3]
            ]

            return (
                best,
                sum(
                    item.price
                    for item in best
                ),
            )

    print(
        f"[OUTFIT COMBINATIONS] "
        f"generated={len(combinations)}"
    )

    # =====================================================
    # Reference total price
    #
    # IMPORTANT FIX:
    #
    # Do NOT use median of all combinations.
    #
    # Instead, calculate a realistic target total from
    # category reference prices.
    # =====================================================

    reference_categories = [
        "top",
        "bottom",
        "shoe",
    ]

    reference_parts = [
        category_reference_prices[category]
        for category in reference_categories
        if category in category_reference_prices
    ]

    reference_price = (
        float(sum(reference_parts))
        if reference_parts
        else None
    )

    print(
        f"[OUTFIT REFERENCE PRICE] "
        f"target={reference_price}"
    )

    # =====================================================
    # Score combinations
    # =====================================================

    scored_combinations = []

    for combination in combinations:

        valid, total_price = (
            validate_combination_budget(
                combination=combination,
                profile=profile,
            )
        )

        if not valid:
            continue

        score = score_combination(
            combination=combination,
            profile=profile,
            message=message,
            reference_price=reference_price,
            category_reference_prices=(
                category_reference_prices
            ),
            intent=intent,
        )

        scored_combinations.append(
            (
                score,
                total_price,
                combination,
            )
        )

    # =====================================================
    # Select best combination
    # =====================================================

    if scored_combinations:

        scored_combinations.sort(
            key=lambda item: (
                item[0],
                -item[1],
            ),
            reverse=True,
        )

        (
            best_score,
            best_total,
            best_combination,
        ) = scored_combinations[0]

        print(
            "\n[SELECTED OUTFIT]"
        )

        for index, item in enumerate(
            best_combination,
            start=1,
        ):

            category = get_product_category(
                item
            )

            print(
                f"{index}. "
                f"[{category}] "
                f"{item.name} | "
                f"price={item.price}"
            )

        print(
            f"[OUTFIT SCORE] "
            f"{best_score}"
        )

        print(
            f"[OUTFIT TOTAL] "
            f"{best_total}"
        )

        return (
            best_combination,
            best_total,
        )

    # =====================================================
    # Fallback
    # =====================================================

    fallback = []

    if top_candidates:
        fallback.append(
            top_candidates[0]
        )

    if bottom_candidates:
        fallback.append(
            bottom_candidates[0]
        )

    if shoe_candidates:
        fallback.append(
            shoe_candidates[0]
        )

    if not fallback:

        fallback = [
            product_item
            for _, product_item
            in ranked[:3]
        ]

    total_price = sum(
        item.price
        for item in fallback
    )

    print(
        "\n[FALLBACK OUTFIT]"
    )

    for index, item in enumerate(
        fallback,
        start=1,
    ):

        print(
            f"{index}. "
            f"{item.name} | "
            f"price={item.price}"
        )

    print(
        f"[FALLBACK TOTAL] "
        f"{total_price}"
    )

    return (
        fallback,
        total_price,
    )


# =========================================================
# PRODUCT RANKING
# =========================================================

def rank_products(
    products: list[Product],
    profile: Optional[UserProfile],
    message: str,
    intent: Optional[RequestIntent] = None,
) -> list[Product]:

    scored = []

    for product_item in products:

        score = score_outfit_product(
            product=product_item,
            profile=profile,
            message=message,
            intent=intent,
        )

        scored.append(
            (
                score,
                product_item,
            )
        )

    scored.sort(
        key=lambda item: (
            item[0],
            -item[1].price,
        ),
        reverse=True,
    )

    print(
        "\n[PRODUCT RANKING]"
    )

    for index, (
        score,
        product_item,
    ) in enumerate(
        scored[:10],
        start=1,
    ):

        print(
            f"{index}. "
            f"score={score} | "
            f"{product_item.name}"
        )

    return [
        product_item
        for _, product_item
        in scored
    ]


# =========================================================
# AGENT
# =========================================================

def run_agent(
    message,
    profile=None,
    conversation=None,
):

    # =====================================================
    # Extract current request
    # =====================================================

    intent = extract_request_intent(
        message
    )

    profile_context = build_profile_context(
        profile
    )

    products = []

    # =====================================================
    # Product search
    # =====================================================

    if should_search_products(message):

        queries = build_product_search_queries(
            message=message,
            profile=profile,
            intent=intent,
        )

        print(
            f"[SEARCH QUERY] "
            f"message={message}"
        )

        print(
            f"[SEARCH QUERY] "
            f"queries={queries}"
        )

        # -------------------------------------------------
        # Budget behavior
        # -------------------------------------------------

        budget_type = get_budget_type(
            profile
        )

        min_price = None
        max_price = None

        if budget_type == "custom":

            min_price, max_price = (
                normalize_budget(
                    profile
                )
            )

        elif budget_type not in [
            "economic",
            "medium",
            "free",
        ]:

            if profile:

                budget_amount = (
                    get_total_outfit_budget(
                        profile
                    )
                )

                if budget_amount:
                    max_price = budget_amount

        products = (
            search_multiple_product_queries(
                queries=queries,
                min_price=min_price,
                max_price=max_price,
            )
        )

    # =====================================================
    # No products
    # =====================================================

    if not products:

        no_product_answer = (
            "فعلاً محصول واقعی و قابل استفاده‌ای "
            "برای این درخواست پیدا نکردم."
        )

        return (
            no_product_answer,
            [],
        )

    # =====================================================
    # Outfit request
    # =====================================================

    if is_outfit_request(message):

        outfit_products, total_price = (
            select_outfit(
                products=products,
                profile=profile,
                message=message,
                intent=intent,
            )
        )

        selected_products = (
            outfit_products
        )

    else:

        ranked_products = rank_products(
            products=products,
            profile=profile,
            message=message,
            intent=intent,
        )

        selected_products = (
            ranked_products[:6]
        )

        total_price = sum(
            item.price
            for item in selected_products
        )

    # =====================================================
    # Prepare product context for AI
    # =====================================================

    product_context = (
        format_products_for_ai(
            selected_products
        )
    )

    # =====================================================
    # Budget status
    # =====================================================

    budget_status = ""

    if profile:

        budget_type = get_budget_type(
            profile
        )

        if budget_type == "economic":

            budget_status = """
کاربر بودجه اقتصادی دارد.
محصولات گران‌تر را فقط زمانی پیشنهاد بده
که جایگزین مناسب‌تری وجود نداشته باشد.
"""

        elif budget_type == "medium":

            budget_status = """
کاربر بودجه متوسط دارد.
از انتخاب محصولات بسیار گران خودداری کن.
اگر محصول مشابه و مناسب‌تری با قیمت پایین‌تر
وجود دارد، آن را ترجیح بده.
قیمت واقعی محصولات را تغییر نده.
"""

        elif budget_type == "free":

            budget_status = """
کاربر محدودیت بودجه مشخصی تعیین نکرده است.
اما همچنان محصولات غیرمنطقی و بسیار گران را
بدون دلیل پیشنهاد نده.
"""

        elif budget_type == "custom":

            min_price, max_price = (
                normalize_budget(
                    profile
                )
            )

            budget_status = f"""
محدوده قیمت سفارشی کاربر:

حداقل: {min_price}
حداکثر: {max_price}
"""

    # =====================================================
    # Current request context
    # =====================================================

    request_context = f"""
نیاز استخراج‌شده از درخواست فعلی کاربر:

رنگ‌ها:
{", ".join(intent.colors) if intent.colors else "مشخص نشده"}

دسته‌های لباس:
{", ".join(intent.categories) if intent.categories else "مشخص نشده"}

استایل:
{", ".join(intent.styles) if intent.styles else "مشخص نشده"}

ویژگی‌های ظاهری لباس:
{", ".join(intent.features) if intent.features else "مشخص نشده"}

موقعیت:
{", ".join(intent.occasions) if intent.occasions else "مشخص نشده"}

این اطلاعات مربوط به درخواست فعلی کاربر است
و در صورت تضاد با ترجیحات عمومی پروفایل،
درخواست فعلی اولویت دارد.
"""

    # =====================================================
    # Conversation
    # =====================================================

    conversation_text = ""

    if conversation:

        conversation_text = "\n".join(
            [
                f"{item.get('role', '')}: "
                f"{item.get('content', '')}"
                for item in conversation[-8:]
            ]
        )

    # =====================================================
    # Prompt
    # =====================================================

    user_prompt = f"""
پروفایل کاربر:

{profile_context}

{budget_status}

{request_context}

گفت‌وگوی قبلی:

{conversation_text}

درخواست فعلی کاربر:

{message}

محصولات واقعی پیدا شده:

{product_context}

بر اساس این اطلاعات پاسخ بده.

اگر درخواست مربوط به یک ست است:

- فقط محصولات موجود در لیست بالا را معرفی کن.
- محصول جدیدی خارج از این لیست اضافه نکن.
- نام دقیق محصول را تغییر نده.
- فروشگاه واقعی را تغییر نده.
- قیمت واقعی را تغییر نده.
- URL واقعی را تغییر نده.
- اگر سایز خاصی موجود است، فقط همان را بگو.
- مجموع قیمت واقعی همین محصولات انتخاب‌شده را دقیق حساب کن.
- توضیح کوتاه و کاربردی بده.
- برای دانشگاه و روزمره، کفش و لباس بیش از حد رسمی را پیشنهاد نده.
- اگر کاربر رنگ مشخصی در درخواست فعلی گفته،
  همان رنگ را نسبت به ترجیحات عمومی پروفایل در اولویت قرار بده.
- اگر کاربر ویژگی مشخصی مثل «راسته»، «اسلیم»
  یا «اورسایز» خواسته، فقط در صورت وجود شواهد
  در اطلاعات واقعی محصول آن را به محصول نسبت بده.
"""

    # =====================================================
    # AI request
    # =====================================================

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=0.2,
    )

    answer = (
        response.choices[0]
        .message.content
    )

    return (
        answer,
        selected_products,
    )