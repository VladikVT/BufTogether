"""
Virtual Key mapping between Windows (VK_*) and macOS (Carbon Virtual Keycodes).
"""

# Windows VK constants
VK_LBUTTON = 0x01
VK_RBUTTON = 0x02
VK_CANCEL = 0x03
VK_MBUTTON = 0x04
VK_BACK = 0x08
VK_TAB = 0x09
VK_CLEAR = 0x0C
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12          # Alt
VK_PAUSE = 0x13
VK_CAPITAL = 0x14       # Caps Lock
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_PRIOR = 0x21         # Page Up
VK_NEXT = 0x22          # Page Down
VK_END = 0x23
VK_HOME = 0x24
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_SNAPSHOT = 0x2C      # Print Screen
VK_INSERT = 0x2D
VK_DELETE = 0x2E
VK_HELP = 0x2F

# Digits 0x30 - 0x39
# Letters 0x41 - 0x5A

VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_APPS = 0x5D

VK_NUMPAD0 = 0x60
VK_NUMPAD1 = 0x61
VK_NUMPAD2 = 0x62
VK_NUMPAD3 = 0x63
VK_NUMPAD4 = 0x64
VK_NUMPAD5 = 0x65
VK_NUMPAD6 = 0x66
VK_NUMPAD7 = 0x67
VK_NUMPAD8 = 0x68
VK_NUMPAD9 = 0x69
VK_MULTIPLY = 0x6A
VK_ADD = 0x6B
VK_SEPARATOR = 0x6C
VK_SUBTRACT = 0x6D
VK_DECIMAL = 0x6E
VK_DIVIDE = 0x6F

VK_F1 = 0x70
VK_F2 = 0x71
VK_F3 = 0x72
VK_F4 = 0x73
VK_F5 = 0x74
VK_F6 = 0x75
VK_F7 = 0x76
VK_F8 = 0x77
VK_F9 = 0x78
VK_F10 = 0x79
VK_F11 = 0x7A
VK_F12 = 0x7B
VK_F13 = 0x7C
VK_F14 = 0x7D
VK_F15 = 0x7E
VK_F16 = 0x7F
VK_F17 = 0x80
VK_F18 = 0x81
VK_F19 = 0x82
VK_F20 = 0x83
VK_F21 = 0x84
VK_F22 = 0x85
VK_F23 = 0x86
VK_F24 = 0x87

VK_NUMLOCK = 0x90
VK_SCROLL = 0x91

VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LMENU = 0xA4         # Left Alt
VK_RMENU = 0xA5         # Right Alt

VK_OEM_1 = 0xBA         # ;:
VK_OEM_PLUS = 0xBB      # =+
VK_OEM_COMMA = 0xBC     # ,<
VK_OEM_MINUS = 0xBD     # -_
VK_OEM_PERIOD = 0xBE    # .>
VK_OEM_2 = 0xBF         # /?
VK_OEM_3 = 0xC0         # `~
VK_OEM_4 = 0xDB         # [{
VK_OEM_5 = 0xDC         # \|
VK_OEM_6 = 0xDD         # ]}
VK_OEM_7 = 0xDE         # '"

# macOS Carbon Virtual Key Codes
MAC_A = 0x00
MAC_S = 0x01
MAC_D = 0x02
MAC_F = 0x03
MAC_H = 0x04
MAC_G = 0x05
MAC_Z = 0x06
MAC_X = 0x07
MAC_C = 0x08
MAC_V = 0x09
MAC_B = 0x0B
MAC_Q = 0x0C
MAC_W = 0x0D
MAC_E = 0x0E
MAC_R = 0x0F
MAC_Y = 0x10
MAC_T = 0x11
MAC_1 = 0x12
MAC_2 = 0x13
MAC_3 = 0x14
MAC_4 = 0x15
MAC_6 = 0x16
MAC_5 = 0x17
MAC_EQUAL = 0x18
MAC_9 = 0x19
MAC_7 = 0x1A
MAC_MINUS = 0x1B
MAC_8 = 0x1C
MAC_0 = 0x1D
MAC_RIGHTBRACKET = 0x1E
MAC_O = 0x1F
MAC_U = 0x20
MAC_LEFTBRACKET = 0x21
MAC_I = 0x22
MAC_P = 0x23
MAC_L = 0x25
MAC_J = 0x26
MAC_QUOTE = 0x27
MAC_K = 0x28
MAC_SEMICOLON = 0x29
MAC_BACKSLASH = 0x2A
MAC_COMMA = 0x2B
MAC_SLASH = 0x2C
MAC_N = 0x2D
MAC_M = 0x2E
MAC_PERIOD = 0x2F
MAC_GRAVE = 0x32

