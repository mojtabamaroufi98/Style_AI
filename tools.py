from typing import List
from models import Product


def search_products(
    query: str,
    min_price: int | None = None,
    max_price: int | None = None,
) -> List[Product]:
    """
    Search real products from Iranian stores.

    IMPORTANT:
    This function currently has no real store/provider connected.
    Therefore it returns an empty list instead of fabricating
    product names, prices or URLs.
    """

    print(
        f"[PRODUCT SEARCH] query={query}, "
        f"min_price={min_price}, max_price={max_price}"
    )

    return []


def format_products_for_ai(products: List[Product]) -> str:
    if not products:
        return (
            "هیچ محصول واقعی از فروشگاه متصل دریافت نشده است. "
            "قیمت، لینک، نام فروشگاه یا موجودی محصول اختراع نکن."
        )

    lines = []

    for product in products:
        lines.append(
            f"""
نام: {product.name}
فروشگاه: {product.store}
قیمت: {product.price}
قیمت قبلی: {product.old_price}
سایزها: {", ".join(product.sizes)}
رنگ‌ها: {", ".join(product.colors)}
جنس: {product.material}
لینک: {product.url}
""".strip()
        )

    return "\n\n".join(lines)