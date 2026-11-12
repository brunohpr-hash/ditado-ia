"""Teste de stub v1.7.6 — modo Cobrança de honorários: instrução, atalho, migração, modelo e teto."""
import copy, hashlib, importlib.util, json, os, sys, tempfile, types
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

RAIZ = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ditado", RAIZ / "main.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
assert mod.APP_VERSION == "1.7.6", mod.APP_VERSION
assert json.loads((RAIZ / "version.json").read_text(encoding="utf-8"))["version"] == "1.7.6"

NOME = "Cobrança de honorários"
# instrução de fábrica da v1.5.4–v1.7.4 (a que está salva nos PCs e na nuvem)
ANTIGO = (
    "Você transforma ditados por voz em mensagens de cobrança de honorários "
    "contábeis, em português do Brasil, prontas para enviar no WhatsApp. "
    "Remova muletas e hesitações; corrija gramática e pontuação. "
    "ESTRUTURA OBRIGATÓRIA da mensagem:\n"
    "1. Saudação cordial (use o nome do cliente se for dito).\n"
    "2. Uma frase breve informando que há honorário(s) pendente(s).\n"
    "3. CADA pendência em BLOCO SEPARADO, neste formato (uma linha por campo, "
    "com estes emojis):\n"
    "📄 Competência: <mês/ano>\n"
    "📅 Vencimento: <data>\n"
    "💰 Valor: R$ <valor>\n"
    "(linha em branco entre um bloco e outro)\n"
    "4. Se houver mais de uma pendência, após os blocos inclua: "
    "💵 Total: R$ <soma dos valores> — some você mesmo com atenção.\n"
    "5. Fechamento educado pedindo o pagamento/confirmação (use o prazo que "
    "a pessoa ditar, ex.: 'ainda hoje', 'até sexta'; se não ditar prazo, "
    "peça apenas a gentileza da confirmação).\n"
    "REGRAS: NÃO invente competência, data, valor ou prazo que não foram "
    "ditos — se faltar um campo, escreva 'a confirmar'. NÃO adicione juros, "
    "multas ou ameaças que não foram ditados. Tom sempre cordial e "
    "profissional, nunca agressivo. NÃO adicione assinatura a menos que "
    "a pessoa dite. Responda SOMENTE com a mensagem final, sem comentários."
)
sha = lambda t: hashlib.sha256(" ".join(t.split()).encode("utf-8")).hexdigest()
assert sha(ANTIGO) in mod.HONORARIOS_PROMPTS_ANTIGOS, "hash da instrução antiga não confere"
assert sha(mod.HONORARIOS_PROMPT) not in mod.HONORARIOS_PROMPTS_ANTIGOS

# ---------- fábrica: instalação nova já nasce com atalho padrão, esforço baixo e instrução nova
fab = [m for m in mod.DEFAULT_CONFIG["modes"] if m["nome"] == NOME][0]
assert fab["hotkey"] == "ctrl+shift+h" and fab["prompt"] == mod.HONORARIOS_PROMPT
assert fab["esforco"] == "none" and fab["modelo"] == "qwen/qwen3.8-27b"
P = mod.HONORARIOS_PROMPT
for trecho in ("📄 Competência:", "📅 Vencimento:", "💰 Valor:", "💵 Total:", "NÃO RESUMA", "a confirmar"):
    assert trecho in P, trecho
assert "frase breve informando que há honorário(s) pendente(s).\n3." not in P  # a regra que encurtava
outros = {m["nome"]: m["hotkey"] for m in mod.DEFAULT_CONFIG["modes"] if m["nome"] != NOME}
assert outros == {"E-mail profissional": "alt+e", "Traduzir para inglês": "alt+t"}, outros  # não mexi nos outros


