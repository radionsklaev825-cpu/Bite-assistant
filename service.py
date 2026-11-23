# -*- coding: utf-8 -*-
"""Фоновый сервис Байта: слушает «Запуск, Байт», потом команду «запусти ...»."""
import json
import os
import queue
import time
import traceback

from jnius import PythonJavaClass, autoclass, java_method

from logic import (is_wake, match_alias, match_label, parse_command)

# ---- настройки -------------------------------------------------------------
WAKE_GRAMMAR = '["запуск байт", "[unk]"]'   # слова-активатор для Vosk
COMMAND_TIMEOUT = 8.0                         # сек. ждать команду после «Байт на связи»
SAMPLE_RATE = 16000.0
ALIAS_MIN = 0.84                              # порог совпадения со списком apps.py
LABEL_MIN = 0.65                              # порог совпадения с названием приложения
# ----------------------------------------------------------------------------

BASE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE, "model")
VOICE_DIR = os.path.join(BASE, "voise")

PythonService = autoclass("org.kivy.android.PythonService")
service = PythonService.mService
Context = autoclass("android.content.Context")
Intent = autoclass("android.content.Intent")
MediaPlayer = autoclass("android.media.MediaPlayer")
PowerManager = autoclass("android.os.PowerManager")
Model = autoclass("org.vosk.Model")
Recognizer = autoclass("org.vosk.Recognizer")
SpeechService = autoclass("org.vosk.android.SpeechService")

events = queue.Queue()


# ---- журнал и статус (файлы видны в памяти телефона) -------------------------
def _out_dir():
    d = service.getExternalFilesDir(None)
    if d is None:
        d = service.getFilesDir()
    return str(d.getAbsolutePath())


