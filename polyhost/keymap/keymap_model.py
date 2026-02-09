class KeymapModel:
    def __init__(self, layers, rows, cols):
        self.layers = layers
        self.rows = rows
        self.cols = cols

        # 3D array: layer → row → col → uint16 keycode
        self.keymap = [
            [
                [0x0000 for _ in range(cols)]
                for _ in range(rows)
            ]
            for _ in range(layers)
        ]

        self.current_layer = 0

    def set_key(self, layer, row, col, keycode):
        self.keymap[layer][row][col] = keycode

    def get_key(self, layer, row, col):
        return self.keymap[layer][row][col]
