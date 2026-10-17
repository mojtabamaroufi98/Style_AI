import os
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

from models import UserProfile, Product
from tools import search_products, format_products_for_ai


load_dotenv()


# =========================================================
# AI CONFIG
# =========================================================

AI_API_KEY = os.getenv("AI_API_KEY")
AI_BASE_URL = os.getenv("AI_BASE_URL")
AI_MODEL = os.getenv("AI_MODEL")


if not AI_API_KEY:
    raise RuntimeError("AI_API_KEY is not configured.")

if not AI_BASE_URL:
    raise RuntimeError("AI_BASE_URL is not configured.")

if not AI_MODEL:
    raise RuntimeError("AI_MODEL is not configured.")


client = OpenAI(
    api_key=AI_API_KEY,
    base_url=AI_BASE_URL
)


# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """
تو StyleAI هستی؛ یک استایلیست هوشمند و دستیار خرید لباس برای کاربران ایرانی.

وظایف تو:

1. پیشنهاد استایل متناسب با کاربر
2. توجه به جنسیت، فرم بدن، قد، وزن و سایز در صورت وجود
3. توجه به سبک مورد علاقه کاربر
4. توجه به رنگ‌های مورد علاقه و رنگ‌هایی که کاربر نمی‌پسندد
5. توجه به مناسبت، فصل و موقعیت استفاده
6. توجه به بودجه کاربر
7. کمک به انتخاب و ترکیب لباس‌ها
8. ادامه دادن طبیعی مکالمه و استفاده از اطلاعات پیام‌های قبلی

قوانین مهم:

- همیشه فارسی پاسخ بده.
- پاسخ‌ها طبیعی، دوستانه و کاربردی باشند.
- اگر اطلاعات کافی نیست، فقط اطلاعات ضروری را از کاربر بپرس.
- از اطلاعات موجود در پروفایل و تاریخچه مکالمه استفاده کن.
- اگر کاربر گفت «همون»، «این»، «قبلی»، «برای اون»، «این ست» و موارد مشابه،
  منظور را با توجه به تاریخچه مکالمه تفسیر کن.
- قیمت، لینک، موجودی یا نام فروشگاه را هرگز حدس نزن.
- اگر محصول واقعی از ابزار جستجو دریافت نشده است، ادعا نکن که محصول واقعی پیدا شده.
- تشخیص پزشکی یا ادعای تخصص پزشکی انجام نده.
- پیشنهادها را کوتاه، واضح و قابل اجرا ارائه کن.
"""


# =========================================================
# PROFILE
# =========================================================

def build_profile_context(
    profile: Optional[UserProfile]
) -> str:

    if not profile:
        return "اطلاعات پروفایل کاربر در دسترس نیست."

    profile_data = []

    if profile.gender:
        profile_data.append(
            f"جنسیت: {profile.gender}"
        )

    if profile.body_shape:
        profile_data.append(
            f"فرم بدن: {profile.body_shape}"
        )

    if profile.height_cm is not None:
        profile_data.append(
            f"قد: {profile.height_cm} سانتی‌متر"
        )

    if profile.weight_kg is not None:
        profile_data.append(
            f"وزن: {profile.weight_kg} کیلوگرم"
        )

    if profile.size:
        profile_data.append(
            f"سایز: {profile.size}"
        )

    if profile.chest is not None:
        profile_data.append(
            f"دور سینه: {profile.chest}"
        )

    if profile.waist is not None:
        profile_data.append(
            f"دور کمر: {profile.waist}"
        )

    if profile.hip is not None:
        profile_data.append(
            f"دور باسن: {profile.hip}"
        )

    if profile.shoulder is not None:
        profile_data.append(
            f"عرض شانه: {profile.shoulder}"
        )

    if profile.styles:
        profile_data.append(
            f"سبک‌های مورد علاقه: {', '.join(profile.styles)}"
        )

    if profile.liked_colors:
        profile_data.append(
            f"رنگ‌های مورد علاقه: {', '.join(profile.liked_colors)}"
        )

    if profile.disliked_colors:
        profile_data.append(
            f"رنگ‌های نامطلوب: {', '.join(profile.disliked_colors)}"
        )

    if profile.occasions:
        profile_data.append(
            f"مناسبت‌ها: {', '.join(profile.occasions)}"
        )

    if profile.budget:
        profile_data.append(
            f"بودجه: {profile.budget}"
        )

    if profile.min_price is not None:
        profile_data.append(
            f"حداقل قیمت: {profile.min_price}"
        )

    if profile.max_price is not None:
        profile_data.append(
            f"حداکثر قیمت: {profile.max_price}"
        )

    if not profile_data:
        return "اطلاعات پروفایل کاربر هنوز تکمیل نشده است."

    return "\n".join(profile_data)


# =========================================================
# PRODUCT SEARCH DECISION
# =========================================================

def should_search_products(message: str) -> bool:

    keywords = [
        "لباس",
        "پیراهن",
        "شلوار",
        "کت",
        "مانتو",
        "کفش",
        "هودی",
        "تیشرت",
        "تی‌شرت",
        "پالتو",
        "خرید",
        "فروشگاه",
        "محصول",
        "قیمت",
        "ارزان",
        "اقتصادی",
        "خریداری",
        "لینک",
        "سایز"
    ]

    message_lower = message.lower()

    return any(
        keyword in message_lower
        for keyword in keywords
    )


# =========================================================
# AGENT
# =========================================================

def run_agent(
    message: str,
    profile: UserProfile | None = None,
    conversation=None
) -> tuple[str, list]:

    conversation = conversation or []

    profile_context = build_profile_context(
        profile
    )

    products: list[Product] = []

    # -----------------------------------------------------
    # Product search
    # -----------------------------------------------------

    if should_search_products(message):

        min_price = (
            profile.min_price
            if profile
            else None
        )

        max_price = (
            profile.max_price
            if profile
            else None
        )

        products = search_products(
            query=message,
            min_price=min_price,
            max_price=max_price
        )

    # -----------------------------------------------------
    # Build messages
    # -----------------------------------------------------

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "system",
            "content": (
                "اطلاعات فعلی پروفایل کاربر:\n\n"
                + profile_context
            )
        }
    ]

    # حافظه کوتاه‌مدت
    if conversation:
        messages.extend(
            conversation
        )

    # اطلاعات واقعی محصولات
    if products:

        product_context = (
            format_products_for_ai(
                products
            )
        )

        messages.append(
            {
                "role": "system",
                "content": (
                    "محصولات واقعی دریافت‌شده از ابزار جستجو:\n\n"
                    + product_context
                )
            }
        )

    else:

        messages.append(
            {
                "role": "system",
                "content": (
                    "در حال حاضر محصول واقعی از فروشگاه "
                    "دریافت نشده است. "
                    "اطلاعات محصول، قیمت، لینک یا فروشگاه "
                    "اختراع نکن."
                )
            }
        )

    # پیام جدید کاربر
    messages.append(
        {
            "role": "user",
            "content": message
        }
    )

    # -----------------------------------------------------
    # AI Request
    # -----------------------------------------------------

    response = client.chat.completions.create(
        model=AI_MODEL,
        messages=messages,
        temperature=0.7
    )

    answer = response.choices[0].message.content

    if not answer:
        answer = (
            "متأسفانه نتونستم پاسخ مناسبی آماده کنم."
        )

    return answer, products