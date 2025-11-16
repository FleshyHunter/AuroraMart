from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0002_voucher_voucherassignment'),
    ]

    operations = [
        # Remove the previous unique_together constraint so duplicate VoucherAssignment
        # rows can be created (we allow duplicates for non-welcome vouchers by design).
        migrations.AlterUniqueTogether(
            name='voucherassignment',
            unique_together=set(),
        ),
    ]
