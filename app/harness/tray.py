"""System tray icon via ctypes (Win32 only, no dependencies; Windows 7+).

On other platforms Tray.start() returns False and the GUI behaves as a normal window.
"""
import ctypes
import sys
import threading

IS_WIN = sys.platform == "win32"
CLASS_NAME = "CopilotHarnessTray"

if IS_WIN:
    from ctypes import wintypes

    WM_NULL, WM_DESTROY, WM_CLOSE = 0x0000, 0x0002, 0x0010
    WM_LBUTTONUP, WM_LBUTTONDBLCLK, WM_RBUTTONUP = 0x0202, 0x0203, 0x0205
    WM_APP_TRAY, WM_APP_SHOW = 0x8001, 0x8002
    NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
    NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 1, 2, 4, 0x10
    NIIF_INFO = 1
    MF_STRING, MF_SEPARATOR = 0, 0x800
    TPM_RIGHTBUTTON, TPM_RETURNCMD = 2, 0x100
    IDI_APPLICATION = 32512

    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT,
                                 wintypes.WPARAM, wintypes.LPARAM)

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                    ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                    ("hInstance", wintypes.HANDLE), ("hIcon", wintypes.HANDLE),
                    ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HANDLE),
                    ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

    class NOTIFYICONDATAW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
                    ("uFlags", wintypes.UINT), ("uCallbackMessage", wintypes.UINT),
                    ("hIcon", wintypes.HANDLE), ("szTip", ctypes.c_wchar * 128),
                    ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
                    ("szInfo", ctypes.c_wchar * 256), ("uVersion", wintypes.UINT),
                    ("szInfoTitle", ctypes.c_wchar * 64), ("dwInfoFlags", wintypes.DWORD),
                    ("guidItem", GUID), ("hBalloonIcon", wintypes.HANDLE)]

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    def _sig(fn, res, *args):
        fn.restype, fn.argtypes = res, list(args)

    H = wintypes.HANDLE
    _sig(user32.DefWindowProcW, LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    _sig(user32.RegisterClassW, wintypes.ATOM, ctypes.POINTER(WNDCLASSW))
    _sig(user32.CreateWindowExW, wintypes.HWND, wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
         wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
         wintypes.HWND, H, H, ctypes.c_void_p)
    _sig(user32.PostMessageW, wintypes.BOOL, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    _sig(user32.GetMessageW, ctypes.c_int, ctypes.POINTER(wintypes.MSG), wintypes.HWND,
         wintypes.UINT, wintypes.UINT)
    _sig(user32.TranslateMessage, wintypes.BOOL, ctypes.POINTER(wintypes.MSG))
    _sig(user32.DispatchMessageW, LRESULT, ctypes.POINTER(wintypes.MSG))
    _sig(user32.DestroyWindow, wintypes.BOOL, wintypes.HWND)
    _sig(user32.PostQuitMessage, None, ctypes.c_int)
    _sig(user32.RegisterWindowMessageW, wintypes.UINT, wintypes.LPCWSTR)
    _sig(user32.CreatePopupMenu, H)
    _sig(user32.AppendMenuW, wintypes.BOOL, H, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR)
    _sig(user32.TrackPopupMenu, wintypes.BOOL, H, wintypes.UINT, ctypes.c_int, ctypes.c_int,
         ctypes.c_int, wintypes.HWND, ctypes.c_void_p)
    _sig(user32.DestroyMenu, wintypes.BOOL, H)
    _sig(user32.GetCursorPos, wintypes.BOOL, ctypes.POINTER(wintypes.POINT))
    _sig(user32.SetForegroundWindow, wintypes.BOOL, wintypes.HWND)
    _sig(user32.FindWindowW, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR)
    _sig(user32.LoadIconW, H, H, ctypes.c_void_p)
    _sig(user32.LoadImageW, H, H, wintypes.LPCWSTR, wintypes.UINT,
         ctypes.c_int, ctypes.c_int, wintypes.UINT)
    _sig(user32.GetSystemMetrics, ctypes.c_int, ctypes.c_int)
    _sig(user32.DestroyIcon, wintypes.BOOL, H)
    _sig(shell32.Shell_NotifyIconW, wintypes.BOOL, wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW))
    _sig(kernel32.GetModuleHandleW, H, wintypes.LPCWSTR)


def signal_existing():
    """If another instance owns the tray, asks it to show its window. Returns True if found."""
    if not IS_WIN:
        return False
    hwnd = user32.FindWindowW(CLASS_NAME, None)
    if hwnd:
        user32.PostMessageW(hwnd, WM_APP_SHOW, 0, 0)
        return True
    return False


class Tray:
    """Callbacks run on the tray thread; keep them thread-safe (e.g. queue.put)."""

    def __init__(self, tooltip, on_show, on_quit, on_update=None, icon_path=None):
        self.tooltip = tooltip[:127]
        self.on_show = on_show
        self.on_quit = on_quit
        self.on_update = on_update
        self.icon_path = icon_path
        self.icon_error = None
        self._icon = None
        self._owns_icon = False
        self.hwnd = None
        self._ready = threading.Event()
        self._proc = None
        self._taskbar_created = 0

    def start(self):
        if not IS_WIN:
            return False
        threading.Thread(target=self._run, daemon=True).start()
        self._ready.wait(5)
        return bool(self.hwnd)

    def stop(self):
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)

    def notify(self, title, text):
        if not self.hwnd:
            return
        nid = self._nid(NIF_INFO)
        nid.szInfoTitle, nid.szInfo, nid.dwInfoFlags = title[:63], text[:255], NIIF_INFO
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

    def _nid(self, flags):
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd, nid.uID, nid.uFlags = self.hwnd, 1, flags
        return nid

    def _add(self):
        nid = self._nid(NIF_MESSAGE | NIF_ICON | NIF_TIP)
        nid.uCallbackMessage = WM_APP_TRAY
        nid.hIcon = self._icon
        nid.szTip = self.tooltip
        return shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

    def _run(self):
        try:
            if self.icon_path:
                self._icon = user32.LoadImageW(None, self.icon_path, 1,
                                              user32.GetSystemMetrics(49),
                                              user32.GetSystemMetrics(50), 0x10)
                self._owns_icon = bool(self._icon)
                if not self._icon:
                    self.icon_error = "Não foi possível carregar o ícone da bandeja; será usado o ícone padrão."
            if not self._icon:
                self._icon = user32.LoadIconW(None, ctypes.c_void_p(IDI_APPLICATION))
            self._proc = WNDPROC(self._wndproc)  # keep a reference or it gets collected
            hinst = kernel32.GetModuleHandleW(None)
            wc = WNDCLASSW()
            wc.lpfnWndProc, wc.hInstance, wc.lpszClassName = self._proc, hinst, CLASS_NAME
            user32.RegisterClassW(ctypes.byref(wc))
            self._taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")
            hwnd = user32.CreateWindowExW(0, CLASS_NAME, self.tooltip, 0, 0, 0, 0, 0,
                                          None, None, hinst, None)
            if not hwnd:
                return
            self.hwnd = hwnd
            if not self._add():
                self.hwnd = None
                user32.DestroyWindow(hwnd)
                return
        finally:
            if not self.hwnd and self._owns_icon:
                user32.DestroyIcon(self._icon)
                self._icon = None
                self._owns_icon = False
            self._ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _wndproc(self, hwnd, msg, wp, lp):
        if msg == WM_APP_TRAY:
            ev = lp & 0xFFFF
            if ev in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                self.on_show()
            elif ev == WM_RBUTTONUP:
                self._menu(hwnd)
            return 0
        if msg == WM_APP_SHOW:
            self.on_show()
            return 0
        if self._taskbar_created and msg == self._taskbar_created:
            self._add()  # explorer restarted
            return 0
        if msg == WM_CLOSE:
            user32.DestroyWindow(hwnd)
            return 0
        if msg == WM_DESTROY:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid(0)))
            if self._owns_icon:
                user32.DestroyIcon(self._icon)
                self._icon = None
                self._owns_icon = False
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wp, lp)

    def _menu(self, hwnd):
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, MF_STRING, 1, "Abrir")
        if self.on_update:
            user32.AppendMenuW(menu, MF_STRING, 3, "Verificar atualizações")
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, 2, "Sair")
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(hwnd)  # required so the menu closes when clicking elsewhere
        cmd = user32.TrackPopupMenu(menu, TPM_RETURNCMD | TPM_RIGHTBUTTON, pt.x, pt.y, 0, hwnd, None)
        user32.PostMessageW(hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(menu)
        if cmd == 1:
            self.on_show()
        elif cmd == 2:
            self.on_quit()
        elif cmd == 3 and self.on_update:
            self.on_update()
