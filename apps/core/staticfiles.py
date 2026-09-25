from whitenoise.storage import CompressedManifestStaticFilesStorage


class StaticFilesStorage(CompressedManifestStaticFilesStorage):
    manifest_strict = False

    def url(self, name, force=False):
        while name.startswith("./"):
            name = name[2:]

        clean_name = name.lstrip("/")
        try:
            return super().url(clean_name, force=force)
        except (ValueError, KeyError):
            return f"{self.base_url}{clean_name}"
