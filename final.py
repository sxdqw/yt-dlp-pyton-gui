import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import subprocess
import os
import sys
import threading
import json
import re
from pathlib import Path

# ==========================
#  CONFIG & CONSTANTS
# ==========================
APP_NAME = "yt-dlp-gui"
YTDLP_BIN = "yt-dlp"
DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.expanduser('~'), 'Downloads')

# UI Colors (YouTube Dark)
colors = {
    'bg': '#0F0F0F',
    'bg_secondary': '#222222',
    'fg': '#F1F1F1',
    'accent': '#F1F1F1',
    'accent_fg': '#0F0F0F',
    'entry_bg': '#121212',
    'entry_fg': '#F1F1F1',
    'button': '#3F3F3F',
    'button_fg': '#F1F1F1',
    'button_hover': '#555555',
    'error': '#FF4D4D',
    'log_download': '#3DA6FF',
    'log_process': '#FFD700',
    'selected_bg': '#272727',
    'selected_fg': '#F1F1F1',
}

# Format presets: (label -> yt-dlp -f expression)
FORMAT_OPTIONS = {
    'Видео (WebM)': {
        '144p': 'bv*[ext=webm][height<=144]+ba*[ext=webm]',
        '240p': 'bv*[ext=webm][height<=240]+ba*[ext=webm]',
        '360p': 'bv*[ext=webm][height<=360]+ba*[ext=webm]',
        '480p': 'bv*[ext=webm][height<=480]+ba*[ext=webm]',
        '720p': 'bv*[ext=webm][height<=720]+ba*[ext=webm]',
        '1080p': 'bv*[ext=webm][height<=1080]+ba*[ext=webm]',
    },
    'Видео (MP4/AVC)': {
        '1080p (MP4)': 'bv*[vcodec*=avc1][height<=1080]+ba[ext=m4a]/bv*[ext=mp4][height<=1080]+ba[ext=m4a]'
    },
    'High Res (WebM)': {
        '2K (1440p)': 'bv*[ext=webm][height<=1440]+ba*[ext=webm]',
        '4K (2160p)': 'bv*[ext=webm][height<=2160]+ba*[ext=webm]',
        '8K (4320p)': 'bv*[ext=webm][height<=4320]+ba*[ext=webm]',
    },
    'Аудио': {
        'MP3 (192kbps)': 'ba/bestaudio',
        'M4A (AAC)': 'ba*[ext=m4a]/bestaudio[ext=m4a]',
        'OPUS (Lossy)': 'ba/bestaudio',
        'WAV (Uncompressed)': 'ba/bestaudio',
        'FLAC (Lossless)': 'ba/bestaudio',
    }
}

# ==========================
#  Helpers
# ==========================

def platform_config_dir() -> Path:
    """Return per-OS config dir."""
    if sys.platform.startswith('win'):
        base = os.environ.get('APPDATA') or os.path.expanduser('~')
        return Path(base) / APP_NAME
    elif sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / APP_NAME
    else:
        return Path.home() / '.config' / APP_NAME

CONFIG_DIR = platform_config_dir()
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / 'config.json'

