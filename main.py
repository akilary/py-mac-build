import logging
import multiprocessing
import platform
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import ttk, messagebox

import undetected_chromedriver as uc
from selenium.common import NoSuchWindowException, WebDriverException

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

PROFILE_DIR = BASE_DIR / "profiles"

IS_MAC = platform.system() == "Darwin"

MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)

DEVICE = (412, 915, 2.625)

_WATCH_INTERVAL = 2.5 if IS_MAC else 0.7  # На Mac каждый CDP вызов стоит дороже - опрашиваем реже

CITY_MAP = {
    "Moscow": "Москва",
    "Saint_Petersburg": "Санкт-Петербург",
    "Novosibirsk": "Новосибирск",
    "Yekaterinburg": "Екатеринбург",
    "Kazan": "Казань",
    "Nizhny_Novgorod": "Нижний Новгород",
    "Chelyabinsk": "Челябинск",
    "Samara": "Самара",
    "Omsk": "Омск",
    "Rostov-on-Don": "Ростов-на-Дону",
    "Ufa": "Уфа",
    "Krasnoyarsk": "Красноярск",
    "Voronezh": "Воронеж",
    "Perm": "Пермь",
    "Volgograd": "Волгоград",
    "Krasnodar": "Краснодар",
    "Saratov": "Саратов",
    "Tyumen": "Тюмень",
    "Tolyatti": "Тольятти",
    "Izhevsk": "Ижевск",
    "Barnaul": "Барнаул",
    "Ulyanovsk": "Ульяновск",
    "Irkutsk": "Иркутск",
    "Khabarovsk": "Хабаровск",
    "Makhachkala": "Махачкала",
    "Yaroslavl": "Ярославль",
    "Vladivostok": "Владивосток",
    "Orenburg": "Оренбург",
    "Tomsk": "Томск",
    "Kemerovo": "Кемерово",
    "Novokuznetsk": "Новокузнецк",
    "Ryazan": "Рязань",
    "Astrakhan": "Астрахань",
    "Penza": "Пенза",
    "Naberezhnye_Chelny": "Набережные Челны",
    "Lipetsk": "Липецк",
    "Tula": "Тула",
    "Kirov": "Киров",
    "Cheboksary": "Чебоксары",
    "Ulan-Ude": "Улан-Удэ",
    "Kaliningrad": "Калининград",
}


def _setup_logging() -> logging.Logger:
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
    return sorted([p.name for p in PROFILE_DIR.iterdir() if p.is_dir()])


def create_profile(city_en: str) -> None:
    """Создаёт папку для профиля"""
    (PROFILE_DIR / city_en).mkdir(exist_ok=True)


def delete_profile(city_en: str) -> None:
    """Удаляет профиль"""
    shutil.rmtree(PROFILE_DIR / city_en, ignore_errors=True)


def _remove_quarantine(path: str) -> None:
    """Снимает карантин Gatekeeper с chromedriver-mac-arm64"""
    if not IS_MAC:
        return

    p = Path(path)
    if not p.exists():
        logger.warning("_remove_quarantine: файл не найден: %s", path)
        return

    logger.debug("Снимаю карантин: %s", path)

    before = subprocess.run(["xattr", "-l", path], capture_output=True, text=True)
    if before.stdout.strip():
        logger.debug("Атрибуты до:\n%s", before.stdout.strip())
    else:
        logger.debug("Атрибуты до: нет расширенных атрибутов")

    r1 = subprocess.run(["xattr", "-dr", "com.apple.quarantine", path], capture_output=True, text=True)
    r2 = subprocess.run(["chmod", "+x", path], capture_output=True, text=True)

    if r1.returncode != 0 and r1.stderr:
        logger.warning("xattr stderr: %s", r1.stderr.strip())
    if r2.returncode != 0 and r2.stderr:
        logger.warning("chmod stderr: %s", r2.stderr.strip())

    after = subprocess.run(["xattr", "-l", path], capture_output=True, text=True)
    if after.stdout.strip():
        logger.warning("Атрибуты остались после снятия карантина:\n%s", after.stdout.strip())
    else:
        logger.info("Карантин успешно снят: %s", p.name)


