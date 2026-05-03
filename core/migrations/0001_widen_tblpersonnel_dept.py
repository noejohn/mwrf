from django.db import migrations


class Migration(migrations.Migration):
    dependencies = []

    operations = [
        migrations.RunSQL(
            sql='ALTER TABLE "tblpersonnel" ALTER COLUMN "personneldept" TYPE varchar(50);',
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
