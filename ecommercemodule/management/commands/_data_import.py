from __future__ import annotations

from csv import DictReader, reader
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.db import transaction
from django.utils.text import slugify

from ecommercemodule.models import (
    Category,
    Customer,
    Order,
    OrderItem,
    Product,
    SubCategory,
)


User = get_user_model()

PRODUCT_HEADERS = {
    "sku": "SKU code",
    "name": "Product name",
    "description": "Product description",
    "category": "Product Category",
    "subcategory": "Product Subcategory",
    "qoh": "Quantity on hand",
    "reorder": "Reorder Quantity",
    "price": "Unit price",
    "rating": "Product rating",
}

CUSTOMER_HEADERS = [
    "age",
    "gender",
    "employment_status",
    "occupation",
    "education",
    "household_size",
    "has_children",
    "monthly_income_sgd",
    "preferred_category",
]

TRANSACTION_TRUE_VALUES = {"1", "true", "True", "YES", "yes"}


def default_data_path(filename: str) -> Path:
    base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
    return base_dir / "data" / filename


def _parse_int(value: object, field: str, allow_blank: bool = False) -> int:
    if value is None or str(value).strip() == "":
        if allow_blank:
            return 0
        raise CommandError(f"Missing value for {field}")
    try:
        result = int(str(value).strip())
    except Exception as exc:
        raise CommandError(f"Invalid integer for {field}: {value!r}") from exc
    if result < 0:
        raise CommandError(f"{field} cannot be negative (value={result})")
    return result


def _parse_decimal(value: object, field: str, allow_blank: bool = False) -> Decimal:
    if value is None or str(value).strip() == "":
        if allow_blank:
            return Decimal("0.00")
        raise CommandError(f"Missing value for {field}")
    try:
        result = Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise CommandError(f"Invalid decimal for {field}: {value!r}") from exc
    if result < 0:
        raise CommandError(f"{field} cannot be negative (value={result})")
    return result.quantize(Decimal("0.01"))


def _parse_rating(value: object) -> Optional[float]:
    if value is None or str(value).strip() == "":
        return None
    try:
        rating = float(str(value).strip())
    except ValueError as exc:
        raise CommandError(f"Invalid rating (0-5): {value!r}") from exc
    if not 0 <= rating <= 5:
        raise CommandError(f"Rating must be between 0 and 5 (value={rating})")
    return rating


def _get_category(name: str) -> Category:
    name = (name or "").strip()
    if not name:
        raise CommandError("Category name cannot be blank")
    category, _ = Category.objects.get_or_create(name=name, defaults={"slug": slugify(name)})
    expected_slug = slugify(category.name)
    if category.slug != expected_slug:
        category.slug = expected_slug
        category.save(update_fields=["slug"])
    return category


def _get_subcategory(category: Category, name: str) -> SubCategory:
    name = (name or "").strip()
    if not name:
        raise CommandError("Subcategory name cannot be blank")
    subcategory, _ = SubCategory.objects.get_or_create(
        category=category, name=name, defaults={"slug": slugify(name)}
    )
    return subcategory


def import_products_from_csv(csv_path: Path, update_existing: bool = False) -> Tuple[int, int, int]:
    if not csv_path.exists():
        raise CommandError(f"Products CSV not found: {csv_path}")

    created = updated = skipped = 0
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        csv_reader = DictReader(handle)
        missing = [label for label in PRODUCT_HEADERS.values() if label not in (csv_reader.fieldnames or [])]
        if missing:
            fieldnames = csv_reader.fieldnames or []
            looks_like_transactions = bool(fieldnames) and all(
                isinstance(col, str) and col and (" " not in col) for col in fieldnames
            )
            hint = (
                " It looks like you may have passed the transactions CSV. Use: `python manage.py import_transactions --csv <transactions.csv>`"
                if looks_like_transactions
                else ""
            )
            raise CommandError(f"Product CSV missing headers: {missing}.{hint}")

        for line_number, row in enumerate(csv_reader, start=2):
            try:
                sku = str(row[PRODUCT_HEADERS["sku"]]).strip()
                if not sku:
                    raise CommandError("SKU is required")
                name = str(row[PRODUCT_HEADERS["name"]]).strip()
                description = (row[PRODUCT_HEADERS["description"]] or "").strip()
                category = _get_category(row[PRODUCT_HEADERS["category"]])
                subcategory = _get_subcategory(category, row[PRODUCT_HEADERS["subcategory"]])
                qoh = _parse_int(row[PRODUCT_HEADERS["qoh"]], "Quantity on hand", allow_blank=True)
                reorder = _parse_int(row[PRODUCT_HEADERS["reorder"]], "Reorder Quantity", allow_blank=True)
                price = _parse_decimal(row[PRODUCT_HEADERS["price"]], "Unit price", allow_blank=True)
                rating = _parse_rating(row[PRODUCT_HEADERS["rating"]])

                defaults = dict(
                    name=name,
                    description=description,
                    category=category,
                    subcategory=subcategory,
                    quantity_on_hand=qoh,
                    reorder_quantity=reorder,
                    unit_price=price,
                    rating=rating,
                    is_active=True,
                )

                product, created_flag = Product.objects.get_or_create(sku=sku, defaults=defaults)
                if created_flag:
                    created += 1
                elif update_existing:
                    for field, value in defaults.items():
                        setattr(product, field, value)
                    product.save()
                    updated += 1
                else:
                    skipped += 1
            except CommandError as exc:
                raise CommandError(f"Products row {line_number}: {exc}") from exc

    return created, updated, skipped


