import os
import json
from pathlib import Path
from decimal import Decimal, InvalidOperation

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.db import transaction
from products.models import Product
from categories.models import Category


# JSON-ის status -> Product.status (გასუფთავებული: strip + lower)
STATUS_MAP = {
    "hidden": "hidden",
    "no_image": "no_image",
    "in_stock": "in_stock",
    "out_of_stock": "out_of_stock",
    "file_img": "",        # სურათიანი = უსტატუსო
    "fille_img": "",
}

# ეს სტატუსები საიტიდანაც დაიმალოს (is_active=False)
DEACTIVATE = {"hidden"}


def load_json():
    json_path = Path(__file__).resolve().parent / "fixed_products.json"

    if not json_path.exists():
        raise FileNotFoundError(f"JSON ვერ მოიძებნა: {json_path}")

    with json_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, dict):
        data = data.get("products", [])

    if not isinstance(data, list):
        raise ValueError("JSON უნდა შეიცავდეს პროდუქტების სიას.")

    return data


def sync_statuses(data):
    """არსებულ პროდუქტებს status-ს უმატებს JSON-იდან.

    ადმინში უკვე დაყენებულ status-ს არ ეხება.
    FORCE_STATUS_SYNC=1 -> არსებულსაც გადაწერს.
    """
    force = os.environ.get("FORCE_STATUS_SYNC") == "1"
    updated = 0
    unknown = {}

    for item in data:
        if not isinstance(item, dict) or item.get("id") is None:
            continue

        raw = str(item.get("status") or "").strip().lower()
        if not raw:
            continue

        if raw not in STATUS_MAP:
            unknown[raw] = unknown.get(raw, 0) + 1
            continue

        new_status = STATUS_MAP[raw]

        qs = Product.objects.filter(id=int(item["id"]))
        if not force:
            qs = qs.filter(status="")

        fields = {"status": new_status}
        if new_status in DEACTIVATE:
            fields["is_active"] = False

        updated += qs.update(**fields)

    print(f"სტატუსი განახლდა: {updated}")
    if unknown:
        print(f"უცნობი სტატუსები (გამოტოვებულია): {unknown}")


def import_products():
    data = load_json()

    # ბაზაში უკვე პროდუქტებია -> არსებულს არ ვეხებით (ადმინიდან შეცვლილი/წაშლილი
    # პროდუქტები შენარჩუნდება), მხოლოდ ცარიელ status-ებს ვავსებთ JSON-იდან.
    if Product.objects.exists():
        print(f"ბაზაში უკვე {Product.objects.count()} პროდუქტია — იმპორტი გამოტოვებულია.")
        sync_statuses(data)
        return

    created = 0
    skipped = 0

    fields = {field.name for field in Product._meta.get_fields()}
    price_field = Product._meta.get_field("price")
    integer_price = price_field.get_internal_type() in (
        "IntegerField",
        "PositiveIntegerField",
        "BigIntegerField",
        "PositiveBigIntegerField",
    )

    img_field_name = "img" if "img" in fields else "image"
    img_max_len = getattr(Product._meta.get_field(img_field_name), "max_length", None)

    with transaction.atomic():
        for index, item in enumerate(data, start=1):
            try:
                if not isinstance(item, dict):
                    skipped += 1
                    continue

                name = str(item.get("name") or "").strip()
                if not name:
                    skipped += 1
                    print(f"{index}: სახელი არ აქვს — გამოტოვებულია")
                    continue

                categories = item.get("category", [])
                if not isinstance(categories, list):
                    categories = [categories] if categories else []

                category_name = next(
                    (
                        str(value).strip()
                        for value in categories
                        if value is not None and str(value).strip()
                    ),
                    "სხვა",
                )

                category, _ = Category.objects.get_or_create(name=category_name)

                images = item.get("images", [])
                if not isinstance(images, list):
                    images = [images] if images else []

                image = next(
                    (
                        str(value).strip()
                        for value in images
                        if value and str(value).strip()
                    ),
                    "",
                )

                # Postgres-ში ძალიან გრძელი ტექსტი (მაგ. base64 სურათი) ველში არ ეტევა
                if img_max_len and len(image) > img_max_len:
                    print(f"{index}: სურათი ძალიან გრძელია ({len(image)}), გამოტოვებულია: {name}")
                    image = ""

                raw_price = item.get("price")
                price = Decimal(str(raw_price or 0).strip())

                if not price.is_finite() or price < 0:
                    raise ValueError("არასწორი ფასი")

                if integer_price:
                    if price != price.to_integral_value():
                        raise ValueError(f"ფასი მთელი რიცხვი უნდა იყოს: {price}")
                    price = int(price)

                defaults = {
                    "name": name,
                    "price": price,
                }

                if "description" in fields:
                    defaults["description"] = item.get("description") or ""

                if "badge" in fields:
                    defaults["badge"] = item.get("badge") or ""

                if "category" in fields:
                    defaults["category"] = category

                defaults[img_field_name] = image

                # status JSON-იდან
                if "status" in fields:
                    raw_status = str(item.get("status") or "").strip().lower()
                    status_value = STATUS_MAP.get(raw_status, "")
                    defaults["status"] = status_value
                    if status_value in DEACTIVATE and "is_active" in fields:
                        defaults["is_active"] = False

                product_id = item.get("id")

                if product_id is not None:
                    Product.objects.create(id=int(product_id), **defaults)
                else:
                    Product.objects.create(**defaults)

                created += 1
                print(f"{index}/{len(data)} დაემატა: {name}")

            except (ValueError, TypeError, InvalidOperation, OverflowError) as error:
                skipped += 1
                print(f"{index}/{len(data)} გამოტოვებულია: {error}")

    print("\n========== იმპორტის შედეგი ==========")
    print(f"JSON-ში სულ: {len(data)}")
    print(f"დაემატა: {created}")
    print(f"გამოტოვებული: {skipped}")
    print(f"ბაზაში არსებული სულ: {Product.objects.count()}")
    print("=====================================")


if __name__ == "__main__":
    import_products()