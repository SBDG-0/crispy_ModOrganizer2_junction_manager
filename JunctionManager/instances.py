# SPDX-License-Identifier: MIT
"""Read MO2 instance locations without editing their configuration."""
from dataclasses import dataclass, replace
from pathlib import Path
import os
from PyQt6.QtCore import QSettings, Qt, QTimer, QSize, pyqtSlot
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                            QToolButton, QScrollArea, QWidget, QSizePolicy)
from .interface import FolderWindow
from .localization import LanguagePreference, tr
from .help_dialog import HelpDialog, installed_help_icon, mo2_help_action


@dataclass(frozen=True)
class Instance:
    name: str
    mods: Path
    configuration: Path | None
    current: bool = False


def normalized(path):
    return os.path.normcase(os.path.abspath(path))


def instance_from_ini(filename):
    filename = Path(filename).absolute()
    if not filename.is_file():
        raise ValueError(f'Instance configuration not found: {filename}')
    settings = QSettings(str(filename), QSettings.Format.IniFormat)
    base_text = str(settings.value('Settings/base_directory', str(filename.parent)))
    base = Path(os.path.expandvars(base_text))
    if not base.is_absolute():
        base = filename.parent / base
    mods_text = str(settings.value('Settings/mod_directory', '%BASE_DIR%/mods'))
    mods = Path(os.path.expandvars(mods_text.replace('%BASE_DIR%', str(base))))
    if not mods.is_absolute():
        mods = base / mods
    name = filename.parent.name if filename.parent.name else 'Portable instance'
    return Instance(name, mods.absolute(), filename)


def enumerate_instances(organizer, registry=None, installation=None):
    registry = Path(registry) if registry else Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'ModOrganizer'
    installation = Path(installation) if installation else Path(__file__).resolve().parents[2]
    configs = list(registry.glob('*/ModOrganizer.ini')) if registry.is_dir() else []
    if (installation / 'ModOrganizer.ini').is_file():
        configs.append(installation / 'ModOrganizer.ini')
    found, used = [], set()
    for path in configs:
        if normalized(path) in used:
            continue
        used.add(normalized(path))
        try:
            found.append(instance_from_ini(path))
        except (OSError, ValueError):
            continue
    current_root = Path(organizer.modsPath()).absolute()
    current = next((item for item in found if normalized(item.mods) == normalized(current_root)), None)
    if current:
        found.remove(current)
        current = replace(current, mods=current_root, current=True)
    else:
        current = Instance('Current instance', current_root, None, True)
    return [current] + sorted(found, key=lambda item: item.name.casefold())


