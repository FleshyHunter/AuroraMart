from django.core.management.base import BaseCommand
from django.db.models import QuerySet

from ecommercemodule.models import Product

try:
    from auroramart.ml.recommender import loaded_rules, get_recommendations
except Exception:  # pragma: no cover
    loaded_rules = None
    def get_recommendations(rules, items, metric='confidence', top_n=5):  # type: ignore
        return []


class Command(BaseCommand):
    help = "Analyze ML association rule recommendation coverage across products."

    def add_arguments(self, parser):
        parser.add_argument(
            '--metric', default='confidence', choices=['confidence', 'lift', 'support'],
            help='Metric to sort rules by when generating per-product recommendations.'
        )
        parser.add_argument(
            '--top-n', type=int, default=5, help='Top N recommendations to consider per product.'
        )
        parser.add_argument(
            '--active-only', action='store_true', help='Limit analysis to active products only.'
        )
        parser.add_argument(
            '--show-lists', action='store_true', help='Print SKU lists for each category (may be long).'
        )

    def handle(self, *args, **options):
        metric = options['metric']
        top_n = options['top_n']
        active_only = options['active_only']
        show_lists = options['show_lists']

        qs: QuerySet[Product] = Product.objects.all()
        if active_only:
            qs = qs.filter(is_active=True)

        products = list(qs)
        total = len(products)
        if total == 0:
            self.stdout.write(self.style.WARNING('No products found for analysis.'))
            return

        if loaded_rules is None:
            self.stdout.write(self.style.WARNING('No association rules loaded. All products will have zero recommendations.'))
            self._print_summary(total, 0, total)
            return

        # Precompute antecedent and consequent SKU sets directly from rules for faster reasoning.
        antecedent_skus = set()
        consequent_skus = set()
        try:
            for _, row in loaded_rules.iterrows():  # type: ignore[attr-defined]
                antecedent_skus.update(row['antecedents'])
                consequent_skus.update(row['consequents'])
        except Exception:
            self.stdout.write(self.style.ERROR('Loaded rules structure unexpected; falling back to per-product calls only.'))
            antecedent_skus = set()
            consequent_skus = set()

        with_recs = []
        no_recs = []
        not_in_any_antecedent = []
        never_recommended_as_target = []

        for p in products:
            sku = p.sku
            recs = get_recommendations(loaded_rules, [sku], metric=metric, top_n=top_n)
            if recs:
                with_recs.append(sku)
            else:
                no_recs.append(sku)
                if sku not in antecedent_skus:
                    not_in_any_antecedent.append(sku)
            if sku not in consequent_skus:
                never_recommended_as_target.append(sku)

        self._print_summary(total, len(with_recs), len(no_recs))

        self.stdout.write('Reason breakdown for products without recommendations:')
        self.stdout.write(f'- Not in any rule antecedent: {len(not_in_any_antecedent)}')
        self.stdout.write(f'- In antecedents but produced no top-{top_n} results (metric={metric}): {len(no_recs) - len(not_in_any_antecedent)}')
        self.stdout.write(f'Products never appear as consequents (cannot be recommended to others): {len(never_recommended_as_target)}')

        if show_lists:
            self.stdout.write('\nSKU Lists:')
            self.stdout.write(f'With recommendations ({len(with_recs)}): {with_recs}')
            self.stdout.write(f'Without recommendations ({len(no_recs)}): {no_recs}')
            self.stdout.write(f'Not in any antecedent ({len(not_in_any_antecedent)}): {not_in_any_antecedent}')
            self.stdout.write(f'Never in consequents ({len(never_recommended_as_target)}): {never_recommended_as_target}')

    def _print_summary(self, total: int, with_recs: int, no_recs: int):
        coverage = (with_recs / total) * 100 if total else 0.0
        self.stdout.write('\nRecommendation Coverage Summary:')
        self.stdout.write(f'Total products analyzed: {total}')
        self.stdout.write(f'Products with >=1 recommendation: {with_recs}')
        self.stdout.write(f'Products with zero recommendations: {no_recs}')
        self.stdout.write(f'Coverage: {coverage:.2f}%')