def salvo(**honor):
    """config.json como está hoje no PC do Bruno (modos sem carimbo)."""
    base = {"nome": NOME, "hotkey": "alt+h", "ativo": True, "prompt": ANTIGO}
    base.update(honor)
    return {"hotkey": "ctrl+shift+d", "language": "pt", "_lang_migrated": True, "api_key": "gsk_x",
            "modes": [{"nome": "E-mail profissional", "hotkey": "alt+e", "ativo": True, "prompt": "p-email"},
                      {"nome": "Traduzir para inglês", "hotkey": "alt+t", "ativo": True, "prompt": "p-en"},
                      base]}


def carrega(cfg_salvo):
    mod.APP_DIR.mkdir(parents=True, exist_ok=True)
    mod.CONFIG_PATH.write_text(json.dumps(cfg_salvo, ensure_ascii=False), encoding="utf-8")
    cfg = mod.load_config()
    return cfg, [m for m in cfg["modes"] if m["nome"] == NOME]


# ---------- 1) caso do Bruno: instrução e atalho de fábrica antigos -> ambos atualizados e gravados
cfg, h = carrega(salvo())
assert len(h) == 1 and h[0]["prompt"] == mod.HONORARIOS_PROMPT and h[0]["hotkey"] == "ctrl+shift+h"
assert h[0]["esforco"] == "none" and h[0]["modelo"] == "qwen/qwen3.8-27b"
assert h[0]["ativo"] is True and h[0].get("atualizado_em") and cfg["_atualizado_em"]
disco = json.loads(mod.CONFIG_PATH.read_text(encoding="utf-8"))
hd = [m for m in disco["modes"] if m["nome"] == NOME][0]
assert hd["prompt"] == mod.HONORARIOS_PROMPT and hd["hotkey"] == "ctrl+shift+h", "migração não foi gravada"
assert [m["hotkey"] for m in cfg["modes"] if m["nome"] != NOME] == ["alt+e", "alt+t"]
assert [m["prompt"] for m in cfg["modes"] if m["nome"] != NOME] == ["p-email", "p-en"]
assert cfg["hotkey"] == "ctrl+shift+d" and cfg["api_key"] == "gsk_x"

# ---------- 2) idempotente: abrir o app de novo não mexe em nada (nem no carimbo)
carimbo = h[0]["atualizado_em"]
cfg2 = mod.load_config(); h2 = [m for m in cfg2["modes"] if m["nome"] == NOME][0]
assert h2["atualizado_em"] == carimbo and h2["prompt"] == mod.HONORARIOS_PROMPT
assert mod.migrate_honorarios(cfg2) is False

# ---------- 3) instrução editada pelo usuário: fica como está; o atalho de fábrica ainda migra
cfg, h = carrega(salvo(prompt="minha instrução personalizada"))
assert h[0]["prompt"] == "minha instrução personalizada" and "esforco" not in h[0] and "modelo" not in h[0]
assert h[0]["hotkey"] == "ctrl+shift+h"

# ---------- 4) atalho escolhido pelo usuário: fica como está; a instrução de fábrica ainda migra
cfg, h = carrega(salvo(hotkey="alt+k"))
assert h[0]["hotkey"] == "alt+k" and h[0]["prompt"] == mod.HONORARIOS_PROMPT

# ---------- 5) Ctrl+Shift+H já ocupado por outro modo (ou pelo atalho principal): não cria conflito
ocupado = salvo(); ocupado["modes"][0]["hotkey"] = "Ctrl+Shift+H"
cfg, h = carrega(ocupado)
assert h[0]["hotkey"] == "alt+h" and h[0]["prompt"] == mod.HONORARIOS_PROMPT
ocupado = salvo(); ocupado["hotkey"] = "ctrl+shift+h"
cfg, h = carrega(ocupado)
assert h[0]["hotkey"] == "alt+h"

# ---------- 6) modo apagado pelo usuário: não volta e nada quebra
apagado = salvo(); apagado["modes"] = apagado["modes"][:2]; apagado["modes_removed"] = [NOME]
cfg, h = carrega(apagado)
assert h == [] and len(cfg["modes"]) == 2

