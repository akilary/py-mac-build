import logging
import os
import platform
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import traceback
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from tkinter import ttk, messagebox
from typing import Callable

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

PROFILE_DIR = BASE_DIR / "profiles"
BROWSERS_PATH = BASE_DIR / "playwright_browsers"

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(BROWSERS_PATH)

from playwright.sync_api import sync_playwright, Geolocation, BrowserContext


@dataclass
class CityInfo:
    ru: str
    lat: float
    lon: float
    tz: str


CITIES = {
    "Moscow": CityInfo("Москва", 55.7558, 37.6173, "Europe/Moscow"),
    "Saint_Petersburg": CityInfo("Санкт-Петербург", 59.9343, 30.3351, "Europe/Moscow"),
    "Novosibirsk": CityInfo("Новосибирск", 54.9885, 82.9207, "Asia/Novosibirsk"),
    "Yekaterinburg": CityInfo("Екатеринбург", 56.8389, 60.6057, "Asia/Yekaterinburg"),
    "Kazan": CityInfo("Казань", 55.8304, 49.0661, "Europe/Moscow"),
    "Nizhny_Novgorod": CityInfo("Нижний Новгород", 56.2965, 43.9361, "Europe/Moscow"),
    "Chelyabinsk": CityInfo("Челябинск", 55.1644, 61.4368, "Asia/Yekaterinburg"),
    "Samara": CityInfo("Самара", 53.2001, 50.1500, "Europe/Samara"),
    "Omsk": CityInfo("Омск", 54.9885, 73.3242, "Asia/Omsk"),
    "Rostov-on-Don": CityInfo("Ростов-на-Дону", 47.2357, 39.7015, "Europe/Moscow"),
    "Ufa": CityInfo("Уфа", 54.7388, 55.9721, "Asia/Yekaterinburg"),
    "Krasnoyarsk": CityInfo("Красноярск", 56.0153, 92.8932, "Asia/Krasnoyarsk"),
    "Voronezh": CityInfo("Воронеж", 51.6755, 39.2088, "Europe/Moscow"),
    "Perm": CityInfo("Пермь", 58.0105, 56.2502, "Asia/Yekaterinburg"),
    "Volgograd": CityInfo("Волгоград", 48.7080, 44.5133, "Europe/Moscow"),
    "Krasnodar": CityInfo("Краснодар", 45.0448, 38.9760, "Europe/Moscow"),
    "Saratov": CityInfo("Саратов", 51.5924, 46.0342, "Europe/Moscow"),
    "Tyumen": CityInfo("Тюмень", 57.1522, 68.0000, "Asia/Yekaterinburg"),
    "Tolyatti": CityInfo("Тольятти", 53.5303, 49.3461, "Europe/Samara"),
    "Izhevsk": CityInfo("Ижевск", 56.8527, 53.2114, "Europe/Samara"),
    "Barnaul": CityInfo("Барнаул", 53.3606, 83.7636, "Asia/Barnaul"),
    "Ulyanovsk": CityInfo("Ульяновск", 54.3282, 48.3866, "Europe/Samara"),
    "Irkutsk": CityInfo("Иркутск", 52.2978, 104.2964, "Asia/Irkutsk"),
    "Khabarovsk": CityInfo("Хабаровск", 48.4827, 135.0840, "Asia/Vladivostok"),
    "Makhachkala": CityInfo("Махачкала", 42.9849, 47.5047, "Europe/Moscow"),
    "Yaroslavl": CityInfo("Ярославль", 57.6261, 39.8845, "Europe/Moscow"),
    "Vladivostok": CityInfo("Владивосток", 43.1155, 131.8855, "Asia/Vladivostok"),
    "Orenburg": CityInfo("Оренбург", 51.7879, 55.1007, "Asia/Yekaterinburg"),
    "Tomsk": CityInfo("Томск", 56.4977, 84.9744, "Asia/Tomsk"),
    "Kemerovo": CityInfo("Кемерово", 55.3908, 86.0627, "Asia/Novosibirsk"),
    "Novokuznetsk": CityInfo("Новокузнецк", 53.7557, 87.1099, "Asia/Novosibirsk"),
    "Ryazan": CityInfo("Рязань", 54.6269, 39.6916, "Europe/Moscow"),
    "Astrakhan": CityInfo("Астрахань", 46.3479, 48.0326, "Europe/Astrakhan"),
    "Penza": CityInfo("Пенза", 53.2007, 45.0046, "Europe/Moscow"),
    "Naberezhnye_Chelny": CityInfo("Набережные Челны", 55.7558, 52.4355, "Europe/Moscow"),
    "Lipetsk": CityInfo("Липецк", 52.6031, 39.5708, "Europe/Moscow"),
    "Tula": CityInfo("Тула", 54.1961, 37.6182, "Europe/Moscow"),
    "Kirov": CityInfo("Киров", 58.6035, 49.6680, "Europe/Kirov"),
    "Cheboksary": CityInfo("Чебоксары", 56.1439, 47.2489, "Europe/Moscow"),
    "Ulan-Ude": CityInfo("Улан-Удэ", 51.8272, 107.6064, "Asia/Irkutsk"),
    "Kaliningrad": CityInfo("Калининград", 54.7065, 20.5110, "Europe/Kaliningrad"),
}


