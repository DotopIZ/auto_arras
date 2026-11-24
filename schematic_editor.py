import tkinter as tk
from tkinter import filedialog, messagebox
import json
import time
import copy

from auto_arras.config import (
    EDITOR_TOOLS, EDITOR_TOOL_TO_ID, EDITOR_TOOL_TO_GROUP, MAX_WALL_SIZE,
)


# ============================================================
#  Chunked-коллекции
# ============================================================

class _ChunkIndexBase(dict):
    """Базовый словарь с пространственным индексом по чанкам."""
    CHUNK_SIZE = 32

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._chunks = {}
        for key in self.keys():
            self._chunk_add(key)

    # --- должно быть переопределено в наследниках ---
    def _chunks_of(self, key):
        raise NotImplementedError

    # --- низкоуровневые операции с индексом ---
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

    # --- обход ключей, попадающих в чанки диапазона ---
    def _iter_chunk_keys(self, min_col, max_col, min_row, max_row):
        cs = self.CHUNK_SIZE
        for cx in range(min_col // cs, max_col // cs + 1):
            for cy in range(min_row // cs, max_row // cs + 1):
                for key in self._chunks.get((cx, cy), ()):
                    yield key


class ChunkedLayerData(_ChunkIndexBase):
    """Клетки (col, row) → item."""
    def _chunks_of(self, key):
        cs = self.CHUNK_SIZE
        return ((key[0] // cs, key[1] // cs),)

    def cells_in_view(self, min_col, max_col, min_row, max_row):
        for key in self._iter_chunk_keys(min_col, max_col, min_row, max_row):
            yield key, self[key]


class ChunkedLayerLines(_ChunkIndexBase):
    """Линии ((c1,r1),(c2,r2)) → item."""
    def _chunks_of(self, key):
        (c1, r1), (c2, r2) = key
        min_c, max_c = (c1, c2) if c1 <= c2 else (c2, c1)
        min_r, max_r = (r1, r2) if r1 <= r2 else (r2, r1)
        cs = self.CHUNK_SIZE
        return ((cx, cy)
                for cx in range(min_c // cs, max_c // cs + 1)
                for cy in range(min_r // cs, max_r // cs + 1))

    def lines_in_view(self, min_col, max_col, min_row, max_row):
        seen = set()
        for key in self._iter_chunk_keys(min_col, max_col, min_row, max_row):
            if key in seen:
                continue
            seen.add(key)
            yield key, self[key]


# ============================================================
#  Основное приложение
# ============================================================

class GridApp:
    CAMERA_SPEED = 1500.0
    # Запас куллинга по осям: покрывает любую клетку с SIZE ≤ MAX_WALL_SIZE
    CULL_MARGIN = MAX_WALL_SIZE

    def __init__(self, root, tools=None):
        self.root = root
        self.root.title("Бесконечная сетка с инструментами и экспортом")

        # --- параметры отображения ---
        self.default_cell_size = 25
        self.cell_size = self.default_cell_size
        self.min_cell_size_grid = 15
        self.min_cell_size_text = 35
        self.min_cell_size_marker = 1
        self.min_cell_size_arrow = 15

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

        # --- состояние мыши/камеры ---
        self.is_moving_selection = False
        self.is_panning = False
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.pan_cam_start_x = 0.0
        self.pan_cam_start_y = 0.0
        self.space_pan_active = False
        self._space_panning = False
        self.mouse_x = self.view_width / 2
        self.mouse_y = self.view_height / 2
        self.tool_buttons = {}

        # --- слои и состояние ---
        self.layers = [self._create_new_layer("Слой 1")]
        self.active_layer_idx = 0
        self.soloed_layer = None
        self.line_start = None

        self.undo_stack = []
        self.redo_stack = []

        self.floating_data = None
        self.floating_lines = None
        self.floating_offset = (0, 0)
        self._floating_state_saved = False
        self.clipboard = None

        self.selection = None
        self.sel_start = None
        self.sel_end = None
        self.sel_rect_id = None

        self.mouse_col = 0
        self.mouse_row = 0

        # --- инструменты ---
        self.parse_tools(tools)
        self.tool_prop_values = {
            name: {p: "0" for p in data[1]}
            for name, data in self.tools.items()
        }
        if not self.tools:
            raise ValueError("Список инструментов пуст")
        first_name = next(iter(self.tools))
        self.current_value = first_name
        self.current_color = self.tools[first_name][0]
        self.current_props_list = self.tools[first_name][1]

        # --- UI ---
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

    # ============================================================
    #  Свойства и утилиты
    # ============================================================

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

    def _get_color(self, tool_name, default="white"):
        data = self.tools.get(tool_name)
        return data[0] if data else default

    def _world_to_cell(self, world_x, world_y):
        return int(world_x // self.cell_size), int(world_y // self.cell_size)

    def _event_to_cell(self, event):
        return self._world_to_cell(event.x + self.cam_x, event.y + self.cam_y)

    def _selection_bounds(self):
        """Возвращает (min_c, min_r, max_c, max_r) или None."""
        return self.selection

    # ---------- итераторы по прямоугольнику (через чанки) ----------

    def _iter_cells_in_rect(self, min_c, min_r, max_c, max_r):
        data = self.grid_data
        if isinstance(data, ChunkedLayerData):
            for loc, item in data.cells_in_view(min_c, max_c, min_r, max_r):
                c, r = loc
                if min_c <= c <= max_c and min_r <= r <= max_r:
                    yield loc, item
        else:
            for loc, item in data.items():
                c, r = loc
                if min_c <= c <= max_c and min_r <= r <= max_r:
                    yield loc, item

    def _iter_cells_in_rect_keys(self, min_c, min_r, max_c, max_r):
        for loc, _ in self._iter_cells_in_rect(min_c, min_r, max_c, max_r):
            yield loc

    def _iter_lines_in_rect(self, min_c, min_r, max_c, max_r):
        lines = self.grid_lines
        src = (lines.lines_in_view(min_c, max_c, min_r, max_r)
               if isinstance(lines, ChunkedLayerLines) else lines.items())
        for key, item in src:
            (c1, r1), (c2, r2) = key
            if (min_c <= c1 <= max_c and min_r <= r1 <= max_r and
                    min_c <= c2 <= max_c and min_r <= r2 <= max_r):
                yield key, item

    def _iter_lines_in_rect_keys(self, min_c, min_r, max_c, max_r):
        for key, _ in self._iter_lines_in_rect(min_c, min_r, max_c, max_r):
            yield key

    def _has_content_in_selection(self, min_c, min_r, max_c, max_r):
        has_elements = next(
            self._iter_cells_in_rect_keys(min_c, min_r, max_c, max_r), None) is not None
        has_lines = next(
            self._iter_lines_in_rect_keys(min_c, min_r, max_c, max_r), None) is not None
        return has_elements, has_lines

    # ---------- вспомогательные операции над выделением ----------

    def _lift_selection_to_floating(self, min_c, min_r, max_c, max_r):
        """Вырезает содержимое прямоугольника в плавающее состояние."""
        self.floating_data = {}
        self.floating_lines = {}

        cell_keys = []
        for (c, r), item in self._iter_cells_in_rect(min_c, min_r, max_c, max_r):
            self.floating_data[(c - min_c, r - min_r)] = {
                "tool": item["tool"], "props": item["props"].copy()
            }
            cell_keys.append((c, r))
        for key in cell_keys:
            del self.grid_data[key]

        line_keys = []
        for key, item in self._iter_lines_in_rect(min_c, min_r, max_c, max_r):
            (c1, r1), (c2, r2) = key
            self.floating_lines[((c1 - min_c, r1 - min_r), (c2 - min_c, r2 - min_r))] = {
                "tool": item["tool"], "props": item["props"].copy()
            }
            line_keys.append(key)
        for key in line_keys:
            del self.grid_lines[key]

        self.floating_offset = (min_c, min_r)
        self.selection = None

    def _delete_selection_content(self, min_c, min_r, max_c, max_r):
        for key in list(self._iter_cells_in_rect_keys(min_c, min_r, max_c, max_r)):
            del self.grid_data[key]
        for key in list(self._iter_lines_in_rect_keys(min_c, min_r, max_c, max_r)):
            del self.grid_lines[key]

    # ============================================================
    #  Инструменты
    # ============================================================

    def parse_tools(self, tools_input):
        if tools_input is None:
            tools_input = {
                "Основное": {
                    "Стена": ["black", []],
                    "Вода": ["blue", []],
                    "Трава": ["green", []],
                }
            }
        first_val = next(iter(tools_input.values()))
        self.grouped_tools = tools_input if isinstance(first_val, dict) \
            else {"Инструменты": tools_input}

        self.tools = {}
        for group_content in self.grouped_tools.values():
            for name, data in group_content.items():
                self.tools[name] = data

    def _highlight_tool(self, name):
        for n, b in self.tool_buttons.items():
            try:
                b.config(relief=tk.SUNKEN if n == name else tk.RAISED)
            except tk.TclError:
                pass

    def select_tool(self, name, color, props):
        self.commit_floating()
        self.current_value = name
        self.current_color = color
        self.current_props_list = props
        self._highlight_tool(name)
        self.update_right_toolbar()

    def pick_tool_at(self, col, row):
        loc = (col, row)
        if loc not in self.grid_data:
            return
        item = self.grid_data[loc]
        tool_name = item["tool"]
        if tool_name not in self.tools:
            return
        self.tool_prop_values[tool_name] = item["props"].copy()
        self.select_tool(tool_name, self.tools[tool_name][0], self.tools[tool_name][1])

    # ============================================================
    #  Левая панель инструментов
    # ============================================================

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

        self.toolbar_title = tk.Label(
            header_frame, text="Инструменты", font=("Arial", 10, "bold"))
        self.toolbar_title.pack(side=tk.LEFT, padx=5)

        self.toolbar_content = tk.Frame(self.left_toolbar)
        self.toolbar_content.pack(fill=tk.BOTH, expand=True)

        tool_canvas = tk.Canvas(self.toolbar_content, highlightthickness=0)
        tool_scrollbar = tk.Scrollbar(
            self.toolbar_content, orient="vertical", command=tool_canvas.yview)
        scrollable_frame = tk.Frame(tool_canvas)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: tool_canvas.configure(scrollregion=tool_canvas.bbox("all")))
        canvas_window = tool_canvas.create_window(
            (0, 0), window=scrollable_frame, anchor="nw")
        tool_canvas.bind(
            '<Configure>',
            lambda e: tool_canvas.itemconfig(canvas_window, width=e.width))
        tool_canvas.configure(yscrollcommand=tool_scrollbar.set)

        tool_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tool_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_toolbar_wheel(event):
            step = 2
            if event.delta:
                tool_canvas.yview_scroll(int(-step * (event.delta / 120)), "units")
            elif event.num == 4:
                tool_canvas.yview_scroll(-step, "units")
            elif event.num == 5:
                tool_canvas.yview_scroll(step, "units")
            return "break"

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

            toggle_btn = tk.Button(
                grp_header, text="▼", width=2, relief=tk.FLAT, bg="#e0e0e0",
                font=("Arial", 8),
                command=lambda b=None, f=content_frame: None)
            toggle_btn.config(
                command=lambda b=toggle_btn, f=content_frame: toggle_group(b, f))
            toggle_btn.pack(side=tk.LEFT)

            tk.Label(grp_header, text=group_name, font=("Arial", 9, "bold"),
                     bg="#e0e0e0", anchor="w").pack(
                side=tk.LEFT, fill=tk.X, expand=True, padx=2)

            for name, data in items.items():
                color = data[0]
                props = data[1]
                btn = tk.Button(
                    content_frame, text=name, bg=color,
                    relief=tk.RAISED, bd=2,
                    fg="white" if color.lower() in (
                        "black", "blue", "red", "green",
                        "#000000", "#1e90ff", "#2c3e50", "#c0392b") else "black",
                    anchor="w",
                    command=lambda n=name, c=color, p=props: self.select_tool(n, c, p))
                btn.pack(fill=tk.X, padx=2, pady=1)
                self.tool_buttons[name] = btn

        def _bind_wheel_recursive(widget):
            widget.bind("<MouseWheel>", _on_toolbar_wheel, add="+")
            widget.bind("<Button-4>", _on_toolbar_wheel, add="+")
            widget.bind("<Button-5>", _on_toolbar_wheel, add="+")
            for child in widget.winfo_children():
                _bind_wheel_recursive(child)

        _bind_wheel_recursive(scrollable_frame)
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

    # ============================================================
    #  Меню
    # ============================================================

    def create_menu(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Новый", command=self.new_schematic, accelerator="Ctrl+N")
        file_menu.add_command(label="Открыть", command=self.load_dictionary_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Сохранить", command=self.save_dictionary_file, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Экспорт", command=self.export_data, accelerator="Ctrl+E")
        menubar.add_cascade(label="Файл", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
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
        menubar.add_cascade(label="Правка", menu=edit_menu)

        layers_menu = tk.Menu(menubar, tearoff=0)
        layers_menu.add_command(label="Добавить слой", command=self.add_layer)
        layers_menu.add_command(
            label="Удалить активный слой",
            command=lambda: self.remove_layer(self.active_layer_idx))
        menubar.add_cascade(label="Слои", menu=layers_menu)

        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Сброс камеры", command=self.reset_camera)
        menubar.add_cascade(label="Инструменты", menu=tools_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Горячие клавиши", command=self.show_help, accelerator="F1")
        menubar.add_cascade(label="Справка", menu=help_menu)

        self.menubar = menubar
        self.root.config(menu=menubar)

    # ============================================================
    #  Файловые операции
    # ============================================================

    def new_schematic(self):
        if self.is_dirty:
            response = messagebox.askyesnocancel(
                "Новая схематика",
                "Есть несохранённые изменения. Сохранить их перед созданием новой схематики?")
            if response is None:
                return
            if response is True and not self.save_dictionary_file():
                return

        self.commit_floating()
        self.layers = [self._create_new_layer("Слой 1")]
        self.active_layer_idx = 0
        self.soloed_layer = None

        self._clear_selection_and_floating()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._reset_camera_state()

        self.is_dirty = False
        self.update_title()
        self.update_right_toolbar()
        self.request_redraw()

    def reset_camera(self):
        self.commit_floating()
        self._reset_camera_state()
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
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")])
        if not file_path:
            return False
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                if isinstance(processed_data, (dict, list)):
                    json.dump(processed_data, f, ensure_ascii=False, indent=4)
                else:
                    f.write(str(processed_data))
            print(f"Данные успешно экспортированы в {file_path}")
            return True
        except Exception as e:
            messagebox.showerror("Ошибка экспорта", f"Ошибка записи файла: {e}")
            return False

    def save_dictionary_file(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not file_path:
            return False
        payload = {
            "layers": [
                {
                    "name": l["name"], "visible": l["visible"],
                    "cells": {f"{c},{r}": item for (c, r), item in l["data"].items()},
                    "lines": {f"{c1},{r1};{c2},{r2}": v
                              for ((c1, r1), (c2, r2)), v
                              in l.get("lines", {}).items()},
                } for l in self.layers
            ]
        }
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=4)
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
                    cells = {}
                    for key_str, item in l_data.get("cells", {}).items():
                        c_str, r_str = key_str.split(",")
                        cells[(int(c_str), int(r_str))] = item
                    lines = {}
                    for key_str, item in l_data.get("lines", {}).items():
                        p1, p2 = key_str.split(";")
                        c1, r1 = map(int, p1.split(","))
                        c2, r2 = map(int, p2.split(","))
                        lines[((c1, r1), (c2, r2))] = item
                    new_layers.append({
                        "name": l_data.get("name", "Слой"),
                        "visible": l_data.get("visible", True),
                        "data": ChunkedLayerData(cells),
                        "lines": ChunkedLayerLines(lines),
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

    def on_closing(self):
        if self.is_dirty:
            response = messagebox.askyesnocancel(
                "Сохранение", "У вас есть несохраненные изменения. Сохранить перед выходом?")
            if response is True and self.save_dictionary_file():
                self.root.destroy()
            elif response is False:
                self.root.destroy()
        else:
            self.root.destroy()

    # ============================================================
    #  Undo / Redo
    # ============================================================

    def _snapshot_layers(self):
        return [
            {
                "name": l["name"],
                "visible": l["visible"],
                "data": {loc: {"tool": d["tool"], "props": d["props"].copy()}
                         for loc, d in l["data"].items()},
                "lines": {k: {"tool": v["tool"], "props": v["props"].copy()}
                          for k, v in l.get("lines", {}).items()},
            } for l in self.layers
        ]

    def _deserialize_layer(self, l):
        return {
            "name": l["name"],
            "visible": l["visible"],
            "data": ChunkedLayerData(
                {loc: {"tool": d["tool"], "props": d["props"].copy()}
                 for loc, d in l["data"].items()}),
            "lines": ChunkedLayerLines(
                {k: {"tool": v["tool"], "props": v["props"].copy()}
                 for k, v in l.get("lines", {}).items()}),
        }

    def save_state(self):
        self.undo_stack.append({
            "active_layer_idx": self.active_layer_idx,
            "layers": self._snapshot_layers(),
        })
        self.redo_stack.clear()
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)
        self.mark_dirty()

    def _restore_state(self, state):
        self.active_layer_idx = state["active_layer_idx"]
        self.layers = [self._deserialize_layer(l) for l in state["layers"]]
        self._clear_selection_and_floating()
        self.update_right_toolbar()
        self.request_redraw()

    def undo(self, event=None):
        # Сначала разбираемся с активным floating.
        if self.floating_data is not None or self.floating_lines is not None:
            if not self._floating_state_saved:
                # Новая плавающая операция (например, вставка) — просто отменяем.
                self._clear_selection_and_floating()
                self.request_redraw()
                return
            # Иначе — операция move/cut; снапшот уже сохранён.
        if not self.undo_stack:
            return
        current_state = {
            "active_layer_idx": self.active_layer_idx,
            "layers": self._snapshot_layers(),
        }
        self.redo_stack.append(current_state)
        self._restore_state(self.undo_stack.pop())
        self.mark_dirty()

    def redo(self, event=None):
        if not self.redo_stack:
            return
        self._clear_selection_and_floating()
        current_state = {
            "active_layer_idx": self.active_layer_idx,
            "layers": self._snapshot_layers(),
        }
        self.undo_stack.append(current_state)
        self._restore_state(self.redo_stack.pop())
        self.mark_dirty()

    # ============================================================
    #  Слои
    # ============================================================

    def _create_new_layer(self, name):
        return {
            "name": name,
            "visible": True,
            "data": ChunkedLayerData(),
            "lines": ChunkedLayerLines(),
        }

    def add_layer(self):
        self.commit_floating()
        self.save_state()
        self.layers.append(self._create_new_layer(f"Слой {len(self.layers) + 1}"))
        self.active_layer_idx = len(self.layers) - 1
        self.update_right_toolbar()
        self.request_redraw()

    def set_active_layer(self, idx):
        self.commit_floating()
        self.active_layer_idx = idx
        self.update_right_toolbar()
        self.request_redraw()

    def remove_layer(self, idx):
        if len(self.layers) <= 1:
            messagebox.showwarning("Удаление слоя", "Нельзя удалить единственный слой.")
            return
        if not (0 <= idx < len(self.layers)):
            return
        layer_name = self.layers[idx]["name"]
        if not messagebox.askyesno("Удаление слоя", f"Удалить слой '{layer_name}'?"):
            return

        self.commit_floating()
        self.save_state()
        del self.layers[idx]

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

    def solo_layer_visibility(self, idx):
        if idx != self.soloed_layer:
            self.soloed_layer = idx
            for i, layer in enumerate(self.layers):
                layer["visible"] = (i == idx)
        else:
            self.soloed_layer = None
            for layer in self.layers:
                layer["visible"] = True
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

    # ============================================================
    #  Правый тулбар
    # ============================================================

    def validate_digit(self, value):
        return value == "" or value.isdigit()

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

    def update_prop_value(self, prop_name, var):
        self.tool_prop_values[self.current_value][prop_name] = var.get()

    def update_right_toolbar(self):
        if not self.right_toolbar.winfo_ismapped():
            self.right_toolbar.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)

        for widget in self.right_toolbar.winfo_children():
            widget.destroy()

        # --- Слои ---
        layers_header = tk.Frame(self.right_toolbar)
        layers_header.pack(fill=tk.X, padx=5, pady=(5, 2))
        tk.Label(layers_header, text="Слои", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        tk.Button(layers_header, text="+ Слой", font=("Arial", 8),
                  command=self.add_layer).pack(side=tk.RIGHT)

        tk.Frame(self.right_toolbar, height=1, bg="gray").pack(fill=tk.X, padx=5, pady=2)

        layers_frame = tk.Frame(self.right_toolbar)
        layers_frame.pack(fill=tk.X, padx=5, pady=2)

        for idx in range(len(self.layers) - 1, -1, -1):
            layer = self.layers[idx]
            is_active = (idx == self.active_layer_idx)
            bg_color = "#d0e0f0" if is_active else "#f0f0f0"

            row = tk.Frame(layers_frame, bg=bg_color, bd=1, relief=tk.RIDGE)
            row.pack(fill=tk.X, pady=1)
            row.columnconfigure(1, weight=1)

            vis_btn = tk.Button(
                row, text="👁" if layer["visible"] else "🙈",
                width=2, relief=tk.FLAT, bg=bg_color,
                command=lambda i=idx: self.toggle_layer_visibility(i))
            vis_btn.grid(row=0, column=0, sticky="w")
            vis_btn.bind("<Button-3>", lambda e, i=idx: self.solo_layer_visibility(i))

            name_btn = tk.Button(
                row, text=layer["name"], anchor="w", relief=tk.FLAT,
                font=("Arial", 9, "bold" if is_active else "normal"),
                bg=bg_color,
                command=lambda i=idx: self.set_active_layer(i))
            name_btn.grid(row=0, column=1, sticky="ew")
            name_btn.bind("<Double-Button-1>", lambda e, i=idx: self.rename_layer(i))

            tk.Button(row, text="▲", width=1, relief=tk.FLAT, bg=bg_color,
                      command=lambda i=idx: self.move_layer(i, 1)
                      ).grid(row=0, column=2, sticky="e")
            tk.Button(row, text="▼", width=1, relief=tk.FLAT, bg=bg_color,
                      command=lambda i=idx: self.move_layer(i, -1)
                      ).grid(row=0, column=3, sticky="e")

            if len(self.layers) > 1:
                tk.Button(row, text="X", width=2, fg="red", relief=tk.FLAT, bg=bg_color,
                          command=lambda i=idx: self.remove_layer(i)
                          ).grid(row=0, column=4, sticky="e")

        # --- Свойства инструмента ---
        if not self.current_props_list:
            return
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
                          lambda *a, p=prop, v=var: self.update_prop_value(p, v))
            tk.Entry(row_frame, width=8, textvariable=var,
                     validate='key', validatecommand=vcmd).pack(side=tk.RIGHT)

    # ============================================================
    #  Заголовок и статус
    # ============================================================

    def mark_dirty(self):
        self.is_dirty = True
        self.update_title()

    def update_title(self):
        base = "Бесконечная сетка с инструментами и экспортом"
        self.root.title(base + (" *" if self.is_dirty else ""))

    def _update_status(self):
        scale_pct = round(self.cell_size / self.default_cell_size * 100)
        self.status_bar.config(
            text=f"Координаты: ({self.mouse_col}, {self.mouse_row}) | Масштаб: {scale_pct}%")

    def global_click_handler(self, event):
        if not isinstance(event.widget, tk.Entry):
            self.root.focus_set()

    # ============================================================
    #  Камера и зум
    # ============================================================

    def _reset_camera_state(self):
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.cell_size = self.default_cell_size

    def zoom_at(self, screen_x, screen_y, factor):
        if factor > 1 and self.cell_size >= self.zoom_in_limit:
            return
        if factor < 1 and self.cell_size <= self.zoom_out_limit:
            return
        col_world = (screen_x + self.cam_x) / self.cell_size
        row_world = (screen_y + self.cam_y) / self.cell_size
        self.cell_size *= factor
        self.cam_x = col_world * self.cell_size - screen_x
        self.cam_y = row_world * self.cell_size - screen_y
        self._update_status()
        self.request_redraw()

    def zoom_wheel(self, event):
        factor = self.zoom_speed if event.delta > 0 else 1 / self.zoom_speed
        self.zoom_at(event.x, event.y, factor)

    def animate_camera(self):
        now = time.perf_counter()
        if self._last_anim_time is None:
            self._last_anim_time = now
            self.cam_vx = 0.0
            self.cam_vy = 0.0
        dt = min(now - self._last_anim_time, 0.05)
        self._last_anim_time = now

        speed = self.CAMERA_SPEED
        target_vx = target_vy = 0.0
        if 'w' in self.pressed_keys:
            target_vy -= speed
        if 's' in self.pressed_keys:
            target_vy += speed
        if 'a' in self.pressed_keys:
            target_vx -= speed
        if 'd' in self.pressed_keys:
            target_vx += speed

        lerp = 1.0 - (0.75 ** (dt * 60.0))
        self.cam_vx += (target_vx - self.cam_vx) * lerp
        self.cam_vy += (target_vy - self.cam_vy) * lerp

        moving = (abs(self.cam_vx) > 0.01 or abs(self.cam_vy) > 0.01
                  or bool(self.pressed_keys))
        if moving:
            self.cam_x += self.cam_vx * dt
            self.cam_y += self.cam_vy * dt
            self.request_redraw()
            elapsed = time.perf_counter() - now
            delay_ms = max(1, int(16 - elapsed * 1000))
            self.root.after(delay_ms, self.animate_camera)
        else:
            self.cam_vx = self.cam_vy = 0.0
            self.is_moving = False
            self._last_anim_time = None

    # ============================================================
    #  Перерисовка
    # ============================================================

    def request_redraw(self):
        if self._redraw_scheduled:
            return
        self._redraw_scheduled = True
        self.root.after_idle(self._do_redraw)

    def _do_redraw(self):
        self._redraw_scheduled = False
        if getattr(self, 'canvas', None):
            self.redraw_canvas()

    def _draw_cell(self, c, r, item, draw_text, font_size, outline=""):
        x1 = c * self.cell_size - self.cam_x
        y1 = r * self.cell_size - self.cam_y
        tool_name = item["tool"]
        size = item["props"].get("SIZE")
        draw_size = self.cell_size
        if size is not None and tool_name not in ("POLY",):
            draw_size *= (int(size) + 1)
        color = self._get_color(tool_name)
        self.canvas.create_rectangle(
            x1, y1, x1 + draw_size, y1 + draw_size,
            fill=color, outline=outline)
        if draw_text:
            self.canvas.create_text(
                x1 + draw_size / 2, y1 + draw_size / 2,
                text=tool_name, fill=self.get_contrast_color(color),
                font=("Arial", font_size, "bold"))

    def _draw_line(self, x1, y1, x2, y2, item, draw_text, font_size):
        color = self._get_color(item["tool"], "black")
        line_width = max(2, int(self.cell_size / 8))
        r_start = line_width * 1.5
        self.canvas.create_oval(
            x1 - r_start, y1 - r_start, x1 + r_start, y1 + r_start,
            fill=color, outline=color)
        arrow_size = max(8, int(self.cell_size / 4))
        arrow_shape = (arrow_size, arrow_size + 2, max(3, arrow_size // 3))
        self.canvas.create_line(
            x1, y1, x2, y2, fill=color, width=line_width,
            arrow=tk.LAST, arrowshape=arrow_shape)
        if draw_text:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            self.canvas.create_text(
                mx, my, text=item["tool"], fill=color,
                font=("Arial", font_size, "bold"))

    def _draw_layer_cells(self, layer, start_col, end_col, start_row, end_row,
                          draw_text, font_size):
        margin = self.CULL_MARGIN
        data = layer["data"]
        if isinstance(data, ChunkedLayerData):
            for loc, item in data.cells_in_view(
                    start_col - margin, end_col + margin,
                    start_row - margin, end_row + margin):
                self._draw_cell(loc[0], loc[1], item, draw_text, font_size)
        else:
            lo_c, hi_c = start_col - margin, end_col + margin
            lo_r, hi_r = start_row - margin, end_row + margin
            for loc, item in data.items():
                c, r = loc
                if lo_c <= c <= hi_c and lo_r <= r <= hi_r:
                    self._draw_cell(c, r, item, draw_text, font_size)

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

        for layer in self.layers:
            if not layer["visible"]:
                continue

            self._draw_layer_cells(
                layer, start_col, end_col, start_row, end_row,
                draw_text, cell_font_size)

            if draw_lines:
                lines = layer.get("lines", {})
                src = (lines.lines_in_view(start_col, end_col - 1, start_row, end_row - 1)
                       if isinstance(lines, ChunkedLayerLines) else lines.items())
                for (start_loc, end_loc), item in src:
                    c1, r1 = start_loc
                    c2, r2 = end_loc
                    x1 = c1 * self.cell_size - self.cam_x + self.cell_size / 2
                    y1 = r1 * self.cell_size - self.cam_y + self.cell_size / 2
                    x2 = c2 * self.cell_size - self.cam_x + self.cell_size / 2
                    y2 = r2 * self.cell_size - self.cam_y + self.cell_size / 2
                    self._draw_line(x1, y1, x2, y2, item, False, 0)

        # Маркер (0, 0)
        if start_col <= 0 < end_col and start_row <= 0 < end_row:
            ox1 = -self.cam_x
            oy1 = -self.cam_y
            ox2 = ox1 + self.cell_size
            oy2 = oy1 + self.cell_size
            self.canvas.create_rectangle(
                ox1, oy1, ox2, oy2, outline="#e74c3c", width=3, dash=(3, 3))
            if self.cell_size >= self.min_cell_size_marker:
                self.canvas.create_text(
                    ox1 + 5, oy1 + 5, text="(0,0)", anchor="nw",
                    fill="#e74c3c", font=("Arial", 8, "bold"))

        # Плавающие клетки
        if self.floating_data:
            for (rel_c, rel_r), item in self.floating_data.items():
                abs_c = self.floating_offset[0] + rel_c
                abs_r = self.floating_offset[1] + rel_r
                if (start_col <= abs_c < end_col
                        and start_row <= abs_r < end_row):
                    self._draw_cell(
                        abs_c, abs_r, item, draw_text,
                        max(8, int(self.cell_size / 5)), outline_color)

        # Плавающие линии
        if self.floating_lines:
            for (rel_start, rel_end), item in self.floating_lines.items():
                c1 = self.floating_offset[0] + rel_start[0]
                r1 = self.floating_offset[1] + rel_start[1]
                c2 = self.floating_offset[0] + rel_end[0]
                r2 = self.floating_offset[1] + rel_end[1]
                if ((start_col <= c1 < end_col and start_row <= r1 < end_row) or
                        (start_col <= c2 < end_col and start_row <= r2 < end_row)):
                    x1 = c1 * self.cell_size - self.cam_x + self.cell_size / 2
                    y1 = r1 * self.cell_size - self.cam_y + self.cell_size / 2
                    x2 = c2 * self.cell_size - self.cam_x + self.cell_size / 2
                    y2 = r2 * self.cell_size - self.cam_y + self.cell_size / 2
                    self._draw_line(
                        x1, y1, x2, y2, item, draw_text,
                        max(8, int(self.cell_size / 6)))

        self.update_selection_rect_visual()

    # ============================================================
    #  Холст
    # ============================================================

    def create_canvas(self):
        if getattr(self, 'canvas', None):
            self.canvas.destroy()

        self.canvas = tk.Canvas(
            self.canvas_frame, width=self.view_width,
            height=self.view_height, bg="white")
        self.canvas.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<B1-Motion>", self.on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_release)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<B3-Motion>", self.erase)

        self.canvas.bind("<Button-2>", self.start_pan)
        self.canvas.bind("<B2-Motion>", self.pan_camera)
        self.canvas.bind("<ButtonRelease-2>", self.end_pan)

        self.canvas.bind("<Alt-Button-1>", self.pick_tool)
        self.canvas.bind("<Motion>", self.track_mouse)

        self.canvas.bind("<MouseWheel>", self.zoom_wheel)
        self.canvas.bind("<Button-4>",
                         lambda e: self.zoom_at(e.x, e.y, self.zoom_speed))
        self.canvas.bind("<Button-5>",
                         lambda e: self.zoom_at(e.x, e.y, 1 / self.zoom_speed))

        self.canvas.bind("<Shift-Button-1>", self.start_selection)
        self.canvas.bind("<Shift-B1-Motion>", self.update_selection)
        self.canvas.bind("<Shift-ButtonRelease-1>", self.end_selection)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        self.request_redraw()

    def _on_canvas_resize(self, event):
        self.view_width = max(1, event.width)
        self.view_height = max(1, event.height)
        if hasattr(self, "layers"):
            self.request_redraw()

    # ============================================================
    #  Горячие клавиши
    # ============================================================

    def bind_hotkeys(self):
        for seq, cb in [
            ("<Control-c>", self.copy_selection), ("<Control-C>", self.copy_selection),
            ("<Control-x>", self.cut_selection),  ("<Control-X>", self.cut_selection),
            ("<Control-v>", self.paste_selection),("<Control-V>", self.paste_selection),
            ("<Delete>", self.delete_selection),  ("<BackSpace>", self.delete_selection),
            ("<Control-z>", self.undo),           ("<Control-Z>", self.undo),
            ("<Control-Shift-z>", self.redo),     ("<Control-Shift-Z>", self.redo),
            ("<Control-y>", self.redo),           ("<Control-Y>", self.redo),
            ("<Control-s>", lambda e: self.save_dictionary_file()),
            ("<Control-S>", lambda e: self.save_dictionary_file()),
            ("<Control-o>", lambda e: self.load_dictionary_file()),
            ("<Control-O>", lambda e: self.load_dictionary_file()),
            ("<Control-e>", lambda e: self.export_data()),
            ("<Control-E>", lambda e: self.export_data()),
            ("<Control-n>", lambda e: self.new_schematic()),
            ("<Control-N>", lambda e: self.new_schematic()),
            ("<Escape>", self.cancel_action),
            ("<Control-a>", self.select_all),     ("<Control-A>", self.select_all),
            ("<Control-d>", self.deselect_all),   ("<Control-D>", self.deselect_all),
            ("<F1>", self.show_help),
            ("<Home>", lambda e: self.reset_camera()),
            ("<Control-0>", lambda e: self.reset_camera()),
            ("<Control-KP_0>", lambda e: self.reset_camera()),
            ("<bracketleft>", self.prev_layer),
            ("<bracketright>", self.next_layer),
            ("<Control-Tab>", self.next_layer),
            ("<Control-Shift-Tab>", self.prev_layer),
            ("<Control-ISO_Left_Tab>", self.prev_layer),
            ("<KeyPress-space>", self._space_pan_press),
            ("<KeyRelease-space>", self._space_pan_release),
        ]:
            self.root.bind(seq, cb)

        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)

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
            cx = self.mouse_x or self.view_width / 2
            cy = self.mouse_y or self.view_height / 2
            self.zoom_at(cx, cy, self.zoom_speed)
        elif key in ('minus', 'kp_subtract'):
            cx = self.mouse_x or self.view_width / 2
            cy = self.mouse_y or self.view_height / 2
            self.zoom_at(cx, cy, 1 / self.zoom_speed)

    def on_key_release(self, event):
        key = event.keysym.lower()
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)

    # ============================================================
    #  Панорамирование пробелом
    # ============================================================

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

    # ============================================================
    #  Обработчики мыши
    # ============================================================

    def track_mouse(self, event):
        self.mouse_col, self.mouse_row = self._event_to_cell(event)
        self.mouse_x = event.x
        self.mouse_y = event.y
        self._update_status()

        if (self.floating_data is not None or self.floating_lines is not None) \
                and not self.is_moving_selection:
            self.floating_offset = (self.mouse_col, self.mouse_row)
            self.request_redraw()

    def is_click_on_selection(self, col, row):
        if self.floating_data:
            rel_c = col - self.floating_offset[0]
            rel_r = row - self.floating_offset[1]
            if (rel_c, rel_r) in self.floating_data:
                return True
        if self.selection:
            min_c, min_r, max_c, max_r = self.selection
            return min_c <= col <= max_c and min_r <= row <= max_r
        return False

    def on_left_click(self, event):
        # --- space-pan ---
        if self.space_pan_active:
            self.pan_start_x = event.x
            self.pan_start_y = event.y
            self.pan_cam_start_x = self.cam_x
            self.pan_cam_start_y = self.cam_y
            self._space_panning = True
            return
        # Shift+ЛКМ / Ctrl+ЛКМ — это старт выделения (обрабатывается отдельными bind'ами).
        if (event.state & 0x0001) or (event.state & 0x0004):
            return

        col, row = self._event_to_cell(event)

        # --- click on active floating: продолжить перетаскивание ---
        if self.floating_data is not None or self.floating_lines is not None:
            if self.is_click_on_selection(col, row):
                self.is_moving_selection = True
                self.move_start_mouse = (col, row)
                self.initial_offset = self.floating_offset
                return
            self.commit_floating()
            return

        # --- click on regular selection: поднять в floating ---
        if self.selection and self.is_click_on_selection(col, row):
            min_c, min_r, max_c, max_r = self.selection
            has_elements, has_lines = self._has_content_in_selection(
                min_c, min_r, max_c, max_r)
            if has_elements or has_lines:
                self.save_state()
                self._floating_state_saved = True
                self._lift_selection_to_floating(min_c, min_r, max_c, max_r)
                self.is_moving_selection = True
                self.move_start_mouse = (col, row)
                self.initial_offset = self.floating_offset
                self.request_redraw()
            return

        # --- обычная кисть / старт линии ---
        self.commit_floating()
        if self.is_line_tool(self.current_value):
            self.line_start = (col, row)
        else:
            self.save_state()
            self.paint(event)

    def on_left_drag(self, event):
        if self._space_panning:
            dx = event.x - self.pan_start_x
            dy = event.y - self.pan_start_y
            self.cam_x = self.pan_cam_start_x - dx
            self.cam_y = self.pan_cam_start_y - dy
            self.request_redraw()
            return
        # Shift/Ctrl/Alt обрабатываются отдельными bind'ами.
        if (event.state & 0x0001) or (event.state & 0x0004) or (event.state & 0x0008):
            return

        if self.line_start is not None:
            self.canvas.delete("temp_line")
            c1, r1 = self.line_start
            x1 = c1 * self.cell_size - self.cam_x + self.cell_size / 2
            y1 = r1 * self.cell_size - self.cam_y + self.cell_size / 2
            col, row = self._event_to_cell(event)
            x2 = col * self.cell_size - self.cam_x + self.cell_size / 2
            y2 = row * self.cell_size - self.cam_y + self.cell_size / 2

            color = self.tools.get(self.current_value, ["black"])[0]
            r_start = 4
            self.canvas.create_oval(
                x1 - r_start, y1 - r_start, x1 + r_start, y1 + r_start,
                fill=color, outline=color, tags="temp_line")
            self.canvas.create_line(
                x1, y1, x2, y2, fill=color, width=3, dash=(4, 4),
                arrow=tk.LAST, tags="temp_line")
            return

        if self.is_moving_selection:
            self.during_move(event)
        else:
            self.paint(event)

    def on_left_release(self, event):
        if self._space_panning:
            self._space_panning = False
            return

        if self.line_start is not None:
            self.canvas.delete("temp_line")
            col, row = self._event_to_cell(event)
            if (col, row) != self.line_start:
                self.save_state()
                props = {p: self.tool_prop_values[self.current_value].get(p, "0")
                         for p in self.current_props_list}
                self.grid_lines[(self.line_start, (col, row))] = {
                    "tool": self.current_value, "props": props}
                self.mark_dirty()
                self.request_redraw()
            self.line_start = None

        self.is_moving_selection = False
        self.move_start_mouse = None

    def on_right_click(self, event):
        col, row = self._event_to_cell(event)
        loc = (col, row)

        has_content = loc in self.grid_data
        has_lines = any(loc == k[0] or loc == k[1] for k in self.grid_lines)
        has_floating = False
        if self.floating_data:
            rel_c = col - self.floating_offset[0]
            rel_r = row - self.floating_offset[1]
            has_floating = (rel_c, rel_r) in self.floating_data

        if has_content or has_lines or has_floating:
            self.save_state()
        self.erase(event)

    def erase(self, event):
        col, row = self._event_to_cell(event)
        loc = (col, row)
        modified = False

        if loc in self.grid_data:
            del self.grid_data[loc]
            modified = True

        lines_to_delete = [k for k in self.grid_lines
                           if k[0] == loc or k[1] == loc]
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
        col, row = self._event_to_cell(event)
        loc = (col, row)
        props_snapshot = {p: self.tool_prop_values[self.current_value].get(p, "0")
                          for p in self.current_props_list}
        new_item = {"tool": self.current_value, "props": props_snapshot}
        if self.grid_data.get(loc) != new_item:
            self.grid_data[loc] = new_item
            self.mark_dirty()
            self.request_redraw()

    def start_pan(self, event):
        self.commit_floating()
        self.is_panning = True
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self.pan_cam_start_x = self.cam_x
        self.pan_cam_start_y = self.cam_y
        self.canvas.config(cursor="fleur")

    def pan_camera(self, event):
        if not self.is_panning:
            return
        dx = event.x - self.pan_start_x
        dy = event.y - self.pan_start_y
        self.cam_x = self.pan_cam_start_x - dx
        self.cam_y = self.pan_cam_start_y - dy
        self.mouse_col = int((event.x + self.cam_x) // self.cell_size)
        self.mouse_row = int((event.y + self.cam_y) // self.cell_size)
        self.status_bar.config(
            text=f"Координаты: ({self.mouse_col}, {self.mouse_row})")
        self.request_redraw()

    def end_pan(self, event):
        self.is_panning = False
        self.canvas.config(cursor="")

    def pick_tool(self, event):
        col, row = self._event_to_cell(event)
        self.pick_tool_at(col, row)

    # ============================================================
    #  Плавающее перетаскивание
    # ============================================================

    def during_move(self, event):
        if not self.is_moving_selection:
            return
        if self.floating_data is None and self.floating_lines is None:
            return
        col, row = self._event_to_cell(event)
        dx = col - self.move_start_mouse[0]
        dy = row - self.move_start_mouse[1]
        self.floating_offset = (self.initial_offset[0] + dx,
                                self.initial_offset[1] + dy)
        self.request_redraw()

    def commit_floating(self):
        has_changed = False

        if self.floating_data is not None:
            if not self._floating_state_saved:
                self.save_state()
            for (rel_c, rel_r), item in self.floating_data.items():
                abs_c = self.floating_offset[0] + rel_c
                abs_r = self.floating_offset[1] + rel_r
                self.grid_data[(abs_c, abs_r)] = {
                    "tool": item["tool"], "props": item["props"].copy()}
            self.floating_data = None
            has_changed = True

        if self.floating_lines is not None:
            if not has_changed and not self._floating_state_saved:
                self.save_state()
            for (rel_start, rel_end), item in self.floating_lines.items():
                abs_start = (self.floating_offset[0] + rel_start[0],
                             self.floating_offset[1] + rel_start[1])
                abs_end = (self.floating_offset[0] + rel_end[0],
                           self.floating_offset[1] + rel_end[1])
                self.grid_lines[(abs_start, abs_end)] = {
                    "tool": item["tool"], "props": item["props"].copy()}
            self.floating_lines = None
            has_changed = True

        if has_changed:
            self._floating_state_saved = False
            self.mark_dirty()
            self._clear_selection_and_floating()

        self.request_redraw()

    # ============================================================
    #  Выделение
    # ============================================================

    def _clear_selection_and_floating(self):
        self.selection = None
        self.sel_start = None
        self.sel_end = None
        self.floating_data = None
        self.floating_lines = None
        self._floating_state_saved = False
        if self.sel_rect_id:
            self.canvas.delete(self.sel_rect_id)
            self.sel_rect_id = None

    def start_selection(self, event):
        self.commit_floating()
        col, row = self._event_to_cell(event)
        self.sel_start = (col, row)
        self.sel_end = (col, row)
        self.selection = (col, row, col, row)
        self.update_selection_rect_visual()

    def update_selection(self, event):
        col, row = self._event_to_cell(event)
        self.sel_end = (col, row)
        c1, r1 = self.sel_start
        c2, r2 = self.sel_end
        self.selection = (min(c1, c2), min(r1, r2), max(c1, c2), max(r1, r2))
        self.update_selection_rect_visual()

    def end_selection(self, event=None):
        self.sel_start = None
        self.sel_end = None

    def deselect_all(self, event=None):
        self.selection = None
        if self.sel_rect_id:
            self.canvas.delete(self.sel_rect_id)
            self.sel_rect_id = None

    def select_all(self, event=None):
        if self.floating_data is not None or self.floating_lines is not None:
            return
        if not self.grid_data and not self.grid_lines:
            return
        cs, rs = [], []
        for (c, r) in self.grid_data:
            cs.append(c); rs.append(r)
        for (c1, r1), (c2, r2) in self.grid_lines:
            cs.extend((c1, c2)); rs.extend((r1, r2))
        if cs:
            self.selection = (min(cs), min(rs), max(cs), max(rs))
            self.update_selection_rect_visual()

    def update_selection_rect_visual(self):
        min_c = min_r = max_c = max_r = None

        if self.floating_data:
            max_rel_c = max(c for c, _ in self.floating_data)
            max_rel_r = max(r for _, r in self.floating_data)
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

    def cancel_action(self, event=None):
        if self.line_start is not None:
            self.line_start = None
            self.canvas.delete("temp_line")
            return
        if self.floating_data is not None or self.floating_lines is not None:
            if self._floating_state_saved:
                self.undo()
            else:
                self._clear_selection_and_floating()
                self.request_redraw()
            return
        if self.selection:
            self.deselect_all()

    # ============================================================
    #  Буфер обмена
    # ============================================================

    def copy_selection(self, event=None):
        if self.floating_data is not None or self.floating_lines is not None:
            self.clipboard = {
                "cells": {k: {"tool": v["tool"], "props": v["props"].copy()}
                          for k, v in (self.floating_data or {}).items()},
                "lines": {k: {"tool": v["tool"], "props": v["props"].copy()}
                          for k, v in (self.floating_lines or {}).items()},
            }
            return

        if not self.selection:
            return
        min_c, min_r, max_c, max_r = self.selection
        cells_clip = {}
        for (c, r), item in self._iter_cells_in_rect(min_c, min_r, max_c, max_r):
            cells_clip[(c - min_c, r - min_r)] = {
                "tool": item["tool"], "props": item["props"].copy()}
        lines_clip = {}
        for key, item in self._iter_lines_in_rect(min_c, min_r, max_c, max_r):
            (c1, r1), (c2, r2) = key
            lines_clip[((c1 - min_c, r1 - min_r), (c2 - min_c, r2 - min_r))] = {
                "tool": item["tool"], "props": item["props"].copy()}
        self.clipboard = {"cells": cells_clip, "lines": lines_clip}

    def cut_selection(self, event=None):
        if self.floating_data is not None or self.floating_lines is not None:
            self.copy_selection()
            self.save_state()
            self._clear_selection_and_floating()
            self.mark_dirty()
            self.request_redraw()
            return
        if not self.selection:
            return
        self.copy_selection()
        min_c, min_r, max_c, max_r = self.selection
        has_elements, has_lines = self._has_content_in_selection(
            min_c, min_r, max_c, max_r)
        if has_elements or has_lines:
            self.save_state()
            self._floating_state_saved = True
            self._lift_selection_to_floating(min_c, min_r, max_c, max_r)
            self.mark_dirty()
            self.request_redraw()

    def paste_selection(self, event=None):
        if not self.clipboard:
            return
        self.commit_floating()
        self.floating_data = {k: {"tool": v["tool"], "props": v["props"].copy()}
                              for k, v in self.clipboard.get("cells", {}).items()}
        self.floating_lines = {k: {"tool": v["tool"], "props": v["props"].copy()}
                               for k, v in self.clipboard.get("lines", {}).items()}
        self.floating_offset = (self.mouse_col, self.mouse_row)
        self._floating_state_saved = False
        self.mark_dirty()
        self.request_redraw()

    def delete_selection(self, event=None):
        if self.floating_data is not None or self.floating_lines is not None:
            self.save_state()
            self._clear_selection_and_floating()
            self.mark_dirty()
            self.request_redraw()
            return
        if not self.selection:
            return
        min_c, min_r, max_c, max_r = self.selection
        has_elements, has_lines = self._has_content_in_selection(
            min_c, min_r, max_c, max_r)
        if has_elements or has_lines:
            self.save_state()
            self._delete_selection_content(min_c, min_r, max_c, max_r)
            self._clear_selection_and_floating()
            self.mark_dirty()
            self.request_redraw()

    # ============================================================
    #  Справка
    # ============================================================

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


# ============================================================
#  Экспорт
# ============================================================

def get_wall_end_pos(x, y, size):
    return x + size, y + size


def export(exported_layers):
    ret = []
    for layer in exported_layers:
        lines = layer['lines']
        for pos, data in layer['data'].items():
            tool = data['tool']
            props = data['props']
            group = EDITOR_TOOL_TO_GROUP[tool]
            if group == "WALLS":
                if tool == "PRWALL":
                    ret.append(f"wall {pos[0]} {pos[1]}")
                else:
                    change = props.get("CHANGE TYPE", '0')
                    if change == '1':
                        ret.append(f"wall_type {pos[0]} {pos[1]} "
                                   f"{EDITOR_TOOL_TO_ID[tool]}")
                    elif change == '2':
                        ret.append(f"wall {pos[0]} {pos[1]}")
                    else:
                        size = props.get("SIZE", '0')
                        if size == '0':
                            ret.append(f"type_wall {pos[0]} {pos[1]} "
                                       f"{EDITOR_TOOL_TO_ID[tool]}")
                        else:
                            x2, y2 = get_wall_end_pos(pos[0], pos[1], int(size))
                            ret.append(f"type_wall {pos[0]} {pos[1]} {x2} {y2} "
                                       f"{EDITOR_TOOL_TO_ID[tool]}")
            elif group == "OTHER":
                if tool == "POLY":
                    if props.get("CHANGE TYPE", '0') == '0':
                        ret.append(f"polygon {pos[0]} {pos[1]} "
                                   f"{props['CLASS']} {props['SIZE']} {props['TIER']}")
                    else:
                        ret.append(f"polygon_type {pos[0]} {pos[1]} "
                                   f"{props['CLASS']} {props['SIZE']} {props['TIER']}")
            if props.get("TEAM") == '1':
                ret.append("team")

        for poses, data in lines.items():
            tool = data['tool']
            ret.append(f"joint {poses[0][0]} {poses[0][1]} "
                       f"{poses[1][0]} {poses[1][1]} {EDITOR_TOOL_TO_ID[tool]}")
    return '\n'.join(ret)


# ============================================================
#  Точка входа
# ============================================================

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1200x700")

    # Глубокая копия: не модифицируем импортированный EDITOR_TOOLS.
    my_custom_tools = copy.deepcopy(EDITOR_TOOLS)

    for group, tools in my_custom_tools.items():
        for name, tool in tools.items():
            col = tool[0]
            props = copy.deepcopy(tool[1:]) if len(tool) > 1 else []
            if len(props) == 0:
                props = [[]]
            if group in ("WALLS", "OTHER"):
                for extra in ("CHANGE TYPE", "TEAM"):
                    if extra not in props[0]:
                        props[0].append(extra)
            if group == "WALLS" and "SIZE" not in props[0]:
                props[0].append("SIZE")
            r, g, b, a = col
            tools[name] = [f"#{b:02x}{g:02x}{r:02x}", *props]

    app = GridApp(root, tools=my_custom_tools)

    root.resizable(True, True)
    root.minsize(700, 400)
    root.mainloop()