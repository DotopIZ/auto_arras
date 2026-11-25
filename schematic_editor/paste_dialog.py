"""GUI-диалог настройки и запуска print_template.paste_template."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os

from auto_arras.print_template import paste_template
from schematic_editor.i18n import TRANSLATIONS, translate


_FIELDS = [
    ("arena_size",           "paste_fld_arena",       "64",        int),
    ("lvl",                  "paste_fld_lvl",         "45",        int),
    ("tank",                 "paste_fld_tank",        "spectator", str),
    ("press_interval",       "paste_fld_interval",    "0.05",      float),
    ("seconds_before_paste", "paste_fld_delay",       "5",         float),
    ("grid_search_radius",   "paste_fld_radius",      "20",        int),
    ("snap_offset",          "paste_fld_snap_offset", "0.5",       float),
]

_BOOLS = [
    ("snap_to_grid", "paste_bool_snap",    False),
    ("anchor_grid",  "paste_bool_anchor",  True),
    ("do_warning",   "paste_bool_warning", True),
]


class PasteDialog(tk.Toplevel):
    def __init__(self, master, template_text=None, lang="en"):
        super().__init__(master)
        self.lang = lang if lang in TRANSLATIONS else "en"
        self.template_text = template_text   # контент из редактора (опционально)

        self._vars = {}
        self._bools = {}

        self.title(self.t("paste_dialog_title"))
        self.transient(master)
        self.grab_set()
        self.resizable(False, False)

        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(1, weight=1)
        row = 0

        # «Использовать текущую схему» — только если редактор передал контент
        self._use_current = None
        if template_text is not None:
            self._use_current = tk.BooleanVar(value=False)
            ttk.Checkbutton(
                body, text=self.t("paste_use_current"),
                variable=self._use_current,
                command=self._toggle_source,
            ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 4))
            row += 1

        # Файл шаблона + Обзор
        ttk.Label(body, text=self.t("paste_lbl_file") + ":").grid(
            row=row, column=0, sticky="w", pady=3, padx=(0, 8))
        file_frame = ttk.Frame(body)
        file_frame.grid(row=row, column=1, sticky="ew", pady=3)
        file_frame.columnconfigure(0, weight=1)
        self._file_var = tk.StringVar(value="")
        self._file_entry = ttk.Entry(file_frame, textvariable=self._file_var)
        self._file_entry.grid(row=0, column=0, sticky="ew")
        self._browse_btn = ttk.Button(
            file_frame, text=self.t("paste_btn_browse"),
            command=self._on_browse)
        self._browse_btn.grid(row=0, column=1, padx=(4, 0))
        row += 1

        # Параметры
        for name, label_key, default, _conv in _FIELDS:
            ttk.Label(body, text=self.t(label_key) + ":").grid(
                row=row, column=0, sticky="w", pady=3, padx=(0, 8))
            var = tk.StringVar(value=default)
            self._vars[name] = var
            ttk.Entry(body, textvariable=var, width=24).grid(
                row=row, column=1, sticky="ew", pady=3)
            row += 1

        # Флаги
        for name, label_key, default in _BOOLS:
            var = tk.BooleanVar(value=default)
            self._bools[name] = var
            ttk.Checkbutton(body, text=self.t(label_key), variable=var).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=2)
            row += 1

        buttons = ttk.Frame(body)
        buttons.grid(row=row, column=0, columnspan=2,
                     pady=(12, 0), sticky="e")
        ttk.Button(buttons, text=self.t("paste_btn_ok"),
                   command=self._on_ok).pack(side=tk.RIGHT, padx=4)
        ttk.Button(buttons, text=self.t("paste_btn_cancel"),
                   command=self.destroy).pack(side=tk.RIGHT)

        self.bind("<Escape>", lambda e: self.destroy())
        self._toggle_source()

    def t(self, key, *args, **kwargs):
        return translate(self.lang, key, *args, **kwargs)

    def _toggle_source(self):
        use_current = self._use_current is not None and self._use_current.get()
        state = "disabled" if use_current else "normal"
        self._file_entry.config(state=state)
        self._browse_btn.config(state=state)

    def _on_browse(self):
        path = filedialog.askopenfilename(
            parent=self,
            title=self.t("paste_lbl_file"),
            filetypes=[
                (self.t("paste_filetype_txt"), "*.txt"),
                (self.t("paste_filetype_all"), "*.*"),
            ],
        )
        if path:
            self._file_var.set(path)

    def _collect_kwargs(self):
        kwargs = {}
        for name, label_key, _default, conv in _FIELDS:
            raw = self._vars[name].get().strip()
            try:
                kwargs[name] = conv(raw)
            except (ValueError, TypeError):
                raise ValueError(
                    self.t("paste_err_field", self.t(label_key), raw))
        for name, _label_key, _default in _BOOLS:
            kwargs[name] = self._bools[name].get()
        kwargs["do_warning"] = False   # предупреждение уже покажем здесь
        return kwargs

    def _get_content(self):
        if self._use_current is not None and self._use_current.get():
            return self.template_text
        path = self._file_var.get().strip()
        if not path:
            raise ValueError(self.t("paste_err_no_file"))
        if not os.path.isfile(path):
            raise ValueError(self.t("paste_err_file_not_found", path))
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            raise ValueError(self.t("paste_err_read_file", e))

    def _on_ok(self):
        try:
            content = self._get_content()
            if not content or not content.strip():
                raise ValueError(self.t("paste_err_empty"))
            kwargs = self._collect_kwargs()
        except ValueError as e:
            messagebox.showerror(self.t("paste_err_title"), str(e), parent=self)
            return

        if self._bools["do_warning"].get():
            proceed = messagebox.askokcancel(
                self.t("paste_warn_title"),
                self.t("paste_warn_text",
                       delay=kwargs["seconds_before_paste"],
                       tank=kwargs["tank"],
                       lvl=kwargs["lvl"]),
                parent=self,
            )
            if not proceed:
                return

        self.destroy()

        # Передаём КОНТЕНТ (str), а не путь
        def run():
            print(content)
            paste_template(content, **kwargs)

        threading.Thread(target=run, daemon=True).start()