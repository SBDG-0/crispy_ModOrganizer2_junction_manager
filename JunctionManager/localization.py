# SPDX-License-Identifier: MIT
"""Plugin-scoped translations; MO2's application translators are untouched."""
import json
from pathlib import Path
from PyQt6.QtCore import QLocale, QSettings

LANGUAGES = [('en', 'English'), ('de', 'Deutsch'), ('fr', 'Français'), ('ar', 'العربية'),
             ('ja', '日本語'), ('zh', '简体中文'), ('ru', 'Русский')]
_catalog = json.loads((Path(__file__).parent / 'translations.json').read_text(encoding='utf-8'))
_language = 'en'


def tr(text):
    return _catalog.get(_language, {}).get(text, text)


class LanguagePreference:
    def __init__(self, organizer, configuration=None):
        self.organizer = organizer
        self.configuration = configuration
        self.selection = organizer.persistent('JunctionManager', 'language', None)
        if self.selection is None:
            self.selection = organizer.persistent('ModFolderLinks', 'language', 'auto')
        if self.selection not in {'auto', *(key for key, _ in LANGUAGES)}:
            self.selection = 'auto'
        self.activate()

    def activate(self):
        global _language
        choice = self.selection
        if choice == 'auto':
            choice = str(QSettings(str(self.configuration), QSettings.Format.IniFormat).value('Settings/language', '') or '') if self.configuration else ''
            choice = choice or QLocale().name()
        code = choice.replace('-', '_').split('_')[0].lower()
        _language = code if code in {key for key, _ in LANGUAGES} else 'en'
        self.effective = _language

    def choose(self, value):
        self.selection = value
        self.organizer.setPersistent('JunctionManager', 'language', value)
        self.activate()
