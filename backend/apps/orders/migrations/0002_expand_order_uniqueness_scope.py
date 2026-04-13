from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='organizationorder',
            unique_together={('order_no', 'order_date', 'organization', 'route', 'currency_type', 'denomination')},
        ),
    ]
