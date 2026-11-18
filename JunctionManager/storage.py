# SPDX-License-Identifier: MIT
"""Local directory junction operations. No manager-specific state is stored."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os
import shutil
import stat
import subprocess
import uuid


class Stopped(Exception):
    pass


def checkpoint(stop):
    if stop is not None and stop.is_set():
        raise Stopped('Operation cancelled. Completed links were kept.')


def is_directory_link(path):
    try:
        info = os.lstat(path)
        return os.path.isjunction(path) or (
            stat.S_ISLNK(info.st_mode) and bool(info.st_file_attributes & stat.FILE_ATTRIBUTE_DIRECTORY))
    except OSError:
        return False


def location(path):
    return Path(os.path.abspath(path))


def local_folder(path):
    folder = location(path).resolve()
    if not folder.is_dir():
        raise ValueError(f'Source folder is unavailable: {folder}')
    if not folder.drive or folder.drive.startswith('\\\\'):
        raise ValueError('Select a folder on a local drive.')
    return folder


def separate(source, destination):
    a, b = source.resolve(), destination.resolve()
    if a == b or a in b.parents or b in a.parents:
        raise ValueError('Source and destination must be separate folders, without nesting.')


def make_junction(source, destination):
    source, destination = local_folder(source), location(destination)
    separate(source, destination)
    if os.path.lexists(destination):
        raise FileExistsError(f'Destination already exists: {destination.name}')
    local_folder(destination.parent)
    # Paths travel as environment values, never as PowerShell source code. This
    # also preserves quotes, Unicode, %, $, &, ! and brackets in folder names.
    environment = os.environ.copy()
    environment['MFL_NEW_LOCATION'] = str(destination)
    environment['MFL_ORIGINAL_LOCATION'] = str(source)
    executable = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    script = "$ErrorActionPreference='Stop'; $mflTarget=[System.Management.Automation.WildcardPattern]::Escape($env:MFL_ORIGINAL_LOCATION); New-Item -ItemType Junction -Path $env:MFL_NEW_LOCATION -Target $mflTarget | Out-Null"
    result = subprocess.run([str(executable), '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', script],
                            env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
    if result.returncode:
        # Never clean up an unexpected ordinary directory: preserve it for review.
        if is_directory_link(destination):
            os.rmdir(destination)
        detail = result.stderr.decode(errors='replace').strip()
        raise OSError(detail or 'Windows could not create the junction.')
    if not is_directory_link(destination) or destination.resolve() != source:
        if is_directory_link(destination):
            os.rmdir(destination)
        raise OSError('Windows did not create the expected directory junction.')


def unlink_folder(path):
    if not is_directory_link(path):
        raise ValueError('Only a directory link can be removed. Ordinary folders are protected.')
    os.rmdir(path)


@dataclass(frozen=True)
class FolderLink:
    destination: Path
    source: Path
    kind: str
    available: bool


def discover(mods_directory):
    found = []
    for child in location(mods_directory).iterdir():
        if is_directory_link(child):
            origin = child.resolve(strict=False)
            found.append(FolderLink(child, origin, 'Junction' if os.path.isjunction(child) else 'Directory symlink', origin.is_dir()))
    return sorted(found, key=lambda row: row.destination.name.casefold())


def fingerprint(folder, stop=None):
    """Hash content and empty directories, refusing nested reparse points."""
    root = Path(folder)
    records = {}
    todo = [root]
    while todo:
        checkpoint(stop)
        current = todo.pop()
        for child in current.iterdir():
            checkpoint(stop)
            attributes = child.lstat()
            if getattr(attributes, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError(f'Nested links are not compared: {child}')
            key = child.relative_to(root).as_posix().casefold()
            if key in records:
                raise ValueError('Folder contains ambiguous names differing only by case.')
            if child.is_dir():
                records[key] = ('directory',)
                todo.append(child)
            elif child.is_file():
                digest = sha256()
                with child.open('rb') as stream:
                    while True:
                        checkpoint(stop)
                        block = stream.read(262144)
                        if not block:
                            break
                        digest.update(block)
                records[key] = ('file', attributes.st_size, digest.digest())
            else:
                raise ValueError(f'Unsupported entry: {child}')
    return records


def find_duplicates(source_parent, mods_directory, stop=None):
    source_parent, mods_directory = local_folder(source_parent), local_folder(mods_directory)
    separate(source_parent, mods_directory)
    candidates, notes = [], []
    installed = {p.name.casefold(): p for p in mods_directory.iterdir() if p.is_dir() and not is_directory_link(p)}
    for source in source_parent.iterdir():
        checkpoint(stop)
        target = installed.get(source.name.casefold())
        if target is None or not source.is_dir():
            continue
        try:
            separate(source, target)
            if fingerprint(source, stop) == fingerprint(target, stop):
                candidates.append((source, target))
        except (OSError, ValueError) as error:
            notes.append(f'{source.name}: {error}')
    return candidates, notes


def convert_duplicate(source, destination, stop=None):
    """Recheck a duplicate, swap it for a junction, roll back failed creation."""
    source, destination = local_folder(source), location(destination)
    separate(source, destination)
    if is_directory_link(destination) or not destination.is_dir():
        raise ValueError('Destination must still be an ordinary mod folder.')
    if fingerprint(source, stop) != fingerprint(destination, stop):
        raise ValueError('Content changed or differs; destination was left untouched.')
    checkpoint(stop)
    saved = destination.with_name('.mfl-recovery-' + uuid.uuid4().hex)
    destination.rename(saved)
    try:
        make_junction(source, destination)
    except Exception:
        if os.path.lexists(destination):
            raise RuntimeError(f'Original folder retained at {saved}; destination needs review.')
        saved.rename(destination)
        raise
    try:
        shutil.rmtree(saved)
    except OSError:
        return f'Linked {destination.name}; duplicate backup retained at {saved}'
    return f'Linked {destination.name}'


def change_source(destination, replacement):
    destination, replacement = location(destination), local_folder(replacement)
    separate(replacement, destination)
    if not is_directory_link(destination):
        raise ValueError('Select an existing directory link.')
    saved = destination.with_name('.mfl-recovery-' + uuid.uuid4().hex)
    destination.rename(saved)
    try:
        make_junction(replacement, destination)
    except Exception:
        if os.path.lexists(destination):
            raise RuntimeError(f'Original link retained at {saved}; destination needs review.')
        saved.rename(destination)
        raise
    unlink_folder(saved)
