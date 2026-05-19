from __future__ import annotations

import argparse
import ctypes
import threading
import tkinter as tk
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, cast


TRANSPARENT_COLOR = "#00ff00"


@dataclass(frozen=True)
class WorkdayClockConfig:
    start_hour: int = 8
    end_hour: int = 20
    window_width: int = 68
    bar_width: int = 4
    edge_padding: int = 2
    top_padding: int = 7
    bottom_padding: int = 7
    click_through: bool = True
    window_opacity: float = 1.0
    tray_icon: Path | None = None


def workday_progress(
    now: datetime,
    *,
    start_hour: int = 8,
    end_hour: int = 20,
) -> float:
    start_minutes = start_hour * 60
    end_minutes = end_hour * 60
    if end_minutes <= start_minutes:
        raise ValueError("end_hour must be greater than start_hour")

    current_minutes = (
        now.hour * 60
        + now.minute
        + (now.second / 60.0)
        + (now.microsecond / 60_000_000.0)
    )
    progress = (current_minutes - start_minutes) / (end_minutes - start_minutes)
    return max(0.0, min(1.0, progress))


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HICON),
    ]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HCURSOR),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", POINT),
    ]


class TrayIcon:
    WM_TRAY = 0x8000 + 42
    WM_RBUTTONUP = 0x0205
    WM_CONTEXTMENU = 0x007B
    WM_LBUTTONDBLCLK = 0x0203
    WM_COMMAND = 0x0111
    WM_CLOSE = 0x0010
    WM_DESTROY = 0x0002
    WM_NULL = 0x0000

    NIM_ADD = 0x00000000
    NIM_DELETE = 0x00000002
    NIM_SETVERSION = 0x00000004
    NIF_MESSAGE = 0x00000001
    NIF_ICON = 0x00000002
    NIF_TIP = 0x00000004
    NOTIFYICON_VERSION_4 = 4

    IMAGE_ICON = 1
    LR_LOADFROMFILE = 0x00000010
    LR_DEFAULTSIZE = 0x00000040
    IDI_APPLICATION = 32512

    MF_STRING = 0x00000000
    TPM_RIGHTBUTTON = 0x0002
    TPM_RETURNCMD = 0x0100
    EXIT_COMMAND_ID = 1001

    def __init__(
        self,
        *,
        icon_path: Path | None,
        tooltip: str,
        on_exit: Callable[[], None],
        on_activate: Callable[[], None] | None = None,
        exit_label: str = "Exit Workday Clock",
    ) -> None:
        self.icon_path = icon_path
        self.tooltip = tooltip[:127]
        self.on_exit = on_exit
        self.on_activate = on_activate
        self.exit_label = exit_label[:63]
        self._user32 = ctypes.windll.user32
        self._shell32 = ctypes.windll.shell32
        self._kernel32 = ctypes.windll.kernel32
        self._configure_win32_signatures()
        self._thread_id = 0
        self._hwnd: int | None = None
        self._icon: int | None = None
        self._nid: NOTIFYICONDATAW | None = None
        self._ready = threading.Event()
        self._stop_requested = threading.Event()
        self._wndproc = self._make_wndproc()
        self._thread = threading.Thread(target=self._message_loop, name="WorkdayClockTray", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=3.0)

    def _configure_win32_signatures(self) -> None:
        self._user32.DefWindowProcW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        self._user32.DefWindowProcW.restype = ctypes.c_longlong
        self._user32.PostMessageW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        self._user32.PostMessageW.restype = wintypes.BOOL
        self._user32.DestroyWindow.argtypes = [wintypes.HWND]
        self._user32.DestroyWindow.restype = wintypes.BOOL
        self._user32.TrackPopupMenu.argtypes = [
            wintypes.HMENU,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HWND,
            ctypes.c_void_p,
        ]
        self._user32.TrackPopupMenu.restype = wintypes.BOOL

    def dispose(self) -> None:
        if self._hwnd:
            self._user32.PostMessageW(self._hwnd, self.WM_CLOSE, 0, 0)
        self._stop_requested.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _message_loop(self) -> None:
        self._thread_id = int(self._kernel32.GetCurrentThreadId())
        class_name = "WorkdayClockTrayWindow"
        hinstance = self._kernel32.GetModuleHandleW(None)

        wndclass = WNDCLASSW()
        wndclass.lpfnWndProc = ctypes.cast(self._wndproc, ctypes.c_void_p).value
        wndclass.hInstance = hinstance
        wndclass.lpszClassName = class_name
        self._user32.RegisterClassW(ctypes.byref(wndclass))

        self._hwnd = self._user32.CreateWindowExW(
            0,
            class_name,
            "WorkdayClockTray",
            0,
            0,
            0,
            0,
            0,
            None,
            None,
            hinstance,
            None,
        )
        if not self._hwnd:
            self._ready.set()
            return

        self._icon = self._load_icon()
        self._nid = self._make_notify_data(self._hwnd, self._icon)
        self._add_icon(self._nid)
        self._ready.set()

        msg = MSG()
        while self._user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            self._user32.TranslateMessage(ctypes.byref(msg))
            self._user32.DispatchMessageW(ctypes.byref(msg))

        self._cleanup()

    def _make_notify_data(self, hwnd: int, icon: int) -> NOTIFYICONDATAW:
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = hwnd
        nid.uID = 1
        nid.uFlags = self.NIF_MESSAGE | self.NIF_ICON | self.NIF_TIP
        nid.uCallbackMessage = self.WM_TRAY
        nid.hIcon = icon
        nid.szTip = self.tooltip
        nid.uVersion = self.NOTIFYICON_VERSION_4
        return nid

    def _add_icon(self, nid: NOTIFYICONDATAW) -> None:
        self._shell32.Shell_NotifyIconW.argtypes = [
            wintypes.DWORD,
            ctypes.POINTER(NOTIFYICONDATAW),
        ]
        self._shell32.Shell_NotifyIconW.restype = wintypes.BOOL
        self._shell32.Shell_NotifyIconW(self.NIM_ADD, ctypes.byref(nid))
        self._shell32.Shell_NotifyIconW(self.NIM_SETVERSION, ctypes.byref(nid))

    def _load_icon(self) -> int:
        self._user32.LoadImageW.argtypes = [
            wintypes.HINSTANCE,
            wintypes.LPCWSTR,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        self._user32.LoadImageW.restype = wintypes.HANDLE
        if self.icon_path and self.icon_path.exists():
            icon = self._user32.LoadImageW(
                None,
                str(self.icon_path),
                self.IMAGE_ICON,
                0,
                0,
                self.LR_LOADFROMFILE | self.LR_DEFAULTSIZE,
            )
            if icon:
                return int(icon)

        self._user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
        self._user32.LoadIconW.restype = wintypes.HICON
        return int(self._user32.LoadIconW(None, wintypes.LPCWSTR(self.IDI_APPLICATION)))

    def _make_wndproc(self) -> object:
        callback_type = ctypes.WINFUNCTYPE(
            ctypes.c_longlong,
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        )

        def wndproc(hwnd: int, msg: int, wparam: int, lparam: int) -> int:
            if msg == self.WM_TRAY:
                event = int(lparam) & 0xFFFF
                if event in {self.WM_RBUTTONUP, self.WM_CONTEXTMENU}:
                    self._show_menu(hwnd)
                    return 0
                if event == self.WM_LBUTTONDBLCLK and self.on_activate is not None:
                    self.on_activate()
                    return 0
            if msg == self.WM_COMMAND and (int(wparam) & 0xFFFF) == self.EXIT_COMMAND_ID:
                self.on_exit()
                return 0
            if msg == self.WM_CLOSE:
                self._user32.DestroyWindow(hwnd)
                return 0
            if msg == self.WM_DESTROY:
                self._user32.PostQuitMessage(0)
                return 0
            return int(
                self._user32.DefWindowProcW(
                    wintypes.HWND(hwnd),
                    wintypes.UINT(msg),
                    wintypes.WPARAM(wparam),
                    wintypes.LPARAM(lparam),
                )
            )

        return callback_type(wndproc)

    def _show_menu(self, hwnd: int) -> None:
        menu = self._user32.CreatePopupMenu()
        if not menu:
            return
        try:
            self._user32.AppendMenuW(menu, self.MF_STRING, self.EXIT_COMMAND_ID, self.exit_label)
            point = POINT()
            self._user32.GetCursorPos(ctypes.byref(point))
            self._user32.SetForegroundWindow(hwnd)
            command = self._user32.TrackPopupMenu(
                menu,
                self.TPM_RETURNCMD | self.TPM_RIGHTBUTTON,
                point.x,
                point.y,
                0,
                hwnd,
                None,
            )
            self._user32.PostMessageW(hwnd, self.WM_NULL, 0, 0)
            if command == self.EXIT_COMMAND_ID:
                self.on_exit()
        finally:
            self._user32.DestroyMenu(menu)

    def _cleanup(self) -> None:
        if self._nid is not None:
            self._shell32.Shell_NotifyIconW(self.NIM_DELETE, ctypes.byref(self._nid))
            self._nid = None
        if self._icon:
            self._user32.DestroyIcon(self._icon)
            self._icon = None


class WorkdayClockOverlay:
    def __init__(self, config: WorkdayClockConfig) -> None:
        self.config = config
        self.tray: TrayIcon | None = None
        self._set_dpi_awareness()
        self.root = tk.Tk()
        self.root.title("Workday Clock")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT_COLOR)
        self.root.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)

        self.canvas_height = 480
        self.canvas = tk.Canvas(
            self.root,
            width=self.config.window_width,
            height=self.canvas_height,
            bg=TRANSPARENT_COLOR,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()

        self.hour_font = ("Small Fonts", 5)
        self.time_font = ("Small Fonts", 6, "bold")
        self._draw()
        self._position_window()
        self.root.update_idletasks()
        self._apply_win32_window_styles()
        if hasattr(ctypes, "windll"):
            self.tray = TrayIcon(
                icon_path=self.config.tray_icon,
                tooltip="Workday Clock",
                on_exit=lambda: self.root.after(0, self.shutdown),
                on_activate=lambda: self.root.after(0, self._draw),
            )

    def run(self) -> None:
        self._schedule_tick()
        self._schedule_position_refresh()
        self.root.mainloop()

    def shutdown(self) -> None:
        if self.tray is not None:
            self.tray.dispose()
            self.tray = None
        self.root.destroy()

    def _schedule_tick(self) -> None:
        self._draw()
        self.root.after(1000, self._schedule_tick)

    def _schedule_position_refresh(self) -> None:
        self._position_window()
        self.root.after(10_000, self._schedule_position_refresh)

    def _draw(self) -> None:
        self.canvas.delete("all")
        now = datetime.now().astimezone()
        progress = workday_progress(
            now,
            start_hour=self.config.start_hour,
            end_hour=self.config.end_hour,
        )
        right = self.config.window_width
        bar_x2 = right - self.config.edge_padding
        bar_x1 = bar_x2 - self.config.bar_width
        top = self.config.top_padding
        bottom = max(top + 1, self.canvas_height - self.config.bottom_padding)
        span = bottom - top
        current_y = top + int(round(span * progress))

        self.canvas.create_line(bar_x1 - 1, top, bar_x1 - 1, bottom, fill="#06363b", width=1)
        self.canvas.create_rectangle(bar_x1, top, bar_x2, bottom, fill="#06272c", outline="")
        if current_y > top:
            self.canvas.create_rectangle(bar_x1, top, bar_x2, current_y, fill="#0b4a50", outline="")
        if current_y < bottom:
            self.canvas.create_rectangle(bar_x1, current_y, bar_x2, bottom, fill="#35f6ff", outline="")
            self.canvas.create_line(bar_x2 + 1, current_y, bar_x2 + 1, bottom, fill="#b9ffff", width=1)

        self.canvas.create_line(bar_x1 - 5, current_y, bar_x2 + 1, current_y, fill="#d9ffff", width=1)
        self.canvas.create_line(bar_x1 - 2, current_y - 2, bar_x1 - 2, current_y + 2, fill="#d9ffff", width=1)

        total_hours = self.config.end_hour - self.config.start_hour
        for index, hour in enumerate(range(self.config.start_hour, self.config.end_hour + 1)):
            y = top + int(round(span * (index / total_hours)))
            major_color = "#9efaff" if hour in {self.config.start_hour, self.config.end_hour} else "#45dce6"
            tick_len = 8 if hour in {self.config.start_hour, self.config.end_hour} else 5
            self.canvas.create_line(bar_x1 - tick_len, y, bar_x1 - 1, y, fill=major_color, width=1)
            self._pixel_text(
                bar_x1 - tick_len - 2,
                y,
                f"{hour:02d}",
                fill=major_color,
                font=self.hour_font,
                anchor="e",
            )

        current_label_y = max(top + 5, min(bottom - 5, current_y))
        self._pixel_text(
            bar_x1 - 13,
            current_label_y,
            now.strftime("%H:%M"),
            fill="#ecfeff",
            font=self.time_font,
            anchor="e",
        )
        self.canvas.create_line(bar_x1 - 11, current_label_y, bar_x1 - 5, current_y, fill="#8ffaff", width=1)

    def _pixel_text(
        self,
        x: int,
        y: int,
        text: str,
        *,
        fill: str,
        font: tuple[str, int] | tuple[str, int, str],
        anchor: str,
    ) -> None:
        self.canvas.create_text(x + 1, y + 1, text=text, anchor=anchor, fill="#001013", font=font)
        self.canvas.create_text(x, y, text=text, anchor=anchor, fill=fill, font=font)

    def _position_window(self) -> None:
        _left, top, right, bottom = self._primary_work_area()
        height = max(1, bottom - top)
        if height != self.canvas_height:
            self.canvas_height = height
            self.canvas.configure(height=height)
        x = right - self.config.window_width
        self.root.geometry(f"{self.config.window_width}x{height}+{x}+{top}")

    def _primary_work_area(self) -> tuple[int, int, int, int]:
        if hasattr(ctypes, "windll"):
            try:
                class RECT(ctypes.Structure):
                    _fields_ = [
                        ("left", ctypes.c_long),
                        ("top", ctypes.c_long),
                        ("right", ctypes.c_long),
                        ("bottom", ctypes.c_long),
                    ]

                rect = RECT()
                ok = ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
                if ok and rect.right > rect.left and rect.bottom > rect.top:
                    return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)
            except (AttributeError, OSError):
                pass
        return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def _apply_win32_window_styles(self) -> None:
        if not hasattr(ctypes, "windll"):
            return
        hwnd = ctypes.c_void_p(self.root.winfo_id())
        user32 = ctypes.windll.user32

        get_window_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
        set_window_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
        get_window_long.argtypes = [ctypes.c_void_p, ctypes.c_int]
        set_window_long.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_longlong]
        get_window_long.restype = ctypes.c_longlong
        set_window_long.restype = ctypes.c_longlong

        style = int(get_window_long(hwnd, -20))
        style |= 0x00080000 | 0x00000080
        if self.config.click_through:
            style |= 0x00000020
        set_window_long(hwnd, -20, style)

        set_layered = cast(object, getattr(user32, "SetLayeredWindowAttributes", None))
        if callable(set_layered):
            alpha = max(1, min(255, int(self.config.window_opacity * 255)))
            flags = 0x00000001
            if alpha < 255:
                flags |= 0x00000002
            set_layered(hwnd, self._colorref(TRANSPARENT_COLOR), alpha, flags)

    def _colorref(self, hex_color: str) -> int:
        color = hex_color.removeprefix("#")
        red = int(color[0:2], 16)
        green = int(color[2:4], 16)
        blue = int(color[4:6], 16)
        return red | (green << 8) | (blue << 16)

    def _set_dpi_awareness(self) -> None:
        if not hasattr(ctypes, "windll"):
            return
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Thin right-edge workday clock overlay.")
    parser.add_argument("--once", action="store_true", help="Print the current workday clock state and exit.")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Disable click-through so the clock window can be inspected while developing.",
    )
    parser.add_argument("--start-hour", type=int, default=8, help="Workday start hour, 24-hour clock.")
    parser.add_argument("--end-hour", type=int, default=20, help="Workday end hour, 24-hour clock.")
    parser.add_argument("--bar-width", type=int, default=4, help="Cyan strip width in pixels.")
    parser.add_argument("--window-width", type=int, default=68, help="Transparent overlay width in pixels.")
    args = parser.parse_args()

    config = WorkdayClockConfig(
        start_hour=args.start_hour,
        end_hour=args.end_hour,
        bar_width=max(1, args.bar_width),
        window_width=max(32, args.window_width),
        click_through=not args.interactive,
    )

    if args.once:
        now = datetime.now().astimezone()
        print(f"time={now:%H:%M:%S}")
        print(f"start={config.start_hour:02d}:00")
        print(f"end={config.end_hour:02d}:00")
        print(f"elapsed={workday_progress(now, start_hour=config.start_hour, end_hour=config.end_hour) * 100:.1f}%")
        return 0

    overlay = WorkdayClockOverlay(config)
    overlay.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
