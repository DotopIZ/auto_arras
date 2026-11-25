"""Локализация редактора схематик."""


TRANSLATIONS = {
    "ru": {
        "app_title": "Редактор схематик arras.io",
        "menu_file": "Файл",
        "menu_new": "Новый",
        "menu_open": "Открыть",
        "menu_save": "Сохранить",
        "menu_export": "Экспорт",
        "menu_edit": "Правка",
        "menu_undo": "Отменить",
        "menu_redo": "Повторить",
        "menu_cut": "Вырезать",
        "menu_copy": "Копировать",
        "menu_paste": "Вставить",
        "menu_delete": "Удалить",
        "menu_select_all": "Выделить всё",
        "menu_deselect": "Снять выделение",
        "menu_layers": "Слои",
        "menu_add_layer": "Добавить слой",
        "menu_remove_layer": "Удалить активный слой",
        "menu_tools": "Инструменты",
        "menu_reset_camera": "Сброс камеры",
        "menu_help": "Справка",
        "menu_hotkeys": "Горячие клавиши",
        "menu_language": "Язык",
        "lang_ru": "Русский",
        "lang_en": "English",
        "toolbar_tools": "Инструменты",
        "toolbar_layers": "Слои",
        "toolbar_add_layer": "+ Слой",
        "toolbar_props": "Свойства: {}",
        "status_bar": "Координаты: ({}, {}) | Масштаб: {}%",
        "msg_new_title": "Новая схематика",
        "msg_new_text": "Есть несохранённые изменения. Сохранить их перед созданием новой схематики?",
        "msg_del_layer_title": "Удаление слоя",
        "msg_del_layer_text": "Удалить слой '{}'?",
        "msg_last_layer_text": "Нельзя удалить единственный слой.",
        "msg_exit_title": "Сохранение",
        "msg_exit_text": "У вас есть несохранённые изменения. Сохранить перед выходом?",
        "msg_export_err_title": "Ошибка экспорта",
        "msg_export_prep_err": "Не удалось подготовить данные: {}",
        "msg_export_write_err": "Ошибка записи файла: {}",
        "msg_export_success": "Данные успешно экспортированы в {}",
        "msg_save_err_title": "Ошибка сохранения",
        "msg_save_err": "Не удалось сохранить: {}",
        "msg_load_err_title": "Ошибка загрузки",
        "msg_load_err": "Не удалось загрузить: {}",
        "rename_title": "Переименование слоя",
        "rename_prompt": "Новое имя слоя:",
        "save_dialog_title": "Сохранить проект",
        "open_dialog_title": "Открыть проект",
        "export_dialog_title": "Экспорт схемы",
        "help_title": "Справка — горячие клавиши",
        "help_close": "Закрыть",
        "help_text": (
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
            "  Alt+ЛКМ / I       — Пипетка\n"
            "  Клик по выделению — Перетащить\n"
            "  Esc               — Отменить линию / перенос / выделение\n\n"
            "СЛОИ\n"
            "  [ / ]             — Предыдущий / Следующий слой\n"
            "  Ctrl+Tab / Ctrl+Shift+Tab — То же\n"
            "  Двойной клик по имени — Переименовать слой\n"
            "  ПКМ по глазу      — Изолировать слой\n\n"
            "  F1                — Эта справка"
        ),
        "menu_paste_game": "Вставить в arras.io...",
        "paste_dialog_title": "Вставка в arras.io",
        "paste_fld_arena": "Размер арены",
        "paste_fld_lvl": "Уровень (0-45)",
        "paste_fld_tank": "Танк",
        "paste_fld_interval": "Интервал нажатия (с)",
        "paste_fld_delay": "Задержка перед стартом (с)",
        "paste_fld_radius": "Радиус поиска сетки (px)",
        "paste_fld_snap_offset": "Смещение привязки",
        "paste_bool_snap": "Привязать к сетке",
        "paste_bool_anchor": "Якорь по сетке",
        "paste_bool_warning": "Показывать предупреждение",
        "paste_btn_ok": "Вставить",
        "paste_btn_cancel": "Отмена",
        "paste_err_title": "Ошибка",
        "paste_err_field": "Неверное значение поля '{}': {}",
        "paste_warn_title": "Внимание",
        "paste_warn_text": (
            "Вставка начнётся через {delay:.1f} с.\n\n"
            "Перед этим убедитесь, что:\n"
            "  • arras.io открыт в полноэкранном режиме\n"
            "  • включено принудительное соотношение 16:9 (Settings → Secrets)\n"
            "  • у танка стандартный зум\n"
            "  • выбран танк '{tank}' и уровень {lvl}"
        ),
        "paste_lbl_file": "Файл шаблона",
        "paste_btn_browse": "Обзор…",
        "paste_use_current": "Использовать текущую схему",
        "paste_filetype_txt": "Текстовые файлы",
        "paste_filetype_all": "Все файлы",
        "paste_err_no_file": "Файл не выбран.",
        "paste_err_file_not_found": "Файл не найден: {}",
        "paste_err_read_file": "Не удалось прочитать файл: {}",
        "paste_err_empty": "Шаблон пуст.",
    },
    "en": {
        "app_title": "Arras.io schematic editor",
        "menu_file": "File",
        "menu_new": "New",
        "menu_open": "Open",
        "menu_save": "Save",
        "menu_export": "Export",
        "menu_edit": "Edit",
        "menu_undo": "Undo",
        "menu_redo": "Redo",
        "menu_cut": "Cut",
        "menu_copy": "Copy",
        "menu_paste": "Paste",
        "menu_delete": "Delete",
        "menu_select_all": "Select all",
        "menu_deselect": "Deselect",
        "menu_layers": "Layers",
        "menu_add_layer": "Add layer",
        "menu_remove_layer": "Remove active layer",
        "menu_tools": "Tools",
        "menu_reset_camera": "Reset camera",
        "menu_help": "Help",
        "menu_hotkeys": "Hotkeys",
        "menu_language": "Language",
        "lang_ru": "Русский",
        "lang_en": "English",
        "toolbar_tools": "Tools",
        "toolbar_layers": "Layers",
        "toolbar_add_layer": "+ Layer",
        "toolbar_props": "Properties: {}",
        "status_bar": "Coords: ({}, {}) | Zoom: {}%",
        "msg_new_title": "New schematic",
        "msg_new_text": "You have unsaved changes. Save them before creating a new schematic?",
        "msg_del_layer_title": "Delete layer",
        "msg_del_layer_text": "Delete layer '{}'?",
        "msg_last_layer_text": "Cannot delete the only layer.",
        "msg_exit_title": "Save",
        "msg_exit_text": "You have unsaved changes. Save before exit?",
        "msg_export_err_title": "Export error",
        "msg_export_prep_err": "Could not prepare data: {}",
        "msg_export_write_err": "Could not write file: {}",
        "msg_export_success": "Data exported to {}",
        "msg_save_err_title": "Save error",
        "msg_save_err": "Could not save: {}",
        "msg_load_err_title": "Load error",
        "msg_load_err": "Could not load: {}",
        "rename_title": "Rename layer",
        "rename_prompt": "New layer name:",
        "save_dialog_title": "Save project",
        "open_dialog_title": "Open project",
        "export_dialog_title": "Export schematic",
        "help_title": "Help — hotkeys",
        "help_close": "Close",
        "help_text": (
            "HOTKEYS\n"
            "─────────────────────────────\n"
            "FILE\n"
            "  Ctrl+N            — New schematic\n"
            "  Ctrl+O            — Open\n"
            "  Ctrl+S            — Save\n"
            "  Ctrl+E            — Export\n\n"
            "EDIT\n"
            "  Ctrl+Z            — Undo\n"
            "  Ctrl+Y / Ctrl+Shift+Z — Redo\n"
            "  Ctrl+C / Ctrl+X / Ctrl+V — Copy / Cut / Paste\n"
            "  Ctrl+A            — Select all\n"
            "  Ctrl+D / Esc      — Deselect\n"
            "  Delete / Backspace — Delete selection\n\n"
            "CAMERA\n"
            "  Mouse wheel       — Zoom (at cursor)\n"
            "  + / -             — Zoom\n"
            "  MMB + drag        — Pan\n"
            "  Space + drag      — Pan\n"
            "  WASD              — Camera move\n"
            "  Home / Ctrl+0     — Reset camera\n\n"
            "TOOLS\n"
            "  LMB               — Paint\n"
            "  RMB               — Erase\n"
            "  Shift+LMB (drag)  — Rect selection\n"
            "  Ctrl+LMB (drag)   — Rect selection\n"
            "  Alt+LMB / I       — Eyedropper\n"
            "  Click selection   — Drag\n"
            "  Esc               — Cancel line / move / selection\n\n"
            "LAYERS\n"
            "  [ / ]             — Prev / Next layer\n"
            "  Ctrl+Tab / Ctrl+Shift+Tab — Same\n"
            "  Double-click name — Rename layer\n"
            "  RMB on eye        — Solo layer\n\n"
            "  F1                — This help"
        ),
        "menu_paste_game": "Paste into arras.io...",
        "paste_dialog_title": "Paste into arras.io",
        "paste_fld_arena": "Arena size",
        "paste_fld_lvl": "Level (0-45)",
        "paste_fld_tank": "Tank",
        "paste_fld_interval": "Press interval (s)",
        "paste_fld_delay": "Delay before start (s)",
        "paste_fld_radius": "Grid search radius (px)",
        "paste_fld_snap_offset": "Snap offset",
        "paste_bool_snap": "Snap to grid",
        "paste_bool_anchor": "Anchor grid",
        "paste_bool_warning": "Show warning",
        "paste_btn_ok": "Paste",
        "paste_btn_cancel": "Cancel",
        "paste_err_title": "Error",
        "paste_err_field": "Invalid value for '{}': {}",
        "paste_warn_title": "Warning",
        "paste_warn_text": (
            "Paste starts in {delay:.1f} s.\n\n"
            "Before that, make sure:\n"
            "  • arras.io is in fullscreen mode\n"
            "  • forced 16:9 aspect ratio is on (Settings → Secrets)\n"
            "  • tank zoom is default\n"
            "  • tank '{tank}' and level {lvl} are selected"
        ),
        "paste_lbl_file": "Template file",
        "paste_btn_browse": "Browse…",
        "paste_use_current": "Use current schematic",
        "paste_filetype_txt": "Text files",
        "paste_filetype_all": "All files",
        "paste_err_no_file": "No file selected.",
        "paste_err_file_not_found": "File not found: {}",
        "paste_err_read_file": "Failed to read file: {}",
        "paste_err_empty": "Template is empty.",
    },
}


def translate(lang, key, *args, **kwargs):
    """Перевод по ключу с форматированием (позиционным или именованным)."""
    table = TRANSLATIONS.get(lang) or TRANSLATIONS["en"]
    template = table.get(key, key)
    if args or kwargs:
        return template.format(*args, **kwargs)
    return template