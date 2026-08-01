import tkinter as tk
from tkinter import filedialog, messagebox
import json
import math

# Внешняя функция экспорта, вызываемая приложением.


class GridApp:
    def __init__(self, root, cell_size=25, tools=None, 
                min_cell_size_grid=10, 
                min_cell_size_text=35, 
                min_cell_size_marker=25):
        self.root = root
        self.root.title("Бесконечная сетка с инструментами и экспортом")
        
        self.cell_size = cell_size
        self.min_cell_size_grid = min_cell_size_grid
        self.min_cell_size_text = min_cell_size_text
        self.min_cell_size_marker = min_cell_size_marker
        
        # В начале __init__ сохраняем дефолтный зум:
        self.default_cell_size = cell_size
        
        # Флаг наличия несохраненных изменений
        self.is_dirty = False
        
        # Настройки виртуальной камеры (viewport)
        self.view_width = 900
        self.view_height = 600
        self.cam_x = 0.0
        self.cam_y = 0.0
        
        # Плавное управление движением камеры
        self.cam_vx = 0.0
        self.cam_vy = 0.0
        self.pressed_keys = set()
        self.is_moving = False
        
        self.max_speed = 100
        self.min_speed = 30
        
        self.zoom_speed = 1.2
        self.zoom_in_limit = 1000
        self.zoom_out_limit = 0.1
        
        # Флаг перетаскивания выделения мышью
        self.is_moving_selection = False
        
        # Основной словарь постоянных данных сетки: {(x, y): {"tool": name, "props": {...}}}
        # В __init__ заменяем self.grid_data = {} на:
        # ЗАМЕНИТЕ инициализацию self.layers в __init__ на эту:
        self.layers = [
            {"name": "Слой 1", "visible": True, "data": {}, "lines": {}}
        ]
        self.active_layer_idx = 0
        self.line_start = None  # Переменная для хранения начала линии
        
        # Стеки для отмены и возврата действий (Undo / Redo)
        self.undo_stack = []
        self.redo_stack = []
        
        # Плавающие данные (для перемещения выделения и вставки)
        self.floating_data = None      # Клетки во время перемещения/вставки
        self.floating_lines = None     # Линии во время перемещения/вставки
        self.floating_offset = (0, 0)
        self.clipboard = None          # Буфер: {"cells": {...}, "lines": {...}}
        
        # Состояние статического выделения
        self.selection = None          # (min_c, min_r, max_c, max_r)
        self.sel_start = None          # (col, row)
        self.sel_rect_id = None        # ID прямоугольника выделения на холсте
        
        # Позиция мыши для вставки
        self.mouse_col = 0
        self.mouse_row = 0
        
        # Нормализация структуры инструментов (поддержка групп и плоских словарей)
        self.parse_tools(tools)
            
        # Хранилище введенных значений параметров для каждого инструмента
        self.tool_prop_values = {}
        for name, data in self.tools.items():
            props = data[1]
            self.tool_prop_values[name] = {p: "0" for p in props}
            
        first_name = list(self.tools.keys())[0]
        self.current_value = first_name
        self.current_color = self.tools[first_name][0]
        self.current_props_list = self.tools[first_name][1]

        # Верхнее главное меню
        self.create_menu()

        # Главный контейнер
        self.main_container = tk.Frame(self.root)
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # Левый прокручиваемый тулбар для инструментов
        self.left_toolbar = tk.Frame(self.main_container, bd=1, relief=tk.RAISED, width=100)
        self.left_toolbar.pack(side=tk.LEFT, fill=tk.Y, padx=2, pady=2)
        self.left_toolbar.pack_propagate(False)
        # Добавляем в __init__ флаг состояния панелей
        self.left_toolbar_visible = True

        # Холст для сетки
        self.canvas_frame = tk.Frame(self.main_container)
        self.canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Правый тулбар для параметров инструмента
        self.right_toolbar = tk.Frame(self.main_container, bd=1, relief=tk.RAISED, width=120)
        self.right_toolbar.pack_propagate(False)
        
        # В самом конце __init__ добавляем статус-бар:
        self.status_bar = tk.Label(self.root, text="Координаты: (0, 0)", anchor="w", bd=1, relief=tk.SUNKEN, font=("Arial", 9))
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.create_left_toolbar()
        self.create_canvas()
        self.update_right_toolbar()
        self.bind_hotkeys()
        
        # Перехват закрытия окна для предупреждения о несохраненных данных
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Регистрируем глобальный клик для снятия фокуса с полей ввода
        self.root.bind_all("<Button-1>", self.global_click_handler, add="+")
    
    # === ДОБАВИТЬ СРАЗУ ПОСЛЕ __init__ ===
    @property
    def grid_data(self):
        return self.layers[self.active_layer_idx]["data"]

    @grid_data.setter
    def grid_data(self, value):
        self.layers[self.active_layer_idx]["data"] = value

    @property
    def grid_lines(self):
        """Возвращает данные линий текущего активного слоя."""
        return self.layers[self.active_layer_idx]["lines"]

    @grid_lines.setter
    def grid_lines(self, value):
        self.layers[self.active_layer_idx]["lines"] = value

    def is_line_tool(self, name):
        """Проверяет, является ли инструмент линией (3-й аргумент 'line')."""
        data = self.tools.get(name, [])
        return len(data) >= 3 and data[2] == "line"
    

    def parse_tools(self, tools_input):
        """Нормализует входящие инструменты в структуру с группами и плоский словарь."""
        if tools_input is None:
            tools_input = {
                "Основное": {
                    "Стена": ["black", []],
                    "Вода": ["blue", []],
                    "Трава": ["green", []]
                }
            }

        # Проверяем, вложенный ли словарь (с группами) или плоский
        first_val = next(iter(tools_input.values()))
        if isinstance(first_val, dict):
            self.grouped_tools = tools_input
        else:
            self.grouped_tools = {"Инструменты": tools_input}

        # Создаем плоский словарь для быстрого поиска: {tool_name: [color, props]}
        self.tools = {}
        for group_name, group_content in self.grouped_tools.items():
            for name, data in group_content.items():
                self.tools[name] = data

    def create_left_toolbar(self):
        """Создает левую панель инструментов с прокруткой и кнопкой скрытия."""
        for widget in self.left_toolbar.winfo_children():
            widget.destroy()

        # Верхняя плашка с кнопкой скрытия
        header_frame = tk.Frame(self.left_toolbar)
        header_frame.pack(fill=tk.X, pady=2)

        self.toggle_toolbar_btn = tk.Button(
            header_frame, text="◄", width=2, relief=tk.FLAT, font=("Arial", 9, "bold"),
            command=self.toggle_left_toolbar
        )
        self.toggle_toolbar_btn.pack(side=tk.RIGHT, padx=2)

        self.toolbar_title = tk.Label(header_frame, text="Инструменты", font=("Arial", 10, "bold"))
        self.toolbar_title.pack(side=tk.LEFT, padx=5)

        # Контейнер для содержимого (скрывается целиком)
        self.toolbar_content = tk.Frame(self.left_toolbar)
        self.toolbar_content.pack(fill=tk.BOTH, expand=True)

        tool_canvas = tk.Canvas(self.toolbar_content, highlightthickness=0)
        tool_scrollbar = tk.Scrollbar(self.toolbar_content, orient="vertical", command=tool_canvas.yview)
        scrollable_frame = tk.Frame(tool_canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: tool_canvas.configure(scrollregion=tool_canvas.bbox("all"))
        )

        canvas_window = tool_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        tool_canvas.bind('<Configure>', lambda e: tool_canvas.itemconfig(canvas_window, width=e.width))
        tool_canvas.configure(yscrollcommand=tool_scrollbar.set)

        tool_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tool_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_toolbar_wheel(event):
            if event.delta:
                tool_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif event.num == 4:
                tool_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                tool_canvas.yview_scroll(1, "units")

        tool_canvas.bind("<MouseWheel>", _on_toolbar_wheel)
        tool_canvas.bind("<Button-4>", _on_toolbar_wheel)
        tool_canvas.bind("<Button-5>", _on_toolbar_wheel)
        scrollable_frame.bind("<MouseWheel>", _on_toolbar_wheel)

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

            toggle_btn = tk.Button(grp_header, text="▼", width=2, relief=tk.FLAT, bg="#e0e0e0", font=("Arial", 8))
            toggle_btn.config(command=lambda b=toggle_btn, f=content_frame: toggle_group(b, f))
            toggle_btn.pack(side=tk.LEFT)

            group_lbl = tk.Label(grp_header, text=group_name, font=("Arial", 9, "bold"), bg="#e0e0e0", anchor="w")
            group_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

            for name, data in items.items():
                color = data[0]
                props = data[1]
                btn = tk.Button(
                    content_frame, 
                    text=name, 
                    bg=color,
                    fg="white" if color.lower() in ["black", "blue", "red", "green", "#000000", "#1e90ff", "#2c3e50", "#c0392b"] else "black",
                    anchor="w",
                    command=lambda n=name, c=color, p=props: self.select_tool(n, c, p)
                )
                btn.pack(fill=tk.X, padx=2, pady=1)

    def toggle_left_toolbar(self):
        """Переключает видимость содержимого левой панели."""
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
        """Создает верхнее системное меню приложения."""
        self.menubar = tk.Menu(self.root)
        
        # Меню Файл
        file_menu = tk.Menu(self.menubar, tearoff=0)
        file_menu.add_command(label="Открыть", command=self.load_dictionary_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Сохранить", command=self.save_dictionary_file, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Экспорт", command=self.export_data, accelerator="Ctrl+E")
        self.menubar.add_cascade(label="Файл", menu=file_menu)

        # Меню Инструменты
        tools_menu = tk.Menu(self.menubar, tearoff=0)
        tools_menu.add_command(label="Сброс камеры", command=self.reset_camera)
        self.menubar.add_cascade(label="Инструменты", menu=tools_menu)
        
        self.root.config(menu=self.menubar)

    def reset_camera(self):
        """Сбрасывает положение и зум камеры к значениям по умолчанию."""
        self.commit_floating()
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.cell_size = self.default_cell_size
        self.redraw_canvas()

    def export_data(self):
        """Вызывает внешнюю функцию экспорта с отсортированным списком слоев."""
        exported_layers = []

        processed_data = export(self.layers)
        
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
                self.is_dirty = False
                return True
            except Exception as e:
                print(f"Ошибка экспорта файла: {e}")
        return False

    def on_closing(self):
        """Обрабатывает попытку закрытия окна с проверкой несохраненных изменений."""
        if self.is_dirty:
            response = messagebox.askyesnocancel("Сохранение", "У вас есть несохраненные изменения. Сохранить перед выходом?")
            if response is True:
                if self.save_dictionary_file():
                    self.root.destroy()
            elif response is False:
                self.root.destroy()
        else:
            self.root.destroy()

    def mark_dirty(self):
        """Помечает состояние как измененное."""
        self.is_dirty = True

    def global_click_handler(self, event):
        """Снимает фокус с поля ввода, если кликнули не по нему."""
        if not isinstance(event.widget, tk.Entry):
            self.root.focus_set()

    def validate_digit(self, value):
        """Разрешает ввод только цифр или пустой строки."""
        if value == "" or value.isdigit():
            return True
        return False

    def get_contrast_color(self, hex_color):
        """Определяет контрастный цвет текста (белый или черный) по цвету фона."""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6:
            return "black"
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            return "white" if luminance < 0.5 else "black"
        except:
            return "black"

    def save_state(self):
            state = {
                "active_layer_idx": self.active_layer_idx,
                "layers": [
                    {
                        "name": l["name"], "visible": l["visible"],
                        "data": {loc: {"tool": d["tool"], "props": d["props"].copy()} for loc, d in l["data"].items()},
                        "lines": {k: {"tool": v["tool"], "props": v["props"].copy()} for k, v in l.get("lines", {}).items()}
                    } for l in self.layers
                ]
            }
            self.undo_stack.append(state)
            self.redo_stack.clear()
            if len(self.undo_stack) > 50: self.undo_stack.pop(0)
            self.mark_dirty()

    def _restore_state(self, state):
        self.active_layer_idx = state["active_layer_idx"]
        self.layers = [
            {
                "name": l["name"], "visible": l["visible"],
                "data": {loc: {"tool": d["tool"], "props": d["props"].copy()} for loc, d in l["data"].items()},
                "lines": {k: {"tool": v["tool"], "props": v["props"].copy()} for k, v in l.get("lines", {}).items()}
            } for l in state["layers"]
        ]
        self.update_right_toolbar()
        self.redraw_canvas()
    
    def undo(self, event=None):
        if not self.undo_stack:
            return
        current_state = {
            "active_layer_idx": self.active_layer_idx,
            "layers": [{"name": l["name"], "visible": l["visible"], "data": {loc: {"tool": d["tool"], "props": d["props"].copy()} for loc, d in l["data"].items()}} for l in self.layers]
        }
        self.redo_stack.append(current_state)
        self._restore_state(self.undo_stack.pop())
        self.mark_dirty()

    def redo(self, event=None):
        if not self.redo_stack:
            return
        current_state = {
            "active_layer_idx": self.active_layer_idx,
            "layers": [{"name": l["name"], "visible": l["visible"], "data": {loc: {"tool": d["tool"], "props": d["props"].copy()} for loc, d in l["data"].items()}} for l in self.layers]
        }
        self.undo_stack.append(current_state)
        self._restore_state(self.redo_stack.pop())
        self.mark_dirty()

    def add_layer(self):
        self.commit_floating()
        self.save_state()
        new_name = f"Слой {len(self.layers) + 1}"
        self.layers.append({"name": new_name, "visible": True, "data": {}, "lines": {}})
        self.active_layer_idx = len(self.layers) - 1
        self.update_right_toolbar()
        self.redraw_canvas()

    def save_dictionary_file(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if file_path:
            save_payload = {
                "layers": [
                    {
                        "name": l["name"], "visible": l["visible"],
                        "cells": {f"{c},{r}": item for (c, r), item in l["data"].items()},
                        "lines": {f"{c1},{r1};{c2},{r2}": v for ((c1, r1), (c2, r2)), v in l.get("lines", {}).items()}
                    } for l in self.layers
                ]
            }
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(save_payload, f, ensure_ascii=False, indent=4)
                self.is_dirty = False
                return True
            except Exception as e:
                print(f"Ошибка сохранения файла: {e}")
        return False

    def load_dictionary_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f: data_loaded = json.load(f)
                self.save_state()
                self.layers = []
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

                        self.layers.append({
                            "name": l_data.get("name", "Слой"),
                            "visible": l_data.get("visible", True),
                            "data": layer_dict, "lines": layer_lines
                        })
                self.active_layer_idx = 0
                self.update_right_toolbar()
                self.redraw_canvas()
                self.is_dirty = False
            except Exception as e:
                print(f"Ошибка загрузки: {e}")


    def update_right_toolbar(self):
        """Обновляет правый тулбар: панель слоев + свойства выбранного инструмента."""
        self.right_toolbar.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
        
        for widget in self.right_toolbar.winfo_children():
            widget.destroy()

        # --- БЛОК 1: Управление слоями ---
        layers_header = tk.Frame(self.right_toolbar)
        layers_header.pack(fill=tk.X, padx=5, pady=(5, 2))
        
        tk.Label(layers_header, text="Слои", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        
        # Кнопка добавления нового слоя
        add_btn = tk.Button(layers_header, text="+ Слой", font=("Arial", 8), command=self.add_layer)
        add_btn.pack(side=tk.RIGHT)

        tk.Frame(self.right_toolbar, height=1, bg="gray").pack(fill=tk.X, padx=5, pady=2)

        # Контейнер для списка слоев (отображаем от верхнего слоя к нижнему)
        layers_frame = tk.Frame(self.right_toolbar)
        layers_frame.pack(fill=tk.X, padx=5, pady=2)

        for idx in range(len(self.layers) - 1, -1, -1):
            layer = self.layers[idx]
            is_active = (idx == self.active_layer_idx)
            
            row = tk.Frame(layers_frame, bg="#d0e0f0" if is_active else "#f0f0f0", bd=1, relief=tk.RIDGE)
            row.pack(fill=tk.X, pady=1)

            # Видимость слоя (глаз)
            vis_icon = "👁" if layer["visible"] else "🙈"
            vis_btn = tk.Button(
                row, text=vis_icon, width=2, relief=tk.FLAT,
                bg="#d0e0f0" if is_active else "#f0f0f0",
                command=lambda i=idx: self.toggle_layer_visibility(i)
            )
            vis_btn.pack(side=tk.LEFT)

            # Выбор слоя активным
            name_btn = tk.Button(
                row, text=layer["name"], anchor="w", relief=tk.FLAT,
                font=("Arial", 9, "bold" if is_active else "normal"),
                bg="#d0e0f0" if is_active else "#f0f0f0",
                command=lambda i=idx: self.set_active_layer(i)
            )
            name_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

            # Перемещение слоя выше/ниже
            up_btn = tk.Button(row, text="▲", width=1, relief=tk.FLAT, command=lambda i=idx: self.move_layer(i, 1))
            up_btn.pack(side=tk.LEFT)
            
            down_btn = tk.Button(row, text="▼", width=1, relief=tk.FLAT, command=lambda i=idx: self.move_layer(i, -1))
            down_btn.pack(side=tk.LEFT)

            # Удаление слоя (если слоев больше одного)
            if len(self.layers) > 1:
                del_btn = tk.Button(row, text="✕", width=2, fg="red", relief=tk.FLAT, command=lambda i=idx: self.remove_layer(i))
                del_btn.pack(side=tk.RIGHT)

        # --- БЛОК 2: Свойства инструмента ---
        if self.current_props_list:
            tk.Frame(self.right_toolbar, height=2, bg="gray").pack(fill=tk.X, padx=5, pady=10)
            tk.Label(self.right_toolbar, text=f"Свойства: {self.current_value}", font=("Arial", 10, "bold")).pack(anchor="w", padx=5, pady=2)

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
                var.trace_add("write", lambda *args, p=prop, v=var: self.update_prop_value(p, v))

                entry = tk.Entry(row_frame, width=8, textvariable=var, validate='key', validatecommand=vcmd)
                entry.pack(side=tk.RIGHT)

    # --- Методы управления слоями ---
    def set_active_layer(self, idx):
        self.commit_floating()
        self.active_layer_idx = idx
        self.update_right_toolbar()
        self.redraw_canvas()


    def remove_layer(self, idx):
        if len(self.layers) <= 1:
            return
        self.commit_floating()
        self.save_state()
        del self.layers[idx]
        if self.active_layer_idx >= len(self.layers):
            self.active_layer_idx = len(self.layers) - 1
        self.update_right_toolbar()
        self.redraw_canvas()

    def toggle_layer_visibility(self, idx):
        self.layers[idx]["visible"] = not self.layers[idx]["visible"]
        self.update_right_toolbar()
        self.redraw_canvas()

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
            self.redraw_canvas()
        """Обновляет правый тулбар свойствами выбранного инструмента или скрывает его."""
        if not self.current_props_list:
            self.right_toolbar.pack_forget()
            return

        self.right_toolbar.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
        
        for widget in self.right_toolbar.winfo_children():
            widget.destroy()

        tk.Label(self.right_toolbar, text=f"Свойства: {self.current_value}", font=("Arial", 10, "bold")).pack(anchor="w", padx=5, pady=5)
        tk.Frame(self.right_toolbar, height=1, bg="gray").pack(fill=tk.X, padx=5, pady=2)

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
            var.trace_add("write", lambda *args, p=prop, v=var: self.update_prop_value(p, v))

            entry = tk.Entry(row_frame, width=8, textvariable=var, validate='key', validatecommand=vcmd)
            entry.pack(side=tk.RIGHT)

    def update_prop_value(self, prop_name, var):
        self.tool_prop_values[self.current_value][prop_name] = var.get()

    def create_canvas(self):
        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.destroy()
            
        self.canvas = tk.Canvas(self.canvas_frame, width=self.view_width, height=self.view_height, bg="white")
        self.canvas.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

        # События ЛКМ
        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<B1-Motion>", self.on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_release)
        
        # ПКМ (стереть)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<B3-Motion>", self.erase)
        
        # Средняя кнопка (пипетка) и движение
        self.canvas.bind("<Button-2>", self.pick_tool)
        self.canvas.bind("<Motion>", self.track_mouse)
        
        # Выделение (Ctrl + ЛКМ)
        self.canvas.bind("<Control-Button-1>", self.start_selection)
        self.canvas.bind("<Control-B1-Motion>", self.update_selection)
        
        self.redraw_canvas()

    def bind_hotkeys(self):
        # Буфер обмена и редактирование
        self.root.bind("<Control-c>", self.copy_selection)
        self.root.bind("<Control-C>", self.copy_selection)
        self.root.bind("<Control-x>", self.cut_selection)
        self.root.bind("<Control-X>", self.cut_selection)
        self.root.bind("<Control-v>", self.paste_selection)
        self.root.bind("<Control-V>", self.paste_selection)
        self.root.bind("<Delete>", self.delete_selection)
        self.root.bind("<BackSpace>", self.delete_selection)
        
        # Отмена / Повтор
        self.root.bind("<Control-z>", self.undo)
        self.root.bind("<Control-Z>", self.undo)
        self.root.bind("<Control-Shift-z>", self.redo)
        self.root.bind("<Control-Shift-Z>", self.redo)
        
        # Файловые операции
        self.root.bind("<Control-s>", lambda e: self.save_dictionary_file())
        self.root.bind("<Control-S>", lambda e: self.save_dictionary_file())
        self.root.bind("<Control-o>", lambda e: self.load_dictionary_file())
        self.root.bind("<Control-O>", lambda e: self.load_dictionary_file())
        self.root.bind("<Control-e>", lambda e: self.export_data())
        self.root.bind("<Control-E>", lambda e: self.export_data())
        
        # WASD камера
        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)
        
        # Зум колесиком мыши (Ctrl + колесико)
        self.root.bind("<Control-MouseWheel>", self.zoom_wheel)  
        self.root.bind("<Control-Button-4>", lambda e: self.zoom_in())   
        self.root.bind("<Control-Button-5>", lambda e: self.zoom_out())  

    def on_key_press(self, event):
        if isinstance(self.root.focus_get(), tk.Entry):
            return
        key = event.keysym.lower()
        if key in ['w', 'a', 's', 'd']:
            self.pressed_keys.add(key)
            if not self.is_moving:
                self.is_moving = True
                self.animate_camera()

    def on_key_release(self, event):
        key = event.keysym.lower()
        if key in ['w', 'a', 's', 'd']:
            if key in self.pressed_keys:
                self.pressed_keys.remove(key)

    def animate_camera(self):
        """Плавная анимация движения с масштабируемой скоростью от зума."""
        # Чем меньше cell_size (зум дальше), тем быстрее движется камера по координатам, 
        # чтобы скорость на экране оставалась визуально постоянной.
        base_speed = 350.0  # Коэффициент экранных пикселей в секунду
        max_speed = max(min(base_speed / self.cell_size, self.max_speed), self.min_speed)
        
        target_vx = 0.0
        target_vy = 0.0
        
        if 'w' in self.pressed_keys:
            target_vy -= max_speed
        if 's' in self.pressed_keys:
            target_vy += max_speed
        if 'a' in self.pressed_keys:
            target_vx -= max_speed
        if 'd' in self.pressed_keys:
            target_vx += max_speed

        # Плавная интерполяция скорости (lerp)
        self.cam_vx += (target_vx - self.cam_vx) * 0.25
        self.cam_vy += (target_vy - self.cam_vy) * 0.25

        if abs(self.cam_vx) > 0.01 or abs(self.cam_vy) > 0.01 or self.pressed_keys:
            self.cam_x += self.cam_vx
            self.cam_y += self.cam_vy
            self.redraw_canvas()
            self.root.after(16, self.animate_camera)  # ~60 FPS
        else:
            self.cam_vx = 0.0
            self.cam_vy = 0.0
            self.is_moving = False

    def zoom_in(self):
        if self.cell_size < self.zoom_in_limit:
            self.commit_floating()
            self.cell_size *= self.zoom_speed
            self.redraw_canvas()

    def zoom_out(self):
        if self.cell_size > self.zoom_out_limit:
            self.commit_floating()
            self.cell_size /= self.zoom_speed
            self.redraw_canvas()

    def zoom_wheel(self, event):
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def select_tool(self, name, color, props):
        self.commit_floating()
        self.current_value = name
        self.current_color = color
        self.current_props_list = props
        self.update_right_toolbar()

    def track_mouse(self, event):
        world_x = event.x + self.cam_x
        world_y = event.y + self.cam_y
        self.mouse_col = int(world_x // self.cell_size)
        self.mouse_row = int(world_y // self.cell_size)
        
        self.status_bar.config(text=f"Координаты: ({self.mouse_col}, {self.mouse_row})")

        # ИСПРАВЛЕНИЕ: Если вставляются/перемещаются ячейки ИЛИ линии, обновляем их позицию за курсором
        if self.floating_data is not None or self.floating_lines is not None:
            # Если мы не тянем выделение зажатой кнопкой, а находимся в режиме вставки (пасты)
            if not getattr(self, 'is_moving_selection', False):
                self.floating_offset = (self.mouse_col, self.mouse_row)
                self.redraw_canvas()
    
    def is_click_on_selection(self, col, row):
        """Проверяет, попал ли клик на выделенную или плавающую область."""
        if self.floating_data:
            rel_c = col - self.floating_offset[0]
            rel_r = row - self.floating_offset[1]
            return (rel_c, rel_r) in self.floating_data
        elif self.selection:
            min_c, min_r, max_c, max_r = self.selection
            return min_c <= col <= max_c and min_r <= row <= max_r
        return False

    def on_left_click(self, event):
        if (event.state & 0x0001) or (event.state & 0x0004): 
            return
            
        # ИСПРАВЛЕНИЕ: Проверяем и ячейки, и линии. Если что-то плавает — фиксируем кликом
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
                has_elements = any((c, r) in self.grid_data for r in range(min_r, max_r + 1) for c in range(min_c, max_c + 1))
                has_lines = any((min_c <= c1 <= max_c and min_r <= r1 <= max_r) and (min_c <= c2 <= max_c and min_r <= r2 <= max_r) for (c1, r1), (c2, r2) in self.grid_lines.keys())
                
                if has_elements or has_lines:
                    self.save_state()
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
                    if (min_c <= c1 <= max_c and min_r <= r1 <= max_r) and (min_c <= c2 <= max_c and min_r <= r2 <= max_r):
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
                self.redraw_canvas()

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
        if (event.state & 0x0001) or (event.state & 0x0004):
            return
            
        # Динамическая отрисовка протягиваемой линии
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
            
            # Рисуем кружок в точке старта
            r_start = 4
            self.canvas.create_oval(x1 - r_start, y1 - r_start, x1 + r_start, y1 + r_start, fill=color, outline=color, tags="temp_line")
            # Рисуем линию со стрелкой на конце
            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=3, dash=(4,4), arrow=tk.LAST, tags="temp_line")
            return

        if self.is_moving_selection:
            self.during_move(event)
        else:
            self.paint(event)

    def on_left_release(self, event):
        # Сохранение линии при отпускании мыши
        if getattr(self, 'line_start', None) is not None:
            self.canvas.delete("temp_line")
            world_x = event.x + self.cam_x
            world_y = event.y + self.cam_y
            col = int(world_x // self.cell_size)
            row = int(world_y // self.cell_size)
            
            if (col, row) != self.line_start:
                self.save_state()
                props = {p: self.tool_prop_values[self.current_value].get(p, "0") for p in self.current_props_list}
                start, end = self.line_start, (col, row)
                
                # Направление (start -> end) теперь строго сохраняется
                self.grid_lines[(start, end)] = {"tool": self.current_value, "props": props}
                self.mark_dirty()
                self.redraw_canvas()
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
        
        # Стираем саму клетку
        if location in self.grid_data:
            del self.grid_data[location]
            modified = True
            
        # Стираем все линии, которые подключены к этой клетке
        lines_to_delete = [k for k in self.grid_lines if k[0] == location or k[1] == location]
        for k in lines_to_delete:
            del self.grid_lines[k]
            modified = True
            
        if self.floating_data:
            rel_c, rel_r = col - self.floating_offset[0], row - self.floating_offset[1]
            if (rel_c, rel_r) in self.floating_data:
                del self.floating_data[(rel_c, rel_r)]
                modified = True
                
        if modified:
            self.mark_dirty()
            self.redraw_canvas()

    def paint(self, event):
        world_x = event.x + self.cam_x
        world_y = event.y + self.cam_y
        col = int(world_x // self.cell_size)
        row = int(world_y // self.cell_size)
        
        location = (col, row)
        props_snapshot = {p: self.tool_prop_values[self.current_value].get(p, "0") for p in self.current_props_list}
        new_item = {"tool": self.current_value, "props": props_snapshot}
        if self.grid_data.get(location) != new_item:
            self.grid_data[location] = new_item
            self.mark_dirty()
            self.redraw_canvas()

    def on_right_click(self, event):
        self.save_state()
        self.erase(event)

    def pick_tool(self, event):
        world_x = event.x + self.cam_x
        world_y = event.y + self.cam_y
        col = int(world_x // self.cell_size)
        row = int(world_y // self.cell_size)
        
        location = (col, row)
        if location in self.grid_data:
            item = self.grid_data[location]
            tool_name = item["tool"]
            if tool_name in self.tools:
                color, props = self.tools[tool_name]
                self.tool_prop_values[tool_name] = item["props"].copy()
                self.select_tool(tool_name, color, props)

    def start_selection(self, event):
        self.commit_floating()
        world_x = event.x + self.cam_x
        world_y = event.y + self.cam_y
        col = int(world_x // self.cell_size)
        row = int(world_y // self.cell_size)
        self.sel_start = (col, row)
        self.sel_end = (col, row)
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
        min_c, min_r, max_c, max_r = None, None, None, None
        
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
                x1, y1, x2, y2, outline="#2980b9", width=2, dash=(4, 4), tag="selection_rect"
            )
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
        
        """
        # 1. Отрисовка фоновой пустой сетки
        if draw_outline:
            for r in range(start_row, end_row):
                for c in range(start_col, end_col):
                    x1 = c * self.cell_size - self.cam_x
                    y1 = r * self.cell_size - self.cam_y
                    x2 = x1 + self.cell_size
                    y2 = y1 + self.cell_size
                    self.canvas.create_rectangle(x1, y1, x2, y2, fill="white", outline=outline_color)

        """
        already_drew = set()
        # ЗАМЕНИТЬ блок отрисовки слоев (пункт 2) на этот:
        # 2. Послойная отрисовка закрашенных ячеек и линий
        for layer in reversed(self.layers):
            if not layer["visible"]:
                continue
            
            # Отрисовка клеток
            for loc, item in layer["data"].items():
                c, r = loc
                if loc not in already_drew:
                    if start_col <= c < end_col and start_row <= r < end_row:
                        x1 = c * self.cell_size - self.cam_x
                        y1 = r * self.cell_size - self.cam_y
                        x2 = x1 + self.cell_size
                        y2 = y1 + self.cell_size
                        tool_name = item["tool"]
                        #data = tuple(item["props"].values())
                        color = self.tools.get(tool_name, ["white", []])[0]
                        self.canvas.create_rectangle(x1, y1, x2, y2, fill=color)
                        already_drew.add(loc)
                        #if self.cell_size >= self.min_cell_size_text:
                        #    self.canvas.create_text(x1 + self.cell_size/2, y1 + self.cell_size/2, text=f'{tool_name}\n{data}', fill=self.get_contrast_color(color), font=("Arial", int(self.cell_size/len(tool_name)), "bold"))

            if self.cell_size >= self.min_cell_size_text:
            # Отрисовка линий (связей)
                for (start_loc, end_loc), item in layer.get("lines", {}).items():
                    c1, r1 = start_loc
                    c2, r2 = end_loc
                    
                    # Координаты центров клеток
                    x1 = c1 * self.cell_size - self.cam_x + self.cell_size / 2
                    y1 = r1 * self.cell_size - self.cam_y + self.cell_size / 2
                    x2 = c2 * self.cell_size - self.cam_x + self.cell_size / 2
                    y2 = r2 * self.cell_size - self.cam_y + self.cell_size / 2
                    
                    tool_name = item["tool"]
                    color = self.tools.get(tool_name, ["black"])[0]
                    line_width = max(2, int(self.cell_size / 8))
                    
                    # 1. Кружок в начале линии (Старт)
                    r_start = line_width * 1.5
                    self.canvas.create_oval(x1 - r_start, y1 - r_start, x1 + r_start, y1 + r_start, fill=color, outline=color)

                    # 2. Сама линия со стрелкой в конце (Конец)
                    # Рассчитываем размер стрелки в зависимости от зума (размера клетки)
                    arrow_size = max(8, int(self.cell_size / 4))
                    arrow_shape = (arrow_size, arrow_size + 2, max(3, arrow_size // 3))
                    
                    self.canvas.create_line(
                        x1, y1, x2, y2, 
                        fill=color, 
                        width=line_width, 
                        arrow=tk.LAST, 
                        arrowshape=arrow_shape
                    )


        # 3. Рендер маркера точки (0, 0)
        if start_col <= 0 < end_col and start_row <= 0 < end_row:
            ox1 = 0 * self.cell_size - self.cam_x
            oy1 = 0 * self.cell_size - self.cam_y
            ox2 = ox1 + self.cell_size
            oy2 = oy1 + self.cell_size
            self.canvas.create_rectangle(ox1, oy1, ox2, oy2, outline="#e74c3c", width=3, dash=(3, 3))
            if self.cell_size >= self.min_cell_size_marker:
                self.canvas.create_text(ox1 + 5, oy1 + 5, text="(0,0)", anchor="nw", fill="#e74c3c", font=("Arial", 8, "bold"))
                
        # 4. Отрисовка плавающих данных (вставка / перемещение)
        if self.floating_data:
            for (rel_c, rel_r), item in self.floating_data.items():
                abs_c = self.floating_offset[0] + rel_c
                abs_r = self.floating_offset[1] + rel_r
                if start_col <= abs_c < end_col and start_row <= abs_r < end_row:
                    x1 = abs_c * self.cell_size - self.cam_x
                    y1 = abs_r * self.cell_size - self.cam_y
                    x2 = x1 + self.cell_size
                    y2 = y1 + self.cell_size
                    tool_name = item["tool"]
                    color = self.tools.get(tool_name, ["white", []])[0]
                    self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline=outline_color)
                    
                    if self.cell_size >= self.min_cell_size_text:
                        text_x = x1 + self.cell_size / 2
                        text_y = y1 + self.cell_size / 2
                        text_color = self.get_contrast_color(color)
                        font_size = max(8, int(self.cell_size / 5))
                        self.canvas.create_text(text_x, text_y, text=tool_name, fill=text_color, font=("Arial", font_size, "bold"))
                    
        # Отрисовка плавающих линий (вставка / перемещение)
        if self.floating_lines:
            for (rel_start, rel_end), item in self.floating_lines.items():
                abs_start = (self.floating_offset[0] + rel_start[0], self.floating_offset[1] + rel_start[1])
                abs_end = (self.floating_offset[0] + rel_end[0], self.floating_offset[1] + rel_end[1])
                c1, r1 = abs_start
                c2, r2 = abs_end
                
                if (start_col <= c1 < end_col and start_row <= r1 < end_row) or (start_col <= c2 < end_col and start_row <= r2 < end_row):
                    x1 = c1 * self.cell_size - self.cam_x + self.cell_size / 2
                    y1 = r1 * self.cell_size - self.cam_y + self.cell_size / 2
                    x2 = c2 * self.cell_size - self.cam_x + self.cell_size / 2
                    y2 = r2 * self.cell_size - self.cam_y + self.cell_size / 2
                    
                    tool_name = item["tool"]
                    color = self.tools.get(tool_name, ["black"])[0]
                    line_width = max(2, int(self.cell_size / 8))
                    
                    r_start = line_width * 1.5
                    self.canvas.create_oval(x1 - r_start, y1 - r_start, x1 + r_start, y1 + r_start, fill=color, outline=color)
                    
                    arrow_size = max(8, int(self.cell_size / 4))
                    arrow_shape = (arrow_size, arrow_size + 2, max(3, arrow_size // 3))
                    
                    self.canvas.create_line(
                        x1, y1, x2, y2, 
                        fill=color, 
                        width=line_width, 
                        arrow=tk.LAST, 
                        arrowshape=arrow_shape
                    )
                    
                    if self.cell_size >= self.min_cell_size_text:
                        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                        self.canvas.create_text(mx, my, text=tool_name, fill=color, font=("Arial", max(8, int(self.cell_size/6)), "bold"))
        self.update_selection_rect_visual()

    def copy_selection(self, event=None):
        if self.floating_data or self.floating_lines:
            self.clipboard = {
                "cells": {k: {"tool": v["tool"], "props": v["props"].copy()} for k, v in (self.floating_data or {}).items()},
                "lines": {k: {"tool": v["tool"], "props": v["props"].copy()} for k, v in (self.floating_lines or {}).items()}
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
                # Копируем линии, у которых оба конца находятся внутри прямоугольника выделения
                if (min_c <= c1 <= max_c and min_r <= r1 <= max_r) and (min_c <= c2 <= max_c and min_r <= r2 <= max_r):
                    rel_start = (c1 - min_c, r1 - min_r)
                    rel_end = (c2 - min_c, r2 - min_r)
                    lines_clip[(rel_start, rel_end)] = {
                        "tool": item["tool"],
                        "props": item["props"].copy()
                    }
            
            self.clipboard = {"cells": cells_clip, "lines": lines_clip}
        print("Выделение (ячейки и линии) скопировано.")

    def cut_selection(self, event=None):
        if not self.selection and not self.floating_data and not self.floating_lines:
            return
        self.copy_selection()
        if self.selection:
            min_c, min_r, max_c, max_r = self.selection
            has_elements = any((c, r) in self.grid_data for r in range(min_r, max_r + 1) for c in range(min_c, max_c + 1))
            has_lines = any((min_c <= c1 <= max_c and min_r <= r1 <= max_r) and (min_c <= c2 <= max_c and min_r <= r2 <= max_r) for (c1, r1), (c2, r2) in self.grid_lines.keys())
            
            if has_elements or has_lines:
                self.save_state()
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
                    if (min_c <= c1 <= max_c and min_r <= r1 <= max_r) and (min_c <= c2 <= max_c and min_r <= r2 <= max_r):
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
                self.redraw_canvas()
        print("Выделение вырезано.")

    def paste_selection(self, event=None):
        if not self.clipboard:
            return
        self.commit_floating()
        self.floating_data = {k: {"tool": v["tool"], "props": v["props"].copy()} for k, v in self.clipboard.get("cells", {}).items()}
        self.floating_lines = {k: {"tool": v["tool"], "props": v["props"].copy()} for k, v in self.clipboard.get("lines", {}).items()}
        self.floating_offset = (self.mouse_col, self.mouse_row)
        self.mark_dirty()
        self.redraw_canvas()
        print("Вставлено в режиме выделения.")

    def delete_selection(self, event=None):
        if self.floating_data or self.floating_lines:
            self.save_state()
            self.floating_data = None
            self.floating_lines = None
            self.selection = None
            if self.sel_rect_id:
                self.canvas.delete(self.sel_rect_id)
                self.sel_rect_id = None
            self.mark_dirty()
            self.redraw_canvas()
        elif self.selection:
            min_c, min_r, max_c, max_r = self.selection
            has_elements = any((c, r) in self.grid_data for r in range(min_r, max_r + 1) for c in range(min_c, max_c + 1))
            has_lines = any((min_c <= c1 <= max_c and min_r <= r1 <= max_r) and (min_c <= c2 <= max_c and min_r <= r2 <= max_r) for (c1, r1), (c2, r2) in self.grid_lines.keys())
            
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
                    if (min_c <= c1 <= max_c and min_r <= r1 <= max_r) and (min_c <= c2 <= max_c and min_r <= r2 <= max_r):
                        lines_to_delete.append((start_loc, end_loc))
                for k in lines_to_delete:
                    del self.grid_lines[k]
                    
                self.commit_floating()
                self.mark_dirty()
        print("Удалено.")

    def commit_floating(self):
        has_changed = False
        if self.floating_data:
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
            if not has_changed:
                self.save_state()
            for (rel_start, rel_end), item in self.floating_lines.items():
                abs_start = (self.floating_offset[0] + rel_start[0], self.floating_offset[1] + rel_start[1])
                abs_end = (self.floating_offset[0] + rel_end[0], self.floating_offset[1] + rel_end[1])
                self.grid_lines[(abs_start, abs_end)] = {
                    "tool": item["tool"],
                    "props": item["props"].copy()
                }
            self.floating_lines = None
            has_changed = True

        if has_changed:
            self.mark_dirty()
            
        self.selection = None
        if self.sel_rect_id:
            self.canvas.delete(self.sel_rect_id)
            self.sel_rect_id = None
        self.redraw_canvas()


    def during_move(self, event):
        if self.is_moving_selection and (self.floating_data is not None or self.floating_lines is not None):
            world_x = event.x + self.cam_x
            world_y = event.y + self.cam_y
            col = int(world_x // self.cell_size)
            row = int(world_y // self.cell_size)
            
            dx = col - self.move_start_mouse[0]
            dy = row - self.move_start_mouse[1]
            
            self.floating_offset = (self.initial_offset[0] + dx, self.initial_offset[1] + dy)
            self.redraw_canvas()


from auto_arras.config import EDITOR_TOOLS, EDITOR_TOOL_TO_ID, EDITOR_TOOL_TO_GROUP

def export(exported_layers):
    print(f'ecp{exported_layers}')
    ret = []
    for layer in exported_layers:
        lines = layer['lines']
        layer = layer['data']
        print(layer)
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
                            ret.append(f"wall_type {pos[0]} {pos[1]} {EDITOR_TOOL_TO_ID[tool]}")
                        else:
                            ret.append(f"type_wall {pos[0]} {pos[1]} {EDITOR_TOOL_TO_ID[tool]}")
                case "OTHER":
                    if tool == "POLY":
                        if props["CHANGE TYPE"] == '0':
                            ret.append(f"polygon {pos[0]} {pos[1]} {props["CLASS"]} {props["SIZE"]} {props["TIER"]}")
                        else:
                            ret.append(f"polygon_type {pos[0]} {pos[1]} {props["CLASS"]} {props["SIZE"]} {props["TIER"]}")
        for poses, data in lines.items():
            tool = data['tool']
            ret.append(f"joint {poses[0][0]} {poses[0][1]} {poses[1][0]} {poses[1][1]} {EDITOR_TOOL_TO_ID[tool]}")
    ret = '\n'.join(ret)
    return ret
    

if __name__ == "__main__":
    root = tk.Tk()
    
    # ПРИМЕР: Создаем собственный словарь инструментов в формате {имя: цвет}
    my_custom_tools = EDITOR_TOOLS
    
    for group, tools in EDITOR_TOOLS.items():
        for name, tool in tools.items():
            col = tool[0]
            try:
                props = tool[1:]
            except IndexError:
                props = [list(),]
            if len(props) == 0:
                props = [[]]
            if group in ["WALLS", "OTHER"]:
                props[0].append("CHANGE TYPE")
            r, g, b, a = col
            print(*props)
            my_custom_tools[group][name] = [f"#{b:02x}{g:02x}{r:02x}", *props]
    print(f"{my_custom_tools=}")
    print(f"{EDITOR_TOOL_TO_ID=}")
    
    # Передаем наш словарь в параметр `tools`
    app = GridApp(
        root, 
        cell_size=25, 
        tools=my_custom_tools,
        min_cell_size_grid=25,
        min_cell_size_text=18,
        min_cell_size_marker=20
    )
    
    root.resizable(False, False)
    root.mainloop()