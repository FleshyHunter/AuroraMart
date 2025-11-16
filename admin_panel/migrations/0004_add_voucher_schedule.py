from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0003_remove_voucherassignment_unique_together'),
    ]

    operations = [
        migrations.AddField(
            model_name='voucher',
            name='scheduled_auto_launch',
            field=models.BooleanField(default=False, help_text='If set, voucher will be auto-launched on the scheduled day/month each year when the management command runs.'),
        ),
        migrations.AddField(
            model_name='voucher',
            name='scheduled_month',
            field=models.PositiveSmallIntegerField(blank=True, null=True, help_text='Month for scheduled launch (1-12)'),
        ),
        migrations.AddField(
            model_name='voucher',
            name='scheduled_day',
            field=models.PositiveSmallIntegerField(blank=True, null=True, help_text='Day of month for scheduled launch (1-31)'),
        ),
    ]
