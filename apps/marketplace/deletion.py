from django.db.models import CASCADE


def preserve_community_applications(collector, field, sub_objs, using):
    """Keep community applications and their releases when an author is deleted."""
    collector.add_field_update(field, None, sub_objs.filter(community_protected=True))
    CASCADE(collector, field, sub_objs.filter(community_protected=False), using)
