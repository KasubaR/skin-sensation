import json
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand

from gallery.models import GalleryImage

SEED_DIR = Path(settings.BASE_DIR) / 'media' / 'gallery' / 'seed'
DATA_FILE = Path(__file__).resolve().parent.parent.parent / 'data' / 'gallery_seed.json'


class Command(BaseCommand):
    help = (
        'Import gallery images from media/gallery/seed/{id}.jpg (or .png/.webp). '
        'Place files matching IDs in gallery/data/gallery_seed.json, then run this command.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List seed entries and whether matching image files exist.',
        )

    def handle(self, *args, **options):
        entries = json.loads(DATA_FILE.read_text(encoding='utf-8'))
        dry_run = options['dry_run']
        created = 0
        skipped = 0

        for entry in entries:
            entry_id = entry['id']
            image_path = self._find_image_file(entry_id)
            exists = image_path is not None

            if dry_run:
                status = 'found' if exists else 'missing file'
                self.stdout.write(f"  {entry_id}: {entry['caption']} [{status}]")
                continue

            if GalleryImage.objects.filter(caption=entry['caption']).exists():
                skipped += 1
                continue

            if not exists:
                skipped += 1
                continue

            with image_path.open('rb') as fh:
                obj = GalleryImage(
                    category=entry['category'],
                    caption=entry['caption'],
                    alt_text=entry['alt_text'],
                    layout=entry.get('layout', GalleryImage.Layout.DEFAULT),
                    sort_order=entry.get('sort_order', 0),
                    is_active=True,
                )
                obj.image.save(image_path.name, File(fh), save=True)
                created += 1

        if dry_run:
            self.stdout.write(
                self.style.NOTICE(
                    f'\n{len(entries)} entries defined. Add images to {SEED_DIR} as '
                    f'{{id}}.jpg (e.g. 01.jpg), then run without --dry-run.'
                )
            )
            return

        self.stdout.write(self.style.SUCCESS(f'Created {created} gallery image(s).'))
        if skipped:
            self.stdout.write(
                self.style.WARNING(
                    f'Skipped {skipped} (missing file or duplicate caption). '
                    f'Use dashboard to upload remaining images.'
                )
            )

    def _find_image_file(self, entry_id: str):
        for ext in ('.jpg', '.jpeg', '.png', '.webp'):
            path = SEED_DIR / f'{entry_id}{ext}'
            if path.is_file():
                return path
        return None