def log(msg):
    try:
        with open(os.path.join(_out_dir(), "byte.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + str(msg) + "\n")
    except Exception:
        pass


def status(msg):
    log("STATUS: " + msg)
    try:
        with open(os.path.join(_out_dir(), "status.txt"), "w", encoding="utf-8") as f:
            f.write(msg)
    except Exception:
        pass


# ---- приём событий от Vosk -----------------------------------------------------
def _field(raw, key):
    try:
        return json.loads(str(raw)).get(key, "")
    except Exception:
        return ""


class Listener(PythonJavaClass):
    __javainterfaces__ = ["org/vosk/android/RecognitionListener"]
    __javacontext__ = "app"

    @java_method("(Ljava/lang/String;)V")
    def onPartialResult(self, hypothesis):
        events.put(("partial", _field(hypothesis, "partial")))

    @java_method("(Ljava/lang/String;)V")
    def onResult(self, hypothesis):
        events.put(("result", _field(hypothesis, "text")))

    @java_method("(Ljava/lang/String;)V")
    def onFinalResult(self, hypothesis):
        events.put(("final", _field(hypothesis, "text")))

    @java_method("(Ljava/lang/Exception;)V")
    def onError(self, exception):
        events.put(("error", str(exception)))

    @java_method("()V")
    def onTimeout(self):
        events.put(("timeout", ""))


listener = Listener()   # держим ссылку, чтобы не удалил сборщик мусора


class Ear:
    """Включает и выключает прослушивание микрофона."""

    def __init__(self, model):
        self.model = model
        self.rec = None
        self.ss = None

    def start(self, grammar=None):
        self.stop()
        if grammar:
            self.rec = Recognizer(self.model, SAMPLE_RATE, grammar)
        else:
            self.rec = Recognizer(self.model, SAMPLE_RATE)
        self.ss = SpeechService(self.rec, SAMPLE_RATE)
        self.ss.startListening(listener)

    def stop(self):
        if self.ss is not None:
            try:
                self.ss.cancel()
                self.ss.shutdown()
            except Exception:
                log("ear.stop: " + traceback.format_exc())
            self.ss = None
        if self.rec is not None:
            try:
                self.rec.close()
            except Exception:
                pass
            self.rec = None


def drain():
    while True:
        try:
            events.get_nowait()
        except queue.Empty:
            return


# ---- голос Байта -----------------------------------------------------------------
def say(name):
    path = os.path.join(VOICE_DIR, name + ".mp3")
    if not os.path.exists(path):
        log("нет файла озвучки: " + path)
        return
    mp = MediaPlayer()
    try:
        mp.setDataSource(path)
        mp.prepare()
        mp.start()
        t0 = time.time()
        while mp.isPlaying() and time.time() - t0 < 15:
            time.sleep(0.05)
    finally:
        mp.release()
    time.sleep(0.2)   # дать эху стихнуть, чтобы микрофон не услышал Байта


# ---- запуск приложений -------------------------------------------------------------
def installed_apps(pm):
    intent = Intent(Intent.ACTION_MAIN)
    intent.addCategory(Intent.CATEGORY_LAUNCHER)
    infos = pm.queryIntentActivities(intent, 0)
    apps = []
    for i in range(infos.size()):
        ri = infos.get(i)
        label = str(ri.loadLabel(pm).toString())
        apps.append((label, str(ri.activityInfo.packageName)))
    return apps


def has_launcher(pm, pkg):
    try:
        return pm.getLaunchIntentForPackage(pkg) is not None
    except Exception:
        return False


def find_package(name):
    pm = service.getPackageManager()
    score, pkg = match_alias(name)
    if pkg and score >= ALIAS_MIN and has_launcher(pm, pkg):
        return pkg
    apps = installed_apps(pm)
    score, pkg, label = match_label(name, apps)
    log("поиск по названиям: %r -> %r (%.2f)" % (name, label, score))
    if pkg and score >= LABEL_MIN:
        return pkg
    return None


def start_package(pkg):
    pm = service.getPackageManager()
    it = pm.getLaunchIntentForPackage(pkg)
    if it is None:
        return False
    it.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    service.startActivity(it)
    return True


# ---- один диалог: после «Запуск, Байт» -------------------------------------------------
def handle_command(ear):
    ear.start(None)   # свободное распознавание речи
    deadline = time.time() + COMMAND_TIMEOUT
    heard, spoke = "", False
    while time.time() < deadline:
        try:
            kind, data = events.get(timeout=0.2)
        except queue.Empty:
            continue
        if kind == "partial" and data.strip():
            spoke = True
            deadline = max(deadline, time.time() + 3)   # человек говорит, не обрываем
        elif kind in ("result", "final"):
            if data.strip():
                heard = data
                break
        elif kind == "error":
            log("ошибка распознавания: " + data)
            break
    ear.stop()
    drain()
    log("услышал: %r" % heard)

    if not heard:
        say("not_understood" if spoke else "timeout")
        return
    name = parse_command(heard)
    if not name:
        say("not_understood")
        return
    pkg = find_package(name)
    if not pkg:
        say("not_found")
        return
    say("launching")
    if not start_package(pkg):
        say("not_found")
    else:
        log("запущено: " + pkg)


# ---- главный цикл ------------------------------------------------------------------------
def run_forever():
    pm_power = service.getSystemService(Context.POWER_SERVICE)
    wl = pm_power.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "Byte::listen")
    wl.acquire()

    if not os.path.isdir(MODEL_DIR):
        status("Ошибка: нет папки model (модель Vosk не попала в сборку)")
        raise RuntimeError("model dir missing: " + MODEL_DIR)

    status("Загружаю модель распознавания…")
    model = Model(MODEL_DIR)
    ear = Ear(model)

    say("boot")
    ear.start(WAKE_GRAMMAR)
    status("Байт работает. Скажи «Запуск, Байт»")
    last_wake = 0.0

    while True:
        try:
            kind, data = events.get(timeout=30)
        except queue.Empty:
            continue
        if kind in ("partial", "result", "final") and is_wake(data) \
                and time.time() - last_wake > 2:
            last_wake = time.time()
            log("активация: %r" % data)
            ear.stop()
            drain()
            say("ready")
            handle_command(ear)
            drain()
            ear.start(WAKE_GRAMMAR)
            status("Байт работает. Скажи «Запуск, Байт»")
        elif kind == "error":
            log("ошибка прослушивания: " + data)
            time.sleep(1)
            ear.start(WAKE_GRAMMAR)


if __name__ == "__main__":
    while True:
        try:
            run_forever()
        except Exception:
            log(traceback.format_exc())
            status("Ошибка в сервисе, подробности в файле byte.log")
            time.sleep(10)
