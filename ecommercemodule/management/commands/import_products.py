from pathlib import Path

from django.core.management.base import BaseCommand

from ._data_import import (
    default_data_path,
    import_products_from_csv,
    import_products_from_records,
)


class Command(BaseCommand):
    help = "Import products (with categories/subcategories) from CSV. Uses pandas when available."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            dest="csv_path",
            help="Path to products CSV (default: data/b2c_products_500.csv)",
        )
        parser.add_argument(
            "--update",
            action="store_true",
            help="Update existing products when SKU already exists.",
        )

    def handle(self, *args, **options):
        csv_path = Path(options.get("csv_path") or default_data_path("b2c_products_500.csv"))
        try:
            import pandas as pd  # type: ignore

            # Be tolerant to Windows/Excel encodings.
            encodings = ["utf-8-sig", "utf-8", "cp1252", "latin1"]
            last_err = None
            df = None
            for enc in encodings:
                try:
                    df = pd.read_csv(csv_path, encoding=enc)
                    break
                except Exception as e:  # try next encoding
                    last_err = e
                    df = None
            if df is None:
                raise last_err  # type: ignore[misc]
            records = df.to_dict(orient="records")
            created, updated, skipped = import_products_from_records(
                records, update_existing=options.get("update", False)
            )
        except ModuleNotFoundError:
            created, updated, skipped = import_products_from_csv(
                csv_path, update_existing=options.get("update", False)
            )
        except Exception:
            # If pandas failed for any reason (e.g., encoding), fallback to csv module
            created, updated, skipped = import_products_from_csv(
                csv_path, update_existing=options.get("update", False)
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Products import complete: created={created}, updated={updated}, skipped={skipped}"
            )
        )
