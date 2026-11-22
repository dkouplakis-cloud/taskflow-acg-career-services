
from django.db import migrations


def seed_team_members(apps, schema_editor):
    """
    Populate the database with the five
    ACG Career Services team members.

    Existing records will not be duplicated.
    """

    TeamMember = apps.get_model(
        'core',
        'TeamMember'
    )

    database = schema_editor.connection.alias

    team_members = [
        (
            'Dimitris Megremis',
            'Senior Director'
        ),
        (
            'Marina Perantonaki',
            'Senior Manager'
        ),
        (
            'Alexandra Prindezi',
            'Manager'
        ),
        (
            'Efthimis Charokopos',
            'Senior Counsellor'
        ),
        (
            'Elina Krithari',
            'Special Projects Coordinator'
        ),
    ]

    for full_name, job_title in team_members:
        TeamMember.objects.using(database).get_or_create(
            full_name=full_name,
            defaults={
                'job_title': job_title,
                'is_active': True
            }
        )


class Migration(migrations.Migration):

    dependencies = [
        (
            'core',
            '0002_teammember'
        ),
    ]

    operations = [
        migrations.RunPython(
            seed_team_members,
            migrations.RunPython.noop
        ),
    ]