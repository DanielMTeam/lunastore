from unfold.widgets import UnfoldAdminFileFieldWidget


class SupportAdminFileWidget(UnfoldAdminFileFieldWidget):
    # Keep Unfold's file styling/JS while using the project's named localization keys.
    template_name = 'admin/support/widgets/file.html'
