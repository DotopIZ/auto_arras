def parse_wall_list(wl):
    wl = [(item[2], item[1], item[0], item[3]) for item in wl]
    wl.append((0, 0, 0, 0))

    wl_to_index = {}

    return wl, wl_to_index