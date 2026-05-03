from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_widen_tblpersonnel_dept"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS tblrequestreference (
                    referenceno SERIAL PRIMARY KEY,
                    requestno INTEGER NOT NULL UNIQUE,
                    filename VARCHAR(255) NOT NULL DEFAULT '',
                    contenttype VARCHAR(100) NOT NULL DEFAULT '',
                    filedata BYTEA NOT NULL,
                    uploadedat DATE NOT NULL DEFAULT CURRENT_DATE
                );
            """,
            reverse_sql="DROP TABLE IF EXISTS tblrequestreference;",
        ),
    ]
