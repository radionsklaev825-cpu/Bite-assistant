[app]
title = Байт
package.name = byteassistant
package.domain = org.byteapp
source.dir = .
source.include_exts = py,png,mp3
source.include_patterns = model/*
source.exclude_dirs = bin,.buildozer,.github,.git,venv,__pycache__
version = 0.1
requirements = python3==3.11.9,hostpython3==3.11.9,kivy==2.3.0,pyjnius,android
orientation = portrait
fullscreen = 0

icon.filename = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/icon.png
android.presplash_color = #050B1F

# Фоновый сервис с микрофоном (тип microphone обязателен на Android 14+)
services = Assistant:service.py:foreground:sticky:foregroundServiceType=microphone

android.permissions = RECORD_AUDIO,FOREGROUND_SERVICE,FOREGROUND_SERVICE_MICROPHONE,POST_NOTIFICATIONS,QUERY_ALL_PACKAGES,SYSTEM_ALERT_WINDOW,WAKE_LOCK,REQUEST_IGNORE_BATTERY_OPTIMIZATIONS

android.api = 34
android.minapi = 24
android.ndk = 28c
android.archs = arm64-v8a
android.accept_sdk_license = True

# Распознавание речи Vosk (офлайн) + JNA
android.gradle_dependencies = com.alphacephei:vosk-android:0.3.47,net.java.dev.jna:jna:5.13.0@aar

# нужен свежий python-for-android (поддержка foregroundServiceType)
p4a.branch = develop

[buildozer]
log_level = 2
warn_on_root = 1
