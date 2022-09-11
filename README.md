# Hepyx
Hepyx is a hex editor written on Python 3 with nano-like keybindings.
<sub><sup>(But actually this is just an Okteta for terminals)</sup></sub>


### Requirements
- [Python 3](https://www.python.org/)
    - `curses` module
- [Nuitka](https://nuitka.net/)
<sub><sup>(Actually you can install hepyx without nuitka, but it's harder than with)</sup></sub>

### Installation
```sh
cd hepyx
nuitka --remove-output main.py -o hepyx
mv hepyx /usr/bin/hepyx
```

### Hotkeys
|                Hotkey | Does                         |
|----------------------:|:-----------------------------|
|                Ctrl+X | Exit                         |
|                Ctrl+S | Save changes                 |
|                Ctrl+Z | Undo last change             |
|                Ctrl+E | Change encoding              |
|                Ctrl+G | Goto address                 |
|                Ctrl+F | Find certain string or hex   |
| Ctrl+> (Ctrl+Shift+.) | Go to next search result     |
| Ctrl+< (Ctrl+Shift+,) | Go to previous search result |
|                   Esc | Clear search query           |

