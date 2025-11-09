from pathlib import Path

from django.core.management.base import BaseCommand

from ._data_import import (
    default_data_path,
    import_customers_from_csv,
    import_customers_from_records,
)


class Command(BaseCommand):
    help = "Import Users + CustomerProfiles from CSV. Uses pandas when available."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            dest="csv_path",
            help="Path to customers CSV (default: data/b2c_customers_100.csv)",
        )

    def handle(self, *args, **options):
        csv_path = Path(options.get("csv_path") or default_data_path("b2c_customers_100.csv"))
        try:
            import pandas as pd  # type: ignore

            encodings = ["utf-8-sig", "utf-8", "cp1252", "latin1"]
            last_err = None
            df = None
            for enc in encodings:
                try:
                    df = pd.read_csv(csv_path, encoding=enc)
                    break
                except Exception as e:
                    last_err = e
                    df = None
            if df is None:
                raise last_err  # type: ignore[misc]
            records = df.to_dict(orient="records")
            created = import_customers_from_records(records)
        except ModuleNotFoundError:
            created = import_customers_from_csv(csv_path)
        except Exception:
            created = import_customers_from_csv(csv_path)

        self.stdout.write(self.style.SUCCESS(f"Customer import complete: created={created}"))