# Keypad
MAC_KEYPAD_DECIMAL = 0x41
MAC_KEYPAD_MULTIPLY = 0x43
MAC_KEYPAD_PLUS = 0x45
MAC_KEYPAD_CLEAR = 0x47
MAC_KEYPAD_DIVIDE = 0x4B
MAC_KEYPAD_ENTER = 0x4C
MAC_KEYPAD_MINUS = 0x4E
MAC_KEYPAD_EQUALS = 0x51
MAC_KEYPAD_0 = 0x52
MAC_KEYPAD_1 = 0x53
MAC_KEYPAD_2 = 0x54
MAC_KEYPAD_3 = 0x55
MAC_KEYPAD_4 = 0x56
MAC_KEYPAD_5 = 0x57
MAC_KEYPAD_6 = 0x58
MAC_KEYPAD_7 = 0x59
MAC_KEYPAD_8 = 0x5B
MAC_KEYPAD_9 = 0x5C

# Controls & Special
MAC_RETURN = 0x24
MAC_TAB = 0x30
MAC_SPACE = 0x31
MAC_DELETE = 0x33       # Backspace on PC
MAC_ESCAPE = 0x35
MAC_COMMAND = 0x37      # Left Cmd
MAC_RIGHT_COMMAND = 0x36
MAC_SHIFT = 0x38        # Left Shift
MAC_CAPSLOCK = 0x39
MAC_OPTION = 0x3A       # Left Alt/Option
MAC_CONTROL = 0x3B      # Left Ctrl
MAC_RIGHT_SHIFT = 0x3C
MAC_RIGHT_OPTION = 0x3D
MAC_RIGHT_CONTROL = 0x3E
MAC_FUNCTION = 0x3F

MAC_VOLUME_UP = 0x48
MAC_VOLUME_DOWN = 0x49
MAC_MUTE = 0x4A

MAC_F1 = 0x7A
MAC_F2 = 0x78
MAC_F3 = 0x63
MAC_F4 = 0x76
MAC_F5 = 0x60
MAC_F6 = 0x61
MAC_F7 = 0x62
MAC_F8 = 0x64
MAC_F9 = 0x65
MAC_F10 = 0x6D
MAC_F11 = 0x67
MAC_F12 = 0x6F
MAC_F13 = 0x69
MAC_F14 = 0x6B
MAC_F15 = 0x71
MAC_F16 = 0x6A
MAC_F17 = 0x40
MAC_F18 = 0x4F
MAC_F19 = 0x50
MAC_F20 = 0x5A

MAC_HELP = 0x72
MAC_HOME = 0x73
MAC_PAGE_UP = 0x74
MAC_FORWARD_DELETE = 0x75 # Del on PC
MAC_END = 0x77
MAC_PAGE_DOWN = 0x79
MAC_LEFT = 0x7B
MAC_RIGHT = 0x7C
MAC_DOWN = 0x7D
MAC_UP = 0x7E

