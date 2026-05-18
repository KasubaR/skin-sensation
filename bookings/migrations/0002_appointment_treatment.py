import django.db.models.deletion
from django.db import migrations, models


def migrate_appointment_lines_forward(apps, schema_editor):
    BookableService = apps.get_model('services', 'BookableService')
    Treatment = apps.get_model('services', 'Treatment')
    AppointmentService = apps.get_model('bookings', 'AppointmentService')

    slug_map = {t.slug: t for t in Treatment.objects.all()}
    for old in BookableService.objects.all():
        treatment = slug_map.get(old.slug)
        if not treatment:
            continue
        AppointmentService.objects.filter(service_id=old.pk).update(treatment=treatment)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0001_initial'),
        ('services', '0003_service_treatment_restructure'),
    ]

    operations = [
        migrations.AddField(
            model_name='appointmentservice',
            name='treatment',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='appointment_links',
                to='services.treatment',
            ),
        ),
        migrations.RunPython(migrate_appointment_lines_forward, noop_reverse),
        migrations.RemoveField(
            model_name='appointmentservice',
            name='service',
        ),
        migrations.AlterField(
            model_name='appointmentservice',
            name='treatment',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='appointment_links',
                to='services.treatment',
            ),
        ),
    ]
