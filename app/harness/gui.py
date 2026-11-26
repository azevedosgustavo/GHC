"""Tkinter desktop GUI (stdlib only; works on Windows 7 32-bit with Python 3.8)."""
import json
import os
import queue
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

from .agent import run_agent
from .auth import (AuthError, CONFIG_DIR, CopilotSession, device_poll, device_start, load_github_token,
                   logout)
from .client import ChatClient
from .theme import DARK, MODE_LABELS, MODES, load_mode, resolve, save_mode
from .tray import Tray, signal_existing

CHATS_FILE = os.path.join(CONFIG_DIR, "chats.json")
MODELS = ["gpt-4o", "gpt-4.1", "gpt-4o-mini", "o3-mini", "claude-3.5-sonnet"]
SYSTEM = ("Voce e um assistente de programacao rodando em um harness local. "
          "Use as ferramentas para ler arquivos do workspace quando necessario.")

C = dict(DARK)  # live palette, updated in place by App._apply_theme
COLOR_OPTS = ("bg", "fg", "activebackground", "activeforeground", "selectbackground",
              "selectforeground", "insertbackground")
UI_FONT = ("Segoe UI", 10)
MONO = ("Consolas", 10)


def new_chat():
    return {"id": str(int(time.time() * 1000)), "title": "Nova conversa",
            "messages": [{"role": "system", "content": SYSTEM}]}


