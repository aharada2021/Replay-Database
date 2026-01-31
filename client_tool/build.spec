# -*- mode: python ; coding: utf-8 -*-
import os
import shutil
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

block_cipher = None

# Local capture package submodules (must be listed explicitly)
capture_hiddenimports = [
    'capture',
    'capture.config',
    'capture.exceptions',
    'capture.manager',
    'capture.screen_capture',
    'capture.audio_capture',
    'capture.video_encoder',
]

# Collect windows-capture and pyaudiowpatch submodules if available
try:
    windows_capture_imports = collect_submodules('windows_capture')
    print(f"[build.spec] windows_capture imports: {windows_capture_imports}")
except Exception as e:
    windows_capture_imports = []
    print(f"[build.spec] windows_capture collect failed: {e}")

try:
    pyaudio_imports = collect_submodules('pyaudiowpatch')
    print(f"[build.spec] pyaudiowpatch imports: {pyaudio_imports}")
except Exception as e:
    pyaudio_imports = []
    print(f"[build.spec] pyaudiowpatch collect failed: {e}")

# Collect dynamic libraries
binaries = []

# Try to collect windows-capture DLLs
try:
    binaries.extend(collect_dynamic_libs('windows_capture'))
except Exception:
    pass

# Try to collect pyaudiowpatch DLLs
try:
    binaries.extend(collect_dynamic_libs('pyaudiowpatch'))
except Exception:
    pass

# Find FFmpeg binary
ffmpeg_path = shutil.which('ffmpeg')
print(f"[build.spec] ffmpeg from PATH: {ffmpeg_path}")
if ffmpeg_path:
    binaries.append((ffmpeg_path, '.'))
else:
    # Check common locations on Windows
    common_paths = [
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'ffmpeg', 'bin', 'ffmpeg.exe'),
        'C:/ffmpeg/bin/ffmpeg.exe',
        'C:/Program Files/ffmpeg/bin/ffmpeg.exe',
        'C:/ProgramData/chocolatey/lib/ffmpeg/tools/ffmpeg/bin/ffmpeg.exe',
    ]
    for path in common_paths:
        if os.path.exists(path):
            print(f"[build.spec] ffmpeg found at: {path}")
            binaries.append((path, '.'))
            break
    else:
        print("[build.spec] WARNING: ffmpeg not found!")

print(f"[build.spec] binaries collected: {len(binaries)}")

# Include local capture package as source files
# SPECPATH is provided by PyInstaller and points to the directory containing the spec file
capture_path = os.path.join(SPECPATH, 'capture')
print(f"[build.spec] capture_path: {capture_path}")
print(f"[build.spec] capture_path exists: {os.path.exists(capture_path)}")

datas = [
    (capture_path, 'capture'),
]

# Collect numpy data files
try:
    datas.extend(collect_data_files('numpy'))
except Exception:
    pass

a = Analysis(
    ['wows_replay_uploader.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        # Watchdog
        'watchdog.observers',
        'watchdog.observers.polling',
        'watchdog.observers.winapi',
        'watchdog.observers.read_directory_changes',
        'watchdog.events',
        'multiprocessing',
        # Numpy
        'numpy',
        'numpy.core._methods',
        'numpy.lib.format',
        # Capture module (local package)
        *capture_hiddenimports,
        # Windows capture (optional)
        *windows_capture_imports,
        # PyAudio (optional)
        *pyaudio_imports,
        'pyaudio',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='wows_replay_uploader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
