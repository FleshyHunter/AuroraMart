"""
Management command to generate vouchers and assign them to all existing customers.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from admin_panel.models import Voucher, VoucherAssignment
from ecommercemodule.models import Customer


class Command(BaseCommand):
    help = 'Generate sample vouchers and assign them to all existing customers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-assignment',
            action='store_true',
            help='Only create vouchers without assigning to customers',
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing vouchers with new days_valid values',
        )
        parser.add_argument(
            '--recalculate-expiry',
            action='store_true',
            help='Recalculate expiry dates for existing assignments based on updated days_valid',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== Voucher Generation ===\n'))

        # Define vouchers to create
        vouchers_data = [
            {
                'name': 'Welcome Discount',
                'code': 'WELCOME10',
                'days_valid': 100,
                'percent_off': 10,
                'cap_amount': 10.00,
            },
            {
                'name': 'Mid-Year Sale',
                'code': 'MIDYEAR20',
                'days_valid': 30,
                'percent_off': 20,
                'cap_amount': 30.00,
            },
            {
                'name': 'Flash Sale',
                'code': 'FLASH5',
                'days_valid': 14,
                'percent_off': 5,
                'cap_amount': 5.00,
            },
        ]

        # Create vouchers
        created_vouchers = []
        for voucher_data in vouchers_data:
            voucher, created = Voucher.objects.get_or_create(
                code=voucher_data['code'],
                defaults={
                    'name': voucher_data['name'],
                    'days_valid': voucher_data['days_valid'],
                    'percent_off': voucher_data['percent_off'],
                    'cap_amount': voucher_data['cap_amount'],
                }
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Created voucher: {voucher.name} ({voucher.code}) - '
                        f'{voucher.percent_off}% off (max ${voucher.cap_amount}), '
                        f'valid for {voucher.days_valid} days'
                    )
                )
                created_vouchers.append(voucher)
            else:
                if options['update_existing']:
                    # Update existing voucher with new values
                    voucher.name = voucher_data['name']
                    voucher.days_valid = voucher_data['days_valid']
                    voucher.percent_off = voucher_data['percent_off']
                    voucher.cap_amount = voucher_data['cap_amount']
                    voucher.save()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Updated voucher: {voucher.name} ({voucher.code}) - '
                            f'{voucher.percent_off}% off (max ${voucher.cap_amount}), '
                            f'valid for {voucher.days_valid} days'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'⚠ Voucher already exists: {voucher.code}')
                    )
                created_vouchers.append(voucher)

        self.stdout.write(f'\nTotal vouchers available: {len(created_vouchers)}')

        # Assign to customers
        if not options['skip_assignment']:
            self.stdout.write(self.style.SUCCESS('\n=== Customer Assignment ===\n'))
            
            customers = Customer.objects.all()
            total_customers = customers.count()
            
            if total_customers == 0:
                self.stdout.write(self.style.WARNING('⚠ No customers found in database'))
                return

            self.stdout.write(f'Found {total_customers} customer(s)\n')

            total_assignments = 0
            skipped_assignments = 0

            for customer in customers:
                self.stdout.write(f'\nProcessing: {customer.user.username}')
                
                for voucher in created_vouchers:
                    # Check if assignment already exists
                    existing = VoucherAssignment.objects.filter(
                        voucher=voucher,
                        customer=customer
                    ).first()

                    if existing:
                        self.stdout.write(
                            f'  ⊗ Skipped {voucher.code} (already assigned)'
                        )
                        skipped_assignments += 1
                    else:
                        # Assign voucher to customer
                        assignment = voucher.assign_to_customer(customer)
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  ✓ Assigned {voucher.code} - expires {assignment.expires_at.strftime("%Y-%m-%d")}'
                            )
                        )
                        total_assignments += 1

            # Recalculate expiry dates if requested
            if options['recalculate_expiry']:
                self.stdout.write(self.style.SUCCESS('\n=== Recalculating Expiry Dates ===\n'))
                recalculated = 0
                
                for voucher in created_vouchers:
                    assignments = VoucherAssignment.objects.filter(
                        voucher=voucher,
                        used=False
                    )
                    
                    for assignment in assignments:
                        old_expiry = assignment.expires_at
                        # Recalculate expiry based on assigned_at + voucher's days_valid
                        from datetime import timedelta
                        assignment.expires_at = assignment.assigned_at + timedelta(days=voucher.days_valid)
                        assignment.save()
                        recalculated += 1
                        
                        self.stdout.write(
                            f'  ✓ {voucher.code} for {assignment.customer.user.username}: '
                            f'{old_expiry.strftime("%Y-%m-%d")} → {assignment.expires_at.strftime("%Y-%m-%d")}'
                        )
                
                self.stdout.write(f'\nRecalculated {recalculated} expiry date(s)')

            # Summary
            self.stdout.write(self.style.SUCCESS(f'\n=== Summary ==='))
            self.stdout.write(f'Vouchers created/found: {len(created_vouchers)}')
            self.stdout.write(f'Customers processed: {total_customers}')
            self.stdout.write(f'New assignments: {total_assignments}')
            self.stdout.write(f'Skipped (already assigned): {skipped_assignments}')
            if options['recalculate_expiry']:
                self.stdout.write(f'Expiry dates recalculated: {recalculated}')
            self.stdout.write(self.style.SUCCESS(f'\n✓ Done!\n'))
        else:
            self.stdout.write(self.style.WARNING('\nSkipped customer assignment (--skip-assignment flag)\n'))
