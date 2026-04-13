from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='organizationorder',
            name='qty_coin_001',
            field=models.PositiveIntegerField(default=0, verbose_name='0.01元包数'),
        ),
    ]
