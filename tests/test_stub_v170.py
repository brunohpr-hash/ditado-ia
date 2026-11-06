"""Teste de stub v1.7.0 — sync casa↔escritório + comando sobre seleção."""
import importlib.util, io, json, os, sys, tempfile, types
from pathlib import Path

for name in ("keyboard", "pystray", "sounddevice", "pyperclip", "PIL", "PIL.Image", "PIL.ImageDraw", "numpy"):
    sys.modules[name] = types.ModuleType(name)
sys.modules["PIL"].Image = sys.modules["PIL.Image"]; sys.modules["PIL"].ImageDraw = sys.modules["PIL.ImageDraw"]
sys.modules["numpy"].ndarray = object
tk_stub = types.ModuleType("tkinter")
class _R:
    def __init__(self, *a, **k): pass
    def __getattr__(self, n): return lambda *a, **k: None
tk_stub.Tk = _R; tk_stub.Canvas = _R; sys.modules["tkinter"] = tk_stub
sys.modules["tkinter.font"] = types.ModuleType("tkinter.font")
APPDATA = Path(tempfile.mkdtemp()); os.environ["APPDATA"] = str(APPDATA)

spec = importlib.util.spec_from_file_location("ditado", "/root/projetos/ditado-ia/main.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
assert mod.APP_VERSION == "1.7.0", mod.APP_VERSION
assert json.loads(Path("/root/projetos/ditado-ia/version.json").read_text())["version"] == "1.7.0"

# ---------- merge_sync
casa = {"dictionary": ["DCTFWeb", "PGDAS"], "modes": [{"nome": "E-mail", "hotkey": "alt+e", "atualizado_em": "2026-11-06T10:00"}],
        "language": "pt", "_atualizado_em": "2026-11-06T10:00"}
escritorio = {"dictionary": ["pgdas", "Reinf"], "modes": [{"nome": "E-mail", "hotkey": "alt+m", "atualizado_em": "2026-11-06T11:00"},
              {"nome": "Honorários", "hotkey": "alt+h"}], "language": "auto", "_atualizado_em": "2026-11-06T11:00"}
m = mod.merge_sync(casa, escritorio)
assert m["dictionary"] == ["DCTFWeb", "PGDAS", "Reinf"], m["dictionary"]          # união, dedupe case-insensitive
assert {x["nome"] for x in m["modes"]} == {"E-mail", "Honorários"}
assert [x for x in m["modes"] if x["nome"] == "E-mail"][0]["hotkey"] == "alt+m"  # mais novo vence
assert m["language"] == "auto"                                                   # remoto é mais novo
m2 = mod.merge_sync(escritorio, casa)
assert m2["language"] == "auto"                                                  # local é mais novo -> mantém
assert mod.merge_sync(casa, None)["dictionary"] == ["DCTFWeb", "PGDAS"]

# tombstones: removi "PGDAS" no escritório (mais novo) -> não volta de casa
esc2 = dict(escritorio, dictionary=["Reinf"], dictionary_removed=["pgdas"])
m3 = mod.merge_sync(casa, esc2)
assert "PGDAS" not in m3["dictionary"] and "Reinf" in m3["dictionary"], m3["dictionary"]
# re-adicionei em casa DEPOIS (casa mais nova, sem tombstone) -> volta
casa2 = dict(casa, _atualizado_em="2026-11-06T12:00", dictionary_removed=[])
m4 = mod.merge_sync(casa2, esc2)
assert "PGDAS" in m4["dictionary"], m4["dictionary"]
# modo apagado no escritório não ressuscita
esc3 = dict(escritorio, modes=[], modes_removed=["E-mail"])
m5 = mod.merge_sync(casa, esc3)
assert all(x["nome"] != "E-mail" for x in m5["modes"]), m5["modes"]
# load_config respeita modes_removed (não re-injeta modo de fábrica apagado)
mod.APP_DIR.mkdir(parents=True, exist_ok=True)
mod.CONFIG_PATH.write_text(json.dumps({"modes": [], "modes_removed": ["Cobrança de honorários"], "language": "pt"}), encoding="utf-8")
cfg = mod.load_config()
assert "Cobrança de honorários" not in {x["nome"] for x in cfg["modes"]} and len(cfg["modes"]) == 2

# sync_payload nunca leva chave de API nem atalho
cfg["api_key"] = "gsk_secret"; cfg["hotkey"] = "alt+v"
pl = mod.sync_payload(cfg)
assert "api_key" not in pl and "hotkey" not in pl and "dictionary" in pl

# ---------- Sync: pull/push contra uma API fake (GitHub Contents)
from base64 import b64encode, b64decode
store = {"content": None, "sha": None}
class Resp:
    def __init__(self, code, body=None): self.status_code = code; self._b = body or {}; self.headers = {}
    def raise_for_status(self):
        if self.status_code >= 400: raise RuntimeError(self.status_code)
    def json(self): return self._b
def fake_get(url, headers=None, timeout=None):
    assert url.endswith("/contents/ditado.json") and headers["Authorization"].startswith("token ")
    if store["content"] is None: return Resp(404)
    return Resp(200, {"content": b64encode(store["content"].encode()).decode(), "sha": store["sha"]})
def fake_put(url, headers=None, json=None, timeout=None):
    if store["sha"] and json.get("sha") != store["sha"]: return Resp(409)
    store["content"] = b64decode(json["content"]).decode(); store["sha"] = f"sha{len(store['content'])}"
    return Resp(200, {})
mod.requests.get = fake_get; mod.requests.put = fake_put
mod.SYNC_PATH.write_text(json.dumps({"repo": "x/dados", "github_token": "ghp_t"}), encoding="utf-8")
s = mod.Sync(); assert s.ativo
cfg["dictionary"] = ["DCTFWeb"]
merged = s.push(cfg); assert merged and merged["dictionary"] == ["DCTFWeb"] and store["content"]
# "outro PC" adiciona termo e publica
cfg_outro = dict(cfg, dictionary=["Reinf"], _atualizado_em="2099-01-01")
merged2 = mod.Sync().push(cfg_outro); assert set(merged2["dictionary"]) == {"DCTFWeb", "Reinf"}
# o primeiro PC puxa -> ganha Reinf
remoto, sha = mod.Sync().pull(); assert set(remoto["dictionary"]) == {"DCTFWeb", "Reinf"} and sha

# ---------- bootstrap: reaproveita sync.json do Tarefa IA
mod.SYNC_PATH.unlink()
tia = APPDATA / "TarefaIA"; tia.mkdir(); (tia / "sync.json").write_text(json.dumps({"repo": "x/dados", "github_token": "ghp_t"}))
app = mod.DitadoApp.__new__(mod.DitadoApp); app.cfg = cfg
app._bootstrap_sync_file(); assert mod.SYNC_PATH.exists(), "não copiou do TarefaIA"

# ---------- sync_now aplica merge no cfg e salva
app.register_hotkey = lambda: None; app.notify = lambda m: None
app.cfg["dictionary"] = ["eSocial"]
assert app.sync_now(silent=True) is True
assert set(app.cfg["dictionary"]) == {"eSocial", "DCTFWeb", "Reinf"}, app.cfg["dictionary"]
assert json.loads(mod.CONFIG_PATH.read_text())["dictionary"] == app.cfg["dictionary"]

# ---------- comando sobre seleção: edit_selection manda texto + instrução, sem guard anti-resposta
calls = []
def fake_post(url, **kw): calls.append(kw); return Resp(200, {"choices": [{"message": {"content": "Prezado cliente, segue."}}]})
mod.requests.post = fake_post
p = mod.Pipeline(dict(cfg, provider="groq"))
out = p.edit_selection("oi cliente, segue ai", "deixa mais formal")
msgs = calls[-1]["json"]["messages"]
assert "TEXTO SELECIONADO" in msgs[0]["content"] and "REGRA ABSOLUTA" not in msgs[0]["content"]
assert "<texto_selecionado>\noi cliente, segue ai" in msgs[1]["content"] and "deixa mais formal" in msgs[1]["content"]
assert out == "Prezado cliente, segue."

# ---------- _grab_selection: marcador detecta ausência de seleção; restaura clipboard
clip = {"v": "conteudo antigo"}
mod.pyperclip.copy = lambda t: clip.__setitem__("v", t); mod.pyperclip.paste = lambda: clip["v"]
mod.keyboard.release = lambda k: None
mod.keyboard.send = lambda combo: None            # app sem seleção: Ctrl+C não altera clipboard
app.cfg["selection_command"] = True
assert app._grab_selection() == "" and clip["v"] == "conteudo antigo"
def send_copia(combo): clip["v"] = "  texto marcado  "   # app com seleção
mod.keyboard.send = send_copia
assert app._grab_selection() == "texto marcado" and clip["v"] == "conteudo antigo"
app.cfg["selection_command"] = False
assert app._grab_selection() == ""

print("OK — sync + comando sobre seleção (v%s)" % mod.APP_VERSION)