# ---------- 7) sincronização: a versão migrada vence a cópia antiga da nuvem, nos dois sentidos
cfg, h = carrega(salvo())
nuvem_antiga = {"modes": copy.deepcopy(salvo()["modes"]), "modes_removed": [], "_atualizado_em": "2026-11-11T15:13:25"}
m = mod.merge_sync(mod.sync_payload(cfg) | {"_atualizado_em": cfg["_atualizado_em"]}, nuvem_antiga)
hm = [x for x in m["modes"] if x["nome"] == NOME][0]
assert hm["prompt"] == mod.HONORARIOS_PROMPT and hm["hotkey"] == "ctrl+shift+h", "nuvem antiga desfez a migração"
# o outro PC (ainda sem atualizar) recebe a versão nova pela nuvem
outro_pc = {"modes": copy.deepcopy(salvo()["modes"]), "_atualizado_em": "2026-11-10T09:00:00"}
m2 = mod.merge_sync(outro_pc, m)
hm2 = [x for x in m2["modes"] if x["nome"] == NOME][0]
assert hm2["prompt"] == mod.HONORARIOS_PROMPT and hm2["hotkey"] == "ctrl+shift+h"
assert hm2["esforco"] == "none" and hm2["modelo"] == "qwen/qwen3.8-27b"

# ---------- 7b) PC já na v1.7.5 (instrução nova, esforço low, sem modelo): ganha o modelo sem perder nada
v175 = salvo(prompt=mod.HONORARIOS_PROMPT, hotkey="ctrl+shift+h", esforco="low", atualizado_em="2026-11-12T08:21:07")
cfg, h = carrega(v175)
assert h[0]["modelo"] == "qwen/qwen3.8-27b" and h[0]["esforco"] == "none" and h[0]["hotkey"] == "ctrl+shift+h"
assert h[0]["prompt"] == mod.HONORARIOS_PROMPT and h[0]["atualizado_em"] > "2026-11-12T08:21:07"
# e vence a cópia da v1.7.5 que está na nuvem (carimbo mais antigo)
nuvem_175 = {"modes": copy.deepcopy(v175["modes"]), "modes_removed": [], "_atualizado_em": "2026-11-12T10:21:28"}
m3 = mod.merge_sync(mod.sync_payload(cfg) | {"_atualizado_em": cfg["_atualizado_em"]}, nuvem_175)
hm3 = [x for x in m3["modes"] if x["nome"] == NOME][0]
assert hm3.get("modelo") == "qwen/qwen3.8-27b" and hm3["esforco"] == "none", "nuvem da 1.7.5 desfez o modelo"
assert mod.migrate_honorarios(cfg) is False  # idempotente

# ---------- 8) Pipeline.cleanup: esforço baixo só onde vale, sem cortar em silêncio
class Resp:
    def __init__(self, code, body=None, text=""): self.status_code = code; self._b = body or {}; self.headers = {}; self.text = text
    def raise_for_status(self):
        if self.status_code >= 400: raise RuntimeError(self.status_code)
    def json(self): return self._b
calls = []
fila = []
def fake_post(url, **kw):
    calls.append(copy.deepcopy(kw["json"]))
    return fila.pop(0) if fila else Resp(200, {"choices": [{"finish_reason": "stop", "message": {"content": "<transcricao>ok</transcricao>"}}]})
mod.requests.post = fake_post
base = {"api_key": "gsk_x", "provider": "groq", "cleanup": True, "cleanup_level": "normal", "dictionary": []}

