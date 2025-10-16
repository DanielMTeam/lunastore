from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=140)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"<Category {self.name}>"


class Application(models.Model):
    category = models.ForeignKey(Category, null=True, on_delete=models.SET_NULL)
    title = models.CharField(max_length=80)
    description = models.CharField(max_length=210)
    icon = models.FilePathField(max_length=140, null=True)
    screenshots = models.JSONField(default=list)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    def __repr__(self):
        return f"<Application {self.title}>"


class Distribution(models.Model):
    app = models.ForeignKey(Application, on_delete=models.PROTECT)
    version = models.CharField(max_length=20)
    file = models.FilePathField(max_length=80, null=True)
    url = models.URLField(max_length=140, null=True)
    changelog = models.CharField(max_length=210)
    published = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["app", "published"]

    def __str__(self):
        return f"{self.app} {self.version}"

    def __repr__(self):
        return f"<Distribution {self.app} {self.version}>"


# TODO: create the authorization-specific models
# class Review(models.Model):
#     pass