def import_products_from_records(records: List[dict], update_existing: bool = False) -> Tuple[int, int, int]:
    if not records:
        return 0, 0, 0
    missing = [label for label in PRODUCT_HEADERS.values() if label not in records[0].keys()]
    if missing:
        raise CommandError(f"Product data missing headers: {missing}")

    created = updated = skipped = 0
    for idx, row in enumerate(records, start=2):
        try:
            sku = str(row[PRODUCT_HEADERS["sku"]]).strip()
            if not sku:
                raise CommandError("SKU is required")
            name = str(row[PRODUCT_HEADERS["name"]]).strip()
            description = (row.get(PRODUCT_HEADERS["description"]) or "").strip()
            category = _get_category(row[PRODUCT_HEADERS["category"]])
            subcategory = _get_subcategory(category, row[PRODUCT_HEADERS["subcategory"]])
            qoh = _parse_int(row.get(PRODUCT_HEADERS["qoh"]), "Quantity on hand", allow_blank=True)
            reorder = _parse_int(row.get(PRODUCT_HEADERS["reorder"]), "Reorder Quantity", allow_blank=True)
            price = _parse_decimal(row.get(PRODUCT_HEADERS["price"]), "Unit price", allow_blank=True)
            rating = _parse_rating(row.get(PRODUCT_HEADERS["rating"]))

            defaults = dict(
                name=name,
                description=description,
                category=category,
                subcategory=subcategory,
                quantity_on_hand=qoh,
                reorder_quantity=reorder,
                unit_price=price,
                rating=rating,
                is_active=True,
            )
            product, created_flag = Product.objects.get_or_create(sku=sku, defaults=defaults)
            if created_flag:
                created += 1
            elif update_existing:
                for field, value in defaults.items():
                    setattr(product, field, value)
                product.save()
                updated += 1
            else:
                skipped += 1
        except CommandError as exc:
            raise CommandError(f"Products row {idx}: {exc}") from exc
    return created, updated, skipped


def _unique_username(start_index: int) -> Tuple[str, str, int]:
    counter = start_index
    while True:
        username = f"customer{counter:04d}"
        email = f"{username}@example.com"
        counter += 1
        if not User.objects.filter(username=username).exists():
            return username, email, counter


def import_customers_from_csv(csv_path: Path) -> int:
    if not csv_path.exists():
        raise CommandError(f"Customers CSV not found: {csv_path}")

    created = 0
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        csv_reader = DictReader(handle)
        missing = [header for header in CUSTOMER_HEADERS if header not in (csv_reader.fieldnames or [])]
        if missing:
            raise CommandError(f"Customer CSV missing headers: {missing}")

        counter = User.objects.count() + 1
        for line_number, row in enumerate(csv_reader, start=2):
            username, email, counter = _unique_username(counter)
            user = User.objects.create(username=username, email=email)
            user.set_unusable_password()
            user.save(update_fields=["password"])

            preferred_name = (row.get("preferred_category") or "").strip()
            preferred_category = _get_category(preferred_name) if preferred_name else None

            def _optional_int(value: str) -> Optional[int]:
                if value in (None, "", "NA"):
                    return None
                try:
                    return int(float(value))
                except ValueError as exc:
                    raise CommandError(f"Invalid integer value: {value!r}") from exc

            def _optional_decimal(value: str) -> Optional[Decimal]:
                if value in (None, ""):
                    return None
                try:
                    val = Decimal(str(value)).quantize(Decimal("0.01"))
                except InvalidOperation as exc:
                    raise CommandError(f"Invalid decimal value: {value!r}") from exc
                if val < 0:
                    raise CommandError(f"Decimal cannot be negative: {value!r}")
                return val

            Customer.objects.create(
                user=user,
                age=_optional_int(row.get("age")),
                gender=row.get("gender", ""),
                employment_status=row.get("employment_status", ""),
                occupation=row.get("occupation", ""),
                education=row.get("education", ""),
                household_size=_optional_int(row.get("household_size")),
                has_children=str(row.get("has_children", "0")).strip() in TRANSACTION_TRUE_VALUES,
                monthly_income_sgd=_optional_decimal(row.get("monthly_income_sgd")),
                preferred_category=preferred_category,
            )
            created += 1

    return created


