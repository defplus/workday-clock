# Workday Clock

A thin cyan right-edge workday timer for Windows.

Workday Clock draws a transparent, click-through overlay on the right edge of
the primary display. By default it maps 08:00 to the top of the primary monitor
work area and 20:00 to the bottom. The bright cyan segment is the remaining
workday time, the current time is pinned to its current position, and each hour
has a compact label.

It is intentionally small: Python standard library plus Tkinter only.

## Run

```powershell
python .\run_workday_clock.py --once
python .\run_workday_clock.py
```

Use `Ctrl+C` in the terminal to stop it. For normal detached use:

```powershell
.\start_workday_clock.ps1
.\stop_workday_clock.ps1
```

To launch automatically when you sign in:

```powershell
.\install_startup.ps1
.\uninstall_startup.ps1
```

The overlay also adds a task tray icon. Right-click it and choose
`Exit Workday Clock` to stop cleanly.

## Options

```powershell
python .\run_workday_clock.py --interactive
python .\run_workday_clock.py --start-hour 9 --end-hour 18
python .\run_workday_clock.py --bar-width 3 --window-width 64
```

`--interactive` disables click-through so the overlay window can be inspected.

## Notes

- Windows only.
- The overlay uses the primary monitor work area, so it should avoid the
  taskbar.
- DPI awareness is enabled before the window is positioned.
- The default font asks Windows for `Small Fonts`; Windows may substitute a
  nearby bitmap-like font depending on the environment.

## License

MIT
