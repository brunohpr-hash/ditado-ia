"""Teste de stub do Ditado IA v1.6.0 (roda no Linux sem hardware)."""
import importlib.util, json, os, sys, tempfile, types
from pathlib import Path

for name in ("keyboard", "pystray", "sounddevice", "pyperclip", "PIL", "PIL.Image", "PIL.ImageDraw", "numpy"):
    m = types.ModuleType(name)
    sys.modules[name] = m
sys.modules["PIL"].Image = sys.modules["PIL.Image"]
sys.modules["PIL"].ImageDraw = sys.modules["PIL.ImageDraw"]
sys.modules["numpy"].ndarray = object

tmp = Path(tempfile.mkdtemp())
os.environ["APPDATA"] = str(tmp)

spec = importlib.util.spec_from_file_location("ditado", "/root/projetos/ditado-ia/main.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

assert mod.APP_VERSION == "1.6.1", mod.APP_VERSION
ver = json.loads(Path("/root/projetos/ditado-ia/version.json").read_text())
assert ver["version"] == mod.APP_VERSION, ("version.json desalinhado", ver["version"])

# 1) config antiga com language=auto -> migra para pt uma vez; dicionário nasce vazio
mod.APP_DIR.mkdir(parents=True, exist_ok=True)
mod.CONFIG_PATH.write_text(json.dumps({"language": "auto", "api_key": "gsk_x", "modes": []}), encoding="utf-8")
cfg = mod.load_config()
assert cfg["language"] == "pt" and cfg["_lang_migrated"] is True
assert cfg["dictionary"] == []
assert len(cfg["modes"]) == 3, "modos de fábrica mesclados"
# usuário volta para auto de propósito -> não migra de novo
cfg["language"] = "auto"; mod.save_config(cfg)
assert mod.load_config()["language"] == "auto"

# 2) dicionário: dedupe case-insensitive, ordem preservada, lixo ignorado
cfg["dictionary"] = ["DCTFWeb", " PGDAS ", "dctfweb", "", "Padaria Central Ltda", None, "eSocial"]
terms = mod.dictionary_terms(cfg)
assert terms == ["DCTFWeb", "PGDAS", "Padaria Central Ltda", "eSocial"], terms

# 3) prompt do whisper: curto, termina em ponto, respeita limite
wp = mod.whisper_prompt(cfg)
assert wp == "DCTFWeb, PGDAS, Padaria Central Ltda, eSocial.", wp
assert mod.whisper_prompt({"dictionary": []}) is None
big = {"dictionary": [f"Termo{i:03d}" for i in range(500)]}
assert len(mod.whisper_prompt(big)) <= 601
# guard do LLM
g = mod.dictionary_guard(cfg)
assert "DICIONÁRIO PESSOAL" in g and "eSocial" in g
assert mod.dictionary_guard({"dictionary": []}) == ""

# 4) pipeline usa language + prompt no Whisper e injeta guard no LLM (mock de requests)
calls = []
class FakeResp:
    headers = {}
    def raise_for_status(self): pass
    def json(self):
        return {"text": "ola", "choices": [{"message": {"content": "Olá"}}]}
def fake_post(url, **kw):
    calls.append((url, kw))
    return FakeResp()
mod.requests.post = fake_post
cfg["language"] = "pt"; cfg["provider"] = "groq"
p = mod.Pipeline(cfg)
import io
p.transcribe(io.BytesIO(b"RIFF"))
url, kw = calls[-1]
assert kw["data"]["language"] == "pt" and kw["data"]["prompt"] == wp, kw["data"]
out = p.cleanup("ola dctf web")
sysmsg = calls[-1][1]["json"]["messages"][0]["content"]
assert "DICIONÁRIO PESSOAL" in sysmsg and "REGRA ABSOLUTA" in sysmsg
assert sysmsg.index("DICIONÁRIO PESSOAL") < sysmsg.index("REGRA ABSOLUTA")
assert out == "Olá"

# 5) métodos novos existem na classe
assert hasattr(mod.DitadoApp, "open_dictionary") and hasattr(mod.DitadoApp, "_dictionary_window")
print("OK — todos os testes passaram (v%s)" % mod.APP_VERSION)
