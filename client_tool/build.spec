# -*- mode: python ; coding: utf-8 -*-
import os
import shutil

block_cipher = None

# Find FFmpeg binary
ffmpeg_path = shutil.which('ffmpeg')
ffmpeg_binaries = []
if ffmpeg_path:
    ffmpeg_binaries.append((ffmpeg_path, '.'))
else:
    # Check common locations
    common_paths = [
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'ffmpeg', 'bin', 'ffmpeg.exe'),
        'C:/ffmpeg/bin/ffmpeg.exe',
        'C:/Program Files/ffmpeg/bin/ffmpeg.exe',
    ]
    for path in common_paths:
        if os.path.exists(path):
            ffmpeg_binaries.append((path, '.'))
            break

a = Analysis(
    ['wows_replay_uploader.py'],
    pathex=[],
    binaries=ffmpeg_binaries,
    datas=[],
    hiddenimports=[
        'watchdog.observers',
        'watchdog.observers.polling',
        'watchdog.observers.winapi',
        'watchdog.observers.read_directory_changes',
        'watchdog.events',
        'multiprocessing',
        # Capture module dependencies
        'capture',
        'capture.config',
        'capture.manager',
        'capture.screen_capture',
        'capture.audio_capture',
        'capture.video_encoder',
        'capture.exceptions',
        'numpy',
        'numpy.core._methods',
        'numpy.lib.format',
        # Windows capture (optional)
        'windows_capture',
        # PyAudio (optional)
        'pyaudiowpatch',
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
    console=True,  # コンソールウィンドウを表示
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # アイコンファイルがあれば指定
)
