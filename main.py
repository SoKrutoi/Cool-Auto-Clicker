import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
import keyboard
import mouse
import queue

# Карта скан-кодов к английским символам US раскладки
def build_code_map():
    code_map = {}
    for ch in 'abcdefghijklmnopqrstuvwxyz':
        for code in keyboard.key_to_scan_codes(ch):
            code_map[code] = ch
    for digit in '0123456789':
        for code in keyboard.key_to_scan_codes(digit):
            code_map[code] = digit
    for i in range(1, 13):
        key = f'f{i}'
        for code in keyboard.key_to_scan_codes(key):
            code_map[code] = key
    specials = {'space':'space','enter':'enter','tab':'tab','esc':'esc',
                'up':'up','down':'down','left':'left','right':'right'}
    for key, name in specials.items():
        for code in keyboard.key_to_scan_codes(key):
            code_map[code] = name
    return code_map

class AutoClicker:
    def __init__(self, master):
        self.master = master
        self.master.title("Автокликер")
        self.center_window(300, 180)
        self.running = False
        self.click_thread = None
        self.code_map = build_code_map()
        self.click_action = None  # (type, identifier)
        self.hotkey_handle = None

        # Режим
        ttk.Label(master, text="Режим:").grid(row=0, column=0, padx=5, pady=5, sticky='e')
        self.mode_var = tk.StringVar(value='keyboard')
        self.option_menu = ttk.OptionMenu(master, self.mode_var, 'keyboard', 'keyboard', 'mouse', command=self.on_mode_change)
        self.option_menu.grid(row=0, column=1, padx=5, pady=5, sticky='we')

        # Метка и поле/список для клика
        ttk.Label(master, text="Кнопка для клика:").grid(row=1, column=0, padx=5, pady=5, sticky='e')
        self.key_var = tk.StringVar()
        self.entry = ttk.Entry(master, textvariable=self.key_var, state='readonly')
        self.entry.grid(row=1, column=1, padx=5, pady=5, sticky='we')
        self.entry.bind('<Button-1>', lambda e: self.wait_for_event('click'))

        self.mouse_options = ['left', 'right', 'middle', 'wheel_up', 'wheel_down']
        self.mouse_var = tk.StringVar()
        self.mouse_combo = ttk.Combobox(master, values=self.mouse_options, textvariable=self.mouse_var, state='readonly')
        self.mouse_combo.grid(row=1, column=1, padx=5, pady=5, sticky='we')
        self.mouse_combo.bind('<<ComboboxSelected>>', lambda e: self.on_mouse_selected())

        # Интервал
        ttk.Label(master, text="Интервал (мс):").grid(row=2, column=0, padx=5, pady=5, sticky='e')
        self.interval_var = tk.IntVar(value=100)
        self.interval_spin = ttk.Spinbox(master, from_=1, to=10000, textvariable=self.interval_var)
        self.interval_spin.grid(row=2, column=1, padx=5, pady=5, sticky='we')

        # Хоткей переключения
        ttk.Label(master, text="Клавиша переключения:").grid(row=3, column=0, padx=5, pady=5, sticky='e')
        self.hotkey_var = tk.StringVar(value='f6')
        self.hotkey_entry = ttk.Entry(master, textvariable=self.hotkey_var, state='readonly')
        self.hotkey_entry.grid(row=3, column=1, padx=5, pady=5, sticky='we')
        self.hotkey_entry.bind('<Button-1>', lambda e: self.wait_for_event('toggle'))

        # Устанавливаем дефолтный хоткей F6
        try:
            self.hotkey_handle = keyboard.add_hotkey('f6', self.toggle)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось зарегистрировать хоткей: {e}")

        # Статус
        self.status_label = ttk.Label(master, text="Неактивно", foreground='red')
        self.status_label.grid(row=4, column=0, columnspan=2, pady=10)
        master.columnconfigure(1, weight=1)
        master.protocol("WM_DELETE_WINDOW", self.on_close)

        # Инициализация режима
        self.on_mode_change('keyboard')

    def center_window(self, w, h):
        self.master.update_idletasks()
        x = (self.master.winfo_screenwidth() - w) // 2
        y = (self.master.winfo_screenheight() - h) // 2
        self.master.geometry(f"{w}x{h}+{x}+{y}")

    def on_mode_change(self, mode):
        if mode == 'keyboard':
            self.entry.grid()
            self.mouse_combo.grid_remove()
            self.key_var.set('')
            self.click_action = None
        else:
            self.mouse_combo.grid()
            self.entry.grid_remove()
            self.mouse_var.set(self.mouse_options[0])
            self.click_action = ('mouse', self.mouse_options[0])

    def on_mouse_selected(self):
        self.click_action = ('mouse', self.mouse_var.get())

    def wait_for_event(self, mode):
        self.status_label.config(text="Нажмите клавишу...", foreground='blue')
        q = queue.Queue()

        def listen_keyboard():
            e = keyboard.read_event()
            if e.event_type == keyboard.KEY_DOWN:
                name = self.code_map.get(e.scan_code, e.name)
                q.put((mode, 'keyboard', name))

        threading.Thread(target=listen_keyboard, daemon=True).start()

        def check_queue():
            try:
                m, kind, ident = q.get_nowait()
            except queue.Empty:
                self.master.after(50, check_queue)
                return

            # Обработка Escape: очищаем
            if kind == 'keyboard' and ident == 'esc':
                if m == 'click':
                    self.click_action = None
                    self.key_var.set('')
                else:
                    if self.hotkey_handle:
                        keyboard.remove_hotkey(self.hotkey_handle)
                    self.hotkey_handle = None
                    self.hotkey_var.set('')
                self.update_status()
                return

            if m == 'click':
                self.click_action = (kind, ident)
                self.key_var.set(ident)
            else:
                # переустанавливаем хоткей
                if self.hotkey_handle:
                    keyboard.remove_hotkey(self.hotkey_handle)
                self.hotkey_handle = keyboard.add_hotkey(ident, self.toggle)
                self.hotkey_var.set(ident)

            self.update_status()

        check_queue()

    def toggle(self):
        if self.running:
            self.stop_clicking()
        else:
            self.start_clicking()

    def start_clicking(self):
        if not self.click_action:
            messagebox.showwarning("Внимание", "Не выбрана кнопка для клика.")
            return
        self.running = True
        self.update_status()
        self.click_thread = threading.Thread(target=self.click_loop, daemon=True)
        self.click_thread.start()

    def stop_clicking(self):
        self.running = False
        self.update_status()

    def click_loop(self):
        interval = self.interval_var.get() / 1000.0
        kind, ident = self.click_action
        while self.running:
            if kind == 'keyboard':
                keyboard.send(ident)
            else:
                if ident in ('left', 'right', 'middle'):
                    mouse.click(ident)
                else:
                    mouse.wheel(1 if ident == 'wheel_up' else -1)
            time.sleep(interval)

    def update_status(self):
        text = "Активно" if self.running else "Неактивно"
        color = 'green' if self.running else 'red'
        self.status_label.config(text=text, foreground=color)

    def on_close(self):
        if self.hotkey_handle:
            keyboard.remove_hotkey(self.hotkey_handle)
        self.stop_clicking()
        self.master.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    AutoClicker(root)
    root.mainloop()
