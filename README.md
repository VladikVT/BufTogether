# BufTogether — Cross-Platform KVM (Windows ↔ macOS)

Бесшовный программный KVM-переключатель между **Windows** (хост с физической клавиатурой и мышью) и **macOS** (клиент). Позволяет управлять обоими компьютерами одним комплектом мыши и клавиатуры, синхронизировать буфер обмена и текущую языковую раскладку.

---

## Возможности

- **Управление мышью**:
  - Плавный бесшовный переход курсора через границу экрана (по умолчанию левый край Windows).
  - Полноценная поддержка **Drag & Drop** (выделение и перетаскивание с зажатой кнопкой мыши через нативные события `kCGEventLeftMouseDragged` / `RightMouseDragged`).
  - Вертикальная и горизонтальная прокрутка колесиком мыши.
  - Боковые клавиши мыши (Назад / Вперед / XButton1 / XButton2).
  - Настраиваемая скорость/чувствительность курсора (`--speed`).

- **Управление клавиатурой**:
  - Низкоуровневый перехват клавиатуры на Windows (`WH_KEYBOARD_LL`) с блокировкой системных действий на Windows во время управления Mac.
  - Точный маппинг Windows Virtual Keys в нативные скан-коды macOS Carbon.
  - **Умная адаптация модификаторов**: `Ctrl` на Windows-клавиатуре транслируется как `Command (Cmd)` на Mac, а `Win` — как `Control`. Привычные сочетания `Ctrl+C`, `Ctrl+V`, `Ctrl+Z`, `Ctrl+A`, `Ctrl+T`, `Ctrl+W` работают естественно. (Отключается флагом `--no-swap-ctrl-cmd`).

- **Автоматическая синхронизация раскладки (RU ↔ EN)**:
  - **При переходе курсора**: при уходе мыши на Mac раскладка macOS автоматически выставляется в соответствии с активным языком на Windows (`ABC` или `RussianWin`). При возврате на Windows раскладка на ПК также согласуется.
  - **При переключении языка**: поддерживаются привычные Windows-сочетания:
    - `Alt + Shift`
    - `Ctrl + Shift`
    - `Win + Space` / `Ctrl + Space` / `Alt + Space`
    - `Caps Lock`
  - Переключение происходит мгновенно через нативный API `Carbon.HIToolbox` (`TISSelectInputSource`) глобально во всей системе macOS.
  - При ручной смене раскладки на любой из машин вторая автоматически синхронизируется.

- **Мгновенный буфер обмена**:
  - Двусторонняя передача текста между Windows и Mac.
  - Нулевая нагрузка на процессор в ожидании: отслеживание через системные счетчики изменений (`GetClipboardSequenceNumber` в Win32 и `NSPasteboard.changeCount()` в Cocoa).
  - Моментальный отклик (< 80 мс) и защита от циклического эха.

- **Защита от блокировок и аварийный возврат (Failsafes)**:
  - `ScrollLock` — ручное переключение между мониторами в любой момент.
  - `Pause / Break` — экстренное освобождение мыши и клавиатуры на Windows.
  - **Watchdog** — при обрыве сети или зависании клиента управление автоматически возвращается на Windows через 4 секунды.
  - Автоматическое отпускание всех зажатых клавиш и восстановление видимости системного курсора.

---

## Структура проекта

```text
BufTogether/
├── src/
│   ├── buftogether/
│   │   ├── __init__.py      # Метаданные пакета
│   │   ├── host.py          # Windows Host (Win32 хуки, TCP-сервер)
│   │   ├── client.py        # macOS Client (Quartz, CoreGraphics, HIToolbox)
│   │   ├── protocol.py      # Сетевой бинарный протокол
│   │   └── keycodes.py      # Маппинг клавиш Windows VK → macOS Carbon
│   └── tests/
│       └── test_warp.py     # Диагностические тесты
├── run_host.bat             # Скрипт запуска на Windows
├── run_client.sh            # Скрипт запуска на macOS
├── requirements.txt         # Зависимости Python
├── README.md                # Документация
├── LICENSE                  # Лицензия MIT
└── .gitignore
```

---

## Установка зависимостей

### Windows:
```cmd
.venv\Scripts\pip install -r requirements.txt
```

### macOS:
```bash
.venv/bin/pip install -r requirements.txt
```

---

## Запуск

### 1. Windows (Хост):
```cmd
run_host.bat
```
или через Python:
```cmd
set PYTHONPATH=src
.venv\Scripts\python.exe -m buftogether.host --edge left --speed 1.0
```

#### Параметры хоста:
- `--port PORT` — порт TCP (по умолчанию `6000`).
- `--edge {left,right}` — сторона, на которой расположен экран Mac (по умолчанию `left`).
- `--speed FLOAT` — множитель скорости курсора на Mac (по умолчанию `1.0`).
- `--no-swap-ctrl-cmd` — отключить подмену Ctrl/Cmd (оставить физическое соответствие: Win=Cmd, Ctrl=Control).

---

### 2. macOS (Клиент):
```bash
./run_client.sh 192.168.0.143 6000
```
или через Python:
```bash
PYTHONPATH=src .venv/bin/python -m buftogether.client 192.168.0.143 --port 6000
```

> **Примечание для macOS**: При первом запуске macOS запросит разрешение на **Accessibility (Универсальный доступ)** в *System Settings → Privacy & Security → Accessibility* для Терминала или процесса Python.

