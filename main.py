# -*- coding: utf-8 -*-
"""Экран Байта: одна кнопка. Запускает фоновый сервис, после этого можно выходить."""
import os

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex, platform

Window.clearcolor = get_color_from_hex("#050B1F")

PERMS = ["android.permission.RECORD_AUDIO", "android.permission.POST_NOTIFICATIONS"]
BLUE = "#1E6BFF"
RED = "#C23B4E"


class Droid:
    """Всё, что связано с Android, в одном месте."""

    def __init__(self):
        from jnius import autoclass
        self.autoclass = autoclass
        self.act = autoclass("org.kivy.android.PythonActivity").mActivity
        self.pkg = str(self.act.getPackageName())
        self.Intent = autoclass("android.content.Intent")
        self.Uri = autoclass("android.net.Uri")
        self.Settings = autoclass("android.provider.Settings")
        self.Context = autoclass("android.content.Context")

    def service_cls(self):
        return self.autoclass(self.pkg + ".ServiceAssistant")

    def start_service(self):
        cls = self.service_cls()
        try:
            cls.start(self.act, "icon", "Байт", "Байт работает. Скажи «Запуск, Байт»", "")
        except Exception:
            cls.start(self.act, "")

    def stop_service(self):
        self.service_cls().stop(self.act)

    def is_running(self):
        try:
            am = self.act.getSystemService(self.Context.ACTIVITY_SERVICE)
            lst = am.getRunningServices(100)
            for i in range(lst.size()):
                if str(lst.get(i).service.getClassName()).endswith("ServiceAssistant"):
                    return True
        except Exception:
            pass
        return False

    def can_overlay(self):
        return bool(self.Settings.canDrawOverlays(self.act))

    def open_overlay_settings(self):
        it = self.Intent(self.Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                         self.Uri.parse("package:" + self.pkg))
        self.act.startActivity(it)

    def ask_battery(self):
        try:
            pm = self.act.getSystemService(self.Context.POWER_SERVICE)
            if not pm.isIgnoringBatteryOptimizations(self.pkg):
                it = self.Intent(self.Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                                 self.Uri.parse("package:" + self.pkg))
                self.act.startActivity(it)
        except Exception:
            pass

    def status_text(self):
        try:
            d = self.act.getExternalFilesDir(None)
            with open(os.path.join(str(d.getAbsolutePath()), "status.txt"), encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return ""


class NeonButton(Button):
    def __init__(self, **kw):
        super().__init__(background_normal="", background_down="",
                         background_color=(0, 0, 0, 0), **kw)
        with self.canvas.before:
            self._color = Color(*get_color_from_hex(BLUE))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(30)])
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._rect.pos, self._rect.size = self.pos, self.size

    def set_color(self, hexcolor):
        self._color.rgba = get_color_from_hex(hexcolor)


class ByteApp(App):
    title = "Байт"

    def build(self):
        self.droid = Droid() if platform == "android" else None
        self.running = False

        root = BoxLayout(orientation="vertical", padding=dp(28), spacing=dp(14))
        root.add_widget(Widget(size_hint_y=0.05))
        root.add_widget(Image(source="assets/icon.png", size_hint_y=0.42))
        root.add_widget(Label(text="Байт", font_size=sp(34), bold=True,
                              size_hint_y=None, height=dp(52),
                              color=get_color_from_hex("#CFE3FF")))
        self.button = NeonButton(text="ЗАПУСТИТЬ БАЙТА", font_size=sp(20), bold=True,
                                 size_hint_y=None, height=dp(72))
        self.button.bind(on_release=self.on_button)
        root.add_widget(self.button)
        self.status = Label(text="", font_size=sp(15), halign="center", valign="top",
                            color=get_color_from_hex("#8FA8D8"))
        self.status.bind(size=lambda w, s: setattr(w, "text_size", (s[0], None)))
        root.add_widget(self.status)
        Clock.schedule_interval(self.refresh, 1.5)
        Clock.schedule_once(self.refresh, 0.3)
        return root

    # --- интерфейс -----------------------------------------------------------
    def refresh(self, *_):
        if self.droid is None:
            return
        self.running = self.droid.is_running()
        self.button.text = "ОСТАНОВИТЬ БАЙТА" if self.running else "ЗАПУСТИТЬ БАЙТА"
        self.button.set_color(RED if self.running else BLUE)
        if self.running:
            text = self.droid.status_text()
            if text:
                self.status.text = text

    def say(self, text):
        self.status.text = text

    # --- кнопка ------------------------------------------------------------------
    def on_button(self, *_):
        if self.droid is None:
            self.say("Работает только на Android")
            return
        if self.droid.is_running():
            self.droid.stop_service()
            self.say("Байт остановлен")
            Clock.schedule_once(self.refresh, 0.8)
            return
        from android.permissions import request_permissions
        request_permissions(PERMS, lambda p, g: Clock.schedule_once(self.after_permissions, 0))

    def after_permissions(self, *_):
        from android.permissions import check_permission
        if not check_permission("android.permission.RECORD_AUDIO"):
            self.say("Нужен доступ к микрофону. Разреши его и нажми кнопку ещё раз")
            return
        if not self.droid.can_overlay():
            self.say("Разреши «Поверх других окон» для Байта, вернись и нажми кнопку ещё раз. "
                     "Без этого он не сможет открывать приложения из фона")
            self.droid.open_overlay_settings()
            return
        self.droid.start_service()
        self.say("Запускаю… можно выходить из приложения")
        self.droid.ask_battery()
        Clock.schedule_once(self.refresh, 1.0)


if __name__ == "__main__":
    ByteApp().run()