# ==========================
#  Main App
# ==========================
class YTDLPGUI:
    def __init__(self, master: tk.Tk):
        self.master = master
        master.title("YT-DLP Загрузчик (YouTube Design)")
        master.configure(bg=colors['bg'])
        master.resizable(True, False)  # ширину можно тянуть

        # State variables
        self.download_path = tk.StringVar()
        self.url_var = tk.StringVar()
        self.subfolder_var = tk.StringVar()
        self.selected_format_var = tk.StringVar()

        self.opt_playlist_all = tk.BooleanVar(value=False)
        self.opt_open_after_queue = tk.BooleanVar(value=True)
        self.opt_embed_thumbnail = tk.BooleanVar(value=False)
        self.opt_embed_subs = tk.BooleanVar(value=False)
        self.opt_keep_temp = tk.BooleanVar(value=False)  # -k

        self.net_threads = tk.IntVar(value=8)  # -N
        self.limit_rate = tk.StringVar(value="")  # e.g. 5M

        self.download_queue = []  # list[(url, command, final_dir)]
        self.is_downloading = False
        self.current_process: subprocess.Popen | None = None

        # load settings
        self._load_settings()

        # styles
        self._setup_styles()

        # layout
        self._build_ui()

        # check deps (non-fatal)
        self._check_binaries_silent()

        master.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ---------- UI / Styles ----------
    def _setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except tk.TclError:
            style.theme_use('default')

        style.configure('Rounded.TButton', background=colors['button'], foreground=colors['button_fg'],
                        padding=[10, 5], relief='flat', font=('Arial', 10, 'bold'))
        style.map('Rounded.TButton',
                  background=[('active', colors['button_hover'])],
                  foreground=[('!disabled', colors['button_fg'])])

        style.configure('Accent.Rounded.TButton', background=colors['accent'], foreground=colors['accent_fg'],
                        padding=[12, 6], relief='flat', font=('Arial', 12, 'bold'))
        style.map('Accent.Rounded.TButton', background=[('active', '#D9D9D9')])

        # Radiobuttons without dot indicator
        style.configure('Choice.TRadiobutton', background=colors['button'], foreground=colors['button_fg'],
                        padding=[10, 5], font=('Arial', 10, 'bold'))
        style.map('Choice.TRadiobutton',
                  background=[('active', colors['button_hover'])],
                  foreground=[('!disabled', colors['button_fg'])])
        style.layout('Choice.TRadiobutton', [
            ('Radiobutton.padding', {'sticky': 'nswe', 'children': [
                ('Radiobutton.label', {'sticky': 'nswe'})
            ]})
        ])

        style.configure('ChoiceSelected.TRadiobutton', background=colors['selected_bg'], foreground=colors['selected_fg'],
                        padding=[10, 5], font=('Arial', 10, 'bold'))
        style.map('ChoiceSelected.TRadiobutton',
                  background=[('active', colors['selected_bg'])],
                  foreground=[('!disabled', colors['selected_fg'])])
        style.layout('ChoiceSelected.TRadiobutton', [
            ('Radiobutton.padding', {'sticky': 'nswe', 'children': [
                ('Radiobutton.label', {'sticky': 'nswe'})
            ]})
        ])

    def _build_ui(self):
        main = tk.Frame(self.master, padx=10, pady=10, bg=colors['bg'])
        main.pack(fill='both', expand=True)
        main.grid_columnconfigure(1, weight=1)

        # --- Settings row ---
        settings = tk.Frame(main, bg=colors['bg'])
        settings.grid(row=0, column=0, columnspan=3, sticky='ew')
        settings.grid_columnconfigure(1, weight=1)

        self._label(settings, "Папка:", 0, 0)
        path_entry = self._entry(settings, self.download_path, state='readonly',
                                 readonly_fg=colors['fg'], readonly_bg=colors['bg_secondary'])
        path_entry.grid(row=0, column=1, sticky='we', padx=5)
        self._button(settings, "Выбрать", self.choose_dir).grid(row=0, column=2, padx=(5, 0))

        self._label(settings, "Подпапка:", 1, 0)
        self._entry(settings, self.subfolder_var).grid(row=1, column=1, columnspan=2, sticky='we', padx=5)

        self._label(settings, "URL:", 2, 0)
        self._entry(settings, self.url_var).grid(row=2, column=1, sticky='we', padx=5)
        self._button(settings, "Вставить", self.paste_from_clipboard).grid(row=2, column=2, padx=(5, 0))

        # --- Options row ---
        opts = tk.Frame(main, bg=colors['bg'])
        opts.grid(row=1, column=0, columnspan=3, sticky='ew', pady=(6, 0))

        ttk.Checkbutton(opts, text="Скачать весь плейлист", variable=self.opt_playlist_all).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(opts, text="Встраивать миниатюру", variable=self.opt_embed_thumbnail).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(opts, text="Встраивать субтитры", variable=self.opt_embed_subs).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(opts, text="Сохр. исходные (-k)", variable=self.opt_keep_temp).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(opts, text="Открыть папку после очереди", variable=self.opt_open_after_queue).pack(side=tk.LEFT, padx=5)

        net = tk.Frame(main, bg=colors['bg'])
        net.grid(row=2, column=0, columnspan=3, sticky='ew', pady=(6, 0))
        tk.Label(net, text="Потоков (-N):", bg=colors['bg'], fg=colors['fg']).pack(side=tk.LEFT)
        ttk.Spinbox(net, from_=1, to=32, textvariable=self.net_threads, width=4).pack(side=tk.LEFT, padx=5)
        tk.Label(net, text="Лимит скорости (напр. 5M):", bg=colors['bg'], fg=colors['fg']).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Entry(net, textvariable=self.limit_rate, width=10).pack(side=tk.LEFT, padx=5)

        # --- Formats grid ---
        formats_frame = tk.Frame(main, bg=colors['bg'], pady=10)
        formats_frame.grid(row=3, column=0, columnspan=3, sticky='ew')

        self.format_buttons: list[ttk.Radiobutton] = []
        formats_data: list[tuple[str, str]] = []
        for category, options in FORMAT_OPTIONS.items():
            for text, fmt in options.items():
                formats_data.append((f"{category} - {text}", fmt))

        def sort_key(item_tuple):
            text = item_tuple[0]
            nums = re.findall(r'\d+', text)
            if not nums:
                val = 0
            else:
                val = int(nums[0])
                if 'K' in text and val < 100:
                    val *= 1000
            if 'High Res' in text:
                return 30000 + val
            elif 'Видео' in text:
                return 20000 + val
            elif 'Аудио' in text:
                return 10000 + val
            return val

        formats_data.sort(key=sort_key)
        audio, video = [], []
        for t, v in formats_data:
            (audio if 'Аудио' in t else video).append((t, v))
        formats_data = video + audio

        default_value = next((v for t, v in formats_data if '1080p' in t), formats_data[0][1])
        self.selected_format_var.set(self._load_last_format(default_value))

        for i, (text, value) in enumerate(formats_data):
            display = " - ".join(text.split(' - ')[1:])
            rb = ttk.Radiobutton(formats_frame, text=display, variable=self.selected_format_var,
                                 value=value, style='Choice.TRadiobutton',
                                 command=self._update_format_styles)
            rb.grid(row=i // 3, column=i % 3, sticky='we', padx=5, pady=2)
            self.format_buttons.append(rb)
        self._update_format_styles()

        # --- Queue & Log ---
        queue_frame = tk.Frame(main, bg=colors['bg'], pady=5)
        queue_frame.grid(row=4, column=0, columnspan=3, sticky='ew')
        queue_frame.grid_columnconfigure(0, weight=1)

        buttons_row = tk.Frame(queue_frame, bg=colors['bg'])
        buttons_row.grid(row=0, column=0, columnspan=3, sticky='ew')
        self._button(buttons_row, "Добавить в очередь 🔽", self.add_to_queue).pack(side=tk.LEFT, padx=5, pady=5)
        self._button(buttons_row, "Очистить очередь", self.clear_queue).pack(side=tk.LEFT, padx=5, pady=5)
        self._button(buttons_row, "⏹ Стоп", self.stop_current).pack(side=tk.RIGHT, padx=5, pady=5)
        ttk.Button(buttons_row, text="🚀 СТАРТ", command=self.start_queue_download, style='Accent.Rounded.TButton').pack(side=tk.RIGHT, padx=5, pady=5)

        # Progressbar
        self.progress = ttk.Progressbar(queue_frame, orient='horizontal', mode='determinate', length=400)
        self.progress.grid(row=1, column=0, columnspan=3, sticky='ew', pady=(0, 6))

        # Log widget + scrollbar
        self.log_text_widget = tk.Text(queue_frame, height=12, bg=colors['bg_secondary'], fg=colors['fg'],
                                       bd=1, relief=tk.FLAT, highlightthickness=0, wrap=tk.WORD, font=('Courier', 9))
        self.log_text_widget.grid(row=2, column=0, columnspan=2, sticky='nsew')
        scroll = ttk.Scrollbar(queue_frame, command=self.log_text_widget.yview)
        scroll.grid(row=2, column=2, sticky='ns')
        self.log_text_widget.configure(yscrollcommand=scroll.set)

        # Tags
        self.log_text_widget.tag_config('success', foreground=colors['accent'], background=colors['accent_fg'], font=('Courier', 9, 'bold'))
        self.log_text_widget.tag_config('error', foreground=colors['error'], font=('Courier', 9, 'bold'))
        self.log_text_widget.tag_config('info', foreground=colors['log_download'], font=('Courier', 9, 'bold'))
        self.log_text_widget.tag_config('process', foreground=colors['log_process'])
        self.log_text_widget.tag_config('queue', foreground=colors['fg'])
        self.log_text_widget.tag_config('download', foreground=colors['log_download'], font=('Courier', 9, 'bold'))

    def _label(self, parent, text, row, col):
        lbl = tk.Label(parent, text=text, bg=colors['bg'], fg=colors['fg'], font=('Arial', 10, 'bold'))
        lbl.grid(row=row, column=col, sticky='w', padx=5, pady=5)
        return lbl

    def _entry(self, parent, textvariable, state='normal', readonly_fg=None, readonly_bg=None):
        opts = {
            'textvariable': textvariable,
            'state': state,
            'insertbackground': colors['fg'],
            'relief': tk.FLAT,
            'bd': 0,
            'highlightthickness': 1,
            'highlightbackground': colors['button']
        }
        if state == 'readonly':
            opts['fg'] = readonly_fg or colors['fg']
            opts['bg'] = readonly_bg or colors['entry_bg']
            opts['readonlybackground'] = readonly_bg or colors['entry_bg']
        else:
            opts['fg'] = colors['entry_fg']
            opts['bg'] = colors['entry_bg']
        return tk.Entry(parent, **opts)

    def _button(self, parent, text, command):
        style = 'Accent.Rounded.TButton' if "СТАРТ" in text else 'Rounded.TButton'
        return ttk.Button(parent, text=text, command=command, style=style)

    def _update_format_styles(self):
        sel = self.selected_format_var.get()
        for rb in self.format_buttons:
            if rb.cget('value') == sel:
                rb.configure(style='ChoiceSelected.TRadiobutton')
            else:
                rb.configure(style='Choice.TRadiobutton')
        # persist selection
        self._save_last_format(sel)

    # ---------- Settings ----------
    def _settings_path(self) -> Path:
        return CONFIG_FILE

    def _load_settings(self):
        cfg_path = self._settings_path()
        try:
            with open(cfg_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        self.download_path.set(data.get('download_path', DEFAULT_DOWNLOAD_DIR))
        self.subfolder_var.set(data.get('subfolder', 'yt-dlp_downloads'))

    def _save_settings(self):
        cfg_path = self._settings_path()
        data = {
            'download_path': self.download_path.get(),
            'subfolder': self.subfolder_var.get(),
            'last_format': self.selected_format_var.get(),
            'opts': {
                'playlist_all': self.opt_playlist_all.get(),
                'open_after_queue': self.opt_open_after_queue.get(),
                'embed_thumbnail': self.opt_embed_thumbnail.get(),
                'embed_subs': self.opt_embed_subs.get(),
                'keep_temp': self.opt_keep_temp.get(),
                'net_threads': self.net_threads.get(),
                'limit_rate': self.limit_rate.get(),
            }
        }
        try:
            with open(cfg_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения настроек: {e}")

    def _load_last_format(self, default_val: str) -> str:
        try:
            with open(self._settings_path(), 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('last_format', default_val)
        except Exception:
            return default_val

    def _save_last_format(self, fmt: str):
        # merge-save
        try:
            cfg = {}
            p = self._settings_path()
            if p.exists():
                with open(p, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
            cfg['last_format'] = fmt
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---------- Handlers ----------
    def on_closing(self):
        self._save_settings()
        self.master.destroy()

    def choose_dir(self):
        initial = self.download_path.get() if os.path.exists(self.download_path.get()) else os.path.expanduser('~')
        new_dir = filedialog.askdirectory(initialdir=initial, title="Выберите папку для сохранения")
        if new_dir:
            self.download_path.set(new_dir)
            self._save_settings()

    def paste_from_clipboard(self):
        try:
            self.url_var.set(self.master.clipboard_get())
        except tk.TclError:
            pass

    def clear_queue(self):
        self.download_queue.clear()
        self._log("Очередь очищена\n", 'queue')

    def add_to_queue(self):
        url = self.url_var.get().strip()
        fmt = self.selected_format_var.get().strip()
        if not url:
            messagebox.showerror("Ошибка ввода", "Введите URL для загрузки.")
            return
        if not fmt:
            messagebox.showerror("Ошибка формата", "Выберите формат загрузки.")
            return

        # build output dir
        subfolder = sanitize_subfolder(self.subfolder_var.get())
        final_dir = os.path.join(self.download_path.get(), subfolder)
        os.makedirs(final_dir, exist_ok=True)

        # build command
        cmd = [YTDLP_BIN, '-v', '-N', str(self.net_threads.get()), '-f', fmt]

        # apply options
        if self.opt_keep_temp.get():
            cmd.append('-k')
        if self.opt_embed_thumbnail.get():
            cmd.extend(['--embed-thumbnail'])
        if self.opt_embed_subs.get():
            cmd.extend(['--embed-subs'])
        if self.opt_playlist_all.get():
            cmd.append('--yes-playlist')
        else:
            cmd.append('--no-playlist')
        if self.limit_rate.get().strip():
            cmd.extend(['--limit-rate', self.limit_rate.get().strip()])

        # platform-specific filename policy
        if sys.platform.startswith('win'):
            cmd.append('--windows-filenames')

        # output template
        out_tmpl = os.path.join(final_dir, '%(title).180B [%(id)s].%(ext)s')
        cmd.extend(['-o', out_tmpl])

        cmd.append(url)

        self.download_queue.append((url, cmd, final_dir))
        self._log(f"Добавлено в очередь: {url}\n", 'queue')
        self.url_var.set("")
        self._save_settings()

    def start_queue_download(self):
        if self.is_downloading:
            messagebox.showwarning("Загрузка", "Загрузка уже идет.")
            return
        if not self.download_queue:
            messagebox.showinfo("Очередь", "Очередь загрузки пуста.")
            return
        self.is_downloading = True
        self.progress['value'] = 0
        self._log("\n--- ЗАПУСК ОЧЕРЕДИ ---\n", 'info')
        self._process_queue()

    def stop_current(self):
        proc = self.current_process
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            self._log("\n--- ОСТАНОВЛЕНО ПОЛЬЗОВАТЕЛЕМ ---\n", 'error')

    def _process_queue(self):
        if not self.download_queue:
            self.is_downloading = False
            self._log("\n--- ОЧЕРЕДЬ ЗАВЕРШЕНА ---\n", 'info')
            if self.opt_open_after_queue.get() and self._last_output_dir:
                self._open_folder(self._last_output_dir)
            messagebox.showinfo("Завершено", "Вся очередь загружена!")
            return

        url, command, final_dir = self.download_queue.pop(0)
        self._last_output_dir = final_dir
        self._log(f"\n--- Загрузка: {url} ---\n", 'info')
        self._log(f"Команда: {' '.join(command)}\n")
        threading.Thread(target=self._execute_download, args=(command, final_dir), daemon=True).start()

    def _open_folder(self, path):
        try:
            if sys.platform.startswith('win'):
                os.startfile(path)  # type: ignore
            elif sys.platform == 'darwin':
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            print(f"Не удалось открыть папку: {e}")

    def _execute_download(self, command, final_dir):
        try:
            startupinfo = None
            if sys.platform.startswith('win'):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            self.current_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',
                startupinfo=startupinfo
            )

            for raw in iter(self.current_process.stdout.readline, ''):
                if raw is None:
                    break
                line = raw.replace('\r', '')  # yt-dlp uses carriage returns
                self.master.after(0, self._handle_output_line, line)

            self.current_process.wait()
            rc = self.current_process.returncode
            self.master.after(0, self._on_single_finish, rc, final_dir)
        except FileNotFoundError:
            self.master.after(0, messagebox.showerror, "Критическая ошибка", f"'{YTDLP_BIN}' не найден. Убедитесь, что yt-dlp в PATH.")
            self.master.after(0, self._on_single_finish, -1, None)
        except Exception as e:
            self.master.after(0, messagebox.showerror, "Критическая ошибка", f"Ошибка выполнения: {e}")
            self.master.after(0, self._on_single_finish, -1, None)
        finally:
            self.current_process = None

    def _handle_output_line(self, line: str):
        # progress parse
        if '[download]' in line:
            # match 12.3% or 12%
            m = re.search(r'(\d{1,3}(?:\.\d+)?)%', line)
            if m:
                try:
                    val = float(m.group(1))
                    self.progress['value'] = max(0.0, min(100.0, val))
                except ValueError:
                    pass
            self._log(line, 'download')
        elif any(tag in line for tag in ('[Merger]', '[ExtractAudio]', '[ffmpeg]')):
            self._log(line, 'process')
        else:
            self._log(line)

    def _on_single_finish(self, return_code: int, final_dir: str | None):
        self.progress['value'] = 0
        if return_code == 0:
            self._log("\n--- УСПЕХ ---\n", 'success')
        else:
            self._log(f"\n--- ОШИБКА: Код {return_code} ---\n", 'error')
        self.master.after(300, self._process_queue)

    def _log(self, text: str, tag: str | None = None):
        if not hasattr(self, 'log_text_widget') or not self.log_text_widget.winfo_exists():
            return
        try:
            self.log_text_widget.configure(state='normal')
            if tag:
                self.log_text_widget.insert(tk.END, text, tag)
            else:
                self.log_text_widget.insert(tk.END, text)
            self.log_text_widget.see(tk.END)
            self.log_text_widget.configure(state='disabled')
        except tk.TclError:
            pass

    # ---------- Deps check ----------
    def _check_binaries_silent(self):
        def have(cmd):
            try:
                subprocess.run([cmd, '--version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception:
                return False
        if not have(YTDLP_BIN):
            self._log("ВНИМАНИЕ: yt-dlp не найден в PATH. Установите yt-dlp.\n", 'error')
        # ffmpeg is optional but recommended
        if not have('ffmpeg'):
            self._log("ВНИМАНИЕ: ffmpeg не найден. Некоторые операции могут не работать.\n", 'error')

# ---------- Utilities ----------
def sanitize_subfolder(name: str) -> str:
    name = (name or '').strip() or 'yt-dlp_downloads'
    # Windows forbidden characters
    forbidden = r'<>:"/\\|?*'
    return ''.join(ch for ch in name if ch not in forbidden)


if __name__ == "__main__":
    print("--- Запуск GUI... ---")
    root = tk.Tk()
    app = YTDLPGUI(root)
    root.mainloop()
