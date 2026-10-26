from PyQt5.QtCore import Qt

from ui.widgets import Page, label


class PlaceholderPage(Page):

    def __init__(self, win, eyebrow, title):
        super().__init__(win)
        self.add_header(eyebrow, title, "")
        self.finish()
