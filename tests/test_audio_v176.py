"""Teste v1.7.6 — pausa longa no ditado: enxugar_silencio() e limpar_fantasmas() (numpy real, sem API)."""
import importlib.util, os, sys, tempfile, types
from pathlib import Path

import numpy as np

for name in ("keyboard", "pystray", "sounddevice", "pyperclip", "PIL", "PIL.Image", "PIL.ImageDraw"):
    sys.modules[name] = types.ModuleType(name)
sys.modules["PIL"].Image = sys.modules["PIL.Image"]; sys.modules["PIL"].ImageDraw = sys.modules["PIL.ImageDraw"]
tk_stub = types.ModuleType("tkinter")
class _R:
    def __init__(self, *a, **k): pass
    def __getattr__(self, n): return lambda *a, **k: None
tk_stub.Tk = _R; tk_stub.Canvas = _R; sys.modules["tkinter"] = tk_stub
sys.modules["tkinter.font"] = types.ModuleType("tkinter.font")
os.environ["APPDATA"] = tempfile.mkdtemp()
RAIZ = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ditado", RAIZ / "main.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

SR = 16000
rng = np.random.default_rng(3)


def fala(seg, amp=3000.0):
    """'Fala' sintética: tom modulado em sílabas (energia sobe e desce como voz)."""
    t = np.arange(int(SR * seg)) / SR
    env = 0.55 + 0.45 * np.sin(2 * np.pi * 3.2 * t)
    return (amp * env * np.sin(2 * np.pi * 180 * t)).astype(np.float32)


def sil(seg):
    return np.zeros(int(SR * seg), dtype=np.float32)


def mic(x, ruido=30.0):
    return (x + rng.normal(0, ruido, len(x))).clip(-32768, 32767).astype(np.int16)


dur = lambda a: len(a) / SR
enx = mod.enxugar_silencio

# 1) caso de campo: fala + pausa de 8 s + fala + cauda -> a pausa cai para ~0,6 s e a fala fica inteira
a = mic(np.concatenate([fala(20), sil(8), fala(10), sil(3)]))
e = enx(a, SR)
assert 30.0 <= dur(e) <= 31.6, dur(e)          # 30 s de fala + ~0,6 s de pausa + bordas
assert e.dtype == np.int16 and e.ndim == 1

# 2) silêncio só nas pontas (demorou para começar / segurou a tecla no fim)
e = enx(mic(np.concatenate([sil(4), fala(12), sil(5)])), SR)
assert 12.0 <= dur(e) <= 12.8, dur(e)

# 3) pausas normais de fala (até 0,6 s) não são tocadas
a = mic(np.concatenate([fala(6), sil(0.5), fala(6), sil(0.4), fala(6)]))
assert enx(a, SR) is a

# 4) a 2ª parte bem mais baixa (afastou do microfone) NÃO é tratada como silêncio
a = mic(np.concatenate([fala(20), sil(8), fala(10, amp=450.0), sil(3)]))
e = enx(a, SR)
assert 30.0 <= dur(e) <= 31.6, dur(e)

# 5) fala mais fraca que o chiado do ambiente: na dúvida, não corta a fala
a = mic(np.concatenate([fala(20), sil(8), fala(10, amp=420.0), sil(3)]), ruido=400.0)
assert dur(enx(a, SR)) >= 30.0

# 6) nada a fazer / nada seguro a fazer -> devolve o MESMO áudio
for intacto in (
    mic(fala(0.8)),                                          # curtíssimo
    np.zeros(SR * 5, dtype=np.int16),                        # só silêncio
    mic(np.concatenate([fala(10), sil(8), fala(10)]), ruido=2500.0),  # ruído colado na fala
    mic(fala(10, amp=60.0), ruido=5.0),                      # gravação fraca demais
):
    assert enx(intacto, SR) is intacto

# 7) entrada inesperada não derruba o ditado
assert enx(None, SR) is None

# ---------- frases-fantasma do Whisper (só no fim, só as conhecidas)
lf = mod.limpar_fantasmas
remove = {
    "no valor de R$ 694,14. Obrigado por assistir.": "no valor de R$ 694,14.",
    "daquela empresa Ticaçuê. Legenda Adriana Zanotto": "daquela empresa Ticaçuê.",
    "que é o valor do valor? Legenda por Sônia Ruberti": "que é o valor do valor?",
    "no valor de R$ 136,96. Obrigado por assistir. Legenda por Sônia Ruberti": "no valor de R$ 136,96.",
    "Tenha um ótimo dia!\nLegendas pela comunidade Amara.org": "Tenha um ótimo dia!",
    "Obrigado por assistir.": "",
}
for t, esperado in remove.items():
    out, rem = lf(t)
    assert out == esperado and rem, (t, out, rem)
for t in (
    "Muito obrigado por assistir à reunião de ontem, seu João.",
    "Segue o anexo. Legenda de cores da planilha",
    "Fico muito obrigado por assistir",
    "Obrigado por assistir a apresentação. Segue o material.",
    "Desde já agradeço a sua atenção. Tenha um ótimo dia!",
    "",
):
    assert lf(t) == (t, ""), t
assert lf(None) == (None, "")

print("OK — pausa longa e frases-fantasma v%s" % mod.APP_VERSION)
