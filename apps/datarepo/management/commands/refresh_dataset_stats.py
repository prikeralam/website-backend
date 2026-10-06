from django.core.management.base import BaseCommand

from apps.datarepo.models import Dataset


class Command(BaseCommand):
    help = "Recompute every dataset's row count, column count and column names from its file."

    def handle(self, *args, **options):
        for dataset in Dataset.objects.exclude(file=""):
            dataset.refresh_file_stats()
            dataset.save(update_fields=["row_count", "column_count", "columns"])
            self.stdout.write(f"{dataset.slug}: {dataset.row_count} rows, {dataset.column_count} columns")
