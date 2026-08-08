"""admin widgets for marketplace forms."""

from unfold.widgets import UnfoldAdminTextareaWidget


class UnfoldMarkdownTextareaWidget(UnfoldAdminTextareaWidget):
    # unfold textarea with markdown toolbar for admin editors

    template_name = "unfold/widgets/markdown_textarea.html"
