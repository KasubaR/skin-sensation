from django.db import migrations


def seed_business(apps, schema_editor):
    BusinessInformation = apps.get_model('communications', 'BusinessInformation')
    BusinessInformation.objects.update_or_create(
        pk=1,
        defaults={
            'business_name': 'Skin Sensation Spa',
            'phone_number': '+260 973 407 110',
            'whatsapp_number': '260973407110',
            'email': 'info@skinsensationspa.com',
            'address': 'Kabulonga, Kudu Road, Springbok Close, Lusaka',
            'google_maps_embed_url': (
                'https://www.google.com/maps?q=Kabulonga%2C%20Kudu%20Road%2C%20'
                'Springbok%20Close%2C%20Lusaka&output=embed'
            ),
            'opening_hours': {
                'monday_friday': '8:00 am – 6:00 pm',
                'saturday': '9:00 am – 5:00 pm',
                'sunday': '10:00 am – 4:00 pm',
            },
            'whatsapp_prefill_message': (
                'Hello Skin Sensation Spa, I would like to inquire about your services.'
            ),
            'instagram_url': 'https://www.instagram.com/skinsensationbeautyspa',
        },
    )


def unseed_business(apps, schema_editor):
    BusinessInformation = apps.get_model('communications', 'BusinessInformation')
    BusinessInformation.objects.filter(pk=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('communications', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_business, unseed_business),
    ]
