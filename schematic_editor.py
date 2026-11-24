import tkinter as tk
from tkinter import filedialog, messagebox
import json
import time   # вместо import math
import copy



class ChunkedLayerData(dict):
    """Словарь клеток (col, row) → item с пространственным индексом по чанкам.

    Все существующие операции (grid_data[loc] = item, del grid_data[loc])
    автоматически поддерживают индекс. redraw_canvas обходит только чанки,
    попавшие во вьюпорт, вместо полного перебора всех клеток слоя.
    """
    CHUNK_SIZE = 32

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._chunks = {}
        for key in self.keys():
            self._chunk_add(key)

    def _chunk_add(self, key):
        ck = (key[0] // self.CHUNK_SIZE, key[1] // self.CHUNK_SIZE)
        bucket = self._chunks.get(ck)
        if bucket is None:
            bucket = self._chunks[ck] = set()
        bucket.add(key)

    def _chunk_remove(self, key):
        ck = (key[0] // self.CHUNK_SIZE, key[1] // self.CHUNK_SIZE)
        bucket = self._chunks.get(ck)
        if bucket is not None:
            bucket.discard(key)
            if not bucket:
                del self._chunks[ck]

    def __setitem__(self, key, value):
        if key not in self:
            self._chunk_add(key)
        super().__setitem__(key, value)

    def __delitem__(self, key):
        if key in self:
            self._chunk_remove(key)
        super().__delitem__(key)

    def clear(self):
        super().clear()
        self._chunks.clear()

    def cells_in_view(self, min_col, max_col, min_row, max_row):
        cs = self.CHUNK_SIZE
        for cx in range(min_col // cs, max_col // cs + 1):
            for cy in range(min_row // cs, max_row // cs + 1):
                for key in self._chunks.get((cx, cy), ()):
                    yield key, self[key]


class ChunkedLayerLines(dict):
    """Словарь линий ((c1,r1),(c2,r2)) → item с индексом по bbox-чанкам."""
    CHUNK_SIZE = 32

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._chunks = {}
        for key in self.keys():
            self._chunk_add(key)

    def _chunks_of(self, key):
        (c1, r1), (c2, r2) = key
        min_c, max_c = (c1, c2) if c1 <= c2 else (c2, c1)
        min_r, max_r = (r1, r2) if r1 <= r2 else (r2, r1)
        cs = self.CHUNK_SIZE
        for cx in range(min_c // cs, max_c // cs + 1):
            for cy in range(min_r // cs, max_r // cs + 1):
                yield (cx, cy)

    def _chunk_add(self, key):
        for ck in self._chunks_of(key):
            bucket = self._chunks.get(ck)
            if bucket is None:
                bucket = self._chunks[ck] = set()
            bucket.add(key)

    def _chunk_remove(self, key):
        for ck in self._chunks_of(key):
            bucket = self._chunks.get(ck)
            if bucket is not None:
                bucket.discard(key)
                if not bucket:
                    del self._chunks[ck]

    def __setitem__(self, key, value):
        if key not in self:
            self._chunk_add(key)
        super().__setitem__(key, value)

    def __delitem__(self, key):
        if key in self:
            self._chunk_remove(key)
        super().__delitem__(key)

    def clear(self):
        super().clear()
        self._chunks.clear()

    def lines_in_view(self, min_col, max_col, min_row, max_row):
        cs = self.CHUNK_SIZE
        seen = set()
        for cx in range(min_col // cs, max_col // cs + 1):
            for cy in range(min_row // cs, max_row // cs + 1):
                for key in self._chunks.get((cx, cy), ()):
                    if key in seen:
                        continue
                    seen.add(key)
                    yield key, self[key]

class GridApp:
    CAMERA_SPEED = 1500.0
    _redraw_scheduled = False  # <-- Защита от ошибок инициализации

    def __init__(self, root, tools=None):
        self.root = root
        self.root.title("Бесконечная сетка с инструментами и экспортом")

        self.cell_size = 25
        self.min_cell_size_grid = 15
        self.min_cell_size_text = 35
        self.min_cell_size_marker = 1
        self.min_cell_size_arrow = 15
        self.default_cell_size = self.cell_size

        self.is_dirty = False

        self.view_width = 900
        self.view_height = 600
        self.cam_x = 0.0
        self.cam_y = 0.0

        self.cam_vx = 0.0
        self.cam_vy = 0.0
        self.pressed_keys = set()
        self._redraw_scheduled = False
        self.is_moving = False
        self._last_anim_time = None

        self.zoom_speed = 1.2
        self.zoom_in_limit = 1000
        self.zoom_out_limit = 0.1

        self.is_moving_selection = False
        # Панорамирование камеры средней кнопкой мыши
        self.is_panning = False
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.pan_cam_start_x = 0.0
        self.pan_cam_start_y = 0.0
        # Панорамирование пробелом (как в Photoshop/Figma)
        self.space_pan_active = False
        self._space_panning = False
        # Последняя позиция курсора над холстом (для +/- зума)
        self.mouse_x = self.view_width / 2
        self.mouse_y = self.view_height / 2
        # Словарь кнопок инструментов (для подсветки активного)
        self.tool_buttons = {}

        self.layers = [
            {"name": "Слой 1", "visible": True,
             "data": ChunkedLayerData(), "lines": ChunkedLayerLines()}
        ]
        self.active_layer_idx = 0
        self.line_start = None

        self.undo_stack = []
        self.redo_stack = []

        self.floating_data = None
        self.floating_lines = None
        self.floating_offset = (0, 0)
        # Флаг: состояние перед началом плавающей операции уже сохранено в undo.
        # Нужен, чтобы не сохранять его повторно в commit_floating (иначе один шаг
        # перемещения/вырезания требует ДВУХ undo).
        self._floating_state_saved = False
        self.clipboard = None

        self.selection = None
        self.sel_start = None
        self.sel_end = None
        self.sel_rect_id = None

        self.mouse_col = 0
        self.mouse_row = 0

        self.parse_tools(tools)

        self.tool_prop_values = {}
        for name, data in self.tools.items():
            props = data[1]
            self.tool_prop_values[name] = {p: "0" for p in props}

        if not self.tools:
            raise ValueError("Список инструментов пуст")
        first_name = list(self.tools.keys())[0]
        self.current_value = first_name
        self.current_color = self.tools[first_name][0]
        self.current_props_list = self.tools[first_name][1]

        self.create_menu()

        self.main_container = tk.Frame(self.root)
        self.main_container.pack(fill=tk.BOTH, expand=True)

        self.left_toolbar = tk.Frame(self.main_container, bd=1, relief=tk.RAISED, width=100)
        self.left_toolbar.pack(side=tk.LEFT, fill=tk.Y, padx=2, pady=2)
        self.left_toolbar.pack_propagate(False)
        self.left_toolbar_visible = True

        self.canvas_frame = tk.Frame(self.main_container)
        self.canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.right_toolbar = tk.Frame(self.main_container, bd=1, relief=tk.RAISED, width=160)
        self.right_toolbar.pack_propagate(False)

        self.status_bar = tk.Label(
            self.root, text="Координаты: (0, 0) | Масштаб: 100%",
            anchor="w", bd=1, relief=tk.SUNKEN, font=("Arial", 9))
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.create_left_toolbar()
        self.create_canvas()
        self.update_right_toolbar()
        self.bind_hotkeys()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.bind_all("<Button-1>", self.global_click_handler, add="+")

        self._highlight_tool(self.current_value)
        self.update_title()

    # ==== Свойства ====
    @property
    def grid_data(self):
        return self.layers[self.active_layer_idx]["data"]

    @grid_data.setter
    def grid_data(self, value):
        self.layers[self.active_layer_idx]["data"] = value

    @property
    def grid_lines(self):
        return self.layers[self.active_layer_idx]["lines"]

    @grid_lines.setter
    def grid_lines(self, value):
        self.layers[self.active_layer_idx]["lines"] = value

    def is_line_tool(self, name):
        data = self.tools.get(name, [])
        return len(data) >= 3 and data[2] == "line"

    def parse_tools(self, tools_input):
        if tools_input is None:
            tools_input = {
                "Основное": {
                    "Стена": ["black", []],
                    "Вода": ["blue", []],
                    "Трава": ["green", []]
                }
            }

        first_val = next(iter(tools_input.values()))
        if isinstance(first_val, dict):
            self.grouped_tools = tools_input
        else:
            self.grouped_tools = {"Инструменты": tools_input}

        self.tools = {}
        for group_name, group_content in self.grouped_tools.items():
            for name, data in group_content.items():
                self.tools[name] = data

    # ==== Левая панель ====
    def create_left_toolbar(self):
        self.tool_buttons = {}
        for widget in self.left_toolbar.winfo_children():
            widget.destroy()

        header_frame = tk.Frame(self.left_toolbar)
        header_frame.pack(fill=tk.X, pady=2)

        self.toggle_toolbar_btn = tk.Button(
            header_frame, text="◄", width=2, relief=tk.FLAT,
            font=("Arial", 9, "bold"), command=self.toggle_left_toolbar)
        self.toggle_toolbar_btn.pack(side=tk.RIGHT, padx=2)

        self.toolbar_title = tk.Label(header_frame, text="Инструменты",
                                      font=("Arial", 10, "bold"))
        self.toolbar_title.pack(side=tk.LEFT, padx=5)

        self.toolbar_content = tk.Frame(self.left_toolbar)
        self.toolbar_content.pack(fill=tk.BOTH, expand=True)

        tool_canvas = tk.Canvas(self.toolbar_content, highlightthickness=0)
        tool_scrollbar = tk.Scrollbar(self.toolbar_content, orient="vertical",
                                      command=tool_canvas.yview)
        scrollable_frame = tk.Frame(tool_canvas)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: tool_canvas.configure(scrollregion=tool_canvas.bbox("all"))
        )
        canvas_window = tool_canvas.create_window((0, 0), window=scrollable_frame,
                                                  anchor="nw")
        tool_canvas.bind('<Configure>',
                         lambda e: tool_canvas.itemconfig(canvas_window, width=e.width))
        tool_canvas.configure(yscrollcommand=tool_scrollbar.set)

        tool_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tool_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_toolbar_wheel(event):
            # 2 «щелчка» за одно событие — комфортнее по скорости
            step = 2
            if event.delta:
                tool_canvas.yview_scroll(
                    int(-step * (event.delta / 120)), "units")
            elif event.num == 4:
                tool_canvas.yview_scroll(-step, "units")
            elif event.num == 5:
                tool_canvas.yview_scroll(step, "units")
            return "break"   # важно: не даём событию всплыть выше и не скроллить 2 раза

        # Колесо над самим холстом (пустое пространство под кнопками)
        tool_canvas.bind("<MouseWheel>", _on_toolbar_wheel)
        tool_canvas.bind("<Button-4>", _on_toolbar_wheel)
        tool_canvas.bind("<Button-5>", _on_toolbar_wheel)

        for group_name, items in self.grouped_tools.items():
            group_frame = tk.Frame(scrollable_frame, bd=1, relief=tk.GROOVE)
            group_frame.pack(fill=tk.X, padx=3, pady=3)

            grp_header = tk.Frame(group_frame, bg="#e0e0e0")
            grp_header.pack(fill=tk.X)

            content_frame = tk.Frame(group_frame)
            content_frame.pack(fill=tk.X, padx=2, pady=2)

            def toggle_group(btn, frame):
                if frame.winfo_viewable():
                    frame.pack_forget()
                    btn.config(text="▶")
                else:
                    frame.pack(fill=tk.X, padx=2, pady=2)
                    btn.config(text="▼")

            toggle_btn = tk.Button(grp_header, text="▼", width=2, relief=tk.FLAT,
                                   bg="#e0e0e0", font=("Arial", 8))
            toggle_btn.config(command=lambda b=toggle_btn, f=content_frame:
                              toggle_group(b, f))
            toggle_btn.pack(side=tk.LEFT)

            group_lbl = tk.Label(grp_header, text=group_name, font=("Arial", 9, "bold"),
                                 bg="#e0e0e0", anchor="w")
            group_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

            for name, data in items.items():
                color = data[0]
                props = data[1]
                btn = tk.Button(
                    content_frame, text=name, bg=color,
                    relief=tk.RAISED, bd=2,
                    fg="white" if color.lower() in
                       ["black", "blue", "red", "green", "#000000", "#1e90ff",
                        "#2c3e50", "#c0392b"] else "black",
                    anchor="w",
                    command=lambda n=name, c=color, p=props: self.select_tool(n, c, p)
                )
                btn.pack(fill=tk.X, padx=2, pady=1)
                self.tool_buttons[name] = btn

        # Прокрутка должна работать и когда курсор над кнопкой / заголовком группы.
        # Привязываем ко ВСЕМ потомкам scrollable_frame рекурсивно, с add="+",
        # чтобы не затереть bindings на кнопках (например, Shift+клик).
        def _bind_wheel_recursive(widget):
            widget.bind("<MouseWheel>", _on_toolbar_wheel, add="+")
            widget.bind("<Button-4>", _on_toolbar_wheel, add="+")
            widget.bind("<Button-5>", _on_toolbar_wheel, add="+")
            for child in widget.winfo_children():
                _bind_wheel_recursive(child)

        _bind_wheel_recursive(scrollable_frame)

        # Гарантированно пересчитываем scrollregion после того, как tkinter
        # разложит все виджеты (иначе прокрутка может «не зацепиться»
        # до первого ручного ресайза окна).
        self.left_toolbar.after_idle(
            lambda: tool_canvas.configure(scrollregion=tool_canvas.bbox("all")))

    def toggle_left_toolbar(self):
        if self.left_toolbar_visible:
            self.toolbar_content.pack_forget()
            self.toolbar_title.pack_forget()
            self.left_toolbar.config(width=32)
            self.toggle_toolbar_btn.config(text="►")
            self.left_toolbar_visible = False
        else:
            self.left_toolbar.config(width=100)
            self.toolbar_title.pack(side=tk.LEFT, padx=5)
            self.toolbar_content.pack(fill=tk.BOTH, expand=True)
            self.toggle_toolbar_btn.config(text="◄")
            self.left_toolbar_visible = True

    def create_menu(self):
        self.menubar = tk.Menu(self.root)

        file_menu = tk.Menu(self.menubar, tearoff=0)
        file_menu.add_command(label="Новый", command=self.new_schematic,
                              accelerator="Ctrl+N")
        file_menu.add_command(label="Открыть", command=self.load_dictionary_file,
                              accelerator="Ctrl+O")
        file_menu.add_command(label="Сохранить", command=self.save_dictionary_file,
                              accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Экспорт", command=self.export_data,
                              accelerator="Ctrl+E")
        self.menubar.add_cascade(label="Файл", menu=file_menu)

        edit_menu = tk.Menu(self.menubar, tearoff=0)
        edit_menu.add_command(label="Отменить", command=self.undo, accelerator="Ctrl+Z")
        edit_menu.add_command(label="Повторить", command=self.redo, accelerator="Ctrl+Y")
        edit_menu.add_separator()
        edit_menu.add_command(label="Вырезать", command=self.cut_selection, accelerator="Ctrl+X")
        edit_menu.add_command(label="Копировать", command=self.copy_selection, accelerator="Ctrl+C")
        edit_menu.add_command(label="Вставить", command=self.paste_selection, accelerator="Ctrl+V")
        edit_menu.add_command(label="Удалить", command=self.delete_selection, accelerator="Del")
        edit_menu.add_separator()
        edit_menu.add_command(label="Выделить всё", command=self.select_all, accelerator="Ctrl+A")
        edit_menu.add_command(label="Снять выделение", command=self.deselect_all, accelerator="Ctrl+D")
        self.menubar.add_cascade(label="Правка", menu=edit_menu)

        # Меню "Слои" — добавление/удаление
        layers_menu = tk.Menu(self.menubar, tearoff=0)
        layers_menu.add_command(label="Добавить слой", command=self.add_layer)
        layers_menu.add_command(
            label="Удалить активный слой",
            command=lambda: self.remove_layer(self.active_layer_idx))
        self.menubar.add_cascade(label="Слои", menu=layers_menu)

        tools_menu = tk.Menu(self.menubar, tearoff=0)
        tools_menu.add_command(label="Сброс камеры", command=self.reset_camera)
        self.menubar.add_cascade(label="Инструменты", menu=tools_menu)

        help_menu = tk.Menu(self.menubar, tearoff=0)
        help_menu.add_command(label="Горячие клавиши", command=self.show_help, accelerator="F1")
        self.menubar.add_cascade(label="Справка", menu=help_menu)


        self.root.config(menu=self.menubar)

    def new_schematic(self):
        """Очищает всё и создаёт новую пустую схематику."""
        if self.is_dirty:
            response = messagebox.askyesnocancel(
                "Новая схематика",
                "Есть несохранённые изменения. Создать новую схематику без сохранения?")
            if not response:  # None (Отмена) или False (Нет) — ничего не делаем
                return

        self.commit_floating()
        self.layers = [{"name": "Слой 1", "visible": True,
            "data": ChunkedLayerData(), "lines": ChunkedLayerLines()}]
        self.active_layer_idx = 0

        # Сбрасываем выделение и плавающие данные
        self.selection = None
        self.sel_start = None
        self.sel_end = None
        self.floating_data = None
        self.floating_lines = None
        self._floating_state_saved = False
        if self.sel_rect_id:
            self.canvas.delete(self.sel_rect_id)
            self.sel_rect_id = None

        # Сбрасываем историю и камеру
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.cell_size = self.default_cell_size

        self.is_dirty = False
        self.update_title()
        self.update_right_toolbar()
        self.redraw_canvas()

    def reset_camera(self):
        self.commit_floating()
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.cell_size = self.default_cell_size
        self._update_status()
        self.request_redraw()

    def export_data(self):
        try:
            processed_data = export(self.layers)
        except Exception as e:
            messagebox.showerror("Ошибка экспорта", f"Не удалось подготовить данные: {e}")
            return False

        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    if isinstance(processed_data, (dict, list)):
                        json.dump(processed_data, f, ensure_ascii=False, indent=4)
                    else:
                        f.write(str(processed_data))
                print(f"Данные успешно экспортированы в {file_path}")
                # ВАЖНО: экспорт НЕ сохраняет проект (.json), поэтому не сбрасываем is_dirty
                return True
            except Exception as e:
                messagebox.showerror("Ошибка экспорта", f"Ошибка записи файла: {e}")
        return False

    def on_closing(self):
        if self.is_dirty:
            response = messagebox.askyesnocancel(
                "Сохранение", "У вас есть несохраненные изменения. Сохранить перед выходом?")
            if response is True:
                if self.save_dictionary_file():
                    self.root.destroy()
            elif response is False:
                self.root.destroy()
        else:
            self.root.destroy()

    def mark_dirty(self):
        self.is_dirty = True
        self.update_title()

    def global_click_handler(self, event):
        if not isinstance(event.widget, tk.Entry):
            self.root.focus_set()

    def validate_digit(self, value):
        if value == "" or value.isdigit():
            return True
        return False

    def get_contrast_color(self, hex_color):
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6:
            return "black"
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            return "white" if luminance < 0.5 else "black"
        except Exception:
            return "black"

    # ==== Undo / Redo ====
    def _snapshot_layers(self):
        """Возвращает глубокую копию слоёв (включая lines) для undo/redo."""
        return [
            {
                "name": l["name"],
                "visible": l["visible"],
                "data": {loc: {"tool": d["tool"], "props": d["props"].copy()}
                         for loc, d in l["data"].items()},
                "lines": {k: {"tool": v["tool"], "props": v["props"].copy()}
                          for k, v in l.get("lines", {}).items()}
            } for l in self.layers
        ]

    def save_state(self):
        state = {
            "active_layer_idx": self.active_layer_idx,
            "layers": self._snapshot_layers()
        }
        self.undo_stack.append(state)
        self.redo_stack.clear()
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)
        self.mark_dirty()

    def _restore_state(self, state):
        self.active_layer_idx = state["active_layer_idx"]
        self.layers = [
            {
                "name": l["name"],
                "visible": l["visible"],
                "data": ChunkedLayerData(
                    {loc: {"tool": d["tool"], "props": d["props"].copy()}
                     for loc, d in l["data"].items()}),
                "lines": ChunkedLayerLines(
                    {k: {"tool": v["tool"], "props": v["props"].copy()}
                     for k, v in l.get("lines", {}).items()})
            } for l in state["layers"]
        ]
        # Сбрасываем плавающее состояние — оно не входит в снапшот
        self.floating_data = None
        self.floating_lines = None
        self._floating_state_saved = False
        self.selection = None
        if self.sel_rect_id:
            self.canvas.delete(self.sel_rect_id)
            self.sel_rect_id = None
        self.update_right_toolbar()
        self.request_redraw()

    def undo(self, event=None):
        if not self.undo_stack:
            return
        # Сбрасываем плавающее (в снапшот оно не входит)
        self.floating_data = None
        self.floating_lines = None
        self._floating_state_saved = False
        current_state = {
            "active_layer_idx": self.active_layer_idx,
            "layers": self._snapshot_layers()
        }
        self.redo_stack.append(current_state)
        self._restore_state(self.undo_stack.pop())
        self.mark_dirty()

    def redo(self, event=None):
        if not self.redo_stack:
            return
        self.floating_data = None
        self.floating_lines = None
        self._floating_state_saved = False
        current_state = {
            "active_layer_idx": self.active_layer_idx,
            "layers": self._snapshot_layers()
        }
        self.undo_stack.append(current_state)
        self._restore_state(self.redo_stack.pop())
        self.mark_dirty()

    # ==== Слои ====
    def add_layer(self):
        self.commit_floating()
        self.save_state()
        new_name = f"Слой {len(self.layers) + 1}"
        self.layers.append({"name": new_name, "visible": True,
            "data": ChunkedLayerData(), "lines": ChunkedLayerLines()})
        self.active_layer_idx = len(self.layers) - 1
        self.update_right_toolbar()
        self.request_redraw()

    def save_dictionary_file(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if file_path:
            save_payload = {
                "layers": [
                    {
                        "name": l["name"], "visible": l["visible"],
                        "cells": {f"{c},{r}": item for (c, r), item in l["data"].items()},
                        "lines": {f"{c1},{r1};{c2},{r2}": v
                                  for ((c1, r1), (c2, r2)), v
                                  in l.get("lines", {}).items()}
                    } for l in self.layers
                ]
            }
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(save_payload, f, ensure_ascii=False, indent=4)
                self.is_dirty = False
                self.update_title()
                return True
            except Exception as e:
                messagebox.showerror("Ошибка сохранения", f"Не удалось сохранить: {e}")
        return False

    def load_dictionary_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data_loaded = json.load(f)

            new_layers = []
            if "layers" in data_loaded:
                for l_data in data_loaded["layers"]:
                    layer_dict = {}
                    for key_str, item in l_data.get("cells", {}).items():
                        c_str, r_str = key_str.split(",")
                        layer_dict[(int(c_str), int(r_str))] = item

                    layer_lines = {}
                    for key_str, item in l_data.get("lines", {}).items():
                        p1, p2 = key_str.split(";")
                        c1, r1 = map(int, p1.split(","))
                        c2, r2 = map(int, p2.split(","))
                        layer_lines[((c1, r1), (c2, r2))] = item

                    new_layers.append({
                        "name": l_data.get("name", "Слой"),
                        "visible": l_data.get("visible", True),
                        "data": ChunkedLayerData(layer_dict),
                        "lines": ChunkedLayerLines(layer_lines)
                    })

            self.save_state()
            self.layers = new_layers
            self.active_layer_idx = 0
            self.update_right_toolbar()
            self.request_redraw()
            self.is_dirty = False
            self.update_title()
        except Exception as e:
            messagebox.showerror("Ошибка загрузки", f"Не удалось загрузить: {e}")

    # ==== Правый тулбар ====
    def update_right_toolbar(self):
        self.right_toolbar.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)

        for widget in self.right_toolbar.winfo_children():
            widget.destroy()

        # --- Слои ---
        layers_header = tk.Frame(self.right_toolbar)
        layers_header.pack(fill=tk.X, padx=5, pady=(5, 2))
        tk.Label(layers_header, text="Слои", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        add_btn = tk.Button(layers_header, text="+ Слой", font=("Arial", 8),
                            command=self.add_layer)
        add_btn.pack(side=tk.RIGHT)

        tk.Frame(self.right_toolbar, height=1, bg="gray").pack(fill=tk.X, padx=5, pady=2)

        layers_frame = tk.Frame(self.right_toolbar)
        layers_frame.pack(fill=tk.X, padx=5, pady=2)

        for idx in range(len(self.layers) - 1, -1, -1):
            layer = self.layers[idx]
            is_active = (idx == self.active_layer_idx)
            row = tk.Frame(layers_frame,
                           bg="#d0e0f0" if is_active else "#f0f0f0",
                           bd=1, relief=tk.RIDGE)
            row.pack(fill=tk.X, pady=1)

            bg_color = "#d0e0f0" if is_active else "#f0f0f0"

            # Колонка 1 (имя) растягивается, остальные — фиксированные.
            # grid детерминирован — кнопки никогда не «выдавливаются» за край.
            row.columnconfigure(1, weight=1)

            vis_icon = "👁" if layer["visible"] else "🙈"
            tk.Button(row, text=vis_icon, width=2, relief=tk.FLAT, bg=bg_color,
                      command=lambda i=idx: self.toggle_layer_visibility(i)
                      ).grid(row=0, column=0, sticky="w")

            name_btn = tk.Button(row, text=layer["name"], anchor="w", relief=tk.FLAT,
                font=("Arial", 9, "bold" if is_active else "normal"),
                bg=bg_color,
                command=lambda i=idx: self.set_active_layer(i))
            name_btn.grid(row=0, column=1, sticky="ew")
            name_btn.bind("<Double-Button-1>", lambda e, i=idx: self.rename_layer(i))

            tk.Button(row, text="▲", width=1, relief=tk.FLAT,
                      command=lambda i=idx: self.move_layer(i, 1)
                      ).grid(row=0, column=2, sticky="e")

            tk.Button(row, text="▼", width=1, relief=tk.FLAT,
                      command=lambda i=idx: self.move_layer(i, -1)
                      ).grid(row=0, column=3, sticky="e")

            if len(self.layers) > 1:
                # "✕" (U+2715) на некоторых шрифтах не рендерится — если кнопка
                # снова «пропадёт», поменяйте символ на "×" (U+00D7) или "X".
                tk.Button(row, text="X", width=2, fg="red", relief=tk.FLAT,
                          bg=bg_color,
                          command=lambda i=idx: self.remove_layer(i)
                          ).grid(row=0, column=4, sticky="e")

        # --- Свойства инструмента ---
        if self.current_props_list:
            tk.Frame(self.right_toolbar, height=2, bg="gray").pack(fill=tk.X, padx=5, pady=10)
            tk.Label(self.right_toolbar, text=f"Свойства: {self.current_value}",
                     font=("Arial", 10, "bold")).pack(anchor="w", padx=5, pady=2)

            props_frame = tk.Frame(self.right_toolbar)
            props_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            vcmd = (self.root.register(self.validate_digit), '%P')
            for prop in self.current_props_list:
                row_frame = tk.Frame(props_frame)
                row_frame.pack(fill=tk.X, pady=3)
                tk.Label(row_frame, text=f"{prop}:", width=12, anchor="w").pack(side=tk.LEFT)

                if prop not in self.tool_prop_values[self.current_value]:
                    self.tool_prop_values[self.current_value][prop] = "0"

                var = tk.StringVar(value=self.tool_prop_values[self.current_value][prop])
                var.trace_add("write",
                              lambda *args, p=prop, v=var: self.update_prop_value(p, v))

                tk.Entry(row_frame, width=8, textvariable=var,
                         validate='key', validatecommand=vcmd).pack(side=tk.RIGHT)

    def set_active_layer(self, idx):
        self.commit_floating()
        self.active_layer_idx = idx
        self.update_right_toolbar()
        self.request_redraw()

    def remove_layer(self, idx):
        if len(self.layers) <= 1:
            messagebox.showwarning("Удаление слоя",
                                   "Нельзя удалить единственный слой.")
            return
        if not (0 <= idx < len(self.layers)):
            return

        layer_name = self.layers[idx]["name"]
        if not messagebox.askyesno("Удаление слоя",
                                   f"Удалить слой '{layer_name}'?"):
            return

        self.commit_floating()
        self.save_state()
        del self.layers[idx]

        # Корректная коррекция активного индекса
        if self.active_layer_idx == idx:
            self.active_layer_idx = min(idx, len(self.layers) - 1)
        elif self.active_layer_idx > idx:
            self.active_layer_idx -= 1

        self.update_right_toolbar()
        self.request_redraw()

    def toggle_layer_visibility(self, idx):
        self.layers[idx]["visible"] = not self.layers[idx]["visible"]
        self.update_right_toolbar()
        self.request_redraw()

    def move_layer(self, idx, direction):
        new_idx = idx + direction
        if 0 <= new_idx < len(self.layers):
            self.commit_floating()
            self.save_state()
            self.layers[idx], self.layers[new_idx] = self.layers[new_idx], self.layers[idx]
            if self.active_layer_idx == idx:
                self.active_layer_idx = new_idx
            elif self.active_layer_idx == new_idx:
                self.active_layer_idx = idx
            self.update_right_toolbar()
            self.request_redraw()
        # (Здесь ранее был ошибочно вставлен дубликат тела update_right_toolbar — удалён.)

    def update_prop_value(self, prop_name, var):
        self.tool_prop_values[self.current_value][prop_name] = var.get()

    def request_redraw(self):
        """Ставит перерисовку в очередь (максимум 1 раз за кадр)."""
        if self._redraw_scheduled:
            return
        self._redraw_scheduled = True
        # after_idle выполнится, как только Tkinter закончит обработку текущих событий
        self.root.after_idle(self._do_redraw)

    def _do_redraw(self):
        self._redraw_scheduled = False
        if hasattr(self, 'canvas') and self.canvas:
            self.redraw_canvas()

    # ==== Холст ====
    def create_canvas(self):
        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.destroy()

        self.canvas = tk.Canvas(self.canvas_frame, width=self.view_width,
                                height=self.view_height, bg="white")
        self.canvas.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<B1-Motion>", self.on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_release)

        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<B3-Motion>", self.erase)

                # СКМ — панорамирование камеры (стандарт в графических редакторах)
        self.canvas.bind("<Button-2>", self.start_pan)
        self.canvas.bind("<B2-Motion>", self.pan_camera)
        self.canvas.bind("<ButtonRelease-2>", self.end_pan)

        # Пипетка переехала с СКМ на Alt+ЛКМ (как в Photoshop / Figma)
        self.canvas.bind("<Alt-Button-1>", self.pick_tool)
        self.canvas.bind("<Motion>", self.track_mouse)

        # Зум под курсором (Windows/macOS)
        self.canvas.bind("<MouseWheel>", self.zoom_wheel)
        # Зум под курсором (Linux)
        self.canvas.bind("<Button-4>", lambda e: self.zoom_at(e.x, e.y, self.zoom_speed))
        self.canvas.bind("<Button-5>", lambda e: self.zoom_at(e.x, e.y, 1 / self.zoom_speed))
        # Shift+ЛКМ drag — прямоугольное выделение (интуитивно, как в большинстве редакторов)
        self.canvas.bind("<Shift-Button-1>", self.start_selection)
        self.canvas.bind("<Shift-B1-Motion>", self.update_selection)
        self.canvas.bind("<Shift-ButtonRelease-1>", self.end_selection)

        # Обновление view_width/height при ресайзе окна (иначе куллинг «съезжает»)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        self.request_redraw()

    def _on_canvas_resize(self, event):
        self.view_width = max(1, event.width)
        self.view_height = max(1, event.height)
        if hasattr(self, "layers"):
            self.request_redraw()

    def bind_hotkeys(self):
        self.root.bind("<Control-c>", self.copy_selection)
        self.root.bind("<Control-C>", self.copy_selection)
        self.root.bind("<Control-x>", self.cut_selection)
        self.root.bind("<Control-X>", self.cut_selection)
        self.root.bind("<Control-v>", self.paste_selection)
        self.root.bind("<Control-V>", self.paste_selection)
        self.root.bind("<Delete>", self.delete_selection)
        self.root.bind("<BackSpace>", self.delete_selection)

        self.root.bind("<Control-z>", self.undo)
        self.root.bind("<Control-Z>", self.undo)
        self.root.bind("<Control-Shift-z>", self.redo)
        self.root.bind("<Control-Shift-Z>", self.redo)

        self.root.bind("<Control-s>", lambda e: self.save_dictionary_file())
        self.root.bind("<Control-S>", lambda e: self.save_dictionary_file())
        self.root.bind("<Control-o>", lambda e: self.load_dictionary_file())
        self.root.bind("<Control-O>", lambda e: self.load_dictionary_file())
        self.root.bind("<Control-e>", lambda e: self.export_data())
        self.root.bind("<Control-E>", lambda e: self.export_data())
        self.root.bind("<Control-n>", lambda e: self.new_schematic())
        self.root.bind("<Control-N>", lambda e: self.new_schematic())

        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)

                # Escape — отмена текущего действия (линия / плавающее / выделение)
        self.root.bind("<Escape>", self.cancel_action)
        # Ctrl+A / Ctrl+D
        self.root.bind("<Control-a>", self.select_all)
        self.root.bind("<Control-A>", self.select_all)
        self.root.bind("<Control-d>", self.deselect_all)
        self.root.bind("<Control-D>", self.deselect_all)
        # Ctrl+Y — Redo (альтернатива Ctrl+Shift+Z)
        self.root.bind("<Control-y>", self.redo)
        self.root.bind("<Control-Y>", self.redo)
        # Справка
        self.root.bind("<F1>", self.show_help)
        # Сброс камеры
        self.root.bind("<Home>", lambda e: self.reset_camera())
        self.root.bind("<Control-0>", lambda e: self.reset_camera())
        self.root.bind("<Control-KP_0>", lambda e: self.reset_camera())
        # Переключение слоёв
        self.root.bind("<bracketleft>", self.prev_layer)
        self.root.bind("<bracketright>", self.next_layer)
        self.root.bind("<Control-Tab>", self.next_layer)
        self.root.bind("<Control-Shift-Tab>", self.prev_layer)
        self.root.bind("<Control-ISO_Left_Tab>", self.prev_layer)
        # Панорамирование пробелом (как в Photoshop/Figma)
        self.root.bind("<KeyPress-space>", self._space_pan_press)
        self.root.bind("<KeyRelease-space>", self._space_pan_release)

    def on_key_press(self, event):
        if isinstance(self.root.focus_get(), tk.Entry):
            return
        key = event.keysym.lower()

        if key in ('w', 'a', 's', 'd'):
            self.pressed_keys.add(key)
            if not self.is_moving:
                self.is_moving = True
                self.animate_camera()
        elif key == 'i':
            self.pick_tool_at(self.mouse_col, self.mouse_row)
        elif key in ('plus', 'equal', 'kp_add'):
            cx = self.mouse_x if self.mouse_x else self.view_width / 2
            cy = self.mouse_y if self.mouse_y else self.view_height / 2
            self.zoom_at(cx, cy, self.zoom_speed)
        elif key in ('minus', 'kp_subtract'):
            cx = self.mouse_x if self.mouse_x else self.view_width / 2
            cy = self.mouse_y if self.mouse_y else self.view_height / 2
            self.zoom_at(cx, cy, 1 / self.zoom_speed)
        elif key == 'bracketleft':
            self.prev_layer()
        elif key == 'bracketright':
            self.next_layer()

    def on_key_release(self, event):
        key = event.keysym.lower()
        if key in ['w', 'a', 's', 'd']:
            if key in self.pressed_keys:
                self.pressed_keys.remove(key)

    def animate_camera(self):
        """Плавная анимация камеры, независимая от FPS."""
        now = time.perf_counter()
        if self._last_anim_time is None:
            self._last_anim_time = now
            self.cam_vx = 0.0
            self.cam_vy = 0.0
        dt = now - self._last_anim_time
        self._last_anim_time = now
        # Ограничиваем dt — иначе после системного лага будет огромный скачок
        dt = min(dt, 0.05)

        # Скорость в пикселях/сек. cam_x и cam_vx уже в пикселях —
        # делить на cell_size НЕ нужно (это и давало 32 px/сек вместо 800).
        # Пиксели/сек ⇒ визуальная скорость одинакова при любом зуме.
        speed = self.CAMERA_SPEED

        target_vx = 0.0
        target_vy = 0.0
        if 'w' in self.pressed_keys:
            target_vy -= speed
        if 's' in self.pressed_keys:
            target_vy += speed
        if 'a' in self.pressed_keys:
            target_vx -= speed
        if 'd' in self.pressed_keys:
            target_vx += speed

        # Frame-rate-independent lerp: эквивалент 0.25/кадр при 60 FPS.
        lerp = 1.0 - (0.75 ** (dt * 60.0))
        self.cam_vx += (target_vx - self.cam_vx) * lerp
        self.cam_vy += (target_vy - self.cam_vy) * lerp

        moving = (abs(self.cam_vx) > 0.01 or abs(self.cam_vy) > 0.01
                  or bool(self.pressed_keys))

        if moving:
            self.cam_x += self.cam_vx * dt
            self.cam_y += self.cam_vy * dt
            self.request_redraw()

            # Планируем следующий кадр с поправкой на время отрисовки:
            # это ключевое исправление. Раньше after(16) добавлялось ПОВЕРХ
            # времени redraw_canvas, что снижало реальный FPS до 20-30.
            elapsed = time.perf_counter() - now
            delay_ms = max(1, int(16 - elapsed * 1000))
            self.root.after(delay_ms, self.animate_camera)
        else:
            self.cam_vx = 0.0
            self.cam_vy = 0.0
            self.is_moving = False
            self._last_anim_time = None

    def zoom_at(self, screen_x, screen_y, factor):
        """Зум с сохранением точки под (screen_x, screen_y)."""
        if factor > 1 and self.cell_size >= self.zoom_in_limit:
            return
        if factor < 1 and self.cell_size <= self.zoom_out_limit:
            return
        # Позиция в мировых координатах (в клетках) под экранной точкой
        col_world = (screen_x + self.cam_x) / self.cell_size
        row_world = (screen_y + self.cam_y) / self.cell_size
        self.cell_size *= factor
        # Возвращаем эту точку под тот же экранный пиксель
        self.cam_x = col_world * self.cell_size - screen_x
        self.cam_y = row_world * self.cell_size - screen_y
        self._update_status()
        self.request_redraw()

    def zoom_wheel(self, event):
        factor = self.zoom_speed if event.delta > 0 else 1 / self.zoom_speed
        self.zoom_at(event.x, event.y, factor)

    def select_tool(self, name, color, props):
        self.commit_floating()
        self.current_value = name
        self.current_color = color
        self.current_props_list = props
        self._highlight_tool(name)
        self.update_right_toolbar()

    def track_mouse(self, event):
        world_x = event.x + self.cam_x
        world_y = event.y + self.cam_y
        self.mouse_col = int(world_x // self.cell_size)
        self.mouse_row = int(world_y // self.cell_size)
        self.mouse_x = event.x
        self.mouse_y = event.y

        self._update_status()

        if self.floating_data is not None or self.floating_lines is not None:
            if not getattr(self, 'is_moving_selection', False):
                self.floating_offset = (self.mouse_col, self.mouse_row)
                self.request_redraw()

    def is_click_on_selection(self, col, row):
        if self.floating_data:
            rel_c = col - self.floating_offset[0]
            rel_r = row - self.floating_offset[1]
            return (rel_c, rel_r) in self.floating_data
        elif self.selection:
            min_c, min_r, max_c, max_r = self.selection
            return min_c <= col <= max_c and min_r <= row <= max_r
        return False

    # ==== Обработчики мыши ====
    def on_left_click(self, event):
        if getattr(self, 'space_pan_active', False):
            self.pan_start_x = event.x
            self.pan_start_y = event.y
            self.pan_cam_start_x = self.cam_x
            self.pan_cam_start_y = self.cam_y
            self._space_panning = True
            return
        if (event.state & 0x0001) or (event.state & 0x0004):
            return
        # ... (остальной код без изменений)

        if self.floating_data or self.floating_lines:
            self.commit_floating()
            return

        world_x = event.x + self.cam_x
        world_y = event.y + self.cam_y
        col = int(world_x // self.cell_size)
        row = int(world_y // self.cell_size)

        if self.is_click_on_selection(col, row):
            self.is_moving_selection = True
            if self.selection and not self.floating_data and not self.floating_lines:
                min_c, min_r, max_c, max_r = self.selection
                has_elements = any((c, r) in self.grid_data
                                   for r in range(min_r, max_r + 1)
                                   for c in range(min_c, max_c + 1))
                has_lines = any(
                    (min_c <= c1 <= max_c and min_r <= r1 <= max_r) and
                    (min_c <= c2 <= max_c and min_r <= r2 <= max_r)
                    for (c1, r1), (c2, r2) in self.grid_lines.keys())

                if has_elements or has_lines:
                    # сохраняем один раз ДО перемещения
                    self.save_state()
                    self._floating_state_saved = True

                self.floating_data = {}
                self.floating_lines = {}

                for r in range(min_r, max_r + 1):
                    for c in range(min_c, max_c + 1):
                        loc = (c, r)
                        if loc in self.grid_data:
                            self.floating_data[(c - min_c, r - min_r)] = {
                                "tool": self.grid_data[loc]["tool"],
                                "props": self.grid_data[loc]["props"].copy()
                            }
                            del self.grid_data[loc]

                lines_to_move = []
                for (start_loc, end_loc), item in self.grid_lines.items():
                    c1, r1 = start_loc
                    c2, r2 = end_loc
                    if ((min_c <= c1 <= max_c and min_r <= r1 <= max_r) and
                            (min_c <= c2 <= max_c and min_r <= r2 <= max_r)):
                        rel_start = (c1 - min_c, r1 - min_r)
                        rel_end = (c2 - min_c, r2 - min_r)
                        self.floating_lines[(rel_start, rel_end)] = {
                            "tool": item["tool"],
                            "props": item["props"].copy()
                        }
                        lines_to_move.append((start_loc, end_loc))
                for k in lines_to_move:
                    del self.grid_lines[k]

                self.floating_offset = (min_c, min_r)
                self.selection = None
                self.request_redraw()

            self.move_start_mouse = (col, row)
            self.initial_offset = self.floating_offset
        else:
            self.is_moving_selection = False
            self.commit_floating()

            if self.is_line_tool(self.current_value):
                self.line_start = (col, row)
            else:
                self.save_state()
                self.paint(event)

    def on_left_drag(self, event):
        if getattr(self, '_space_panning', False):
            dx = event.x - self.pan_start_x
            dy = event.y - self.pan_start_y
            self.cam_x = self.pan_cam_start_x - dx
            self.cam_y = self.pan_cam_start_y - dy
            self.request_redraw()
            return
        if (event.state & 0x0001) or (event.state & 0x0004) or (event.state & 0x0008):
            return

        if getattr(self, 'line_start', None) is not None:
            self.canvas.delete("temp_line")
            c1, r1 = self.line_start
            x1 = c1 * self.cell_size - self.cam_x + self.cell_size / 2
            y1 = r1 * self.cell_size - self.cam_y + self.cell_size / 2

            world_x = event.x + self.cam_x
            world_y = event.y + self.cam_y
            col = int(world_x // self.cell_size)
            row = int(world_y // self.cell_size)

            x2 = col * self.cell_size - self.cam_x + self.cell_size / 2
            y2 = row * self.cell_size - self.cam_y + self.cell_size / 2

            color = self.tools.get(self.current_value, ["black"])[0]
            r_start = 4
            self.canvas.create_oval(x1 - r_start, y1 - r_start, x1 + r_start, y1 + r_start,
                                    fill=color, outline=color, tags="temp_line")
            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=3,
                                    dash=(4, 4), arrow=tk.LAST, tags="temp_line")
            return

        if self.is_moving_selection:
            self.during_move(event)
        else:
            self.paint(event)

    def on_left_release(self, event):
        if getattr(self, '_space_panning', False):
            self._space_panning = False
            return
        # ... (остальной код без изменений)
        if getattr(self, 'line_start', None) is not None:
            self.canvas.delete("temp_line")
            world_x = event.x + self.cam_x
            world_y = event.y + self.cam_y
            col = int(world_x // self.cell_size)
            row = int(world_y // self.cell_size)

            if (col, row) != self.line_start:
                self.save_state()
                props = {p: self.tool_prop_values[self.current_value].get(p, "0")
                         for p in self.current_props_list}
                start, end = self.line_start, (col, row)
                self.grid_lines[(start, end)] = {"tool": self.current_value, "props": props}
                self.mark_dirty()
                self.request_redraw()
            self.line_start = None

        self.is_moving_selection = False
        self.move_start_mouse = None

    def erase(self, event):
        world_x = event.x + self.cam_x
        world_y = event.y + self.cam_y
        col = int(world_x // self.cell_size)
        row = int(world_y // self.cell_size)
        location = (col, row)
        modified = False

        if location in self.grid_data:
            del self.grid_data[location]
            modified = True

        lines_to_delete = [k for k in self.grid_lines
                           if k[0] == location or k[1] == location]
        for k in lines_to_delete:
            del self.grid_lines[k]
            modified = True

        if self.floating_data:
            rel_c = col - self.floating_offset[0]
            rel_r = row - self.floating_offset[1]
            if (rel_c, rel_r) in self.floating_data:
                del self.floating_data[(rel_c, rel_r)]
                modified = True

        if modified:
            self.mark_dirty()
            self.request_redraw()

    def paint(self, event):
        world_x = event.x + self.cam_x
        world_y = event.y + self.cam_y
        col = int(world_x // self.cell_size)
        row = int(world_y // self.cell_size)

        location = (col, row)
        props_snapshot = {p: self.tool_prop_values[self.current_value].get(p, "0")
                          for p in self.current_props_list}
        new_item = {"tool": self.current_value, "props": props_snapshot}
        if self.grid_data.get(location) != new_item:
            self.grid_data[location] = new_item
            self.mark_dirty()
            self.request_redraw()

    def on_right_click(self, event):
        world_x = event.x + self.cam_x
        world_y = event.y + self.cam_y
        col = int(world_x // self.cell_size)
        row = int(world_y // self.cell_size)
        location = (col, row)

        # Сохраняем состояние, только если реально есть что стирать
        has_content = location in self.grid_data
        has_lines = any(location == k[0] or location == k[1] for k in self.grid_lines)
        has_floating = False
        if self.floating_data:
            rel_c = col - self.floating_offset[0]
            rel_r = row - self.floating_offset[1]
            has_floating = (rel_c, rel_r) in self.floating_data

        if has_content or has_lines or has_floating:
            self.save_state()
        self.erase(event)
        

    def start_pan(self, event):
        """Начало панорамирования камеры средней кнопкой мыши."""
        self.commit_floating()
        self.is_panning = True
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self.pan_cam_start_x = self.cam_x
        self.pan_cam_start_y = self.cam_y
        self.canvas.config(cursor="fleur")

    def pan_camera(self, event):
        """Двигает камеру вслед за мышью при зажатой СКМ."""
        if not self.is_panning:
            return
        dx = event.x - self.pan_start_x
        dy = event.y - self.pan_start_y
        # Тянем сцену за собой: контент под курсором не «уплывает»
        self.cam_x = self.pan_cam_start_x - dx
        self.cam_y = self.pan_cam_start_y - dy
        # Обновим координаты в статус-баре (курсор «стоит» на новых клетках)
        self.mouse_col = int((event.x + self.cam_x) // self.cell_size)
        self.mouse_row = int((event.y + self.cam_y) // self.cell_size)
        self.status_bar.config(
            text=f"Координаты: ({self.mouse_col}, {self.mouse_row})")
        self.request_redraw()

    def end_pan(self, event):
        self.is_panning = False
        self.canvas.config(cursor="")

    def pick_tool_at(self, col, row):
        """Выбирает инструмент по координатам клетки (без привязки к event)."""
        location = (col, row)
        if location in self.grid_data:
            item = self.grid_data[location]
            tool_name = item["tool"]
            if tool_name in self.tools:
                color = self.tools[tool_name][0]
                props = self.tools[tool_name][1]
                self.tool_prop_values[tool_name] = item["props"].copy()
                self.select_tool(tool_name, color, props)

    def pick_tool(self, event):
        """Пипетка: Alt+ЛКМ по клетке."""
        world_x = event.x + self.cam_x
        world_y = event.y + self.cam_y
        col = int(world_x // self.cell_size)
        row = int(world_y // self.cell_size)
        self.pick_tool_at(col, row)

    # ==== Справка, заголовок, статус ====

    def update_title(self):
        base = "Бесконечная сетка с инструментами и экспортом"
        self.root.title(base + (" *" if self.is_dirty else ""))

    def _update_status(self):
        scale_pct = round(self.cell_size / self.default_cell_size * 100)
        self.status_bar.config(
            text=f"Координаты: ({self.mouse_col}, {self.mouse_row}) | Масштаб: {scale_pct}%")

    def _highlight_tool(self, name):
        for n, b in getattr(self, 'tool_buttons', {}).items():
            try:
                b.config(relief=tk.SUNKEN if n == name else tk.RAISED)
            except tk.TclError:
                pass

    def show_help(self, event=None):
        help_text = (
            "ГОРЯЧИЕ КЛАВИШИ\n"
            "─────────────────────────────\n"
            "ФАЙЛ\n"
            "  Ctrl+N            — Новая схематика\n"
            "  Ctrl+O            — Открыть\n"
            "  Ctrl+S            — Сохранить\n"
            "  Ctrl+E            — Экспорт\n\n"
            "ПРАВКА\n"
            "  Ctrl+Z            — Отменить\n"
            "  Ctrl+Y / Ctrl+Shift+Z — Повторить\n"
            "  Ctrl+C / Ctrl+X / Ctrl+V — Копировать / Вырезать / Вставить\n"
            "  Ctrl+A            — Выделить всё\n"
            "  Ctrl+D / Esc      — Снять выделение\n"
            "  Delete / Backspace — Удалить выделенное\n\n"
            "КАМЕРА\n"
            "  Колёсико мыши     — Зум (в точку курсора)\n"
            "  + / -             — Зум\n"
            "  СКМ + drag        — Панорамирование\n"
            "  Пробел + drag     — Панорамирование\n"
            "  WASD              — Движение камеры\n"
            "  Home / Ctrl+0     — Сброс камеры\n\n"
            "ИНСТРУМЕНТЫ\n"
            "  ЛКМ               — Рисовать\n"
            "  ПКМ               — Стереть\n"
            "  Shift+ЛКМ (drag)  — Прямоугольное выделение\n"
            "  Ctrl+ЛКМ (drag)   — Прямоугольное выделение\n"
            "  Alt+ЛКМ / I       — Пипетка (взять инструмент с клетки)\n"
            "  Клик по выделению — Перетащить\n"
            "  Esc               — Отменить линию / перенос / выделение\n\n"
            "СЛОИ\n"
            "  [ / ]             — Предыдущий / Следующий слой\n"
            "  Ctrl+Tab / Ctrl+Shift+Tab — То же\n"
            "  Двойной клик по имени — Переименовать слой\n"
            "  Меню «Слои»       — Добавить / Удалить\n\n"
            "  F1                — Эта справка"
        )
        win = tk.Toplevel(self.root)
        win.title("Справка — горячие клавиши")
        win.transient(self.root)
        txt = tk.Text(win, wrap=tk.WORD, width=72, height=32,
                      font=("Courier New", 9), padx=10, pady=10)
        txt.pack(fill=tk.BOTH, expand=True)
        txt.insert("1.0", help_text)
        txt.config(state=tk.DISABLED)
        tk.Button(win, text="Закрыть", command=win.destroy).pack(pady=6)

    # ==== Выделение: всё/снять/отмена ====

    def select_all(self, event=None):
        if not self.grid_data and not self.grid_lines:
            return
        cs, rs = [], []
        for (c, r) in self.grid_data:
            cs.append(c)
            rs.append(r)
        for (c1, r1), (c2, r2) in self.grid_lines:
            cs.extend([c1, c2])
            rs.extend([r1, r2])
        if cs:
            self.selection = (min(cs), min(rs), max(cs), max(rs))
            self.update_selection_rect_visual()

    def deselect_all(self, event=None):
        self.selection = None
        if self.sel_rect_id:
            self.canvas.delete(self.sel_rect_id)
            self.sel_rect_id = None

    def end_selection(self, event=None):
        self.sel_start = None
        self.sel_end = None

    def cancel_action(self, event=None):
        # 1) Отмена незавершённой линии
        if getattr(self, 'line_start', None) is not None:
            self.line_start = None
            self.canvas.delete("temp_line")
            return
        # 2) Отмена плавающего (перемещение / вырезание / вставка)
        if self.floating_data or self.floating_lines:
            if self._floating_state_saved:
                self.undo()
            else:
                self.floating_data = None
                self.floating_lines = None
                self._floating_state_saved = False
                self.selection = None
                if self.sel_rect_id:
                    self.canvas.delete(self.sel_rect_id)
                    self.sel_rect_id = None
                self.request_redraw()
            return
        # 3) Снятие выделения
        if self.selection:
            self.deselect_all()

    # ==== Слои ====

    def next_layer(self, event=None):
        if len(self.layers) < 2:
            return
        self.commit_floating()
        self.active_layer_idx = (self.active_layer_idx + 1) % len(self.layers)
        self.update_right_toolbar()
        self.request_redraw()

    def prev_layer(self, event=None):
        if len(self.layers) < 2:
            return
        self.commit_floating()
        self.active_layer_idx = (self.active_layer_idx - 1) % len(self.layers)
        self.update_right_toolbar()
        self.request_redraw()

    def rename_layer(self, idx):
        from tkinter import simpledialog
        new_name = simpledialog.askstring(
            "Переименование слоя", "Новое имя слоя:",
            initialvalue=self.layers[idx]["name"], parent=self.root)
        if new_name and new_name != self.layers[idx]["name"]:
            self.save_state()
            self.layers[idx]["name"] = new_name
            self.update_right_toolbar()
            self.request_redraw()

    # ==== Панорамирование пробелом ====

    def _space_pan_press(self, event):
        if isinstance(self.root.focus_get(), tk.Entry):
            return
        self.space_pan_active = True
        self.canvas.config(cursor="fleur")

    def _space_pan_release(self, event):
        self.space_pan_active = False
        self._space_panning = False
        if not self.is_panning:
            self.canvas.config(cursor="")

    # ==== Выделение ====
    def start_selection(self, event):
        self.commit_floating()
        world_x = event.x + self.cam_x
        world_y = event.y + self.cam_y
        col = int(world_x // self.cell_size)
        row = int(world_y // self.cell_size)
        self.sel_start = (col, row)
        self.sel_end = (col, row)
        self.selection = (col, row, col, row)  # фиксируем сразу, чтобы рамка была видна
        self.update_selection_rect_visual()

    def update_selection(self, event):
        world_x = event.x + self.cam_x
        world_y = event.y + self.cam_y
        col = int(world_x // self.cell_size)
        row = int(world_y // self.cell_size)
        self.sel_end = (col, row)
        c1, r1 = self.sel_start
        c2, r2 = self.sel_end
        self.selection = (min(c1, c2), min(r1, r2), max(c1, c2), max(r1, r2))
        self.update_selection_rect_visual()

    def update_selection_rect_visual(self):
        min_c = min_r = max_c = max_r = None

        if self.floating_data:
            max_rel_c = max(c for c, r in self.floating_data.keys())
            max_rel_r = max(r for c, r in self.floating_data.keys())
            min_c, min_r = self.floating_offset
            max_c = min_c + max_rel_c
            max_r = min_r + max_rel_r
        elif self.selection:
            min_c, min_r, max_c, max_r = self.selection

        if min_c is not None:
            x1 = min_c * self.cell_size - self.cam_x
            y1 = min_r * self.cell_size - self.cam_y
            x2 = (max_c + 1) * self.cell_size - self.cam_x
            y2 = (max_r + 1) * self.cell_size - self.cam_y

            if self.sel_rect_id:
                self.canvas.delete(self.sel_rect_id)
            self.sel_rect_id = self.canvas.create_rectangle(
                x1, y1, x2, y2, outline="#2980b9", width=2, dash=(4, 4),
                tag="selection_rect")
        else:
            if self.sel_rect_id:
                self.canvas.delete(self.sel_rect_id)
                self.sel_rect_id = None

    def redraw_canvas(self):
        self.canvas.delete("all")

        start_col = int(self.cam_x // self.cell_size)
        end_col = int((self.cam_x + self.view_width) // self.cell_size) + 1
        start_row = int(self.cam_y // self.cell_size)
        end_row = int((self.cam_y + self.view_height) // self.cell_size) + 1

        draw_outline = self.cell_size >= self.min_cell_size_grid
        outline_color = "gray" if draw_outline else ""

        cell_font_size = int(self.cell_size * 0.3)
        draw_text = self.cell_size > self.min_cell_size_text
        
        draw_lines = self.cell_size >= self.min_cell_size_arrow

        # Слои снизу вверх: верхний слой рисуется последним и естественно
        # перекрывает нижний. Это одновременно исправляет порядок линий
        # (раньше reversed + already_drew защищал только клетки).
        for layer in self.layers:
            if not layer["visible"]:
                continue

            data = layer["data"]
            if isinstance(data, ChunkedLayerData):
                cell_iter = data.cells_in_view(
                    start_col, end_col - 1, start_row, end_row - 1)
            else:
                cell_iter = iter(data.items())

            for loc, item in cell_iter:
                c, r = loc
                if start_col <= c < end_col and start_row <= r < end_row:
                    x1 = c * self.cell_size - self.cam_x
                    y1 = r * self.cell_size - self.cam_y
                    tool_name = item["tool"]
                    color = self.tools.get(tool_name, ["white", []])[0]
                    self.canvas.create_rectangle(
                        x1, y1, x1 + self.cell_size, y1 + self.cell_size,
                        fill=color)
                    if draw_text:
                        self.canvas.create_text(
                            x1 + self.cell_size / 2, y1 + self.cell_size / 2,
                            text=tool_name, fill=self.get_contrast_color(color),
                            font=("Arial", cell_font_size, "bold"))

            if draw_lines:
                lines = layer.get("lines", {})
                if isinstance(lines, ChunkedLayerLines):
                    line_iter = lines.lines_in_view(
                        start_col, end_col - 1, start_row, end_row - 1)
                else:
                    line_iter = iter(lines.items())

                for (start_loc, end_loc), item in line_iter:
                    c1, r1 = start_loc
                    c2, r2 = end_loc
                    x1 = c1 * self.cell_size - self.cam_x + self.cell_size / 2
                    y1 = r1 * self.cell_size - self.cam_y + self.cell_size / 2
                    x2 = c2 * self.cell_size - self.cam_x + self.cell_size / 2
                    y2 = r2 * self.cell_size - self.cam_y + self.cell_size / 2

                    tool_name = item["tool"]
                    color = self.tools.get(tool_name, ["black"])[0]
                    line_width = max(2, int(self.cell_size / 8))
                    r_start = line_width * 1.5
                    self.canvas.create_oval(
                        x1 - r_start, y1 - r_start, x1 + r_start, y1 + r_start,
                        fill=color, outline=color)
                    arrow_size = max(8, int(self.cell_size / 4))
                    arrow_shape = (arrow_size, arrow_size + 2,
                                   max(3, arrow_size // 3))
                    self.canvas.create_line(
                        x1, y1, x2, y2, fill=color, width=line_width,
                        arrow=tk.LAST, arrowshape=arrow_shape)

        # Маркер (0, 0)
        if start_col <= 0 < end_col and start_row <= 0 < end_row:
            ox1 = -self.cam_x
            oy1 = -self.cam_y
            ox2 = ox1 + self.cell_size
            oy2 = oy1 + self.cell_size
            self.canvas.create_rectangle(ox1, oy1, ox2, oy2,
                                         outline="#e74c3c", width=3, dash=(3, 3))
            if self.cell_size >= self.min_cell_size_marker:
                self.canvas.create_text(ox1 + 5, oy1 + 5, text="(0,0)",
                                        anchor="nw", fill="#e74c3c",
                                        font=("Arial", 8, "bold"))

        # Плавающие клетки
        if self.floating_data:
            for (rel_c, rel_r), item in self.floating_data.items():
                abs_c = self.floating_offset[0] + rel_c
                abs_r = self.floating_offset[1] + rel_r
                if start_col <= abs_c < end_col and start_row <= abs_r < end_row:
                    x1 = abs_c * self.cell_size - self.cam_x
                    y1 = abs_r * self.cell_size - self.cam_y
                    tool_name = item["tool"]
                    color = self.tools.get(tool_name, ["white", []])[0]
                    self.canvas.create_rectangle(
                        x1, y1, x1 + self.cell_size, y1 + self.cell_size,
                        fill=color, outline=outline_color)
                    if draw_text:
                        text_color = self.get_contrast_color(color)
                        font_size = max(8, int(self.cell_size / 5))
                        self.canvas.create_text(
                            x1 + self.cell_size / 2, y1 + self.cell_size / 2,
                            text=tool_name, fill=text_color,
                            font=("Arial", font_size, "bold"))

        # Плавающие линии
        if self.floating_lines:
            for (rel_start, rel_end), item in self.floating_lines.items():
                abs_start = (self.floating_offset[0] + rel_start[0],
                             self.floating_offset[1] + rel_start[1])
                abs_end = (self.floating_offset[0] + rel_end[0],
                           self.floating_offset[1] + rel_end[1])
                c1, r1 = abs_start
                c2, r2 = abs_end
                if ((start_col <= c1 < end_col and start_row <= r1 < end_row) or
                        (start_col <= c2 < end_col and start_row <= r2 < end_row)):
                    x1 = c1 * self.cell_size - self.cam_x + self.cell_size / 2
                    y1 = r1 * self.cell_size - self.cam_y + self.cell_size / 2
                    x2 = c2 * self.cell_size - self.cam_x + self.cell_size / 2
                    y2 = r2 * self.cell_size - self.cam_y + self.cell_size / 2

                    tool_name = item["tool"]
                    color = self.tools.get(tool_name, ["black"])[0]
                    line_width = max(2, int(self.cell_size / 8))
                    r_start = line_width * 1.5
                    self.canvas.create_oval(
                        x1 - r_start, y1 - r_start, x1 + r_start, y1 + r_start,
                        fill=color, outline=color)
                    arrow_size = max(8, int(self.cell_size / 4))
                    arrow_shape = (arrow_size, arrow_size + 2,
                                   max(3, arrow_size // 3))
                    self.canvas.create_line(
                        x1, y1, x2, y2, fill=color, width=line_width,
                        arrow=tk.LAST, arrowshape=arrow_shape)
                    if draw_text:
                        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                        self.canvas.create_text(
                            mx, my, text=tool_name, fill=color,
                            font=("Arial", max(8, int(self.cell_size / 6)), "bold"))

        self.update_selection_rect_visual()
    # ==== Буфер обмена ====
    def copy_selection(self, event=None):
        if self.floating_data or self.floating_lines:
            self.clipboard = {
                "cells": {k: {"tool": v["tool"], "props": v["props"].copy()}
                          for k, v in (self.floating_data or {}).items()},
                "lines": {k: {"tool": v["tool"], "props": v["props"].copy()}
                          for k, v in (self.floating_lines or {}).items()}
            }
        elif self.selection:
            min_c, min_r, max_c, max_r = self.selection
            cells_clip = {}
            for r in range(min_r, max_r + 1):
                for c in range(min_c, max_c + 1):
                    loc = (c, r)
                    if loc in self.grid_data:
                        cells_clip[(c - min_c, r - min_r)] = {
                            "tool": self.grid_data[loc]["tool"],
                            "props": self.grid_data[loc]["props"].copy()
                        }
            lines_clip = {}
            for (start_loc, end_loc), item in self.grid_lines.items():
                c1, r1 = start_loc
                c2, r2 = end_loc
                if ((min_c <= c1 <= max_c and min_r <= r1 <= max_r) and
                        (min_c <= c2 <= max_c and min_r <= r2 <= max_r)):
                    rel_start = (c1 - min_c, r1 - min_r)
                    rel_end = (c2 - min_c, r2 - min_r)
                    lines_clip[(rel_start, rel_end)] = {
                        "tool": item["tool"],
                        "props": item["props"].copy()
                    }
            self.clipboard = {"cells": cells_clip, "lines": lines_clip}

    def cut_selection(self, event=None):
        if not self.selection and not self.floating_data and not self.floating_lines:
            return
        self.copy_selection()
        if self.selection:
            min_c, min_r, max_c, max_r = self.selection
            has_elements = any((c, r) in self.grid_data
                               for r in range(min_r, max_r + 1)
                               for c in range(min_c, max_c + 1))
            has_lines = any(
                (min_c <= c1 <= max_c and min_r <= r1 <= max_r) and
                (min_c <= c2 <= max_c and min_r <= r2 <= max_r)
                for (c1, r1), (c2, r2) in self.grid_lines.keys())

            if has_elements or has_lines:
                self.save_state()
                self._floating_state_saved = True
                self.floating_data = {}
                self.floating_lines = {}

                for r in range(min_r, max_r + 1):
                    for c in range(min_c, max_c + 1):
                        loc = (c, r)
                        if loc in self.grid_data:
                            self.floating_data[(c - min_c, r - min_r)] = {
                                "tool": self.grid_data[loc]["tool"],
                                "props": self.grid_data[loc]["props"].copy()
                            }
                            del self.grid_data[loc]

                lines_to_cut = []
                for (start_loc, end_loc), item in self.grid_lines.items():
                    c1, r1 = start_loc
                    c2, r2 = end_loc
                    if ((min_c <= c1 <= max_c and min_r <= r1 <= max_r) and
                            (min_c <= c2 <= max_c and min_r <= r2 <= max_r)):
                        rel_start = (c1 - min_c, r1 - min_r)
                        rel_end = (c2 - min_c, r2 - min_r)
                        self.floating_lines[(rel_start, rel_end)] = {
                            "tool": item["tool"],
                            "props": item["props"].copy()
                        }
                        lines_to_cut.append((start_loc, end_loc))
                for k in lines_to_cut:
                    del self.grid_lines[k]

                self.floating_offset = (min_c, min_r)
                self.selection = None
                self.mark_dirty()
                self.request_redraw()

    def paste_selection(self, event=None):
        if not self.clipboard:
            return
        self.commit_floating()
        # Плавающее состояние не сохраняем — commit_floating сохранит его при фиксации
        self.floating_data = {k: {"tool": v["tool"], "props": v["props"].copy()}
                              for k, v in self.clipboard.get("cells", {}).items()}
        self.floating_lines = {k: {"tool": v["tool"], "props": v["props"].copy()}
                               for k, v in self.clipboard.get("lines", {}).items()}
        self.floating_offset = (self.mouse_col, self.mouse_row)
        self._floating_state_saved = False
        self.mark_dirty()
        self.request_redraw()

    def delete_selection(self, event=None):
        if self.floating_data or self.floating_lines:
            self.save_state()
            self.floating_data = None
            self.floating_lines = None
            self._floating_state_saved = False
            self.selection = None
            if self.sel_rect_id:
                self.canvas.delete(self.sel_rect_id)
                self.sel_rect_id = None
            self.mark_dirty()
            self.request_redraw()
        elif self.selection:
            min_c, min_r, max_c, max_r = self.selection
            has_elements = any((c, r) in self.grid_data
                               for r in range(min_r, max_r + 1)
                               for c in range(min_c, max_c + 1))
            has_lines = any(
                (min_c <= c1 <= max_c and min_r <= r1 <= max_r) and
                (min_c <= c2 <= max_c and min_r <= r2 <= max_r)
                for (c1, r1), (c2, r2) in self.grid_lines.keys())

            if has_elements or has_lines:
                self.save_state()
                for r in range(min_r, max_r + 1):
                    for c in range(min_c, max_c + 1):
                        loc = (c, r)
                        if loc in self.grid_data:
                            del self.grid_data[loc]

                lines_to_delete = []
                for (start_loc, end_loc) in self.grid_lines.keys():
                    c1, r1 = start_loc
                    c2, r2 = end_loc
                    if ((min_c <= c1 <= max_c and min_r <= r1 <= max_r) and
                            (min_c <= c2 <= max_c and min_r <= r2 <= max_r)):
                        lines_to_delete.append((start_loc, end_loc))
                for k in lines_to_delete:
                    del self.grid_lines[k]

                self.selection = None
                if self.sel_rect_id:
                    self.canvas.delete(self.sel_rect_id)
                    self.sel_rect_id = None
                self.mark_dirty()
                self.request_redraw()

    def commit_floating(self):
        has_changed = False
        if self.floating_data:
            if not self._floating_state_saved:
                self.save_state()
            for (rel_c, rel_r), item in self.floating_data.items():
                abs_c = self.floating_offset[0] + rel_c
                abs_r = self.floating_offset[1] + rel_r
                self.grid_data[(abs_c, abs_r)] = {
                    "tool": item["tool"],
                    "props": item["props"].copy()
                }
            self.floating_data = None
            has_changed = True

        if self.floating_lines:
            if not has_changed and not self._floating_state_saved:
                self.save_state()
            for (rel_start, rel_end), item in self.floating_lines.items():
                abs_start = (self.floating_offset[0] + rel_start[0],
                             self.floating_offset[1] + rel_start[1])
                abs_end = (self.floating_offset[0] + rel_end[0],
                           self.floating_offset[1] + rel_end[1])
                self.grid_lines[(abs_start, abs_end)] = {
                    "tool": item["tool"],
                    "props": item["props"].copy()
                }
            self.floating_lines = None
            has_changed = True

        if has_changed:
            self._floating_state_saved = False
            self.mark_dirty()
            # Сбрасываем выделение только когда реально что-то зафиксировали,
            # иначе zoom_in/reset_camera будут внезапно снимать выделение.
            self.selection = None
            if self.sel_rect_id:
                self.canvas.delete(self.sel_rect_id)
                self.sel_rect_id = None

        self.request_redraw()

    def during_move(self, event):
        if self.is_moving_selection and (self.floating_data is not None
                                         or self.floating_lines is not None):
            world_x = event.x + self.cam_x
            world_y = event.y + self.cam_y
            col = int(world_x // self.cell_size)
            row = int(world_y // self.cell_size)

            dx = col - self.move_start_mouse[0]
            dy = row - self.move_start_mouse[1]

            self.floating_offset = (self.initial_offset[0] + dx,
                                    self.initial_offset[1] + dy)
            self.request_redraw()


from auto_arras.config import EDITOR_TOOLS, EDITOR_TOOL_TO_ID, EDITOR_TOOL_TO_GROUP


def export(exported_layers):
    ret = []
    for layer in exported_layers:
        lines = layer['lines']
        layer = layer['data']
        for pos, data in layer.items():
            tool = data['tool']
            props = data['props']
            group = EDITOR_TOOL_TO_GROUP[tool]
            match group:
                case "WALLS":
                    if tool == "PRWALL":
                        ret.append(f"wall {pos[0]} {pos[1]}")
                    else:
                        if props["CHANGE TYPE"] == '1':
                            ret.append(f"wall_type {pos[0]} {pos[1]} "
                                       f"{EDITOR_TOOL_TO_ID[tool]}")
                        elif props["CHANGE TYPE"] == '2':
                            ret.append(f"wall {pos[0]} {pos[1]}")
                        else:
                            ret.append(f"type_wall {pos[0]} {pos[1]} "
                                       f"{EDITOR_TOOL_TO_ID[tool]}")
                case "OTHER":
                    if tool == "POLY":
                        if props["CHANGE TYPE"] == '0':
                            ret.append(f"polygon {pos[0]} {pos[1]} "
                                       f"{props['CLASS']} {props['SIZE']} {props['TIER']}")
                        else:
                            ret.append(f"polygon_type {pos[0]} {pos[1]} "
                                       f"{props['CLASS']} {props['SIZE']} {props['TIER']}")
            if "TEAM" in props and props["TEAM"] == '1':
                ret.append("team")
        for poses, data in lines.items():
            tool = data['tool']
            ret.append(f"joint {poses[0][0]} {poses[0][1]} "
                       f"{poses[1][0]} {poses[1][1]} {EDITOR_TOOL_TO_ID[tool]}")
    return '\n'.join(ret)


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1200x700")

    # Глубокая копия — иначе модифицируется импортированный EDITOR_TOOLS,
    # и повторный запуск/использование config ломается.
    my_custom_tools = copy.deepcopy(EDITOR_TOOLS)

    for group, tools in my_custom_tools.items():
        for name, tool in tools.items():
            col = tool[0]
            props = copy.deepcopy(tool[1:]) if len(tool) > 1 else []
            if len(props) == 0:
                props = [[]]
            if group in ["WALLS", "OTHER"]:
                # extend не создаёт дубликатов ключей, но при повторном
                # вызове их бы не было — на всякий случай чистим дубликаты
                for extra in ("CHANGE TYPE", "TEAM"):
                    if extra not in props[0]:
                        props[0].append(extra)
            r, g, b, a = col
            tools[name] = [f"#{b:02x}{g:02x}{r:02x}", *props]

    app = GridApp(
        root,
        tools=my_custom_tools,
    )

    # Окно можно свободно тянуть за края/угол.
    root.resizable(True, True)
    # Минимальный размер, при котором обе панели + холст остаются вменяемыми.
    root.minsize(700, 400)
    root.mainloop()