class App(tk.Tk):
    def __init__(self, root_dir, model, minimized=False):
        super().__init__()
        self.title("Copilot Harness")
        self.geometry("1000x680")
        self.minsize(640, 420)
        self.configure(bg=C["bg"])
        self.root_dir = root_dir
        self.q = queue.Queue()
        self.busy = False
        self.stop_flag = False
        self.client = None
        self.chats = self._load_chats()
        self.current = self.chats[0]
        self._sent_len = 0
        self.mode = load_mode()
        self._themed, self._tag_themed = [], []
        self._style_init()
        self._build(model)
        self._register_colors(self)
        self._apply_theme()
        self.after(2000, self._check_system)
        self._refresh_list()
        self._show_chat()
        self.after(50, self._poll)
        self.tray = Tray("Copilot Harness", lambda: self.q.put(("tray", "show")),
                         lambda: self.q.put(("tray", "quit")))
        self.tray_ok = self.tray.start()
        self.protocol("WM_DELETE_WINDOW", self._on_close_window)
        self.after(200, self._ensure_login)
        if minimized and self.tray_ok:
            self.withdraw()

    def _style_init(self):
        try:
            ttk.Style(self).theme_use("clam")  # the only ttk theme that honours custom colours
        except tk.TclError:
            pass

    def _style(self):
        s = ttk.Style(self)
        s.configure("TCombobox", fieldbackground=C["panel"], background=C["panel"],
                    foreground=C["fg"], arrowcolor=C["fg"], bordercolor=C["panel"],
                    lightcolor=C["panel"], darkcolor=C["panel"])
        s.map("TCombobox", fieldbackground=[("readonly", C["panel"])],
              foreground=[("readonly", C["fg"])])
        s.configure("Vertical.TScrollbar", background=C["panel"], troughcolor=C["bg"],
                    bordercolor=C["bg"], arrowcolor=C["dim"], lightcolor=C["panel"],
                    darkcolor=C["panel"])
        self.option_add("*TCombobox*Listbox.background", C["panel"])
        self.option_add("*TCombobox*Listbox.foreground", C["fg"])
        self.option_add("*TCombobox*Listbox.selectBackground", C["accent"])

    # --- theming -----------------------------------------------------
    def _register_colors(self, w):
        """Records which palette role each widget colour uses (matched by value)."""
        inv = {v.lower(): k for k, v in C.items()}
        for opt in COLOR_OPTS:
            try:
                v = str(w.cget(opt)).lower()
            except tk.TclError:
                continue
            if v in inv:
                self._themed.append((w, opt, inv[v]))
        if isinstance(w, tk.Text):
            for tag in w.tag_names():
                for opt in ("foreground", "background"):
                    v = str(w.tag_cget(tag, opt)).lower()
                    if v in inv:
                        self._tag_themed.append((w, tag, opt, inv[v]))
        for ch in w.winfo_children():
            self._register_colors(ch)

    def _apply_theme(self):
        pal, dark = resolve(self.mode)
        C.update(pal)
        self._sys_state = (pal["bg"], pal["accent"])
        for w, opt, key in self._themed:
            w.configure(**{opt: C[key]})
        for w, tag, opt, key in self._tag_themed:
            w.tag_configure(tag, **{opt: C[key]})
        self._style()
        self._paint_send()
        self.theme_btn.config(text="Tema: " + MODE_LABELS[self.mode])

    def _check_system(self):
        # Reacts to Aero colour / composition changes and the OS dark-mode setting.
        pal, _ = resolve(self.mode)
        if (pal["bg"], pal["accent"]) != self._sys_state:
            self._apply_theme()
        self.after(2000, self._check_system)

    def _cycle_theme(self):
        self.mode = MODES[(MODES.index(self.mode) + 1) % len(MODES)]
        save_mode(self.mode)
        self._apply_theme()

    def _paint_send(self):
        self.send_btn.config(text="Parar" if self.busy else "Enviar",
                             bg=C["danger"] if self.busy else C["accent"])

    def _btn(self, parent, text, cmd, bg=None, fg=None):
        return tk.Button(parent, text=text, command=cmd, bg=bg or C["panel"], fg=fg or C["fg"],
                         activebackground=C["sel"], activeforeground=C["fg"], relief="flat",
                         bd=0, padx=12, pady=6, font=UI_FONT, cursor="hand2")

    def _build(self, model):
        side = tk.Frame(self, bg=C["side"], width=240)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        self._btn(side, "+  Nova conversa", self._on_new).pack(fill="x", padx=10, pady=10)
        self.listbox = tk.Listbox(side, bg=C["side"], fg=C["fg"], bd=0, highlightthickness=0,
                                  selectbackground=C["sel"], selectforeground=C["fg"],
                                  activestyle="none", font=UI_FONT)
        self.listbox.pack(fill="both", expand=True, padx=6)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        self.listbox.bind("<Delete>", self._on_delete)
        foot = tk.Frame(side, bg=C["side"])
        foot.pack(fill="x", padx=10, pady=10)
        self.ws_label = tk.Label(foot, bg=C["side"], fg=C["dim"], font=("Segoe UI", 8),
                                 anchor="w", justify="left", wraplength=210)
        self.ws_label.pack(fill="x")
        self._btn(foot, "Pasta de trabalho...", self._pick_dir).pack(fill="x", pady=(4, 0))
        self.theme_btn = self._btn(foot, "Tema", self._cycle_theme)
        self.theme_btn.pack(fill="x", pady=(4, 0))
        self._btn(foot, "Sair da conta", self._on_logout).pack(fill="x", pady=(4, 0))
        self._update_ws()

        main = tk.Frame(self, bg=C["bg"])
        main.pack(side="left", fill="both", expand=True)
        top = tk.Frame(main, bg=C["bg"])
        top.pack(fill="x", padx=16, pady=(10, 0))
        self.model_var = tk.StringVar(value=model)
        ttk.Combobox(top, textvariable=self.model_var, values=MODELS, width=22).pack(side="left")
        self.status = tk.Label(top, bg=C["bg"], fg=C["dim"], font=("Segoe UI", 9))
        self.status.pack(side="right")

        body = tk.Frame(main, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=16, pady=8)
        self.text = tk.Text(body, bg=C["bg"], fg=C["fg"], bd=0, highlightthickness=0, wrap="word",
                            font=UI_FONT, state="disabled", padx=8, pady=8, spacing3=4,
                            cursor="arrow")
        sb = ttk.Scrollbar(body, command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        t = self.text
        t.tag_configure("who_user", foreground=C["dim"], font=("Segoe UI", 9, "bold"), spacing1=12)
        t.tag_configure("who_bot", foreground=C["accent"], font=("Segoe UI", 9, "bold"), spacing1=12)
        t.tag_configure("user", background=C["panel"], lmargin1=10, lmargin2=10, rmargin=10)
        t.tag_configure("code", background=C["code"], font=MONO, lmargin1=12, lmargin2=12, rmargin=12)
        t.tag_configure("inline", background=C["code"], font=MONO)
        t.tag_configure("tool", foreground=C["dim"], font=("Segoe UI", 9, "italic"))
        t.tag_configure("err", foreground=C["err"])

        box = tk.Frame(main, bg=C["panel"])
        box.pack(fill="x", padx=16, pady=(0, 16))
        self.input = tk.Text(box, height=3, bg=C["panel"], fg=C["fg"], insertbackground=C["fg"],
                             bd=0, highlightthickness=0, wrap="word", font=UI_FONT, padx=10, pady=8)
        self.input.pack(side="left", fill="x", expand=True)
        self.send_btn = self._btn(box, "Enviar", self._on_send, bg=C["accent"], fg="white")
        self.send_btn.pack(side="right", padx=8, pady=8)
        self.input.bind("<Return>", self._on_return)
        self.input.focus_set()

    # --- persistence -------------------------------------------------
    def _load_chats(self):
        try:
            with open(CHATS_FILE, encoding="utf-8") as f:
                chats = json.load(f)
            if chats:
                return chats
        except (IOError, ValueError):
            pass
        return [new_chat()]

    def _save_chats(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(CHATS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.chats, f, ensure_ascii=False)
        except IOError:
            pass

    def _on_close_window(self):
        if self.tray_ok:
            self.withdraw()  # keep running in the tray
        else:
            self._quit()

    def _quit(self):
        self._save_chats()
        self.tray.stop()
        self.destroy()

    def _show_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    # --- sidebar -----------------------------------------------------
    def _refresh_list(self):
        self.listbox.delete(0, "end")
        for c in self.chats:
            self.listbox.insert("end", "  " + c["title"])
        self.listbox.selection_set(self.chats.index(self.current))

    def _on_new(self):
        if self.busy:
            return
        self.current = new_chat()
        self.chats.insert(0, self.current)
        self._refresh_list()
        self._show_chat()

    def _on_select(self, _e):
        sel = self.listbox.curselection()
        if self.busy or not sel:
            self._refresh_list()
            return
        self.current = self.chats[sel[0]]
        self._show_chat()

    def _on_delete(self, _e):
        if self.busy:
            return
        self.chats.remove(self.current)
        if not self.chats:
            self.chats.append(new_chat())
        self.current = self.chats[0]
        self._refresh_list()
        self._show_chat()

    def _pick_dir(self):
        d = filedialog.askdirectory(initialdir=self.root_dir)
        if d:
            self.root_dir = d
            self._update_ws()

    def _update_ws(self):
        self.ws_label.config(text="Workspace:\n" + self.root_dir)

    # --- rendering ---------------------------------------------------
    def _insert(self, s, *tags):
        self.text.config(state="normal")
        self.text.insert("end", s, tags)
        self.text.config(state="disabled")
        self.text.see("end")

    def _show_chat(self):
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.config(state="disabled")
        for m in self.current["messages"]:
            if m["role"] == "user":
                self._insert("Voce\n", "who_user")
                self._insert(m["content"] + "\n", "user")
            elif m["role"] == "assistant":
                for tc in m.get("tool_calls") or []:
                    self._insert("-> %s %s\n" % (tc["function"]["name"], tc["function"]["arguments"]), "tool")
                if m.get("content"):
                    self._insert("Copilot\n", "who_bot")
                    self._render_markdown(m["content"])

    def _render_markdown(self, content):
        parts = content.split("```")
        for i, part in enumerate(parts):
            if i % 2:
                body = part.split("\n", 1)[1] if "\n" in part else part
                self._insert(body.strip("\n") + "\n", "code")
            else:
                for j, seg in enumerate(part.split("`")):
                    self._insert(seg, "inline") if j % 2 else self._insert(seg)
        self._insert("\n")

    # --- sending -----------------------------------------------------
    def _on_return(self, e):
        if e.state & 0x1:  # Shift+Enter inserts a newline
            return None
        self._on_send()
        return "break"

    def _on_send(self):
        if self.busy:
            self.stop_flag = True
            self.status.config(text="Parando...")
            return
        text = self.input.get("1.0", "end").strip()
        if not text:
            return
        if not self.client:
            messagebox.showinfo("Login", "Faca login primeiro.")
            return
        self.input.delete("1.0", "end")
        msgs = self.current["messages"]
        if not any(m["role"] == "user" for m in msgs):
            self.current["title"] = text[:30]
            self._refresh_list()
        self._sent_len = len(msgs)
        msgs.append({"role": "user", "content": text})
        self._insert("Voce\n", "who_user")
        self._insert(text + "\n", "user")
        self._insert("Copilot\n", "who_bot")
        self._set_busy(True)
        self.client.model = self.model_var.get().strip() or "gpt-4o"
        threading.Thread(target=self._worker, args=(msgs, self.root_dir), daemon=True).start()

    def _set_busy(self, b):
        self.busy = b
        self.stop_flag = False
        self._paint_send()
        self.status.config(text="Pensando..." if b else "")

    def _worker(self, msgs, root):
        q = self.q
        try:
            run_agent(self.client, msgs, root,
                      on_text=lambda t: q.put(("text", t)),
                      on_tool=lambda n, a: q.put(("tool", n, a)),
                      should_stop=lambda: self.stop_flag)
            q.put(("done",))
        except AuthError as e:
            q.put(("authfail", str(e)))
        except Exception as e:
            q.put(("error", str(e)))

    def _poll(self):
        try:
            while True:
                ev = self.q.get_nowait()
                kind = ev[0]
                if kind == "text":
                    self._insert(ev[1])
                elif kind == "tool":
                    self._insert("\n-> %s %s\n" % (ev[1], ev[2]), "tool")
                elif kind in ("done", "error"):
                    if kind == "error":
                        self._insert("\n[erro] %s\n" % ev[1], "err")
                        del self.current["messages"][self._sent_len:]  # drop the failed turn
                    else:
                        self._show_chat()
                        if self.state() == "withdrawn":
                            self.tray.notify("Copilot Harness", "Resposta pronta.")
                    self._set_busy(False)
                    self._save_chats()
                elif kind == "authfail":
                    del self.current["messages"][self._sent_len:]
                    self._show_chat()
                    self._set_busy(False)
                    self._on_logout(force=True, msg="Sua sessao expirou. Entre novamente.")
                    self._show_window()
                elif kind == "tray":
                    if ev[1] == "show":
                        self._show_window()
                    else:
                        self._quit()
                        return
                elif kind == "login_code":
                    if not self._login_cancelled:
                        self._on_login_code(ev[1])
                elif kind == "loginerr":
                    if not self._login_cancelled:
                        self._show_login("Falha no login: %s" % ev[1])
                elif kind == "token":
                    if not self._login_cancelled:
                        self._on_token(ev[1])
        except queue.Empty:
            pass
        self.after(50, self._poll)

    # --- login -------------------------------------------------------
    def _build_login(self):
        f = tk.Frame(self, bg=C["bg"])
        box = tk.Frame(f, bg=C["bg"])
        box.place(relx=0.5, rely=0.45, anchor="center")
        tk.Label(box, text="Copilot Harness", bg=C["bg"], fg=C["fg"],
                 font=("Segoe UI", 22, "bold")).pack(pady=(0, 6))
        self.login_msg = tk.Label(box, bg=C["bg"], fg=C["dim"], font=UI_FONT, justify="center",
                                  wraplength=420)
        self.login_msg.pack(pady=(0, 14))
        self.login_code = tk.Label(box, bg=C["panel"], fg=C["fg"], font=("Consolas", 26, "bold"),
                                   padx=24, pady=10)
        self.login_btn = self._btn(box, "Entrar com GitHub", self._start_login, bg=C["accent"], fg="white")
        self.login_open = self._btn(box, "Abrir github.com/login/device", self._open_verify)
        self.login_copy = self._btn(box, "Copiar codigo", self._copy_code)
        self.login_cancel = self._btn(box, "Cancelar", self._cancel_login)
        self.login_frame = f
        self._register_colors(f)
        self._login_cancelled = False
        self._device = None

    def _show_login(self, msg="Entre com sua conta GitHub com assinatura Copilot."):
        if not hasattr(self, "login_frame"):
            self._build_login()
        self._login_cancelled = True
        for w in (self.login_code, self.login_open, self.login_copy, self.login_cancel):
            w.pack_forget()
        self.login_msg.config(text=msg)
        self.login_btn.pack(pady=4)
        self.login_frame.place(x=0, y=0, relwidth=1, relheight=1)
        self.login_frame.lift()

    def _ensure_login(self):
        token = load_github_token()
        if token:
            self._on_token(token)
        else:
            self._show_login()

    def _start_login(self):
        self._login_cancelled = False
        self.login_btn.pack_forget()
        self.login_msg.config(text="Conectando ao GitHub...")

        def run():
            try:
                d = self._device = device_start()
                self.q.put(("login_code", d))
                self.q.put(("token", device_poll(d, lambda: self._login_cancelled)))
            except Exception as e:
                self.q.put(("loginerr", str(e)))

        threading.Thread(target=run, daemon=True).start()

    def _on_login_code(self, d):
        self.login_msg.config(text="Abra a pagina do GitHub e digite este codigo.\n"
                                   "Aguardando autorizacao...")
        self.login_code.config(text=d["user_code"])
        self.login_code.pack(pady=8)
        self.login_open.pack(pady=4)
        self.login_copy.pack(pady=4)
        self.login_cancel.pack(pady=4)
        self._copy_code()
        self._open_verify()

    def _open_verify(self):
        if self._device:
            webbrowser.open(self._device["verification_uri"])

    def _copy_code(self):
        if self._device:
            self.clipboard_clear()
            self.clipboard_append(self._device["user_code"])

    def _cancel_login(self):
        self._show_login()

    def _on_token(self, token):
        self._login_cancelled = True
        self.client = ChatClient(CopilotSession(token), self.model_var.get())
        if hasattr(self, "login_frame"):
            self.login_frame.place_forget()
        self.input.focus_set()

    def _on_logout(self, force=False, msg="Voce saiu. Entre novamente para continuar."):
        if self.busy and not force:
            return
        logout()
        self.client = None
        self._show_login(msg)


def run_gui(root_dir, model, minimized=False):
    if signal_existing():  # already running in the tray: just bring it up
        return
    App(root_dir, model, minimized).mainloop()
