# SPDX-License-Identifier: MIT
from pathlib import Path
import logging
import mobase
from PyQt6.QtGui import QIcon
from .instances import InstanceManager
from .indicators import Indicators


class JunctionManager(mobase.IPluginTool):
    def __init__(self):
        super().__init__()
        self.organizer = None
        self.parent = None
        self.window = None
        self.badges = None

    def name(self): return 'JunctionManager'
    def localizedName(self): return 'Junction Manager'
    def displayName(self): return 'Junction Manager'
    def author(self): return 'Junction Manager contributors'
    def description(self): return 'Use local repository mod folders directly in MO2 through directory junctions.'
    def tooltip(self): return 'Create and manage folder links to your local mods'
    def version(self): return mobase.VersionInfo(1, 2, 1)
    def isActive(self): return True
    def icon(self): return QIcon(str(Path(__file__).parent / 'assets/app.svg'))
    def settings(self): return [mobase.PluginSetting('mod_list_badges', 'Show transparent link icons in the mod list (requires restart).', True)]

    def init(self, organizer):
        self.organizer = organizer
        organizer.onUserInterfaceInitialized(self.ui_ready)
        return True

    def ui_ready(self, window):
        self.parent = window
        if self.organizer.pluginSetting(self.name(), 'mod_list_badges') is not False:
            try:
                self.badges = Indicators(self.organizer, window)
            except Exception:
                logging.exception('Junction Manager: could not attach link indicators')

    def setParentWidget(self, widget):
        self.parent = widget

    def display(self):
        if self.window is None:
            self.window = InstanceManager(self.organizer, self.parent)
        else:
            self.window.synchronize()
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()


def createPlugin():
    return JunctionManager()