def _setup_logging() -> logging.Logger:
    """Настройка логера"""
    log_file = BASE_DIR / "debug.log"

    log = logging.getLogger("app")
    if log.handlers:
        return log

    log.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s")

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    log.addHandler(fh)
    log.addHandler(ch)
    return log


logger = logging.getLogger("app")


def list_profiles() -> list[str]:
    """Загружает список профилей"""
    if not PROFILE_DIR.exists():
        return []
    return sorted([p.name for p in PROFILE_DIR.iterdir() if p.is_dir()])


def create_profile(city_en: str) -> None:
    """Создаёт папку для профиля"""
    (PROFILE_DIR / city_en).mkdir(exist_ok=True)


def delete_profile(city_en: str) -> None:
    """Удаляет профиль"""
    shutil.rmtree(PROFILE_DIR / city_en, ignore_errors=True)


def _remove_quarantine(folder: Path) -> None:
    """Снимает macOS Gatekeeper quarantine и при необходимости подписывает бинарник"""
    if not platform.system() == "Darwin":
        return

    if not folder.exists():
        logger.warning("Снятие quarantine пропущено: папка не существует (%s)", folder)
        return

    logger.debug("Снимаю quarantine: %s", folder)

    for cmd in [
        ["xattr", "-dr", "com.apple.quarantine", str(folder)],
        ["chmod", "-R", "+x", str(folder)],
        ["codesign", "--sign", "-", "--force", "--deep", str(folder)],
    ]:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 and r.stderr:
            logger.debug("%s stderr: %s", cmd[0], r.stderr.strip())
        else:
            logger.debug("%s OK", cmd[0])


def ensure_chromium(on_progress: Callable | None = None) -> None:
    """Проверяет наличие Chromium в BROWSERS_PATH"""
    existing = list(BROWSERS_PATH.glob("chromium-*")) if BROWSERS_PATH.exists() else []
    if existing:
        return

    on_progress("Первый запуск: скачиваем Chromium (~150-200 МБ)...")

    BROWSERS_PATH.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"Не удалось установить Chromium:\n{result.stderr}")

    if on_progress:
        on_progress("Chromium успешно установлен")

    _remove_quarantine(BROWSERS_PATH)


def launch_browser(city: str, on_progress: Callable) -> BrowserContext:
    if city not in CITIES:
        raise ValueError(f"Неизвестный город: {city}. Доступные: {list(CITIES.keys())}")

    ensure_chromium(on_progress)

    city_info = CITIES[city]
    profile_path = PROFILE_DIR / city
    profile_path.mkdir(parents=True, exist_ok=True)

    on_progress(f"Запускаю '{city}'...")

    p = sync_playwright().start()
    device = dict(p.devices["Pixel 7"])
    device.pop("default_browser_type", None)

    context = p.chromium.launch_persistent_context(
        user_data_dir=str(profile_path),
        headless=False,
        args=["--disable-blink-features=AutomationControlled", "--disable-infobars", "--disable-gpu-sandbox"],
        timezone_id=city_info.tz,
        geolocation=Geolocation(latitude=city_info.lat, longitude=city_info.lon, accuracy=50),
        permissions=["geolocation"],
        locale="ru-RU",
        color_scheme="dark",
        **device
    )

    context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    page = context.pages[0] if context.pages else context.new_page()
    page.goto("https://yandex.ru/", wait_until="domcontentloaded")
    logger.info("Профиль открыт: %s -> yandex.ru", city)

    on_progress(f"'{CITIES[city].ru}' открыт ●")
    return context


