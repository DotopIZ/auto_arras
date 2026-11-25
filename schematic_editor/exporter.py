"""Экспорт схематик в текстовый формат arras.io."""
from auto_arras.config import EDITOR_TOOL_TO_GROUP, EDITOR_TOOL_TO_ID
from schematic_editor.ui_helpers import safe_int


def get_wall_end_pos(x, y, size):
    return x + size, y + size


def _prop_str(props, key, default="0"):
    """Значение prop-а как строка (пустая строка трактуется как default)."""
    return str(props.get(key, default) or default)


def export(exported_layers):
    ret = []
    for idx, layer in enumerate(exported_layers):
        ret.append(f":layer {idx}")
        for pos, data in layer['data'].items():
            tool = data['tool']
            props = data['props']
            group = EDITOR_TOOL_TO_GROUP.get(tool)
            if group is None:
                continue

            if group == "WALLS":
                toolid = EDITOR_TOOL_TO_ID.get(tool)
                if toolid is None:
                    continue

                change = _prop_str(props, "CHANGE TYPE")
                place = 1
                if change == '1':
                    place = 0
                elif change == '2':
                    toolid = 'None'

                size = safe_int(_prop_str(props, "SIZE"), 0)
                x2, y2 = 'None', 'None'
                if size != 0:
                    x2, y2 = get_wall_end_pos(pos[0], pos[1], size)

                color = props.get("COLOR", 'None')
                if color and color != 'None':
                    try:
                        color = int(color) - 1
                    except (ValueError, TypeError):
                        color = 'None'

                ret.append(
                    f'tcwall place {place} x1 {pos[0]} y1 {pos[1]} '
                    f'x2 {x2} y2 {y2} type {toolid} color {color}'
                )

            elif group == "OTHER" and tool == "POLY":
                klass = _prop_str(props, "CLASS")
                size = _prop_str(props, "SIZE")
                tier = _prop_str(props, "TIER")
                if _prop_str(props, "CHANGE TYPE") == '0':
                    ret.append(f"polygon {pos[0]} {pos[1]} {klass} {size} {tier}")
                else:
                    ret.append(f"polygon_type {pos[0]} {pos[1]} {klass} {size} {tier}")

            if props.get("TEAM") == '1':
                ret.append("team")

        for poses, data in layer.get('lines', {}).items():
            tool = data['tool']
            group = EDITOR_TOOL_TO_GROUP.get(tool)
            tool_id = EDITOR_TOOL_TO_ID.get(tool)
            if tool_id is None:
                continue
            if group == "JOINTS":
                ret.append(
                    f"joint {poses[0][0]} {poses[0][1]} "
                    f"{poses[1][0]} {poses[1][1]} {tool_id}"
                )
            elif group == "ACTIONS":
                ret.append(f"{tool.lower()} x1 {poses[0][0]} y1 {poses[0][1]} x2 {poses[1][0]} y2 {poses[1][1]}")
    return '\n'.join(ret)