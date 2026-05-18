import django.db.models.deletion
from django.db import migrations, models


def migrate_catalog_forward(apps, schema_editor):
    ServiceCategory = apps.get_model('services', 'ServiceCategory')
    BookableService = apps.get_model('services', 'BookableService')
    Service = apps.get_model('services', 'Service')
    Treatment = apps.get_model('services', 'Treatment')

    category_to_service = {}
    for cat in ServiceCategory.objects.all():
        parent, _ = Service.objects.get_or_create(
            slug=cat.slug,
            defaults={
                'name': cat.name,
                'description': cat.description,
                'sort_order': getattr(cat, 'sort_order', 0),
                'is_active': True,
            },
        )
        category_to_service[cat.pk] = parent

    for old in BookableService.objects.select_related('category'):
        parent = category_to_service.get(old.category_id)
        if not parent:
            continue
        Treatment.objects.update_or_create(
            slug=old.slug,
            defaults={
                'service': parent,
                'name': old.name,
                'description': old.description,
                'duration_minutes': old.duration_minutes,
                'price': old.price,
                'price_from': getattr(old, 'price_from', False),
                'price_label': getattr(old, 'price_label', ''),
                'image': old.image,
                'is_featured': old.is_featured,
                'is_active': old.is_active,
                'sort_order': getattr(old, 'sort_order', 0),
            },
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0002_alter_service_options_alter_servicecategory_options_and_more'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Service',
            new_name='BookableService',
        ),
        migrations.AlterModelOptions(
            name='bookableservice',
            options={'ordering': ['category', 'sort_order', 'name']},
        ),
        migrations.CreateModel(
            name='Service',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('slug', models.SlugField(max_length=255, unique=True)),
                ('description', models.TextField(blank=True)),
                ('tagline', models.CharField(blank=True, max_length=255)),
                ('image', models.ImageField(blank=True, upload_to='services/')),
                ('sort_order', models.PositiveSmallIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='Treatment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('slug', models.SlugField(max_length=255, unique=True)),
                ('description', models.TextField(blank=True)),
                ('benefits', models.TextField(blank=True, help_text='One benefit per line, shown on the treatment detail page.')),
                ('duration_minutes', models.PositiveSmallIntegerField()),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('price_from', models.BooleanField(default=False, help_text='Show "From" before the price (e.g. variable or tiered pricing).')),
                ('price_label', models.CharField(blank=True, help_text='Optional override, e.g. K500–K1,000', max_length=64)),
                ('image', models.ImageField(blank=True, upload_to='services/')),
                ('subsection', models.CharField(blank=True, help_text='Non-empty groups treatments under a subheading (e.g. Add-On Treatments).', max_length=64)),
                ('is_featured', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('sort_order', models.PositiveSmallIntegerField(default=0)),
                ('service', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='treatments', to='services.service')),
            ],
            options={
                'ordering': ['service', 'subsection', 'sort_order', 'name'],
            },
        ),
        migrations.AddIndex(
            model_name='treatment',
            index=models.Index(fields=['is_active', 'is_featured'], name='services_tr_is_acti_idx'),
        ),
        migrations.AddIndex(
            model_name='treatment',
            index=models.Index(fields=['service', 'is_active'], name='services_tr_service_idx'),
        ),
        migrations.RunPython(migrate_catalog_forward, noop_reverse),
    ]
