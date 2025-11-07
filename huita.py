import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import subprocess
import os
import sys
import threading
import json
import re # Добавим re для парсинга чисел

# --- КОНФИГУРАЦИЯ ---
YTDLP_BIN = "yt-dlp"
DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.expanduser('~'), 'Downloads')
CONFIG_FILE = 'ytdlp_gui_config.json'

# --- ЦВЕТА ТЕМНОЙ ТЕМЫ (Black Edition) ---
colors = {
    'bg': '#1A1A1A',        # Почти черный
    'bg_secondary': '#000000', # Черный
    'fg': '#EAEAEA',        # Белый
    'accent': '#FFFFFF',    # Белый
    'accent_fg': '#000000', # Черный (для текста на белом акценте)
    'entry_bg': '#1A1A1A',
    'entry_fg': '#FFFFFF',
    'button': '#555555',
    'button_fg': '#EAEAEA',
    'button_hover': '#666666',
    'error': '#FF5555',
    'log_download': '#87CEEB', # Светло-голубой
    'log_process': '#FFD700',  # Желтый
    'selected_bg': '#FFFFFF', # Фон для выбранной кнопки формата
    'selected_fg': '#000000', # Текст для выбранной кнопки формата
}

# Определение форматов (Я ВОССТАНОВИЛ ЭТОТ БЛОК)
FORMAT_OPTIONS = {
    'Видео (WebM)': {
            '144p': ('bv*[ext=webm][height<=144]+ba*[ext=webm]', '--embed-subs --embed-thumbnail'),
            '240p': ('bv*[ext=webm][height<=240]+ba*[ext=webm]', '--embed-subs --embed-thumbnail'),
            '360p': ('bv*[ext=webm][height<=360]+ba*[ext=webm]', '--embed-subs --embed-thumbnail'),
            '480p': ('bv*[ext=webm][height<=480]+ba*[ext=webm]', '--embed-subs --embed-thumbnail'),
            '720p': ('bv*[ext=webm][height<=720]+ba*[ext=webm]', '--embed-subs --embed-thumbnail'),
            '1080p': ('bv*[ext=webm][height<=1080]+ba*[ext=webm]', '--embed-subs --embed-thumbnail'),
        },
        'Видео (MP4/AVC)': {
            '1080p (MP4)': ('bv*[ext=mp4][height<=1080]+ba*[ext=m4a]', '--embed-subs --embed-thumbnail'),
        },
        'High Res (WebM)': {
            '2K (1440p)': ('bv*[ext=webm][height<=1440]+ba*[ext=webm]', '--embed-subs --embed-thumbnail'),
            '4K (2160p)': ('bv*[ext=webm][height<=2160]+ba*[ext=webm]', '--embed-subs --embed-thumbnail'),
            '8K (4320p)': ('bv*[ext=webm][height<=4320]+ba*[ext=webm]', '--embed-subs --embed-thumbnail'),
        },
        'Аудио': {
            'MP3 (192kbps)': ('ba*', '--extract-audio --audio-format mp3 --audio-quality 192K --embed-thumbnail'),
            'M4A (AAC)': ('ba*[ext=m4a]', '--embed-thumbnail'),
            'OPUS (Lossy)': ('ba*', '--extract-audio --audio-format opus --embed-thumbnail'),
            'WAV (Uncompressed)': ('ba*', '--extract-audio --audio-format wav --embed-thumbnail'),
            'FLAC (Lossless)': ('ba*', '--extract-audio --audio-format flac --embed-thumbnail'),
        }
}


