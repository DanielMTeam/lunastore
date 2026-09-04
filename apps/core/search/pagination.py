# page object for search.html templates (django paginator API compatible)
class MeilisearchPage:
    def __init__(self, object_list, number, paginator):
        self.object_list = object_list
        self.number = number
        self.paginator = paginator

    def __iter__(self):
        return iter(self.object_list)

    def __len__(self):
        return len(self.object_list)

    def has_next(self):
        return self.number < self.paginator.num_pages

    def has_previous(self):
        return self.number > 1

    def has_other_pages(self):
        return self.has_next() or self.has_previous()

    @property
    def previous_page_number(self):
        return self.number - 1

    @property
    def next_page_number(self):
        return self.number + 1


# meilisearch paginator: object_list is already the current page,
# total_count comes from meili estimatedTotalHits
class MeilisearchPaginator:
    def __init__(self, object_list, per_page, total_count):
        self.object_list = list(object_list)
        self.per_page = per_page
        self.count = total_count

    @property
    def num_pages(self):
        if self.count == 0:
            return 0
        return (self.count + self.per_page - 1) // self.per_page

    @property
    def page_range(self):
        return range(1, self.num_pages + 1)

    def get_page(self, number):
        try:
            number = int(number)
        except (TypeError, ValueError):
            number = 1
        if number < 1:
            number = 1
        if self.num_pages and number > self.num_pages:
            number = self.num_pages
        return MeilisearchPage(self.object_list, number, self)
