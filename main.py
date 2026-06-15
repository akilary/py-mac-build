import shutil
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox

import undetected_chromedriver as uc
from selenium.common import NoSuchWindowException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.driver_cache import DriverCacheManager

PROFILE_DIR = Path("profiles")
PROFILE_DIR.mkdir(exist_ok=True)

MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)

DEVICE = (412, 915, 2.625)

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


def list_profiles() -> list[str]:
    """Загружает список профилей"""
    return sorted([p.name for p in PROFILE_DIR.iterdir() if p.is_dir()])


def create_profile(city_en: str) -> None:
    """Создаёт папку для профиля"""
    (PROFILE_DIR / city_en).mkdir(exist_ok=True)


def delete_profile(city_en: str) -> None:
    """Удаляет профиль"""
    shutil.rmtree(PROFILE_DIR / city_en, ignore_errors=True)


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
                    except NoSuchWindowException:  # Вкладка закрылась между получением handle и switch_to
                        current_handles.discard(handle)

                known_handles = current_handles
        except WebDriverException:
            break  # Браузер закрыт

        time.sleep(0.3)

    stop_event.set()


def init_driver(city_en: str) -> tuple[uc.Chrome, threading.Event]:
    """Инициализация драйвера"""
    driver_path = ChromeDriverManager(
        cache_manager=DriverCacheManager(root_dir="driver_cache")
    ).install()

    profile_path = (PROFILE_DIR / city_en).absolute()
    profile_path.mkdir(exist_ok=True)

    w, h, _ = DEVICE

    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={profile_path}")
    options.add_argument(f"--window-size={w},{h}")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")

    driver = uc.Chrome(options=options, use_subprocess=True, driver_executable_path=driver_path)

    apply_mobile_emulation(driver)

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
        self._status_var.set(f"Запускаю «{city_ru}»...")
        self.update()

        def run():
            driver, stop_event = init_driver(city_en)  # noqa
            driver.get(f"https://yandex.com/")

            self.active[city_en] = (driver, stop_event)
            self.after(0, self._refresh_list)  # noqa
            self.after(0, lambda: self._status_var.set(f"«{city_ru}» открыт ●"))  # noqa

            while not stop_event.is_set():
                time.sleep(0.5)

            stop_event.set()
            driver.quit()

            self.active.pop(city_en, None)
            self.after(0, self._refresh_list)  # noqa
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
            self._status_var.set(f"Профиль «{city_ru}» удалён")
            self._refresh_list()

    def on_close(self) -> None:
        """ """
        for city_en, (driver, stop_event) in list(self.active.items()):
            stop_event.set()
            driver.quit()
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
