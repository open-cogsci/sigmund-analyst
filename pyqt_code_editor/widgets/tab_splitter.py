from qtpy.QtWidgets import QSplitter


class TabSplitter(QSplitter):
    
    def editors(self):
        """Returns a list of all in this splitter and all sub splitters"""
        editors = []
        for i in range(self.count()):
            editors += self.widget(i).editors()
        return editors

    def tab_widgets(self):
        """Returns a list of all tab widgets in this splitter and all sub splitters"""
        tab_widgets = []
        for i in range(self.count()):
            widget = self.widget(i)
            if isinstance(widget, TabSplitter):
                tab_widgets += widget.tab_widgets()
            else:
                tab_widgets.append(widget)
        return tab_widgets