p = mod.Pipeline(dict(base))
assert p.cleanup("fala", prompt_override="INSTR", effort="low") == "ok" and p.truncated is False
assert calls[-1]["reasoning_effort"] == "low" and calls[-1]["max_tokens"] == mod.MAX_OUT_TOKENS
assert calls[-1]["messages"][0]["content"].startswith("INSTR") and "REGRA ABSOLUTA" in calls[-1]["messages"][0]["content"]
# ditado comum e outros modos: chamada idêntica à de antes (sem o parâmetro)
p.cleanup("fala"); assert "reasoning_effort" not in calls[-1]
p.cleanup("fala", prompt_override="INSTR"); assert "reasoning_effort" not in calls[-1]
# provedor sem modelo de raciocínio: nunca envia
po = mod.Pipeline(dict(base, provider="openai"))
po.cleanup("fala", prompt_override="INSTR", effort="low"); assert "reasoning_effort" not in calls[-1]
# modelo trocado por um que rejeita o parâmetro (400): repete sem ele e entrega
n = len(calls); fila[:] = [Resp(400, text="unknown parameter reasoning_effort")]
assert p.cleanup("fala", prompt_override="INSTR", effort="low") == "ok"
assert len(calls) == n + 2 and "reasoning_effort" in calls[n] and "reasoning_effort" not in calls[n + 1]
# resposta cortada pelo teto: sinaliza (o app avisa o usuário)
fila[:] = [Resp(200, {"choices": [{"finish_reason": "length", "message": {"content": "texto pela meta"}}]})]
assert p.cleanup("fala longa", prompt_override="INSTR", effort="low") == "texto pela meta" and p.truncated is True
p.cleanup("fala"); assert p.truncated is False  # o sinal não vaza para o ditado seguinte
# teto gasto só com raciocínio (conteúdo vazio/None): entrega o bruto, nunca nada
fila[:] = [Resp(200, {"choices": [{"finish_reason": "length", "message": {"content": None}}]})]
assert p.cleanup("fala bruta", prompt_override="INSTR", effort="low") == "fala bruta" and p.truncated is True
# ----- modelo próprio do modo
QW = "qwen/qwen3.8-27b"
assert p.cleanup("fala", prompt_override="INSTR", effort="none", model=QW) == "ok"
assert calls[-1]["model"] == QW and calls[-1]["reasoning_effort"] == "none" and calls[-1]["max_tokens"] == mod.MAX_OUT_TOKENS
# ditado comum e outros modos seguem no modelo padrão, sem o parâmetro
p.cleanup("fala"); assert calls[-1]["model"] == "openai/gpt-oss-120b" and "reasoning_effort" not in calls[-1]
# provedor OpenAI: ignora modelo/esforço do modo (o id não existe lá)
po.cleanup("fala", prompt_override="INSTR", effort="none", model=QW)
assert calls[-1]["model"] == "gpt-4o-mini" and "reasoning_effort" not in calls[-1]
# modelo do modo aposentado (404), recusado (400) ou sem cota (429): cai no padrão com esforço low e entrega
for cod in (404, 400, 429):
    n = len(calls); fila[:] = [Resp(cod, text="model unavailable")]
    assert p.cleanup("fala", prompt_override="INSTR", effort="none", model=QW) == "ok", cod
    assert len(calls) == n + 2 and calls[n]["model"] == QW, cod
    assert calls[n + 1]["model"] == "openai/gpt-oss-120b" and calls[n + 1]["reasoning_effort"] == "low", cod
# ... e se o padrão também recusar o parâmetro, ainda tenta sem ele
n = len(calls); fila[:] = [Resp(404), Resp(400, text="unknown parameter")]
assert p.cleanup("fala", prompt_override="INSTR", effort="none", model=QW) == "ok"
assert len(calls) == n + 3 and "reasoning_effort" not in calls[n + 2] and calls[n + 2]["model"] == "openai/gpt-oss-120b"
# raciocínio vazado no texto é removido
fila[:] = [Resp(200, {"choices": [{"finish_reason": "stop", "message": {"content": "<think>\nvou pensar\n</think>\n\nBom dia, Sr. João."}}]})]
assert p.cleanup("fala", prompt_override="INSTR", effort="none", model=QW) == "Bom dia, Sr. João."
# erro real da API continua subindo (o app entrega o texto bruto)
fila[:] = [Resp(429, text="rate limit")]
try:
    p.cleanup("fala", prompt_override="INSTR", effort="low"); raise AssertionError("429 devia subir")
except RuntimeError:
    pass

print("OK — modo honorários v%s (instrução, atalho, migração, sync, modelo, teto)" % mod.APP_VERSION)
