from whitenoise.storage import CompressedManifestStaticFilesStorage


class StaticFilesStorage(CompressedManifestStaticFilesStorage):
    manifest_strict = False

    def url(self, name, force=False):
        while name.startswith("./"):
            name = name[2:]

        clean_name = name.lstrip("/")
        try:
            hashed_url = super().url(clean_name, force=force)
            # If the hashed file does not actually exist in storage, fall back to unhashed clean_name
            target = hashed_url
            if target.startswith(self.base_url):
                target = target[len(self.base_url):]
            if self.exists(target):
                return hashed_url
            return f"{self.base_url}{clean_name}"
        except (ValueError, KeyError):
            return f"{self.base_url}{clean_name}"
