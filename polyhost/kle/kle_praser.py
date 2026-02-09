

def parse_kle(json_data: list) -> tuple[int, int, dict[str, dict[str, float | int]]]:
    """Parse a www.keyboard-layout-editor.com JSON, which expects the matrix
    positions of the keys as labels. The function will return a tuple with the
    number of columns, number of rows and a dictionary where the key label
    (the matrix index in the format "col,row") is the key, and the value is a dictionary
    containing all key properties like x, y, w, h, r, rx, ry, etc."""
    key_matrix = {}
    y_cursor = 0.0
    current_rotation = 0.0
    current_rx = 0.0
    current_ry = 0.0

    cols = 0
    rows = 0

    for row in json_data:
        x_cursor = 0.0
        row_defaults = {}

        if 'name' in row:
            continue  # skip the metadata

        for item in row:
            if isinstance(item, dict):
                row_defaults.update(item)
                if 'r' in item.keys():
                    current_rotation = float(item['r'])
                if 'rx' in item.keys():
                    current_rx = float(item['rx'])
                    x_cursor = current_rx
                if 'ry' in item.keys():
                    current_ry = float(item['ry'])
                    y_cursor = current_ry
                if 'x' in item.keys():
                    x_cursor += float(item['x'])
                if 'y' in item.keys():
                    y_cursor += float(item['y'])
                continue

            matrix_pos = str(item)
            index = matrix_pos.split(',')
            col = int(index[1])
            row = int(index[0])
            cols = max(cols, col + 1)
            rows = max(rows, row + 1)
            w = float(row_defaults.get('w', 1))
            h = float(row_defaults.get('h', 1))

            key_matrix[matrix_pos] = {
                'x': x_cursor, 'y': y_cursor, 'w': w, 'h': h,
                'r': current_rotation, 'rx': current_rx, 'ry': current_ry,
                'col': col, 'row': row
            }

            x_cursor += w
            row_defaults.clear()

        if current_rotation == 0:
            y_cursor += 1.0

    return rows, cols, key_matrix