class MyListbox(tk.Listbox):
    def curselection(self) -> tuple[int, ...]:
        return super().curselection()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mobile Browser Profiles")
        self.geometry("800x500")
        self.minsize(600, 400)

        self.filtered_profiles = []
        self.active = set()
        self.contexts = {}

        self._build_ui()
        self._refresh_list()

    def _build_ui(self) -> None:
        """Создаёт пользовательский интерфейс"""
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill="both", expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=2)
        main_frame.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(main_frame, text="Профили")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._refresh_list())
        ttk.Entry(left, textvariable=self._search_var).grid(
            row=0, column=0, sticky="ew", padx=5, pady=(5, 2)
        )

        self.listbox = MyListbox(
            left, activestyle="none", selectbackground="#0078d7", selectforeground="white"
        )
        self.listbox.grid(row=1, column=0, sticky="nsew", padx=5, pady=(2, 5))
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        self.listbox.bind("<Double-1>", lambda _: self._open_profile())

        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.columnconfigure(0, weight=1)

        create_frame = ttk.LabelFrame(right_frame, text="Новый профиль")
        create_frame.pack(fill="x")
        create_frame.columnconfigure(1, weight=1)

        ttk.Label(create_frame, text="Город:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.city_var = tk.StringVar()

        city_labels = [f"{city_info.ru} ({en})" for en, city_info in CITIES.items()]

        self.city_combo = ttk.Combobox(
            create_frame, textvariable=self.city_var, values=city_labels, state="readonly"
        )
        self.city_combo.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        ttk.Button(
            create_frame, text="Создать профиль", command=self._create_profile
        ).grid(row=1, column=0, columnspan=2, pady=(0, 10))

        actions_frame = ttk.LabelFrame(right_frame, text="Действия")
        actions_frame.pack(fill="x", pady=10)

        ttk.Button(
            actions_frame, text="Открыть профиль", width=22, command=self._open_profile
        ).grid(row=0, column=0, padx=10, pady=10)

        ttk.Button(
            actions_frame, text="Удалить профиль", width=22, command=self._delete_profile
        ).grid(row=0, column=1, padx=10, pady=10)

        status_frame = ttk.LabelFrame(right_frame, text="Статус")
        status_frame.pack(fill="x")
        self._status_var = tk.StringVar(value="Готов к работе")

        ttk.Label(
            status_frame, textvariable=self._status_var, anchor="w"
        ).pack(fill="x", padx=10, pady=10)

    def _refresh_list(self) -> None:
        """Обновляет список профилей"""
        query = self._search_var.get().lower()
        profiles = list_profiles()

        self.filtered_profiles = [
            p for p in profiles
            if query in p.lower() or query in CITIES.get(p, CityInfo(p, 0, 0, "")).ru.lower()
        ]

        self.listbox.delete(0, "end")
        for city_en in self.filtered_profiles:
            city_ru = CITIES[city_en].ru
            marker = "●" if city_en in self.active else ""
            self.listbox.insert("end", f"{city_ru} ({city_en}) {marker}")

    def _on_select(self, _) -> None:
        """Действие при выборе профиле из списка"""
        if sel := self.listbox.curselection():
            city_en = self.filtered_profiles[sel[0]]

            city_ru = CITIES.get(city_en, CityInfo(city_en, 0, 0, "")).ru
            status = "открыт" if city_en in self.active else "не открыт"
            self._status_var.set(f"{city_ru} - {status}")

    def _selected(self) -> str | None:
        """Возвращает выбранный профиль"""
        sel = self.listbox.curselection()
        return self.filtered_profiles[sel[0]] if sel else None

    def _create_profile(self) -> None:
        """Создаёт профиль"""
        idx = self.city_combo.current()

        if idx < 0:
            messagebox.showinfo("Выберите город", "Выберите город из списка")
            return

        city_en = list(CITIES.keys())[idx]
        if (PROFILE_DIR / city_en).exists():
            messagebox.showinfo("Уже существует", f"Профиль '{CITIES[city_en]}' уже создан")
            return

        create_profile(city_en)
        self._status_var.set(f"Профиль '{CITIES[city_en].ru}' создан")
        self._refresh_list()

    def _open_profile(self) -> None:
        """Открыть профиль"""
        city_en = self._selected()

        if city_en is None:
            messagebox.showinfo("Выберите профиль", "Выберите профиль из списка")
            return

        if city_en in self.active:
            self._status_var.set(f"'{CITIES[city_en].ru}' уже открыт")
            return

        city_ru = CITIES[city_en].ru
        self.safe_progress("Загрузка браузера...")
        self.update()

        def run():
            context = None
            try:
                logger.info("Открываю профиль: %s", city_en)

                context = launch_browser(city_en, self.safe_progress)  # noqa

                self.contexts[city_en] = context
                self.active.add(city_en)

                self.after(0, self._refresh_list)  # noqa
                self.safe_progress(f"'{city_ru}' открыт ●")

                context.wait_for_event("close", timeout=timedelta(hours=5).total_seconds() * 1000)
            except Exception as e:
                tb = traceback.format_exc()
                logger.exception("Ошибка при запуске профиля %s", city_en)
                self.safe_progress(f"Ошибка: {e}")
                self.after(0, lambda: messagebox.showerror("Ошибка запуска", tb))  # noqa
            finally:
                if context is not None:
                    try:
                        context.close()
                        logger.info("Закрыт браузер: %s", city_en)
                    except Exception:
                        logger.exception("Ошибка закрытия %s", city_en)

                self.contexts.pop(city_en, None)

                self.active.discard(city_en)
                self.after(0, self._refresh_list)  # noqa
                self.safe_progress(f"'{city_ru}' закрыт")

        threading.Thread(target=run, daemon=True).start()

    def _delete_profile(self) -> None:
        """Удаляет выбранный профиль"""
        city_en = self._selected()

        if not city_en:
            messagebox.showinfo("Выберите профиль", "Выберите профиль из списка")
            return

        if city_en in self.active:
            messagebox.showwarning("Профиль открыт", "Сначала закройте браузер")
            return

        city_ru = CITIES[city_en].ru
        if messagebox.askyesno(
                "Удалить", f"Удалить профиль «{city_ru}»?\nВсе данные (cookies, история) будут удалены."
        ):
            delete_profile(city_en)
            logger.info("Удалён профиль: %s", city_en)
            self._status_var.set(f"Профиль «{city_ru}» удалён")
            self._refresh_list()

    def safe_progress(self, text: str) -> None:
        """Безопасно обновляет статус из фонового потока"""
        self.after(0, self._status_var.set, text)

    def on_close(self) -> None:
        """Выход из приложения"""
        logger.info("Закрытие приложения")
        self.destroy()


def main() -> None:
    PROFILE_DIR.mkdir(exist_ok=True)

    log = _setup_logging()
    log.info("=" * 50)
    log.info("Запуск приложения")
    log.info("ОС: %s | Архитектура: %s", platform.platform(), platform.machine())
    log.info("Python: %s", sys.version.split()[0])
    log.info("Рабочая папка: %s", BASE_DIR)
    log.info("=" * 50)

    try:
        app = App()
        app.protocol("WM_DELETE_WINDOW", app.on_close)
        app.mainloop()
    except Exception as e:
        logger.exception("Критическая ошибка приложения")

        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Критическая ошибка", str(e))
            root.destroy()
        except tk.TclError:
            logger.exception("Не удалось показать окно ошибки")


if __name__ == "__main__":
    main()
