# SPDX-License-Identifier: MIT
from html import escape
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QTabWidget, QTextBrowser, QPushButton, QStyle
from .localization import tr, LANGUAGES


def mo2_action(widget, object_name):
    # Reference MO2's existing QAction icon, including its theme-selected image.
    # No icon path, texture file, or third-party artwork is copied into the plugin.
    ancestor = widget.parentWidget()
    while ancestor is not None:
        action = ancestor.findChild(QAction, object_name)
        if action is not None:
            return action
        ancestor = ancestor.parentWidget()
    return None


def mo2_help_action(widget):
    return mo2_action(widget, 'actionHelp')


def installed_help_icon(widget):
    action = mo2_help_action(widget)
    if action is not None and not action.icon().isNull():
        return QIcon(action.icon())
    return widget.style().standardIcon(QStyle.StandardPixmap.SP_DialogHelpButton)

USAGE = [
    'Expand the instance you want to manage. The running instance is marked CURRENT and appears first. Expanding another instance does not switch MO2.',
    'Add folder or drag mod folders into an instance section. A junction is created in that instance’s mods folder. Source files stay in their original location; there is no copying or syncing.',
    'Auto Link compares same-name folders against a source parent. Only identical ordinary folders are offered. Confirm the list before replacing duplicate copies with junctions. Changed folders and nested links are skipped.',
    'Select a row to open its source, show the instance’s mods folder, relink it to a new source, or remove just the link. Unavailable means the original folder cannot currently be reached.',
    'Columns fit the window initially. Drag a divider for manual widths, double-click it to fit content, or right-click a header to restore automatic sizing. Double-click paths to scroll and copy them; paths cannot be edited here.',
    'Instances are read automatically from MO2’s registered configurations and this installation’s portable configuration. Instance creation, removal, and switching are handled by MO2. Other instances see link changes when they next refresh.',
]
WARNINGS = [
    'A junction is another route to the same files, not a backup. Editing or deleting files inside a linked mod changes the original files too. Keep backups or commit important work before filesystem changes.',
    'Close the affected instance’s game and MO2-launched tools before creating, replacing, relinking, or removing links. Avoid simultaneous link changes from another MO2 process.',
    'Use Remove link in this plugin to unlink a mod safely. It removes only the directory link and protects ordinary folders. Other tools or recursive deletion commands may follow links into the source.',
    'Auto Link removes the verified duplicate copy after successful conversion. Creation failure restores the original target. If recovery cannot finish, keep the reported .mfl-recovery folder and inspect it before deleting anything.',
    'Moving or renaming a source folder, disconnecting its drive, or changing a drive letter can break links. Restore the location or use Relink. Individual files and network-share sources are not supported.',
    'Cancel stops between operations or while comparing files. Completed changes remain applied. No automatic backup, version control, or undo history is provided.',
]
CREDITS = [
    'Junction Manager · version {version}',
    'Developed by SavageBulldogOG',
    'Built for Mod Organizer 2 by the MO2 team. Runtime dependencies include Python, Qt, PyQt, and Windows PowerShell. These dependencies are supplied separately and retain their own licenses.',
    'This release’s original code, icons, and documentation use the MIT License. Sharing, modification, and commercial use are allowed. Include the copyright and permission notices with copies or substantial portions. No warranty is provided; dependency licenses remain separate.',
    'Inspired by folder-link workflows in the MO2 community. This package contains no code or artwork from other link managers and is not endorsed by those projects.',
    'The help button reuses MO2’s existing Help icon, including its current theme. No copy of that icon is bundled. If MO2’s icon is unavailable, Qt’s standard help icon is used.',
]


class HelpDialog(QDialog):
    def __init__(self, manager):
        super().__init__(manager)
        self.manager = manager
        self.setMinimumSize(480, 350)
        self.resize(650, 500)
        layout = QVBoxLayout(self)
        language_row = QHBoxLayout()
        self.language_label = QLabel()
        language_row.addWidget(self.language_label)
        self.language = QComboBox()
        self.language.addItem('', 'auto')
        for code, label in LANGUAGES:
            self.language.addItem(label, code)
        self.language.setCurrentIndex(self.language.findData(manager.language.selection))
        self.language.setMinimumWidth(190)
        self.language.setEnabled(not any(panel.job for _, _, panel in manager.sections))
        language_row.addWidget(self.language)
        language_row.addStretch()
        self.explanation = QLabel()
        self.explanation.setWordWrap(True)
        self.tabs = QTabWidget()
        self.pages = []
        for title in ('How to use', 'File safety', 'Credits'):
            page = QTextBrowser()
            page.setOpenExternalLinks(True)
            self.tabs.addTab(page, title)
            self.pages.append(page)
        layout.addWidget(self.tabs)
        layout.addLayout(language_row)
        layout.addWidget(self.explanation)
        self.close_button = QPushButton()
        self.close_button.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.language.currentIndexChanged.connect(self.changed)
        self.render()

    def changed(self):
        self.manager.language.choose(self.language.currentData())
        self.manager.retranslate()
        self.render()

    def render(self):
        arabic = self.manager.language.effective == 'ar'
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft if arabic else Qt.LayoutDirection.LeftToRight)
        self.setWindowTitle(tr('Help and settings'))
        self.language_label.setText(tr('Language'))
        self.language.setItemText(0, tr('Follow MO2 (automatic)'))
        self.explanation.setText(tr('Automatic follows the active MO2 instance’s language. An override applies only to this plugin and is saved for this MO2 instance.'))
        self.close_button.setText(tr('Close'))
        for index, (title, paragraphs) in enumerate(zip(('How to use', 'File safety', 'Credits'), (USAGE, WARNINGS, CREDITS))):
            self.tabs.setTabText(index, tr(title))
            text = ''.join('<p>' + escape(tr(paragraph).format(version='1.2.1')) + '</p>' for paragraph in paragraphs)
            if index == 2:
                text += '<p><a href="https://opensource.org/license/mit">MIT License</a> · <a href="https://www.modorganizer.org/">Mod Organizer 2</a></p>'
            if index == 1:
                text += '<p><a href="https://learn.microsoft.com/en-us/windows/win32/fileio/hard-links-and-junctions">Microsoft · Junctions</a></p>'
            self.pages[index].setHtml(text)
            self.pages[index].setLayoutDirection(Qt.LayoutDirection.RightToLeft if arabic else Qt.LayoutDirection.LeftToRight)
