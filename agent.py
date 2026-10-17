import os

from dotenv import load_dotenv
from openai import OpenAI

from models import UserProfile
from tools import search_products, format_products_for_ai


load_dotenv()


API_KEY = os.getenv("AI_API_KEY")
BASE_URL = os.getenv("AI_BASE_URL")
MODEL = os.getenv("AI_MODEL")


client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL
)


SYSTEM_PROMPT = """
تو StyleAI هستی؛ یک دستیار هوشمند استایل و انتخاب لباس برای کاربران فارسی‌زبان.

وظایف تو:
- پیشنهاد استایل بر اساس جنسیت، فرم بدن، قد، وزن و سایز
- توجه به استایل‌های مورد علاقه کاربر
- توجه به رنگ‌های مورد علاقه و رنگ‌های نامطلوب
- پیشنهاد لباس متناسب با موقعیت
- رعایت بودجه
- ساخت ست کامل لباس
- توضیح دلیل مناسب بودن هر پیشنهاد
- ارائه پیشنهادهای کاربردی و قابل فهم

قوانین مهم:

1. همیشه به زبان فارسی پاسخ بده مگر کاربر صریحاً زبان دیگری بخواهد.

2. پاسخ‌ها دوستانه، کاربردی و نسبتاً کوتاه باشند.

3. اطلاعات پروفایل کاربر را در پیشنهادها در نظر بگیر.

4. درباره فرم بدن محترمانه صحبت کن و از قضاوت منفی درباره ظاهر کاربر خودداری کن.

5. اگر اطلاعات کافی وجود ندارد، با اطلاعات موجود بهترین پیشنهاد ممکن را ارائه کن.

6. هیچ قیمت واقعی، تخفیف، موجودی، نام فروشگاه یا لینک خریدی را از خودت نساز.

7. فقط اطلاعات محصولی که ابزار جستجوی محصول در اختیار تو قرار داده می‌تواند به عنوان محصول واقعی معرفی شود.

8. اگر محصول واقعی پیدا نشده، می‌توانی نوع لباس پیشنهاد بدهی؛ مثلاً:
   «کت تک کرم با برش راسته»
اما نباید برای آن فروشگاه، لینک یا قیمت واقعی اختراع کنی.

9. وقتی کاربر ست لباس می‌خواهد، در صورت امکان این بخش‌ها را بررسی کن:
- بالاتنه
- پایین‌تنه
- کفش
- لایه بیرونی در صورت نیاز
- اکسسوری

10. هنگام پیشنهاد رنگ، هماهنگی رنگ‌ها و رنگ‌های مورد علاقه/نامطلوب کاربر را در نظر بگیر.

11. اگر کاربر بودجه مشخص کرده، پیشنهادها باید با آن سازگار باشند.

هدف تو کمک به کاربر برای داشتن استایل مناسب، هماهنگ و قابل اجراست.
"""


def profile_to_text(profile: UserProfile | None) -> str:
    if profile is None:
        return "پروفایل کاربر ارسال نشده است."

    return f"""
جنسیت: {profile.gender}
فرم بدن: {profile.body_shape}

قد: {profile.height_cm}
وزن: {profile.weight_kg}
سایز لباس: {profile.size}

دور سینه: {profile.chest}
دور کمر: {profile.waist}
دور باسن: {profile.hip}
عرض شانه: {profile.shoulder}

استایل‌های مورد علاقه:
{", ".join(profile.styles) if profile.styles else "مشخص نشده"}

رنگ‌های مورد علاقه:
{", ".join(profile.liked_colors) if profile.liked_colors else "مشخص نشده"}

رنگ‌های نامطلوب:
{", ".join(profile.disliked_colors) if profile.disliked_colors else "مشخص نشده"}

موقعیت‌ها:
{", ".join(profile.occasions) if profile.occasions else "مشخص نشده"}

نوع بودجه:
{profile.budget}

حداقل قیمت:
{profile.min_price}

حداکثر قیمت:
{profile.max_price}
""".strip()


def should_search_products(message: str) -> bool:
    keywords = [
        "خرید",
        "محصول",
        "فروشگاه",
        "قیمت",
        "لینک",
        "مانتو",
        "شلوار",
        "پیراهن",
        "کت",
        "کفش",
        "هودی",
        "تیشرت",
        "تی شرت",
        "لباس",
    ]

    message = message.lower()

    return any(keyword in message for keyword in keywords)


def run_agent(
    message: str,
    profile: UserProfile | None = None
) -> tuple[str, list]:

    if not API_KEY:
        raise RuntimeError(
            "AI_API_KEY داخل فایل .env تنظیم نشده است."
        )

    product_text = "جستجوی محصول برای این درخواست انجام نشده است."
    products = []

    if should_search_products(message):

        min_price = profile.min_price if profile else None
        max_price = profile.max_price if profile else None

        products = search_products(
            query=message,
            min_price=min_price,
            max_price=max_price
        )

        product_text = format_products_for_ai(products)

    user_context = f"""
پروفایل کاربر:

{profile_to_text(profile)}

درخواست کاربر:

{message}

اطلاعات محصولات واقعی:

{product_text}
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_context
            }
        ],
        temperature=0.7
    )

    answer = response.choices[0].message.content

    if not answer:
        answer = "متأسفانه نتوانستم پاسخ مناسبی تولید کنم."

    return answer, products