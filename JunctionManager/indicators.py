# SPDX-License-Identifier: MIT
"""Optional transparent adornment; native mod-list painting stays untouched."""
from pathlib import Path
import logging
from PyQt6.QtCore import Qt, QTimer, QRect
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QStyledItemDelegate, QTreeView, QToolTip
from .storage import discover


class AdornedNames(QStyledItemDelegate):
    def __init__(self, tree, base, catalog):
        super().__init__(tree)
        self.base = base
        self.catalog = catalog
        self.symbol = QIcon(str(Path(__file__).parent / 'assets/link.svg'))

    @staticmethod
    def icon_area(option):
        edge = min(13, option.rect.height() - 4)
        return QRect(option.rect.right() - edge - 4, option.rect.center().y() - edge // 2, edge, edge)

    def paint(self, painter, option, index):
        self.base.paint(painter, option, index)
        if str(index.data() or '').casefold() in self.catalog.names and option.rect.width() > 60:
            self.symbol.paint(painter, self.icon_area(option))

    def sizeHint(self, option, index):
        extent = self.base.sizeHint(option, index)
        if str(index.data() or '').casefold() in self.catalog.names:
            extent.setWidth(extent.width() + 21)
        return extent

    def helpEvent(self, event, view, option, index):
        if str(index.data() or '').casefold() in self.catalog.names and self.icon_area(option).contains(event.pos()):
            QToolTip.showText(event.globalPos(), 'Linked mod folder — inspect its source in Junction Manager.', view)
            return True
        return self.base.helpEvent(event, view, option, index)


class Indicators:
    def __init__(self, organizer, host):
        self.organizer = organizer
        self.names = set()
        self.tree = host.findChild(QTreeView, 'modList')
        self.timer = None
        if self.tree is None:
            logging.warning('Junction Manager: native modList widget unavailable; indicators disabled.')
            return
        native = self.tree.itemDelegateForColumn(0) or self.tree.itemDelegate()
        self.drawing = AdornedNames(self.tree, native, self)
        self.tree.setItemDelegateForColumn(0, self.drawing)
        self.timer = QTimer(self.tree)
        self.timer.setInterval(4000)
        self.timer.timeout.connect(self.update)
        self.timer.start()
        self.update()

    def update(self):
        try:
            latest = {item.destination.name.casefold() for item in discover(self.organizer.modsPath())}
        except OSError:
            return
        if latest != self.names:
            self.names = latest
            self.tree.viewport().update()
