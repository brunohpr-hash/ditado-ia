"""Renderiza a pílula real (Tk em Xvfb) em 3 estados e salva PNG de cada um."""
import importlib.util, os, sys, tempfile, time, types
for name in ("keyboard", "pystray", "sounddevice", "pyperclip", "PIL", "PIL.Image", "PIL.ImageDraw", "numpy"):
    sys.modules[name] = types.ModuleType(name)
sys.modules["PIL"].Image = sys.modules["PIL.Image"]; sys.modules["PIL"].ImageDraw = sys.modules["PIL.ImageDraw"]
sys.modules["numpy"].ndarray = object
os.environ["APPDATA"] = tempfile.mkdtemp()
spec = importlib.util.spec_from_file_location("ditado", "/root/projetos/ditado-ia/main.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

ov = mod.Overlay()
time.sleep(1.0)
ov.set_level_source(lambda: 0.7)
import subprocess
def shot(name):
    time.sleep(0.6)
    r = ov._root
    x, y = r.winfo_rootx(), r.winfo_rooty()
    w, h = r.winfo_width(), r.winfo_height()
    out = f"/root/projetos/ditado-ia/tests/pill_{name}.png"
    for k in [k for k in sys.modules if k == "PIL" or k.startswith("PIL.")]:
        del sys.modules[k]
    from PIL import ImageGrab
    im = ImageGrab.grab(bbox=(max(0, x - 20), max(0, y - 20), x + w + 20, y + h + 20), xdisplay=os.environ.get("DISPLAY"))
    im.save(out)
    print(name, w, h, out)

ov.show("Fale…  (solte para enviar)"); shot("1_vazio")
ov.set_text("la la la, la la la, la la la, la la la, la la la"); shot("2_texto")
ov.set_text("Bom dia, Nathalia. Segue a apuração do PGDAS da Padaria Central referente a outubro de 2026, com vencimento em 20 de novembro, no valor de dois mil trezentos e quarenta reais. Qualquer dúvida, estou à disposição. Isso é um texto bem longo para testar o corte no final."); shot("3_longo")
ov.set_processing("Transcrevendo e corrigindo…"); shot("4_processando")
ov.hide(); time.sleep(0.3)
os._exit(0)
