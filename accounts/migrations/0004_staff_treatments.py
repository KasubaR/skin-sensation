from django.db import migrations, models


def migrate_staff_forward(apps, schema_editor):
    BookableService = apps.get_model('services', 'BookableService')
    Treatment = apps.get_model('services', 'Treatment')
    Staff = apps.get_model('accounts', 'Staff')

    slug_map = {t.slug: t for t in Treatment.objects.all()}
    for staff in Staff.objects.all():
        treatment_pks = []
        for old in staff.services.all():
            treatment = slug_map.get(old.slug)
            if treatment:
                treatment_pks.append(treatment.pk)
        if treatment_pks:
            staff.treatments.set(treatment_pks)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_staff_services_customerprofile'),
        ('services', '0003_service_treatment_restructure'),
        ('bookings', '0002_appointment_treatment'),
    ]

    operations = [
        migrations.AddField(
            model_name='staff',
            name='treatments',
            field=models.ManyToManyField(
                blank=True,
                help_text='Leave empty to allow all treatments.',
                related_name='staff_members',
                to='services.treatment',
            ),
        ),
        migrations.RunPython(migrate_staff_forward, noop_reverse),
        migrations.RemoveField(
            model_name='staff',
            name='services',
        ),
    ]
