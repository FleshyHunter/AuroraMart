from pathlib import Path

from django.core.management.base import BaseCommand

from ._data_import import default_data_path, import_transactions_from_csv


class Command(BaseCommand):
    help = "Import historical orders from the transaction basket CSV file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            dest="csv_path",
            help="Path to the transactions CSV (default: data/b2c_products_500_transactions_50k.csv)",
        )
        parser.add_argument(
            "--max-orders",
            type=int,
            default=1000,
            help="Maximum number of orders to create (0 means no limit, default 1000)",
        )

    def handle(self, *args, **options):
        csv_path = (
            Path(options["csv_path"]) if options.get("csv_path") else default_data_path("b2c_products_500_transactions_50k.csv")
        )
        max_orders = int(options.get("max_orders") or 0)
        created = import_transactions_from_csv(csv_path, max_orders=max_orders)
        self.stdout.write(self.style.SUCCESS(f"Transaction import complete: orders_created={created}"))