class InstanceManager(QDialog):
    def __init__(self, organizer, parent=None, registry=None, installation=None):
        super().__init__(parent)
        self.organizer = organizer
        self.registry = registry
        self.installation = installation
        active = enumerate_instances(organizer, registry=registry, installation=installation)[0]
        self.language = LanguagePreference(organizer, active.configuration)
        self.sections = []
        self.close_pending = False
        self.setWindowTitle('Junction Manager')
        self.setWindowIcon(QIcon(str(Path(__file__).parent / 'assets/app.svg')))
        self.resize(1100, 740)
        outer = QVBoxLayout(self)
        intro = QHBoxLayout()
        self.heading = QLabel()
        intro.addWidget(self.heading, 1)
        self.help_button = QToolButton()
        self.help_button.setObjectName('actionHelp')
        self.help_button.setIcon(installed_help_icon(self))
        self.help_source = mo2_help_action(self)
        if self.help_source is not None:
            self.help_source.changed.connect(self.follow_help_icon)
        self.help_button.setIconSize(QSize(18, 18))
        self.help_button.setFixedSize(28, 28)
        self.help_button.setAutoRaise(False)
        self.help_button.clicked.connect(self.show_help)
        intro.addWidget(self.help_button)
        intro.setDirection(QHBoxLayout.Direction.LeftToRight)
        outer.addLayout(intro)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        outer.addWidget(self.scroll)
        shortcut_hint = QLabel('Ctrl+T  show target    ·    Ctrl+S  open source    ·    F5  refresh    ·    Delete  remove link')
        shortcut_hint.setObjectName('ShortcutFooter')
        self.shortcut_hint = shortcut_hint
        shortcut_hint.setStyleSheet('font-size: 8pt; color: #888;')
        shortcut_hint.setToolTip('Shortcuts act on the instance section containing keyboard focus.')
        outer.addWidget(shortcut_hint)
        self.synchronize()
        self.retranslate()
        self.follow_timer = QTimer(self)
        self.follow_timer.setInterval(2000)
        self.follow_timer.timeout.connect(self.follow_current)
        self.follow_timer.start()

    def show_help(self):
        HelpDialog(self).exec()

    @pyqtSlot()
    def follow_help_icon(self):
        self.help_button.setIcon(installed_help_icon(self))

    def retranslate(self):
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft if self.language.effective == 'ar' else Qt.LayoutDirection.LeftToRight)
        self.heading.setText(tr('Mod folders by MO2 instance · current instance first'))
        self.help_button.setToolTip(tr('Help and settings'))
        self.help_button.setAccessibleName(tr('Help and settings'))
        self.shortcut_hint.setText(tr('Ctrl+T  show target    ·    Ctrl+S  open source    ·    F5  refresh    ·    Delete  remove link'))
        self.shortcut_hint.setToolTip(tr('Shortcuts act on the instance section containing keyboard focus.'))
        for info, header, panel in self.sections:
            header.setText((info.name if info.configuration else tr('Current instance')) + ('  ·  ' + tr('CURRENT') if info.current else ''))
            panel.retranslate()

    def follow_current(self):
        if not self.isVisible():
            return
        discovered = enumerate_instances(self.organizer, registry=self.registry, installation=self.installation)
        signature = lambda entries: [(entry.name, normalized(entry.mods), entry.current,
                                      normalized(entry.configuration) if entry.configuration else None) for entry in entries]
        if signature(discovered) != signature([entry for entry, _, _ in self.sections]):
            self.synchronize()

    def synchronize(self):
        if any(panel.job for _, _, panel in self.sections):
            return
        available_instances = enumerate_instances(self.organizer, registry=self.registry, installation=self.installation)
        self.language.configuration = available_instances[0].configuration
        self.language.activate()
        states = {normalized(info.mods): button.isChecked() for info, button, _ in self.sections}
        container = QWidget()
        stack = QVBoxLayout(container)
        stack.setSpacing(6)
        self.sections = []
        for info in available_instances:
            header = QToolButton()
            header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            header.setCheckable(True)
            header.setText((info.name if info.configuration else tr('Current instance')) + ('  ·  ' + tr('CURRENT') if info.current else ''))
            header.setToolTip(str(info.configuration or info.mods))
            header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            panel = FolderWindow(self.organizer, container, info.mods)
            panel.setWindowFlags(Qt.WindowType.Widget)
            def toggle(expanded, body=panel, button=header):
                body.setVisible(expanded)
                button.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
            header.toggled.connect(toggle)
            expanded = info.current or states.get(normalized(info.mods), False)
            header.setChecked(expanded)
            toggle(expanded)
            stack.addWidget(header)
            stack.addWidget(panel, 1)
            self.sections.append((info, header, panel))
        stack.addStretch(0)
        def arrange_sections():
            # With every panel hidden, put surplus space below the headers.
            # Otherwise let the visible tables consume it.
            stack.setStretch(stack.count() - 1,
                             0 if any(button.isChecked() for _, button, _ in self.sections) else 1)
        for _, button, _ in self.sections:
            button.toggled.connect(arrange_sections)
        arrange_sections()
        previous = self.scroll.takeWidget()
        self.scroll.setWidget(container)
        for _, _, panel in self.sections:
            panel.bind_refresh_icon()
        if previous:
            previous.deleteLater()
        self.scroll.verticalScrollBar().setValue(0)
        self.retranslate()


    def closeEvent(self, event):
        busy = [panel for _, _, panel in self.sections if panel.job]
        if busy:
            for panel in busy:
                panel.cancel()
            event.ignore()
            if not self.close_pending:
                self.close_pending = True
                QTimer.singleShot(100, self.complete_close)
        else:
            super().closeEvent(event)

    def complete_close(self):
        if any(panel.job for _, _, panel in self.sections):
            QTimer.singleShot(100, self.complete_close)
        else:
            self.close_pending = False
            self.close()
