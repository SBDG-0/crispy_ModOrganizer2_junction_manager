# SPDX-License-Identifier: MIT
"""Small native Qt interface. Filesystem work runs off the UI thread."""
from pathlib import Path
import threading

from PyQt6.QtCore import Qt, QThread, QTimer, QUrl, QEvent, QSize, pyqtSlot
from PyQt6.QtGui import QDesktopServices, QIcon, QKeySequence, QShortcut, QColor, QPalette
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFileDialog, QMessageBox, QStyledItemDelegate, QMenu, QStyle)
from . import storage
from .localization import tr
from .help_dialog import mo2_action


class BackgroundWork(QThread):
    def __init__(self, action, parent):
        super().__init__(parent)
        self.action = action
        self.stop = threading.Event()
        self.value = None
        self.problem = None

    def run(self):
        try:
            self.value = self.action(self.stop)
        except Exception as error:
            self.problem = str(error)


class InspectPath(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        field = QLineEdit(parent)
        field.setReadOnly(True)
        return field

    def setEditorData(self, editor, index):
        editor.setText(index.data() or '')
        QTimer.singleShot(0, lambda: editor.home(False))

    def setModelData(self, editor, model, index):
        return


class FittedTable(QTableWidget):
    """Fit columns until a user resizes them; preserve that manual choice."""
    def __init__(self, parent=None):
        super().__init__(0, 4, parent)
        self.automatic_widths = True
        self.fitting = False
        self.horizontalHeader().sectionResized.connect(self.width_changed)
        self.viewport().installEventFilter(self)
        self.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.horizontalHeader().customContextMenuRequested.connect(self.header_menu)

    def width_changed(self, section, before, after):
        if not self.fitting:
            self.automatic_widths = False

    def eventFilter(self, watched, event):
        if watched is self.viewport() and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self.fit_columns)
        return super().eventFilter(watched, event)

    def fit_columns(self):
        if not self.automatic_widths: return
        available = self.viewport().width()
        self.fitting = True
        try:
            widths = [int(available * fraction) for fraction in (.23, .10, .32)]
            widths.append(available - sum(widths))
            for column, width in enumerate(widths):
                self.setColumnWidth(column, max(45, width))
        finally:
            self.fitting = False

    def header_menu(self, point):
        menu = QMenu(self)
        reset = menu.addAction(tr('Fit columns to window'))
        if menu.exec(self.horizontalHeader().mapToGlobal(point)) == reset:
            self.automatic_widths = True
            self.fit_columns()