def import_customers_from_records(records: List[dict]) -> int:
    if not records:
        return 0
    missing = [header for header in CUSTOMER_HEADERS if header not in records[0].keys()]
    if missing:
        raise CommandError(f"Customer data missing headers: {missing}")

    created = 0
    counter = User.objects.count() + 1
    for line_number, row in enumerate(records, start=2):
        username, email, counter = _unique_username(counter)
        user = User.objects.create(username=username, email=email)
        user.set_unusable_password()
        user.save(update_fields=["password"])

        preferred_name = (row.get("preferred_category") or "").strip()
        preferred_category = _get_category(preferred_name) if preferred_name else None

        def _optional_int(value: str) -> Optional[int]:
            if value in (None, "", "NA"):
                return None
            try:
                return int(float(value))
            except ValueError as exc:
                raise CommandError(f"Invalid integer value: {value!r}") from exc

        def _optional_decimal(value: str) -> Optional[Decimal]:
            if value in (None, ""):
                return None
            try:
                result = Decimal(str(value)).quantize(Decimal("0.01"))
            except InvalidOperation as exc:
                raise CommandError(f"Invalid decimal value: {value!r}") from exc
            if result < 0:
                raise CommandError(f"Decimal cannot be negative: {value!r}")
            return result

        Customer.objects.create(
            user=user,
            age=_optional_int(row.get("age")),
            gender=row.get("gender", ""),
            employment_status=row.get("employment_status", ""),
            occupation=row.get("occupation", ""),
            education=row.get("education", ""),
            household_size=_optional_int(row.get("household_size")),
            has_children=str(row.get("has_children", "0")).strip() in TRANSACTION_TRUE_VALUES,
            monthly_income_sgd=_optional_decimal(row.get("monthly_income_sgd")),
            preferred_category=preferred_category,
        )
        created += 1

    return created


def import_transactions_from_csv(csv_path: Path, max_orders: int = 1000) -> int:
    if not csv_path.exists():
        raise CommandError(f"Transactions CSV not found: {csv_path}")

    customers = list(Customer.objects.select_related("user"))
    if not customers:
        user = User.objects.create(username="dataset_customer", email="dataset@example.com")
        user.set_unusable_password()
        user.save(update_fields=["password"])
        customers = [Customer.objects.create(user=user)]

    orders_created = 0
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        csv_reader = reader(handle)
        try:
            header = next(csv_reader)
        except StopIteration:
            return 0

        skus = [str(value).strip() for value in header if str(value).strip()]
        product_lookup: Dict[str, Product] = Product.objects.in_bulk(field_name="sku")

        for line_number, row in enumerate(csv_reader, start=2):
            if max_orders and orders_created >= max_orders:
                break

            flags = row[: len(skus)]
            order_items: List[Tuple[Product, int]] = []
            for sku, flag in zip(skus, flags):
                if str(flag).strip() not in TRANSACTION_TRUE_VALUES:
                    continue
                product = product_lookup.get(sku)
                if product:
                    order_items.append((product, 1))

            if not order_items:
                continue

            customer = customers[orders_created % len(customers)]
            total = sum((product.unit_price * quantity for product, quantity in order_items), Decimal("0.00"))

            with transaction.atomic():
                order = Order.objects.create(customer=customer, total_amount=total)
                OrderItem.objects.bulk_create(
                    [
                        OrderItem(
                            order=order,
                            product=product,
                            quantity=quantity,
                            unit_price=product.unit_price,
                        )
                        for product, quantity in order_items
                    ]
                )
            orders_created += 1

    return orders_created