# Static base mapping (letters, numbers, navigation, edit keys)
BASE_VK_TO_MAC = {
    # Letters
    0x41: MAC_A, 0x42: MAC_B, 0x43: MAC_C, 0x44: MAC_D,
    0x45: MAC_E, 0x46: MAC_F, 0x47: MAC_G, 0x48: MAC_H,
    0x49: MAC_I, 0x4A: MAC_J, 0x4B: MAC_K, 0x4C: MAC_L,
    0x4D: MAC_M, 0x4E: MAC_N, 0x4F: MAC_O, 0x50: MAC_P,
    0x51: MAC_Q, 0x52: MAC_R, 0x53: MAC_S, 0x54: MAC_T,
    0x55: MAC_U, 0x56: MAC_V, 0x57: MAC_W, 0x58: MAC_X,
    0x59: MAC_Y, 0x5A: MAC_Z,

    # Number row
    0x30: MAC_0, 0x31: MAC_1, 0x32: MAC_2, 0x33: MAC_3,
    0x34: MAC_4, 0x35: MAC_5, 0x36: MAC_6, 0x37: MAC_7,
    0x38: MAC_8, 0x39: MAC_9,

    # Symbols / punctuation
    VK_OEM_1: MAC_SEMICOLON,
    VK_OEM_PLUS: MAC_EQUAL,
    VK_OEM_COMMA: MAC_COMMA,
    VK_OEM_MINUS: MAC_MINUS,
    VK_OEM_PERIOD: MAC_PERIOD,
    VK_OEM_2: MAC_SLASH,
    VK_OEM_3: MAC_GRAVE,
    VK_OEM_4: MAC_LEFTBRACKET,
    VK_OEM_5: MAC_BACKSLASH,
    VK_OEM_6: MAC_RIGHTBRACKET,
    VK_OEM_7: MAC_QUOTE,

    # Standard edit / movement
    VK_BACK: MAC_DELETE,
    VK_TAB: MAC_TAB,
    VK_RETURN: MAC_RETURN,
    VK_ESCAPE: MAC_ESCAPE,
    VK_SPACE: MAC_SPACE,
    VK_DELETE: MAC_FORWARD_DELETE,
    VK_INSERT: MAC_HELP,
    VK_HOME: MAC_HOME,
    VK_END: MAC_END,
    VK_PRIOR: MAC_PAGE_UP,
    VK_NEXT: MAC_PAGE_DOWN,
    VK_LEFT: MAC_LEFT,
    VK_UP: MAC_UP,
    VK_RIGHT: MAC_RIGHT,
    VK_DOWN: MAC_DOWN,
    VK_SNAPSHOT: MAC_F13,

    # Function keys
    VK_F1: MAC_F1, VK_F2: MAC_F2, VK_F3: MAC_F3, VK_F4: MAC_F4,
    VK_F5: MAC_F5, VK_F6: MAC_F6, VK_F7: MAC_F7, VK_F8: MAC_F8,
    VK_F9: MAC_F9, VK_F10: MAC_F10, VK_F11: MAC_F11, VK_F12: MAC_F12,

    # Numpad
    VK_NUMPAD0: MAC_KEYPAD_0, VK_NUMPAD1: MAC_KEYPAD_1,
    VK_NUMPAD2: MAC_KEYPAD_2, VK_NUMPAD3: MAC_KEYPAD_3,
    VK_NUMPAD4: MAC_KEYPAD_4, VK_NUMPAD5: MAC_KEYPAD_5,
    VK_NUMPAD6: MAC_KEYPAD_6, VK_NUMPAD7: MAC_KEYPAD_7,
    VK_NUMPAD8: MAC_KEYPAD_8, VK_NUMPAD9: MAC_KEYPAD_9,
    VK_MULTIPLY: MAC_KEYPAD_MULTIPLY,
    VK_ADD: MAC_KEYPAD_PLUS,
    VK_SUBTRACT: MAC_KEYPAD_MINUS,
    VK_DECIMAL: MAC_KEYPAD_DECIMAL,
    VK_DIVIDE: MAC_KEYPAD_DIVIDE,
    VK_NUMLOCK: MAC_KEYPAD_CLEAR,

    # Shift / Caps
    VK_SHIFT: MAC_SHIFT,
    VK_LSHIFT: MAC_SHIFT,
    VK_RSHIFT: MAC_RIGHT_SHIFT,
    VK_CAPITAL: MAC_CAPSLOCK,
}


def win_vk_to_mac(vk: int, ctrl_as_cmd: bool = True) -> int | None:
    """
    Translates Windows Virtual Key code to macOS Carbon Virtual Key code.
    If ctrl_as_cmd is True:
        Ctrl -> Command (so Ctrl+C, Ctrl+V, Ctrl+Z feel natural on Windows keyboard)
        Win  -> Control
        Alt  -> Option
    If ctrl_as_cmd is False:
        Ctrl -> Control
        Win  -> Command
        Alt  -> Option
    """
    # Check modifiers first based on mapping mode
    if ctrl_as_cmd:
        if vk in (VK_CONTROL, VK_LCONTROL):
            return MAC_COMMAND
        if vk == VK_RCONTROL:
            return MAC_RIGHT_COMMAND
        if vk in (VK_LWIN, VK_APPS):
            return MAC_CONTROL
        if vk == VK_RWIN:
            return MAC_RIGHT_CONTROL
    else:
        if vk in (VK_CONTROL, VK_LCONTROL):
            return MAC_CONTROL
        if vk == VK_RCONTROL:
            return MAC_RIGHT_CONTROL
        if vk in (VK_LWIN, VK_APPS):
            return MAC_COMMAND
        if vk == VK_RWIN:
            return MAC_RIGHT_COMMAND

    if vk in (VK_MENU, VK_LMENU):
        return MAC_OPTION
    if vk == VK_RMENU:
        return MAC_RIGHT_OPTION

    return BASE_VK_TO_MAC.get(vk)
