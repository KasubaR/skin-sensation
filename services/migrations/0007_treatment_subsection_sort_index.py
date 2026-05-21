from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0006_treatment_name_index'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='treatment',
            index=models.Index(
                fields=['subsection', 'sort_order', 'name'],
                name='svc_tr_subsection_sort_idx',
            ),
        ),
    ]
