"""Teste de stub do Ditado IA v1.6.0 — pílula (overlay) + botões ✕/✓."""
import importlib.util, io, json, os, sys, tempfile, threading, time, types
from pathlib import Path

for name in ("keyboard", "pystray", "sounddevice", "pyperclip", "PIL", "PIL.Image", "PIL.ImageDraw", "numpy"):
    sys.modules[name] = types.ModuleType(name)
sys.modules["PIL"].Image = sys.modules["PIL.Image"]
sys.modules["PIL"].ImageDraw = sys.modules["PIL.ImageDraw"]
sys.modules["numpy"].ndarray = object
os.environ["APPDATA"] = tempfile.mkdtemp()

# tkinter stub: o Overlay sobe uma thread Tk no __init__; aqui só queremos a API
tk_stub = types.ModuleType("tkinter")
class _Root:
    def __init__(self, *a, **k): pass
    def __getattr__(self, n): return lambda *a, **k: None
tk_stub.Tk = _Root; tk_stub.Canvas = _Root
sys.modules["tkinter"] = tk_stub
sys.modules["tkinter.font"] = types.ModuleType("tkinter.font")

spec = importlib.util.spec_from_file_location("ditado", "/root/projetos/ditado-ia/main.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

# --- Overlay: fila thread-safe e API nova
ov = mod.Overlay.__new__(mod.Overlay)
ov._queue, ov._lock = [], threading.Lock()
ov.show("Fale…"); ov.set_text("la la la"); ov.set_processing("Transcrevendo…")
cb_c, cb_s = (lambda: None), (lambda: None)
ov.set_callbacks(cb_c, cb_s); ov.set_level_source(lambda: 0.5); ov.hide()
acts = [a for a, _ in ov._queue]
assert acts == ["show", "text", "processing", "callbacks", "level_fn", "hide"], acts
assert ov._queue[3][1] == (cb_c, cb_s)
assert mod.Overlay.H == 46 and mod.Overlay.ACCENT == "#34d17b"

# --- ciclo de ditado com botões: simula recorder/keyboard/pipeline
class FakeRecorder:
    level = 0.3
    def __init__(self): self.started = False
    def start(self): self.started = True
    def snapshot(self): return None
    def stop(self):
        import array
        return array.array("h", [1000] * 16000 * 2)  # 2s de "áudio"
class FakeOverlay:
    def __init__(self): self.log = []; self.cb = None
    def show(self, t): self.log.append(("show", t))
    def set_text(self, t): self.log.append(("text", t))
    def set_processing(self, t): self.log.append(("processing", t))
    def set_level_source(self, f): pass
    def set_callbacks(self, on_cancel, on_send): self.cb = (on_cancel, on_send)
    def hide(self): self.log.append(("hide", None))

mod.keyboard.is_pressed = lambda k: True  # usuário segura a tecla "para sempre"
mod.keyboard.send = lambda *a, **k: None
mod.keyboard.release = lambda *a, **k: None
mod.pyperclip.copy = lambda t: None; mod.pyperclip.paste = lambda: pasted[-1] if pasted else ""
pasted = []
_copy = mod.pyperclip.copy
mod.pyperclip.copy = lambda t: pasted.append(t)
# sem seleção nestes cenários (o teste da seleção fica em test_stub_v170)
mod.DitadoApp._grab_selection = lambda self: ""
mod.wav_bytes = lambda frames, sr: io.BytesIO(b"x")
mod.beep = lambda *a, **k: None

calls = []
class P:
    def __init__(self, cfg): pass
    def transcribe(self, wav): calls.append("stt"); return "ola mundo"
    def cleanup(self, raw, prompt_override=None, **k): calls.append("llm"); return "Olá, mundo"
mod.Pipeline = P

def new_app():
    app = mod.DitadoApp.__new__(mod.DitadoApp)
    app.cfg = dict(mod.DEFAULT_CONFIG, api_key="k", live_preview=False, show_overlay=True, mode="segurar")
    app.recorder = FakeRecorder(); app.busy = False; app.recording_toggle = False
    app._economy_notified = False; app._recovering = False; app._last_key_evt = 0.0
    app._probe_until = 0.0; app._cancel_requested = False; app._send_requested = False
    app.icon = None; app.overlay = FakeOverlay(); app._hotkey_handle = None
    app.notify = lambda m: None; app._save_pending = lambda a: None
    return app

# 1) clique em ✓ com a tecla ainda pressionada -> encerra e entrega
app = new_app(); calls.clear(); pasted.clear()
t = threading.Thread(target=app._dictate); t.start()
time.sleep(0.3); assert app.overlay.cb, "callbacks registrados"
app.overlay.cb[1]()  # ✓
t.join(5); assert not t.is_alive(), "ditado não encerrou após ✓"
assert calls == ["stt", "llm"] and pasted[-1] == "Olá, mundo", (calls, pasted)
assert ("processing", "Transcrevendo e corrigindo…") in app.overlay.log
assert app.overlay.log[-1][0] == "hide"

# 2) clique em ✕ -> descarta: nada transcrito, nada colado
app = new_app(); calls.clear(); pasted.clear()
t = threading.Thread(target=app._dictate); t.start()
time.sleep(0.3); app.overlay.cb[0]()  # ✕
t.join(5); assert not t.is_alive()
assert calls == [] and pasted == [], (calls, pasted)
assert app.overlay.log[-1][0] == "hide"

# 3) modo toggle: ✓ também encerra e zera recording_toggle
app = new_app(); app.cfg["mode"] = "toggle"; app.recording_toggle = True; calls.clear()
t = threading.Thread(target=app._dictate); t.start()
time.sleep(0.3); app.overlay.cb[1]()
t.join(5); assert not t.is_alive() and app.recording_toggle is False and calls == ["stt", "llm"]

# 4) overlay desligado nas configs -> ciclo normal sem callbacks (segurar/soltar)
app = new_app(); app.cfg["show_overlay"] = False; calls.clear()
mod.keyboard.is_pressed = lambda k: False
app._dictate(); assert calls == ["stt", "llm"] and app.overlay.cb is None

print("OK — pílula + ✕/✓ (v%s)" % mod.APP_VERSION)
