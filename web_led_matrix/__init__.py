"""
File: pixel_grid.py
Author: Taylor
Project: LED Matrix Pixel Grid UI

Description:
    Refactored PixelGrid application separating layout generation into its own class,
    moving control buttons into a recessed panel on the right, adding frame-by-frame animation support,
    introducing Frame objects to store grid data and inter-frame durations,
    and enforcing type-checked properties backed by private dunder attributes.
    Loading from a file will replace the entire animation sequence; exporting saves all frames or a single frame.

Dependencies:
    - PySimpleGUI
    - led_matrix_battery.inputmodule.helpers.DEVICES
    - led_matrix_battery.inputmodule.ledmatrix.render_matrix

Example Usage:
    if __name__ == '__main__':
        app = PixelGrid()
        app.run()
"""
import PySimpleGUI as sg
import json
import os
import copy
from typing import Any, List, Tuple
from is_matrix_forge.led_matrix.constants import DEVICES
from is_matrix_forge.led_matrix.display.helpers import render_matrix



def _is_valid_grid(grid: Any, width: int, height: int) -> bool:
    return (
        isinstance(grid, list)
        and len(grid) == width
        and all(
            isinstance(col, list)
            and len(col) == height
            and all(cell in (0, 1) for cell in col)
            for col in grid
        )
    )


def _is_valid_frames(raw: Any, width: int, height: int) -> bool:
    return (
        isinstance(raw, list)
        and len(raw) > 0
        and all(_is_valid_grid(frame, width, height) for frame in raw)
    )


class Frame:
    """
    Represents a single animation frame with a duration.
    """
    def __init__(self, grid: List[List[int]], duration: float = 1.0):
        # establish context for validation
        Frame.__width = len(grid)
        Frame.__height = len(grid[0]) if grid else 0
        self.grid = grid
        self.duration = duration

    @property
    def grid(self) -> List[List[int]]:
        return self.__grid

    @grid.setter
    def grid(self, value: Any) -> None:
        if not _is_valid_grid(value, Frame.__width, Frame.__height):
            raise ValueError(f"Grid must be {Frame.__width}x{Frame.__height} list of 0/1")
        self.__grid = value

    @property
    def duration(self) -> float:
        return self.__duration

    @duration.setter
    def duration(self, value: Any) -> None:
        try:
            val = float(value)
        except (TypeError, ValueError):
            raise TypeError("Duration must be a number")
        if val <= 0:
            raise ValueError("Duration must be positive")
        self.__duration = val


class PixelGridLayout:
    """
    Builds the PySimpleGUI layout for the pixel grid, control panel,
    and frame animation controls.
    """
    def __init__(
        self,
        width: int = 9,
        height: int = 34,
        button_list: List[str] = None,
        pad: Tuple[int, int] = (0, 0),
        button_size: Tuple[int, int] = (2, 1)
    ):
        self.__width = None
        self.__height = None
        self.__pad = None
        self.__button_size = None
        self.__button_list = None
        self.width = width
        self.height = height
        self.pad = pad
        self.button_size = button_size
        self.button_list = button_list or [
            'Export', 'Export to File', 'Load from File',
            'Send to Matrix', 'Add Frame', 'Exit'
        ]

    @property
    def width(self) -> int:
        return self.__width

    @width.setter
    def width(self, value: Any) -> None:
        if not isinstance(value, int) or value <= 0:
            raise TypeError("Width must be a positive integer")
        self.__width = value

    @property
    def height(self) -> int:
        return self.__height

    @height.setter
    def height(self, value: Any) -> None:
        if not isinstance(value, int) or value <= 0:
            raise TypeError("Height must be a positive integer")
        self.__height = value

    @property
    def pad(self) -> Tuple[int, int]:
        return self.__pad

    @pad.setter
    def pad(self, value: Any) -> None:
        if (
            not isinstance(value, tuple)
            or len(value) != 2
            or not all(isinstance(v, int) for v in value)
        ):
            raise TypeError("pad must be a tuple of two integers")
        self.__pad = value

    @property
    def button_size(self) -> Tuple[int, int]:
        return self.__button_size

    @button_size.setter
    def button_size(self, value: Any) -> None:
        if (
            not isinstance(value, tuple)
            or len(value) != 2
            or not all(isinstance(v, int) for v in value)
        ):
            raise TypeError("button_size must be a tuple of two integers")
        self.__button_size = value

    @property
    def button_list(self) -> List[str]:
        return self.__button_list

    @button_list.setter
    def button_list(self, value: Any) -> None:
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise TypeError("button_list must be a list of strings")
        self.__button_list = value

    def build(self) -> List[List[Any]]:
        grid = [
            [sg.Button(' ', size=self.button_size, key=(col, row), pad=self.pad)
             for col in range(self.width)]
            for row in range(self.height)
        ]
        grid_column = sg.Column(grid)

        controls = [[sg.Button(btn)] for btn in self.button_list]
        control_column = sg.Column(controls, vertical_alignment='top')

        frame_controls = [
            sg.Button('< Prev', key='<Prev>'),
            sg.Text('', key='FRAME_INDICATOR'),
            sg.Button('Next >', key='Next>')
        ]

        layout = [
            [grid_column, sg.VerticalSeparator(), control_column],
            [sg.HorizontalSeparator(pad=(0, 5))],
            [sg.Push(), *frame_controls, sg.Push()]
        ]
        return layout


