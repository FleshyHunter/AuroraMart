"""Launch vouchers scheduled for today's month/day.

This command should be run daily (cron / systemd timer / CI) and will:
 - find vouchers with `scheduled_auto_launch=True` and matching scheduled_month/day
 - if a voucher currently has zero assignments, auto-launch it (create assignments)
 - respect the welcome-voucher uniqueness rule (use assign_to_customers)

Run:
    python3 manage.py launch_scheduled_vouchers
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from admin_panel.models import Voucher, VoucherAssignment
from ecommercemodule.models import Customer
from datetime import timedelta


class Command(BaseCommand):
    help = 'Launch vouchers scheduled for today if they currently have no assignments.'

    def handle(self, *args, **options):
        today = timezone.now().date()
        month = today.month
        day = today.day

        qs = Voucher.objects.filter(scheduled_auto_launch=True, scheduled_month=month, scheduled_day=day)
        total = qs.count()
        if total == 0:
            self.stdout.write('No scheduled vouchers for today.')
            return

        customers = Customer.objects.all()
        num_customers = customers.count()

        for v in qs:
            self.stdout.write(f'Processing scheduled voucher: {v.code} ({v.name})')

            # only launch if voucher currently has no assignments
            has_any = VoucherAssignment.objects.filter(voucher=v).exists()
            if has_any:
                self.stdout.write(f'  - Skipping (already has assignments)')
                continue

            # special-case welcome voucher
            welcome_codes = {'WELCOME10'}
            is_welcome = (v.code and v.code.upper() in welcome_codes) or (v.name and v.name.lower().startswith('welcome'))

            if is_welcome:
                created = v.assign_to_customers(customers)
                self.stdout.write(f'  - Welcome voucher assigned to {created} customers')
                continue

            now = timezone.now()
            expires_delta = timedelta(days=v.days_valid)
            assignments = [
                VoucherAssignment(voucher=v, customer=c, assigned_at=now, expires_at=now + expires_delta)
                for c in customers
            ]
            VoucherAssignment.objects.bulk_create(assignments)
            self.stdout.write(f'  - Created {len(assignments)} assignments')

        self.stdout.write(self.style.SUCCESS('Done.'))