def apply_mobile_emulation(driver: uc.Chrome) -> None:
    """Применяет мобильные настройки к текущей активной вкладке"""
    w, h, dpr = DEVICE

    driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
        "width": w,
        "height": h,
        "deviceScaleFactor": dpr,
        "mobile": True,
        "screenWidth": w,
        "screenHeight": h,
        "positionX": 0,
        "positionY": 0,
        "screenOrientation": {"type": "portraitPrimary", "angle": 0},
    })
    driver.execute_cdp_cmd("Network.setUserAgentOverride", {
        "userAgent": MOBILE_UA,
        "platform": "Linux armv81",
        "acceptLanguage": "ru-RU,ru;q=0.9",
    })
    driver.execute_cdp_cmd("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 5})
    driver.execute_cdp_cmd("Emulation.setLocaleOverride", {"locale": "ru-RU"})
    driver.execute_cdp_cmd("Emulation.setTimezoneOverride", {"timezoneId": "Europe/Moscow"})


def watch_new_tabs(driver: uc.Chrome, stop_event: threading.Event) -> None:
    """Фоновый поток: следит за новыми вкладками и применяет к ним эмуляцию"""
    known_handles = set(driver.window_handles)
    lock = threading.Lock()

    while not stop_event.is_set():
        try:
            with lock:
                current_handles = set(driver.window_handles)
                new_handles = current_handles - known_handles

                for handle in new_handles:
                    try:
                        driver.switch_to.window(handle)
                        apply_mobile_emulation(driver)
                        logger.debug("Эмуляция применена к новой вкладке: %s", handle)
                    except NoSuchWindowException:  # Вкладка закрылась между получением handle и switch_to
                        current_handles.discard(handle)

                known_handles = current_handles
        except WebDriverException:
            logger.info("WebDriver завершил работу - останавливаю watch_new_tabs")
            break  # Браузер закрыт

        time.sleep(_WATCH_INTERVAL)

    stop_event.set()


def init_driver(city_en: str) -> tuple[uc.Chrome, threading.Event]:
    """Инициализация драйвера"""
    profile_path = (PROFILE_DIR / city_en).absolute()
    profile_path.mkdir(exist_ok=True)
    logger.info("Профиль: %s", profile_path)

    if IS_MAC:
        driver_path = str(BASE_DIR / "chromedriver-mac-arm64" / "chromedriver")
    else:
        driver_path = str(BASE_DIR / "chromedriver-win64" / "chromedriver.exe")

    logger.info("Драйвер: %s", driver_path)

    if not Path(driver_path).exists():
        raise FileNotFoundError(f"chromedriver не найден: {driver_path}")

    _remove_quarantine(driver_path)

    w, h, _ = DEVICE

    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={profile_path}")
    options.add_argument(f"--window-size={w},{h}")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")

    logger.info("Запускаю Chrome...")
    driver = uc.Chrome(options=options, use_subprocess=True, driver_executable_path=driver_path)
    logger.info("Chrome запущен")

    apply_mobile_emulation(driver)
    logger.info("Мобильная эмуляция применена")

    stop_event = threading.Event()
    threading.Thread(target=watch_new_tabs, args=(driver, stop_event), daemon=True).start()
    return driver, stop_event


class MyListbox(tk.Listbox):
    def curselection(self) -> tuple[int, ...]:
        return super().curselection()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mobile Browser Profiles")
        self.geometry("800x500")
        self.minsize(600, 400)

        self.filtered_profiles: list[str] = []
        self.active = {}

        self._build_ui()
        self._refresh_list()

    def _build_ui(self) -> None:
        """ """
        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(main, text="Профили")
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

        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)

        create_frame = ttk.LabelFrame(right, text="Новый профиль")
        create_frame.pack(fill="x")
        create_frame.columnconfigure(1, weight=1)

        ttk.Label(create_frame, text="Город:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.city_var = tk.StringVar()

        city_labels = [f"{ru} ({en})" for en, ru in CITY_MAP.items()]

        self.city_combo = ttk.Combobox(
            create_frame, textvariable=self.city_var, values=city_labels, state="readonly"
        )
        self.city_combo.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        ttk.Button(
            create_frame, text="Создать профиль", command=self._create_profile
        ).grid(row=1, column=0, columnspan=2, pady=(0, 10))

        actions_frame = ttk.LabelFrame(right, text="Действия")
        actions_frame.pack(fill="x", pady=10)

        ttk.Button(
            actions_frame, text="Открыть профиль", width=22, command=self._open_profile
        ).grid(row=0, column=0, padx=10, pady=10)

        ttk.Button(
            actions_frame, text="Удалить профиль", width=22, command=self._delete_profile
        ).grid(row=0, column=1, padx=10, pady=10)

        status_frame = ttk.LabelFrame(right, text="Статус")
        status_frame.pack(fill="x")
        self._status_var = tk.StringVar(value="Готов к работе")

        ttk.Label(
            status_frame, textvariable=self._status_var, anchor="w"
        ).pack(fill="x", padx=10, pady=10)

    def _refresh_list(self) -> None:
        """ """
        query = self._search_var.get().lower()
        profiles = list_profiles()

        self.filtered_profiles = [
            p for p in profiles
            if query in p.lower() or query in CITY_MAP.get(p, "").lower()
        ]

        self.listbox.delete(0, "end")
        for city_en in self.filtered_profiles:
            city_ru = CITY_MAP.get(city_en, city_en)
            marker = "●" if city_en in self.active else ""
            self.listbox.insert("end", f"{city_ru} ({city_en}) {marker}")

    def _on_select(self, _) -> None:
        """ """
        if sel := self.listbox.curselection():
            city_en = self.filtered_profiles[sel[0]]

            city_ru = CITY_MAP.get(city_en, city_en)
            status = "открыт" if city_en in self.active else "не открыт"
            self._status_var.set(f"{city_ru} - {status}")

    def _selected(self) -> str | None:
        """ """
        sel = self.listbox.curselection()
        return self.filtered_profiles[sel[0]] if sel else None

    def _create_profile(self):
        """ """
        idx = self.city_combo.current()

        if idx < 0:
            messagebox.showinfo("Выберите город", "Выберите город из списка")
            return

        city_en = list(CITY_MAP.keys())[idx]
        if (PROFILE_DIR / city_en).exists():
            messagebox.showinfo("Уже существует", f"Профиль «{CITY_MAP[city_en]}» уже создан")
            return

        create_profile(city_en)
        self._status_var.set(f"Профиль «{CITY_MAP[city_en]}» создан")
        self._refresh_list()

    def _open_profile(self):
        city_en = self._selected()

        if city_en is None:
            messagebox.showinfo("Выберите профиль", "Выберите профиль из списка")
            return

        if city_en in self.active:
            self._status_var.set(f"«{CITY_MAP.get(city_en)}» уже открыт")
            return

        city_ru = CITY_MAP.get(city_en, city_en)
        self._status_var.set("Загрузка браузера...")
        self.update()

        def run():
            logger.info("Открываю профиль: %s", city_en)
            launched = False
            try:
                driver, stop_event = init_driver(city_en)  # noqa
                self._status_var.set(f"Запускаю «{city_ru}»...")

                driver.get(f"https://yandex.com/")
                logger.info("Страница открыта: yandex.com")
                launched = True

                self.active[city_en] = (driver, stop_event)
                self.after(0, self._refresh_list)  # noqa
                self.after(0, lambda: self._status_var.set(f"«{city_ru}» открыт ●"))  # noqa

                while not stop_event.is_set():
                    time.sleep(0.5)

                stop_event.set()
                driver.quit()
            except Exception as e:
                tb = traceback.format_exc()
                logger.error("Ошибка при запуске профиля %s:\n%s", city_en, tb)
                self.after(0, lambda: self._status_var.set(f"Ошибка: {e}"))  # noqa
                self.after(0, lambda: messagebox.showerror("Ошибка запуска", tb))  # noqa

            finally:
                self.active.pop(city_en, None)
                self.after(0, self._refresh_list)  # noqa
                if launched:
                    self.after(0, lambda: self._status_var.set(f"«{city_ru}» закрыт"))  # noqa

        threading.Thread(target=run, daemon=True).start()

    def _delete_profile(self):
        city_en = self._selected()

        if not city_en:
            messagebox.showinfo("Выберите профиль", "Выберите профиль из списка")
            return

        if city_en in self.active:
            messagebox.showwarning("Профиль открыт", "Сначала закройте браузер этого профиля")
            return

        city_ru = CITY_MAP.get(city_en, city_en)
        if messagebox.askyesno(
                "Удалить", f"Удалить профиль «{city_ru}»?\nВсе данные (cookies, история) будут удалены."
        ):
            delete_profile(city_en)
            logger.info("Удалён профиль: %s", city_en)
            self._status_var.set(f"Профиль «{city_ru}» удалён")
            self._refresh_list()

    def on_close(self) -> None:
        """ """
        logger.info("Закрытие приложения")
        for city_en, (driver, stop_event) in list(self.active.items()):
            stop_event.set()
            driver.quit()
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
    except Exception:
        logger.exception("Критическая ошибка приложения")

        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Критическая ошибка", traceback.format_exc())
            root.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