class FolderWindow(QWidget):
    def __init__(self, organizer, parent=None, mods_directory=None):
        super().__init__(parent)
        self.organizer = organizer
        self.mods = storage.location(mods_directory or organizer.modsPath())
        self.job = None
        self.records = []
        self.setWindowTitle('Junction Manager')
        self.setWindowIcon(QIcon(str(Path(__file__).parent / 'assets/app.svg')))
        self.resize(1040, 560)
        self.setAcceptDrops(True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 6, 10, 6)
        outer.setSpacing(6)
        target_row = QHBoxLayout()
        self.target_label = QLabel()
        target_row.addWidget(self.target_label)
        target = QLineEdit(str(self.mods))
        target.setReadOnly(True)
        target.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        target_row.addWidget(target)
        outer.addLayout(target_row)
        toolbar = QHBoxLayout()
        self.actions = {}
        for text, action in [('Add folder…', self.pick_source), ('Auto Link…', self.compare), ('Refresh', self.reload)]:
            button = QPushButton(tr(text))
            button.clicked.connect(action)
            self.actions[text] = button
            toolbar.addWidget(button)
        self.refresh_source = None
        self.actions['Refresh'].setObjectName('action_Refresh')
        self.actions['Refresh'].setIconSize(QSize(16, 16))
        self.bind_refresh_icon()
        toolbar.addStretch()
        self.query = QLineEdit()
        self.query.setPlaceholderText('Filter names or paths')
        self.query.textChanged.connect(self.populate)
        toolbar.addWidget(self.query)
        outer.addLayout(toolbar)
        drop_hint = QLabel('Drop one or more mod folders anywhere in this window')
        self.drop_hint = drop_hint
        drop_hint.setStyleSheet('color: #888; font-size: 9pt;')
        outer.addWidget(drop_hint)
        self.rows = FittedTable(self)
        self.rows.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.rows.setMinimumHeight(340)
        self.rows.verticalHeader().setMinimumSectionSize(18)
        self.rows.verticalHeader().setDefaultSectionSize(22)
        self.rows.setStyleSheet('QTableWidget::item { padding-top: 0px; padding-bottom: 0px; }')
        self.rows.setHorizontalHeaderLabels(['Mod folder', 'State', 'MO2 location', 'Original folder'])
        self.rows.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.rows.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.rows.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.rows.setAlternatingRowColors(True)
        self.rows.setWordWrap(False)
        self.rows.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.rows.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.rows.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.rows.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.rows.horizontalHeader().sectionHandleDoubleClicked.connect(self.rows.resizeColumnToContents)
        self.rows.verticalHeader().sectionHandleDoubleClicked.connect(self.rows.resizeRowToContents)
        for column in (2, 3):
            self.rows.setItemDelegateForColumn(column, InspectPath(self.rows))
        self.rows.itemSelectionChanged.connect(self.enable_actions)
        outer.addWidget(self.rows, 1)
        operations = QHBoxLayout()
        for text, action in [('Open source', lambda: self.open_selected(True)),
                             ('Show in MO2 folder', lambda: self.open_selected(False)),
                             ('Relink…', self.relink), ('Remove link', self.remove)]:
            button = QPushButton(tr(text))
            button.clicked.connect(action)
            self.actions[text] = button
            operations.addWidget(button)
        operations.addStretch()
        self.cancel_button = QPushButton('Cancel operation')
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.hide()
        operations.addWidget(self.cancel_button)
        outer.addLayout(operations)
        self.status = QLabel()
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        self.key_handlers = [QShortcut(QKeySequence(key), self, activated=handler) for key, handler in (
            ('Ctrl+T', lambda: self.open_selected(False)), ('Ctrl+S', lambda: self.open_selected(True)),
            ('F5', self.reload), ('Delete', self.remove))]
        for shortcut in self.key_handlers:
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.reload()
        self.retranslate()
        self.rows.automatic_widths = True
        QTimer.singleShot(0, self.rows.fit_columns)

    @pyqtSlot()
    def follow_refresh_icon(self):
        symbol = self.refresh_source.icon() if self.refresh_source is not None else QIcon()
        if symbol.isNull():
            symbol = self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        self.actions['Refresh'].setIcon(symbol)

    def bind_refresh_icon(self):
        source = mo2_action(self, 'action_Refresh')
        if source is not self.refresh_source:
            if self.refresh_source is not None:
                self.refresh_source.changed.disconnect(self.follow_refresh_icon)
            self.refresh_source = source
            if source is not None:
                source.changed.connect(self.follow_refresh_icon)
        self.follow_refresh_icon()

    def retranslate(self):
        self.target_label.setText(tr('MO2 mods folder'))
        for source, button in self.actions.items():
            button.setText(tr(source))
        self.query.setPlaceholderText(tr('Filter names or paths'))
        self.drop_hint.setText(tr('Drop one or more mod folders anywhere in this window'))
        self.cancel_button.setText(tr('Cancel operation'))
        self.rows.setHorizontalHeaderLabels([tr(text) for text in ('Mod folder', 'State', 'MO2 location', 'Original folder')])
        if self.job is None:
            self.reload()

    def selected(self):
        return [self.rows.item(row, 0).data(Qt.ItemDataRole.UserRole)
                for row in sorted({index.row() for index in self.rows.selectedIndexes()})]

    def enable_actions(self):
        busy, selected = self.job is not None, self.selected()
        for text, button in self.actions.items():
            needs_selection = text in ('Open source', 'Show in MO2 folder', 'Relink…', 'Remove link')
            button.setEnabled(not busy and (bool(selected) if needs_selection else True))
        self.actions['Relink…'].setEnabled(not busy and len(selected) == 1)

    def reload(self):
        if self.job is not None:
            return
        try:
            self.records = storage.discover(self.mods)
            self.populate()
            missing = sum(not item.available for item in self.records)
            self.status.setText(tr('{total} linked folders · {missing} unavailable').format(total=len(self.records), missing=missing))
        except OSError as error:
            self.status.setText(str(error))

    def populate(self):
        self.rows.setSortingEnabled(False)
        self.rows.setRowCount(0)
        query = self.query.text().casefold()
        for entry in self.records:
            if query not in (str(entry.destination) + str(entry.source)).casefold():
                continue
            row = self.rows.rowCount()
            self.rows.insertRow(row)
            values = (entry.destination.name, tr('Ready') if entry.available else tr('Unavailable'),
                      str(entry.destination), str(entry.source))
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setToolTip(value)
                if column < 2:
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, entry)
                elif column == 1:
                    light_background = self.rows.palette().color(QPalette.ColorRole.Base).lightness() > 128
                    color = ('#23854b' if entry.available else '#bf3845') if light_background else ('#62d995' if entry.available else '#ff8f8f')
                    cell.setForeground(QColor(color))
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    emphasis = cell.font()
                    emphasis.setBold(True)
                    cell.setFont(emphasis)
                self.rows.setItem(row, column, cell)
        self.rows.setSortingEnabled(True)
        self.enable_actions()

    def start(self, label, action, completed=None):
        if self.job is not None:
            return
        self.status.setText(label)
        worker = BackgroundWork(action, self)
        self.job = worker
        self.cancel_button.show()
        self.enable_actions()
        def finished():
            self.job = None
            self.cancel_button.hide()
            self.reload()
            if worker.problem:
                self.status.setText(worker.problem)
            elif completed:
                completed(worker.value)
            elif worker.value:
                self.status.setText('\n'.join(worker.value))
            worker.deleteLater()
        worker.finished.connect(finished)
        worker.start()

    def cancel(self):
        if self.job:
            self.job.stop.set()
            self.status.setText(tr('Stopping after the current filesystem operation…'))

    def changed(self, results):
        if self.mods.resolve() == storage.location(self.organizer.modsPath()).resolve():
            self.organizer.refresh()
        self.status.setText('\n'.join(results[-6:]) if results else tr('No folders changed.'))

    def pick_source(self):
        if self.job: return
        chosen = QFileDialog.getExistingDirectory(self, tr('Select a Source folder'))
        if chosen:
            self.add([Path(chosen)])

    def add(self, folders):
        def execute(stop):
            results = []
            for source in folders:
                if stop.is_set():
                    results.append(tr('Stopped. Completed links were kept.'))
                    break
                try:
                    storage.make_junction(source, self.mods / source.name)
                    results.append(tr('Linked {name}').format(name=source.name))
                except Exception as error:
                    results.append(f'{source.name}: {error}')
            return results
        self.start(tr('Creating folder links…'), execute, self.changed)

    def compare(self):
        if self.job: return
        chosen = QFileDialog.getExistingDirectory(self, tr('Select the parent folder containing mods to use as Source'))
        if not chosen: return
        def confirm(result):
            matches, notes = result
            if not matches:
                self.status.setText(tr('No identical same-name mod folders found.') + '\n' + '\n'.join(notes[:4]))
                return
            names = '\n'.join(source.name for source, _ in matches[:10])
            if len(matches) > 10: names += f'\n…and {len(matches) - 10} more'
            if QMessageBox.question(self, tr('Replace duplicate copies?'),
                    tr('{count} identical mod folders found:\n\n{names}\n\nReplace these MO2 copies with junctions to the originals? Each folder is checked again before replacement.').format(count=len(matches), names=names)) != QMessageBox.StandardButton.Yes:
                return
            def apply(stop):
                results = []
                for source, destination in matches:
                    if stop.is_set():
                        results.append(tr('Stopped. Completed conversions were kept.'))
                        break
                    try:
                        results.append(storage.convert_duplicate(source, destination, stop))
                    except storage.Stopped:
                        results.append(tr('Stopped. Current folder was left unchanged.'))
                        break
                    except Exception as error:
                        results.append(f'{source.name}: {error}')
                return notes[:3] + results
            self.start(tr('Replacing verified duplicate copies…'), apply, self.changed)
        self.start(tr('Comparing folder contents…'), lambda stop: storage.find_duplicates(chosen, self.mods, stop), confirm)

    def open_selected(self, source):
        if self.job: return
        for entry in self.selected():
            path = entry.source if source else self.mods
            if path.is_dir():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
            else:
                self.status.setText(tr('Folder is unavailable: {path}').format(path=path))

    def relink(self):
        if self.job or len(self.selected()) != 1: return
        entry = self.selected()[0]
        chosen = QFileDialog.getExistingDirectory(self, tr('Select a new Source folder'))
        if not chosen: return
        def execute(stop):
            storage.change_source(entry.destination, chosen)
            return [tr('Updated source for {name}').format(name=entry.destination.name)]
        self.start(tr('Changing source…'), execute, self.changed)

    def remove(self):
        if self.job: return
        entries = self.selected()
        if not entries: return
        if QMessageBox.question(self, tr('Remove directory links?'),
                tr('Remove {count} selected link(s) from MO2?\n\nOriginal folders and files stay in place.').format(count=len(entries))) != QMessageBox.StandardButton.Yes:
            return
        def execute(stop):
            results = []
            for entry in entries:
                if stop.is_set(): break
                try:
                    storage.unlink_folder(entry.destination)
                    results.append(tr('Removed link: {name}').format(name=entry.destination.name))
                except Exception as error:
                    results.append(str(error))
            return results
        self.start(tr('Removing directory links…'), execute, self.changed)

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if not self.job and urls and all(url.isLocalFile() and Path(url.toLocalFile()).is_dir() for url in urls):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if self.job: return
        folders = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        if folders and all(path.is_dir() for path in folders):
            event.acceptProposedAction()
            self.add(folders)

    def closeEvent(self, event):
        if self.job:
            self.cancel()
            event.ignore()
        else:
            super().closeEvent(event)
