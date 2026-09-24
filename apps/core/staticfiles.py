from whitenoise.storage import CompressedManifestStaticFilesStorage


class StaticFilesStorage(CompressedManifestStaticFilesStorage):
    def url(self, name, force=False):
        while name.startswith("./"):
            name = name[2:]

            
        try:
            return super().url(name, force=True)
        except ValueError as e:
            if "could not be found" in str(e):
                return name
            raise