class PixelGrid:
    """
    LED matrix pixel grid UI with frame-by-frame animation.
    """
    def __init__(self, width: int = 9, height: int = 34):
        self.__width = None
        self.__height = None
        self.__frames = None
        self.__current_frame = None
        self.__grid = None
        self.__preferred_device = None

        self.width = width
        self.height = height

        base = [[0] * self.height for _ in range(self.width)]
        Frame.__width = self.width
        Frame.__height = self.height
        self.frames = [Frame(copy.deepcopy(base))]
        self.current_frame = 0
        self.grid = self.frames[0].grid
        self.preferred_device = None

        layout = PixelGridLayout(self.width, self.height).build()
        self.window = sg.Window('Pixel Grid', layout, finalize=True)
        self._init_button_colors()
        self._update_frame_indicator()

    @property
    def width(self) -> int:
        return self.__width

    @width.setter
    def width(self, value: Any) -> None:
        if not isinstance(value, int) or value <= 0:
            raise TypeError("Width must be a positive integer")
        self.__width = value

    @property
    def height(self) -> int:
        return self.__height

    @height.setter
    def height(self, value: Any) -> None:
        if not isinstance(value, int) or value <= 0:
            raise TypeError("Height must be a positive integer")
        self.__height = value

    @property
    def frames(self) -> List[Frame]:
        return self.__frames

    @frames.setter
    def frames(self, value: Any) -> None:
        if not isinstance(value, list) or len(value) == 0 or not all(isinstance(f, Frame) for f in value):
            raise TypeError("frames must be a non-empty list of Frame objects")
        self.__frames = value

    @property
    def current_frame(self) -> int:
        return self.__current_frame

    @current_frame.setter
    def current_frame(self, value: Any) -> None:
        if not isinstance(value, int) or not (0 <= value < len(self.frames)):
            raise ValueError("current_frame must be an index into frames list")
        self.__current_frame = value

    @property
    def grid(self) -> List[List[int]]:
        return self.__grid

    @grid.setter
    def grid(self, value: Any) -> None:
        if not _is_valid_grid(value, self.width, self.height):
            raise ValueError("Grid must match width/height and be 0/1 values")
        self.__grid = value
        # update frame's grid as well
        if hasattr(self, 'frames') and self.frames:
            self.frames[self.current_frame].grid = value

    @property
    def preferred_device(self):
        return self.__preferred_device

    @preferred_device.setter
    def preferred_device(self, value: Any) -> None:
        # no strict type check, but could enforce presence in DEVICES
        self.__preferred_device = value

    def _init_button_colors(self) -> None:
        for col in range(self.width):
            for row in range(self.height):
                state = self.grid[col][row]
                color = 'green' if state else 'lightgrey'
                self.window[(col, row)].update(button_color=('black', color))

    def _update_frame_indicator(self) -> None:
        total = len(self.frames)
        idx = self.current_frame + 1
        dur = self.frames[self.current_frame].duration
        self.window['FRAME_INDICATOR'].update(
            f'Frame {idx}/{total} (Duration: {dur}s)'
        )

    def run(self) -> None:
        while True:
            event, _ = self.window.read()
            if event in (sg.WINDOW_CLOSED, 'Exit'):
                break
            handler = getattr(self, f'_handle_{self._normalize(event)}', None)
            if callable(handler):
                handler(event)
            elif isinstance(event, tuple):
                self._toggle_pixel(event)
        self.window.close()

    def _normalize(self, key: Any) -> str:
        s = str(key)
        for ch in " <>,'()":
            s = s.replace(ch, '_')
        return s.strip('_')

    def _toggle_pixel(self, key: Tuple[int, int]) -> None:
        col, row = key
        new = 1 - self.grid[col][row]
        self.grid = [[new if (c==col and r==row) else self.grid[c][r]
                      for r in range(self.height)]
                     for c in range(self.width)]
        self.window[key].update(
            button_color=('black', 'green' if new else 'lightgrey')
        )

    # Frame management
    def add_frame(self) -> None:
        new_grid = copy.deepcopy(self.grid)
        frm = Frame(new_grid)
        self.frames = self.frames + [frm]
        self.current_frame = len(self.frames) - 1
        self.grid = frm.grid
        self._init_button_colors()
        self._update_frame_indicator()

    def prev_frame(self) -> None:
        if self.current_frame > 0:
            self.current_frame -= 1
            self._load_frame()

    def next_frame(self) -> None:
        if self.current_frame < len(self.frames) - 1:
            self.current_frame += 1
            self._load_frame()

    def _load_frame(self) -> None:
        frm = self.frames[self.current_frame]
        self.grid = frm.grid
        self._init_button_colors()
        self._update_frame_indicator()

    # Export handlers
    def _handle_Export(self, _event) -> None:
        data = [f.grid for f in self.frames] if len(self.frames) > 1 else self.frames[0].grid
        print(data)

    def _handle_Export_to_File(self, _event) -> None:
        path = sg.popup_get_file(
            'Save Grid As', save_as=True, no_window=True,
            file_types=(('JSON Files', '*.json'),), default_extension='.json'
        )
        if not path:
            return
        data = [f.grid for f in self.frames] if len(self.frames) > 1 else self.frames[0].grid
        try:
            with open(path, 'w') as f:
                json.dump(data, f)
            sg.popup('Success', f'Saved to {os.path.basename(path)}')
        except Exception as e:
            sg.popup_error('Error', str(e))

    def _handle_Load_from_File(self, _event) -> None:
        path = sg.popup_get_file(
            'Load Grid From', no_window=True,
            file_types=(('JSON Files', '*.json'),)
        )
        if not path:
            return
        try:
            raw = json.load(open(path))
            if _is_valid_grid(raw, self.width, self.height):
                grids = [raw]
            elif _is_valid_frames(raw, self.width, self.height):
                grids = raw
            else:
                sg.popup_error('Invalid format')
                return
            self.frames = [Frame(copy.deepcopy(g)) for g in grids]
            self.current_frame = 0
            self._load_frame()
            sg.popup('Success', f'Loaded {len(self.frames)} frame(s)')
        except Exception as e:
            sg.popup_error('Error', str(e))

    # Send to matrix
    def _handle_Send_to_Matrix(self, _event) -> None:
        devices = DEVICES
        if not devices:
            sg.popup_error('No devices found.')
            return
        if self.preferred_device in devices:
            dev = self.preferred_device
        else:
            descs = [f"{d.device} - {d.description}" for d in devices]
            win = sg.Window('Select Device', [
                [sg.Text('Select device:')],
                [sg.Listbox(descs, size=(40, len(descs)), key='DEV')],
                [sg.Checkbox('Always choose', key='REM')],
                [sg.OK(), sg.Cancel()]
            ], modal=True)
            ev, vals = win.read(); win.close()
            if ev != 'OK' or not vals['DEV']:
                return
            dev = devices[descs.index(vals['DEV'][0])]
            if vals['REM']:
                self.preferred_device = dev
        try:
            render_matrix(dev, self.grid)
            sg.popup('Success', f'Sent to {dev.device}')
        except Exception as e:
            sg.popup_error('Error sending:', str(e))

    # Button-mapped handlers
    def _handle_Add_Frame(self, e): self.add_frame()
    def _handle_Prev(self, e): self.prev_frame()
    def _handle_Next(self, e): self.next_frame()

    def _validate(self, grid: Any) -> bool:
        return _is_valid_grid(grid, self.width, self.height)


if __name__ == '__main__':
    PixelGrid().run()
