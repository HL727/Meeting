import re

from django.conf import settings
from django.contrib.staticfiles.storage import ManifestStaticFilesStorage
from whitenoise.storage import CompressedManifestStaticFilesStorage


class NotStrictManifestStaticFilesStorage(ManifestStaticFilesStorage):
    manifest_strict = False


class NotStrictCompressedManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    manifest_strict = False

    def hashed_name(self, name, *args, **kwargs):
        # Dont hash webpack files again
        if name and re.match(settings.WHITENOISE_IMMUTABLE_FILE_TEST, name):
            return name

        # dont rewrite tinymce filenames. too much dynamic urls in the version running now
        if 'js/tinymce/' in name:  # ignore tinymce urls
            return name

        try:
            return super().hashed_name(name, *args, **kwargs)
        except ValueError:
            if self.manifest_strict:
                raise
            return name
