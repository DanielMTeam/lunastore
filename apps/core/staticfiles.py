from whitenoise.storage import CompressedManifestStaticFilesStorage


class StaticFilesStorage(CompressedManifestStaticFilesStorage):
    def url(self, name, force=False):
        while name.startswith("./"):
            name = name[2:]
        return super().url(name, force=True)