APPLICATIONS_INDEX = "applications"
USERS_INDEX = "users"

APP_LANG_SUFFIXES = ("", "_ru", "_en", "_uk", "_be", "_kk")

APPLICATION_SEARCHABLE = [
    "title",
    "description",
    "slogan",
    "original_author",
]
for _suffix in APP_LANG_SUFFIXES:
    if _suffix:
        APPLICATION_SEARCHABLE.extend([
            f"title{_suffix}",
            f"description{_suffix}",
            f"slogan{_suffix}",
        ])

APPLICATION_FILTERABLE = [
    "user_id",
    "category_ids",
    "price",
    "is_private",
    "is_under_dmca",
]

APPLICATION_SORTABLE = ["id"]

USER_SEARCHABLE = ["username", "description"]
USER_FILTERABLE = ["is_active"]
USER_SORTABLE = ["id"]

APPLICATION_INDEX_SETTINGS = {
    "searchableAttributes": APPLICATION_SEARCHABLE,
    "filterableAttributes": APPLICATION_FILTERABLE,
    "sortableAttributes": APPLICATION_SORTABLE,
}

USER_INDEX_SETTINGS = {
    "searchableAttributes": USER_SEARCHABLE,
    "filterableAttributes": USER_FILTERABLE,
    "sortableAttributes": USER_SORTABLE,
}

SUGGEST_APP_ATTRIBUTES = ["id", "title", "icon_url"]
SUGGEST_USER_ATTRIBUTES = ["id", "username", "avatar_url"]
