from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0003_service_treatment_restructure'),
        ('bookings', '0002_appointment_treatment'),
        ('accounts', '0004_staff_treatments'),
    ]

    operations = [
        migrations.DeleteModel(
            name='BookableService',
        ),
        migrations.DeleteModel(
            name='ServiceCategory',
        ),
    ]