class YTDLPGUI:
    # --- ИСПРАВЛЕНИЕ: УБРАН ЛИШНИЙ ОТСТУП ---
    def __init__(self, master):
        self.master = master
        master.title("YT-DLP Загрузчик (Black Edition - Rounded)")
        master.configure(bg=colors['bg'])
        master.resizable(False, False)

        # --- Переменные ---
        self.download_path = tk.StringVar()
        self.url_var = tk.StringVar()
        self.selected_format_var = tk.StringVar()
        self.subfolder_var = tk.StringVar()

        self.download_queue = [] # [(url, command, final_dir), ...]
        self.is_downloading = False

        # --- Загрузка настроек ---
        self.load_settings()

        # --- Настройка стилей TTK ---
        self.setup_ttk_styles()

        # --- Интерфейс ---
        main_frame = tk.Frame(master, padx=10, pady=10, bg=colors['bg'])
        main_frame.pack(fill='both', expand=True)
        main_frame.grid_columnconfigure(1, weight=1)

        # --- Секция 1: Настройки ---
        settings_frame = tk.Frame(main_frame, bg=colors['bg'])
        settings_frame.grid(row=0, column=0, columnspan=3, sticky='ew')
        settings_frame.grid_columnconfigure(1, weight=1)

        self.create_label(settings_frame, "Папка:", 0, 0)
        # ИСПРАВЛЕНО: Передаем 'readonlybackground'
        path_entry = self.create_entry(settings_frame, textvariable=self.download_path,
                                     state='readonly', readonly_fg=colors['accent'],
                                     readonly_bg=colors['bg_secondary'])
        path_entry.grid(row=0, column=1, sticky='we', padx=5)
        self.create_round_button(settings_frame, text="Выбрать", command=self.choose_dir).grid(row=0, column=2, padx=(5,0))

        self.create_label(settings_frame, "Подпапка:", 1, 0)
        self.create_entry(settings_frame, textvariable=self.subfolder_var).grid(row=1, column=1, columnspan=2, sticky='we', padx=5)

        self.create_label(settings_frame, "URL:", 2, 0)
        self.create_entry(settings_frame, textvariable=self.url_var).grid(row=2, column=1, sticky='we', padx=5)
        self.create_round_button(settings_frame, text="Вставить", command=self.paste_from_clipboard).grid(row=2, column=2, padx=(5,0))

        # --- Секция 2: Форматы ---
        formats_frame = tk.Frame(main_frame, bg=colors['bg'], pady=10)
        formats_frame.grid(row=1, column=0, columnspan=3, sticky='ew')

        self.all_format_options = []
        self.format_buttons = [] # Для отслеживания кнопок формата
        formats_data = [] # Чтобы отсортировать

        # Собираем данные
        for category, options in FORMAT_OPTIONS.items():
            for text, (fmt, post) in options.items():
                # Добавляем категорию для более надежной сортировки
                formats_data.append((f"{category} - {text}", f"{fmt}|{post}"))

        # ИСПРАВЛЕНО: Новая, более надежная функция сортировки
        def sort_key(item_tuple):
            text = item_tuple[0] # item_tuple[0] это 'Видео (WebM) - 144p'

            # Ищем числа (разрешение или битрейт)
            numbers = re.findall(r'\d+', text)

            if not numbers:
                val = 0
            else:
                # Берем первое число (144p -> 144, 2K -> 2, 192kbps -> 192)
                val = int(numbers[0])

                # Приводим 'K' к тысячам (2K -> 2000, 8K -> 8000)
                if 'K' in text and val < 100:
                    val = val * 1000

            # Группируем (сначала High Res, потом Видео, потом Аудио)
            if 'High Res' in text:
                return 30000 + val
            elif 'Видео' in text:
                return 20000 + val
            elif 'Аудио' in text:
                return 10000 + val
            return 0

        # ИСПРАВЛЕНО: Сортируем от меньшего к большему (по возрастанию)
        formats_data.sort(key=sort_key, reverse=False)

        # Аудио форматы всегда в конце, но отсортированы между собой
        audio_options = [opt for opt in formats_data if 'Аудио' in opt[0]]
        video_options = [opt for opt in formats_data if 'Аудио' not in opt[0]]
        formats_data = video_options + audio_options


        self.all_format_options = formats_data

        for i, (text, value) in enumerate(self.all_format_options):
            # Убираем полную категорию для отображения
            display_text = " - ".join(text.split(' - ')[1:])

            rb = ttk.Radiobutton(formats_frame, text=display_text, variable=self.selected_format_var, value=value,
                                style='Rounded.TButton', # Используем наш стиль закругленных кнопок
                                command=self.update_format_button_styles) # Обновляем стили при выборе
            rb.grid(row=i // 3, column=i % 3, sticky='we', padx=5, pady=2)
            self.format_buttons.append(rb) # Сохраняем ссылку на кнопку

        # Устанавливаем выбор по умолчанию (например 1080p)
        default_val_text = '1080p'
        default_value = next((v for t, v in formats_data if default_val_text in t), formats_data[0][1]) # Берем 1080p или первый в списке

        self.selected_format_var.set(default_value)
        self.update_format_button_styles() # Обновляем стили в самом начале

        # --- Секция 3: Очередь/Лог ---
        queue_frame = tk.Frame(main_frame, bg=colors['bg'], pady=5)
        queue_frame.grid(row=2, column=0, columnspan=3, sticky='ew')
        queue_frame.grid_columnconfigure(0, weight=1)

        self.create_round_button(queue_frame, "Добавить в очередь 🔽", command=self.add_to_queue).grid(row=0, column=1, sticky='e', padx=5, pady=(0,5))

        # Замена Listbox на Text для логов
        self.log_text_widget = tk.Text(queue_frame, height=10, bg=colors['bg_secondary'], fg=colors['fg'],
                                    bd=1, relief=tk.FLAT, highlightthickness=0,
                                    selectbackground=colors['accent'], selectforeground=colors['accent_fg'],
                                    wrap=tk.WORD, font=('Courier', 9))
        self.log_text_widget.grid(row=1, column=0, columnspan=2, sticky='we', pady=(5,0))

        # Настройка тегов для логов
        self.log_text_widget.tag_config('success', foreground=colors['accent'], background=colors['accent_fg'], font=('Courier', 9, 'bold'))
        self.log_text_widget.tag_config('error', foreground=colors['error'], font=('Courier', 9, 'bold'))
        self.log_text_widget.tag_config('info', foreground=colors['log_download'], font=('Courier', 9, 'bold'))
        self.log_text_widget.tag_config('process', foreground=colors['log_process'])
        self.log_text_widget.tag_config('queue', foreground=colors['fg'])


        queue_controls = tk.Frame(queue_frame, bg=colors['bg'])
        queue_controls.grid(row=2, column=0, columnspan=2, sticky='ew')

        self.create_round_button(queue_controls, "🚀 СТАРТ", command=self.start_queue_download,
                        bg=colors['accent'], fg=colors['accent_fg'], height=2,
                        font=('Arial', 12, 'bold'), style='Accent.Rounded.TButton').pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5, pady=5)

        # --- Сохранение при выходе ---
        master.protocol("WM_DELETE_WINDOW", self.on_closing)

    # --- Методы GUI (создание виджетов) ---

    def setup_ttk_styles(self):
        style = ttk.Style()
        # ИСПРАВЛЕНО: Принудительно используем 'clam', чтобы стили работали на Linux
        try:
            style.theme_use('clam')
        except tk.TclError:
            print("Тема 'clam' не найдена, используется 'default'. Закругления могут не работать.")
            style.theme_use('default')

        # --- ИСПРАВЛЕНО: Упрощенная иерархия стилей для закругления ---

        # 1. Родительский стиль
        style.configure('Rounded.TButton',
                        background=colors['button'],
                        foreground=colors['button_fg'],
                        padding=[10, 5],
                        relief='flat',
                        focusthickness=0,
                        font=('Arial', 10))
        style.map('Rounded.TButton',
                background=[('active', colors['button_hover']),
                            ('!disabled', colors['button'])],
                foreground=[('!disabled', colors['button_fg'])])

        # 2. Стиль для кнопки СТАРТ (наследует Rounded.TButton)
        style.configure('Accent.Rounded.TButton',
                        parent='Rounded.TButton', # Наследуем
                        background=colors['accent'],
                        foreground=colors['accent_fg'],
                        font=('Arial', 12, 'bold'))
        style.map('Accent.Rounded.TButton',
                background=[('active', colors['fg']), # Белый при наведении
                            ('!active', colors['accent'])],
                foreground=[('!active', colors['accent_fg'])])

        # 3. Стиль для ВЫБРАННОЙ Radiobutton (наследует Rounded.TButton)
        style.configure('Selected.Rounded.TButton',
                        parent='Rounded.TButton', # Наследуем
                        background=colors['selected_bg'],
                        foreground=colors['selected_fg'],
                        font=('Arial', 10, 'bold'))

        # 4. Применяем стиль Rounded.TButton ко ВСЕМ ttk.Radiobutton
        style.map('TRadiobutton',
                  background=[('selected', colors['selected_bg']),
                              ('!selected', colors['button']),
                              ('active', colors['button_hover'])],
                  foreground=[('selected', colors['selected_fg']),
                              ('!selected', colors['button_fg'])])

        # 5. Применяем стиль Rounded.TButton ко ВСЕМ ttk.Button
        style.map('TButton',
                  background=[('active', colors['button_hover']),
                              ('!active', colors['button'])],
                  foreground=[('!active', colors['button_fg'])])

        # 6. Убираем индикатор (точку) у Radiobutton
        style.layout('Rounded.TButton', [
            ('Button.padding', {'sticky': 'nswe', 'children': [
                ('Button.label', {'sticky': 'nswe'})
            ]})
        ])


    def update_format_button_styles(self):
        """Обновляет стили кнопок формата в зависимости от выбора."""
        selected_value = self.selected_format_var.get()
        for rb in self.format_buttons:
            if rb.cget("value") == selected_value:
                # Применяем специальный стиль для ВЫБРАННОЙ
                rb.configure(style='Selected.Rounded.TButton')
            else:
                # Возвращаем обычный стиль
                rb.configure(style='Rounded.TButton')


    def create_label(self, parent, text, row, col):
        label = tk.Label(parent, text=text, bg=colors['bg'], fg=colors['fg'], font=('Arial', 10, 'bold'))
        label.grid(row=row, column=col, sticky='w', padx=5, pady=5)
        return label

    def create_entry(self, parent, textvariable, state='normal', readonly_fg=None, readonly_bg=None):
        entry_options = {
            "textvariable": textvariable,
            "state": state,
            "insertbackground": colors['fg'],
            "relief": tk.FLAT,
            "bd": 0,
            "highlightthickness": 1,
            "highlightbackground": colors['accent'] # Белая рамка
        }

        if state == 'readonly':
            # ИСПРАВЛЕНО: Принудительно ставим bg и fg вдобавок к readonlybackground
            entry_options['fg'] = readonly_fg or colors['entry_fg']
            entry_options['bg'] = readonly_bg or colors['entry_bg']
            entry_options['readonlybackground'] = readonly_bg or colors['entry_bg']
        else:
            entry_options['fg'] = colors['entry_fg']
            entry_options['bg'] = colors['entry_bg']

        entry = tk.Entry(parent, **entry_options)
        return entry

    def create_round_button(self, parent, text, command, width=None, height=1, bg=None, fg=None, font=None, style='Rounded.TButton'):
        # Если это кнопка СТАРТ, используем Accent стиль
        if "СТАРТ" in text:
            style = 'Accent.Rounded.TButton'

        button = ttk.Button(parent, text=text, command=command, style=style)
        if width: button.config(width=width)
        return button

    # --- Методы-обработчики ---

    def load_settings(self):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
            self.download_path.set(config.get('download_path', DEFAULT_DOWNLOAD_DIR))
            self.subfolder_var.set(config.get('subfolder', 'yt-dlp_downloads'))
        except (FileNotFoundError, json.JSONDecodeError):
            self.download_path.set(DEFAULT_DOWNLOAD_DIR)
            self.subfolder_var.set('yt-dlp_downloads')

    def save_settings(self):
        config = {
            'download_path': self.download_path.get(),
            'subfolder': self.subfolder_var.get()
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Ошибка сохранения настроек: {e}")

    def on_closing(self):
        self.save_settings()
        self.master.destroy()

    def choose_dir(self):
        initial_dir = self.download_path.get() if os.path.exists(self.download_path.get()) else os.path.expanduser('~')
        new_dir = filedialog.askdirectory(initialdir=initial_dir, title="Выберите папку для сохранения")
        if new_dir:
            self.download_path.set(new_dir)
            self.save_settings() # Сохраняем сразу

    def paste_from_clipboard(self):
        try:
            self.url_var.set(self.master.clipboard_get())
        except tk.TclError:
            pass # Буфер обмена пуст

    def add_to_queue(self):
        url = self.url_var.get().strip()
        selected_raw = self.selected_format_var.get()

        if not url:
            messagebox.showerror("Ошибка ввода", "Пожалуйста, введите URL для загрузки.")
            return
        if not selected_raw:
            messagebox.showerror("Ошибка формата", "Пожалуйста, выберите формат загрузки.")
            return

        final_dir = os.path.join(self.download_path.get(), self.subfolder_var.get())
        format_str, post_str = selected_raw.split('|', 1)

        try:
            os.makedirs(final_dir, exist_ok=True)

            command = [
                YTDLP_BIN, '-v', '-k', '-N', '8',
                '-f', format_str,
            ]

            if post_str: command.extend(post_str.split())

            # --- ВСЕГДА КАЧАЕМ ПЛЕЙЛИСТ ---
            command.append('--yes-playlist')

            command.extend([
                '--windows-filenames',
                '-o', os.path.join(final_dir, "%(title)s.%(ext)s"),
                url
            ])

            self.download_queue.append((url, command, final_dir))

            # Добавляем в лог-виджет
            self.log_to_widget(f"Добавлено в очередь: {url}\n", 'queue')

            self.url_var.set("")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось подготовить команду: {e}")

    def start_queue_download(self):
        if self.is_downloading:
            messagebox.showwarning("Загрузка", "Загрузка уже идет.")
            return

        if not self.download_queue:
            messagebox.showinfo("Очередь", "Очередь загрузки пуста.")
            return

        self.is_downloading = True
        self.log_to_widget("\n--- ЗАПУСК ОЧЕРЕДИ ---\n", 'info')
        self.process_queue()

    def process_queue(self):
        """Обрабатывает следующий элемент в очереди."""
        if not self.download_queue:
            self.is_downloading = False
            self.log_to_widget("\n--- ОЧЕРЕДЬ ЗАВЕРШЕНА ---\n", 'info')
            messagebox.showinfo("Завершено", "Вся очередь загружена!")
            return

        url, command, final_dir = self.download_queue.pop(0)

        self.log_to_widget(f"\n--- Загрузка: {url} ---\n", 'info')
        self.log_to_widget(f"Команда: {' '.join(command)}\n")

        # Запускаем загрузку в отдельном потоке
        threading.Thread(target=self.execute_download, args=(command, final_dir), daemon=True).start()

    def open_folder(self, path):
        try:
            if sys.platform == "win32": os.startfile(path)
            elif sys.platform == "darwin": subprocess.Popen(["open", path])
            else: subprocess.Popen(["xdg-open", path])
        except Exception as e:
            print(f"Не удалось открыть папку: {e}")

    def execute_download(self, command, final_dir):
        """Выполняет команду yt-dlp в потоке."""

        try:
            # Скрываем консольное окно в Windows
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, bufsize=1, encoding='utf-8',
                                     startupinfo=startupinfo)

            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                self.master.after(0, self.log_to_widget, line)

            process.wait()
            return_code = process.returncode

            # Сообщаем GUI-потоку о завершении
            self.master.after(0, self.on_single_download_finish, return_code, final_dir)

        except FileNotFoundError:
            self.master.after(0, messagebox.showerror, "Критическая ошибка", f"'{YTDLP_BIN}' не найден. Убедитесь, что yt-dlp в PATH.")
            self.master.after(0, self.on_single_download_finish, -1, None) # -1 = код ошибки
        except Exception as e:
            self.master.after(0, messagebox.showerror, "Критическая ошибка", f"Ошибка выполнения: {e}")
            self.master.after(0, self.on_single_download_finish, -1, None)

    # --- Методы для лог-виджета (выполняются в GUI-потоке) ---

    def on_single_download_finish(self, return_code, final_dir):
        """Вызывается в GUI-потоке после завершения subprocess."""

        if return_code == 0:
            self.log_to_widget("\n--- УСПЕХ ---\n", 'success')
            if final_dir:
                self.open_folder(final_dir)
        else:
            self.log_to_widget(f"\n--- ОШИБКА: Код {return_code} ---\n", 'error')

        # Запускаем следующий в очереди
        self.master.after(500, self.process_queue)

    def log_to_widget(self, line, tag=None):
        if not hasattr(self, 'log_text_widget') or not self.log_text_widget.winfo_exists():
            return

        try:
            self.log_text_widget.configure(state='normal')

            if tag:
                self.log_text_widget.insert(tk.END, line, tag)
            # --- Авто-определение тега ---
            elif '[download]' in line:
                self.log_text_widget.insert(tk.END, line, 'download')
            elif '[Merger]' in line or '[ExtractAudio]' in line or '[ffmpeg]' in line:
                self.log_text_widget.insert(tk.END, line, 'process')
            else:
                self.log_text_widget.insert(tk.END, line)

            self.log_text_widget.see(tk.END)
            self.log_text_widget.configure(state='disabled')
        except tk.TclError:
            pass

# --- ИСПРАВЛЕНИЕ: УБРАН ЛИШНИЙ ОТСТУП ---
if __name__ == "__main__":
    print("--- Запуск GUI... ---") # Добавлено для отладки
    root = tk.Tk()
    app = YTDLPGUI(root)
    root.mainloop()
