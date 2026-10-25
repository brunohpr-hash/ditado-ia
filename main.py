# -*- coding: utf-8 -*-
"""
Ditado IA — ditado universal com correção por IA.
Segure o atalho (padrão Alt+V), fale, solte: o texto corrigido é digitado
onde o cursor estiver. Funciona em qualquer aplicativo do Windows.

Pipeline: microfone -> Whisper (Groq/OpenAI) -> correção por IA -> colar texto.
"""

import io
import json
import os
import subprocess
import sys
import threading
import time
import traceback
import wave
from datetime import datetime
from pathlib import Path

import keyboard
import numpy as np
import pyperclip
import pystray
import requests
import sounddevice as sd
from PIL import Image, ImageDraw

APP_NAME = "Ditado IA"
APP_VERSION = "1.3.1"
UPDATE_REPO = "brunohpr-hash/ditado-ia"  # repositório oficial de atualizações
UPDATE_RAW = f"https://raw.githubusercontent.com/{UPDATE_REPO}/main"
APP_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "DitadoIA"
CONFIG_PATH = APP_DIR / "config.json"
HISTORY_PATH = APP_DIR / "historico.jsonl"
PENDING_DIR = APP_DIR / "pendentes"

DEFAULT_CONFIG = {
    "hotkey": "alt+v",
    "mode": "segurar",  # segurar (fala enquanto pressiona) | toggle (aperta 1x liga, 1x desliga)
    "show_overlay": True,  # indicador visual no centro inferior da tela
    "live_preview": True,  # texto ao vivo na caixinha enquanto fala
    "suppress_keys": True,  # engole as teclas do atalho (evita digitar "vvvv" no app)
    "provider": "groq",  # groq | openai
    "api_key": "",
    "cleanup": True,
    "cleanup_level": "normal",  # leve | normal | formal
    "language": "auto",  # auto detecta PT/EN/ES etc.
    "sample_rate": 16000,
    "paste_mode": "clipboard",  # clipboard (ctrl+v) | type (digita char a char)
    "max_seconds": 300,
    "modes": [
        {
            "nome": "E-mail profissional",
            "hotkey": "alt+e",
            "ativo": True,
            "prompt": (
                "Você transforma ditados por voz em e-mails profissionais prontos para envio, "
                "em português do Brasil (ou no idioma falado). Remova muletas, hesitações e "
                "falsos começos; corrija gramática e pontuação. Estruture como e-mail: "
                "saudação adequada (se a pessoa indicar o destinatário, use o nome), "
                "parágrafos curtos e claros, tom cordial e profissional sem ser engessado, "
                "e fechamento educado. Se a fala descrever itens ou pedidos múltiplos, "
                "use lista. NÃO invente informações, nomes ou prazos que não foram ditos. "
                "NÃO adicione assinatura a menos que a pessoa dite uma. "
                "Responda SOMENTE com o texto do e-mail, sem comentários."
            ),
        },
        {
            "nome": "Traduzir para inglês",
            "hotkey": "alt+t",
            "ativo": True,
            "prompt": (
                "Você traduz ditados por voz para inglês natural e fluente. "
                "Remova muletas e hesitações antes de traduzir; corrija a estrutura. "
                "O resultado deve soar como um falante nativo escrevendo, não tradução literal. "
                "Mantenha o tom (informal/profissional) da fala original. "
                "Responda SOMENTE com a tradução em inglês, sem comentários."
            ),
        },
    ],
}

PROVIDERS = {
    "groq": {
        "stt_url": "https://api.groq.com/openai/v1/audio/transcriptions",
        "stt_model": "whisper-large-v3",
        "llm_url": "https://api.groq.com/openai/v1/chat/completions",
        "llm_model": "openai/gpt-oss-120b",
    },
    "openai": {
        "stt_url": "https://api.openai.com/v1/audio/transcriptions",
        "stt_model": "whisper-1",
        "llm_url": "https://api.openai.com/v1/chat/completions",
        "llm_model": "gpt-4o-mini",
    },
}

CLEANUP_PROMPTS = {
    "leve": (
        "Você corrige transcrições de ditado por voz. Remova apenas muletas óbvias "
        "(ééé, hum, tipo assim repetido), vícios de hesitação e repetições acidentais. "
        "Corrija pontuação. NÃO mude o estilo nem o vocabulário da pessoa. "
        "Preserve o idioma original de cada trecho. Responda SOMENTE com o texto final."
    ),
    "normal": (
        "Você corrige e estrutura transcrições de ditado por voz. Entregue um texto limpo, natural e bem organizado: "
        "remova muletas (ééé, hum, né, tipo), hesitações, falsos começos e repetições; "
        "corrija gramática, concordância e pontuação; organize frases que ficaram truncadas. "
        "Mantenha 100% do significado e do tom da pessoa — não acrescente nem invente nada. "
        "Se a pessoa se corrigir no meio da fala ('manda às 3... não, melhor, às 4'), use só a versão final. "
        "ESTRUTURA (muito importante): fala é corrida, mas texto bom respira. "
        "Separe o conteúdo em parágrafos curtos (2 a 4 frases cada), um para cada ideia ou assunto. "
        "Quando a pessoa mudar de assunto, iniciar outro raciocínio ou fizer uma ressalva longa, comece um novo parágrafo. "
        "Prefira frases mais curtas: divida períodos longos demais em dois ou três, sem mudar o sentido. "
        "Se o ditado for curto (1 ou 2 frases), não force estrutura: devolva simples. "
        "FORMATAÇÃO: se a fala descrever itens, tarefas, passos ou uma enumeração, formate como lista "
        "(numerada quando houver ordem ou prioridade; com hífens quando não houver). "
        "Se a pessoa reordenar prioridades falando ('na verdade, primeiro X'), a lista final deve refletir a ordem final. "
        "Preserve o idioma original de cada trecho (se misturar português e inglês, mantenha a mistura). "
        "Responda SOMENTE com o texto final, sem comentários."
    ),
    "formal": (
        "Você transforma transcrições de ditado por voz em texto profissional bem estruturado. "
        "Remova muletas e hesitações, corrija gramática e pontuação, eleve levemente o registro "
        "para um tom profissional (e-mails, documentos), mantendo fiel o significado. "
        "ESTRUTURA: organize em parágrafos curtos (2 a 4 frases), um por ideia; "
        "novo assunto ou novo raciocínio = novo parágrafo; divida frases longas demais em frases menores. "
        "Se o ditado for curto, devolva simples, sem forçar estrutura. "
        "Se a fala descrever itens, tarefas ou passos, formate como lista numerada ou com hífens. "
        "Não invente conteúdo. Preserve o idioma original. "
        "Responda SOMENTE com o texto final."
    ),
}


# ---------------------------------------------------------------- utilidades

def log(msg):
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        with open(APP_DIR / "app.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n")
    except Exception:
        pass


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        if CONFIG_PATH.exists():
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except Exception as e:
        log(f"erro lendo config: {e}")
    return cfg


def save_config(cfg):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def append_history(entry):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_history(limit=50):
    if not HISTORY_PATH.exists():
        return []
    lines = HISTORY_PATH.read_text(encoding="utf-8").strip().splitlines()
    out = []
    for ln in lines[-limit:]:
        try:
            out.append(json.loads(ln))
        except Exception:
            pass
    return list(reversed(out))


def wav_bytes(frames, sample_rate):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(frames.tobytes())
    buf.seek(0)
    return buf


def beep(freq=880, dur=120):
    try:
        import winsound
        winsound.Beep(freq, dur)
    except Exception:
        pass


# ---------------------------------------------------------------- pipeline

class Pipeline:
    def __init__(self, cfg):
        self.cfg = cfg

    def _headers(self):
        return {"Authorization": f"Bearer {self.cfg['api_key']}"}

    def transcribe(self, wav_io):
        p = PROVIDERS[self.cfg["provider"]]
        data = {"model": p["stt_model"], "response_format": "json"}
        if self.cfg["language"] not in ("auto", "", None):
            data["language"] = self.cfg["language"]
        r = requests.post(
            p["stt_url"],
            headers=self._headers(),
            files={"file": ("audio.wav", wav_io, "audio/wav")},
            data=data,
            timeout=120,
        )
        r.raise_for_status()
        return (r.json().get("text") or "").strip()

    def cleanup(self, raw_text, prompt_override=None):
        if not raw_text:
            return raw_text
        if prompt_override is None and not self.cfg.get("cleanup", True):
            return raw_text
        p = PROVIDERS[self.cfg["provider"]]
        prompt = prompt_override or CLEANUP_PROMPTS.get(
            self.cfg.get("cleanup_level", "normal"), CLEANUP_PROMPTS["normal"])
        r = requests.post(
            p["llm_url"],
            headers={**self._headers(), "Content-Type": "application/json"},
            json={
                "model": p["llm_model"],
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": raw_text},
                ],
            },
            timeout=60,
        )
        r.raise_for_status()
        out = r.json()["choices"][0]["message"]["content"].strip()
        return out or raw_text


# ---------------------------------------------------------------- gravador

class Recorder:
    def __init__(self, cfg):
        self.cfg = cfg
        self._frames = []
        self._stream = None
        self.level = 0.0  # nível do microfone (0..1), para a animação

    def start(self):
        self._frames = []
        self.level = 0.0
        sr = int(self.cfg.get("sample_rate", 16000))

        def cb(indata, n, t, status):
            self._frames.append(indata.copy())
            try:
                rms = float(np.sqrt(np.mean(indata.astype(np.float32) ** 2))) / 32768.0
                # suaviza: sobe rápido, desce devagar
                alvo = min(1.0, rms * 14.0)
                self.level = max(alvo, self.level * 0.85)
            except Exception:
                pass

        self._stream = sd.InputStream(samplerate=sr, channels=1, dtype="int16", callback=cb)
        self._stream.start()

    def snapshot(self):
        """Áudio acumulado até agora, sem parar a gravação (para prévia ao vivo)."""
        frames = list(self._frames)
        if not frames:
            return None
        try:
            return np.concatenate(frames, axis=0).flatten()
        except Exception:
            return None

    def stop(self):
        self.level = 0.0
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if not self._frames:
            return None
        return np.concatenate(self._frames, axis=0).flatten()


# ---------------------------------------------------------------- update

UPDATE_FILES = ["main.py", "requirements.txt", "LEIA-ME.md", "iniciar.bat", "instalar.bat"]


def check_remote_version(timeout=10):
    """Retorna (versao_remota, changelog) ou (None, None) se offline/erro."""
    try:
        r = requests.get(f"{UPDATE_RAW}/version.json", timeout=timeout)
        r.raise_for_status()
        d = r.json()
        return d.get("version"), d.get("changelog", "")
    except Exception as e:
        log(f"update check falhou: {e}")
        return None, None


def version_tuple(v):
    try:
        return tuple(int(x) for x in str(v).split("."))
    except Exception:
        return (0,)


def download_update(app_dir):
    """Baixa os arquivos novos para <app_dir>. Retorna lista dos atualizados."""
    updated = []
    for fname in UPDATE_FILES:
        try:
            r = requests.get(f"{UPDATE_RAW}/{fname}", timeout=30)
            if r.status_code != 200:
                continue
            dest = app_dir / fname
            tmp = dest.with_suffix(dest.suffix + ".new")
            tmp.write_bytes(r.content)
            tmp.replace(dest)  # troca atômica
            updated.append(fname)
        except Exception as e:
            log(f"update: falha baixando {fname}: {e}")
    return updated


def restart_app():
    """Reinicia o app com o código novo (bootstrap pythonw, sem console)."""
    script = Path(__file__).resolve()
    exe = sys.executable
    # pythonw.exe do venv se existir (sem janela de console)
    pyw = Path(exe).with_name("pythonw.exe")
    if pyw.exists():
        exe = str(pyw)
    try:
        if os.name == "nt":
            # bootstrap em python puro: espera 2s (app velho solta hooks/ícone)
            # e relança — sem cmd/ping, que falhavam sem console
            boot = ("import time,subprocess; time.sleep(2); "
                    f"subprocess.Popen([{exe!r}, {str(script)!r}], "
                    f"cwd={str(script.parent)!r})")
            flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | NEW_PROCESS_GROUP
            subprocess.Popen([exe, "-c", boot], creationflags=flags, close_fds=True)
            log("restart: bootstrap lançado")
        else:
            subprocess.Popen([exe, str(script)], cwd=str(script.parent))
    except Exception as e:
        log(f"restart falhou: {e}")
    os._exit(0)


# ---------------------------------------------------------------- overlay

class Overlay:
    """Caixinha flutuante no centro inferior: texto ao vivo + ondas animadas."""

    BG = "#1e1e28"
    ACCENT = "#34d17b"  # verde das ondas
    N_BARS = 24

    def __init__(self):
        self._root = None
        self._label = None
        self._canvas = None
        self._queue = []
        self._lock = threading.Lock()
        self._visible = False
        self._level_fn = None   # callback que devolve o nível do mic (0..1)
        self._phase = 0.0
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        import tkinter as tk
        self._root = tk.Tk()
        self._root.overrideredirect(True)  # sem borda/título
        self._root.attributes("-topmost", True)
        try:
            self._root.attributes("-alpha", 0.94)
        except Exception:
            pass
        self._root.configure(bg=self.BG)

        self._label = tk.Label(
            self._root, text="", font=("Segoe UI", 11),
            fg="#ffffff", bg=self.BG, padx=18, pady=(10),
            wraplength=560, justify="left",
        )
        self._label.pack(fill="x")

        self._canvas = tk.Canvas(
            self._root, width=600, height=34, bg=self.BG,
            highlightthickness=0, bd=0,
        )
        self._canvas.pack(pady=(0, 8))

        self._root.withdraw()

        def reposition():
            self._root.update_idletasks()
            w = max(self._root.winfo_reqwidth(), 620)
            h = self._root.winfo_reqheight()
            sw = self._root.winfo_screenwidth()
            sh = self._root.winfo_screenheight()
            self._root.geometry(f"{w}x{h}+{(sw - w) // 2}+{sh - h - 70}")

        def draw_waves():
            self._canvas.delete("all")
            if not self._visible:
                return
            import math
            lvl = 0.0
            if self._level_fn:
                try:
                    lvl = max(0.0, min(1.0, float(self._level_fn())))
                except Exception:
                    lvl = 0.0
            self._phase += 0.35
            cw = int(self._canvas.winfo_width()) or 600
            ch = 34
            mid = ch / 2
            n = self.N_BARS
            total_w = n * 14
            x0 = (cw - total_w) / 2
            for i in range(n):
                # cada barra oscila com fase própria; altura = base + voz
                osc = (math.sin(self._phase + i * 0.55) + 1) / 2  # 0..1
                h_base = 3 + osc * 4
                h_voice = lvl * 22 * (0.4 + 0.6 * osc)
                bh = min(mid - 2, h_base + h_voice)
                x = x0 + i * 14
                self._canvas.create_rectangle(
                    x, mid - bh, x + 7, mid + bh,
                    fill=self.ACCENT, outline="",
                )

        def poll():
            with self._lock:
                actions = self._queue[:]
                self._queue.clear()
            for act, arg in actions:
                if act == "show":
                    self._label.config(text=arg)
                    if not self._visible:
                        self._visible = True
                        self._root.deiconify()
                    reposition()
                elif act == "text":
                    self._label.config(text=arg)
                    reposition()
                elif act == "level_fn":
                    self._level_fn = arg
                elif act == "hide":
                    self._visible = False
                    self._level_fn = None
                    self._root.withdraw()
            if self._visible:
                draw_waves()
            self._root.after(50, poll)

        self._root.after(50, poll)
        self._root.mainloop()

    def show(self, text):
        with self._lock:
            self._queue.append(("show", text))

    def set_text(self, text):
        """Atualiza só o texto (prévia ao vivo), mantendo a caixinha aberta."""
        with self._lock:
            self._queue.append(("text", text))

    def set_level_source(self, fn):
        """Define a função que fornece o nível do microfone (0..1)."""
        with self._lock:
            self._queue.append(("level_fn", fn))

    def hide(self):
        with self._lock:
            self._queue.append(("hide", None))


# ---------------------------------------------------------------- app

class DitadoApp:
    def __init__(self):
        self.cfg = load_config()
        self.recorder = Recorder(self.cfg)
        self.busy = False
        self.recording_toggle = False  # estado do modo toggle (mãos livres)
        self.icon = None
        self.overlay = None
        self._hotkey_handle = None

    # ---------- texto -> cursor
    def paste_text(self, text):
        if self.cfg.get("paste_mode") == "type":
            keyboard.write(text, delay=0.005)
            return
        old = None
        try:
            old = pyperclip.paste()
        except Exception:
            pass
        pyperclip.copy(text)
        time.sleep(0.08)
        keyboard.send("ctrl+v")
        time.sleep(0.25)
        if old is not None:
            try:
                pyperclip.copy(old)
            except Exception:
                pass

    # ---------- ciclo de ditado
    def on_hotkey(self, mode=None):
        """mode=None -> ditado padrão; mode=dict -> modo customizado (ex.: e-mail)."""
        if self.cfg.get("mode", "segurar") == "toggle":
            # mãos livres: 1º toque começa, 2º toque encerra
            if self.recording_toggle:
                self.recording_toggle = False  # _dictate percebe e finaliza
            else:
                if self.busy:
                    return
                self.recording_toggle = True
                threading.Thread(target=self._dictate, args=(mode,), daemon=True).start()
        else:
            if self.busy:
                return
            threading.Thread(target=self._dictate, args=(mode,), daemon=True).start()

    def _main_key(self):
        return self.cfg["hotkey"].split("+")[-1].strip()

    def _overlay_show(self, text):
        if self.overlay and self.cfg.get("show_overlay", True):
            self.overlay.show(text)

    def _overlay_hide(self):
        if self.overlay:
            self.overlay.hide()

    def _dictate(self, mode=None):
        self.busy = True
        toggle_mode = self.cfg.get("mode", "segurar") == "toggle"
        mode_name = (mode or {}).get("nome")
        mode_prompt = (mode or {}).get("prompt")
        mode_hotkey = (mode or {}).get("hotkey") or self.cfg["hotkey"]
        try:
            beep(880, 100)
            label = f"🎙️  {mode_name} — Escutando..." if mode_name else "🎙️  Escutando..."
            hint = ("  (solte para enviar)" if not toggle_mode
                    else f"  ({mode_hotkey.upper()} para parar)")
            self._overlay_show(label + hint)
            self.recorder.start()
            if self.overlay and self.cfg.get("show_overlay", True):
                self.overlay.set_level_source(lambda: self.recorder.level)

            # ---- prévia ao vivo: transcreve o acumulado a cada ~2,5s
            stop_preview = threading.Event()

            def live_preview():
                if not self.cfg.get("live_preview", True):
                    return
                pipe_prev = Pipeline(self.cfg)
                last_len = 0
                while not stop_preview.wait(2.5):
                    snap = self.recorder.snapshot()
                    if snap is None or len(snap) < self.cfg["sample_rate"]:
                        continue
                    if len(snap) == last_len:  # nada de áudio novo
                        continue
                    last_len = len(snap)
                    try:
                        parcial = pipe_prev.transcribe(
                            wav_bytes(snap, self.cfg["sample_rate"]))
                        if parcial and not stop_preview.is_set():
                            # mostra só o final, para caber na caixinha
                            if len(parcial) > 220:
                                parcial = "…" + parcial[-220:]
                            self.overlay.set_text(parcial)
                    except Exception:
                        pass  # prévia é melhor-esforço; o ditado final não depende dela

            if self.overlay and self.cfg.get("show_overlay", True):
                threading.Thread(target=live_preview, daemon=True).start()

            key = mode_hotkey.split("+")[-1].strip()
            t0 = time.time()
            if toggle_mode:
                while self.recording_toggle:
                    if time.time() - t0 > self.cfg.get("max_seconds", 300):
                        self.recording_toggle = False
                        break
                    time.sleep(0.05)
            else:
                while keyboard.is_pressed(key):
                    if time.time() - t0 > self.cfg.get("max_seconds", 300):
                        break
                    time.sleep(0.03)
            stop_preview.set()
            audio = self.recorder.stop()
            beep(660, 80)
            if audio is None or len(audio) < self.cfg["sample_rate"] // 4:
                self._overlay_hide()
                return  # gravação curta demais

            self._overlay_show("✨  Transcrevendo e corrigindo...")
            wav = wav_bytes(audio, self.cfg["sample_rate"])
            pipe = Pipeline(self.cfg)
            try:
                raw = pipe.transcribe(wav)
            except Exception as e:
                body = getattr(getattr(e, "response", None), "text", "")
                log(f"erro API (transcricao): {e} | {body[:300]}\n{traceback.format_exc()}")
                self._save_pending(audio)
                self.notify("Sem conexão com a IA. Áudio salvo em pendentes.")
                beep(300, 300)
                return
            try:
                final = pipe.cleanup(raw, prompt_override=mode_prompt)
            except Exception as e:
                body = getattr(getattr(e, "response", None), "text", "")
                log(f"erro API (correcao, usando texto bruto): {e} | {body[:300]}")
                final = raw  # transcrição ok; entrega sem correção

            if final:
                self.paste_text(final)
                append_history({
                    "ts": datetime.now().isoformat(timespec="seconds"),
                    "bruto": raw,
                    "final": final,
                    "modo": mode_name or "padrão",
                })
        finally:
            self._overlay_hide()
            self.recording_toggle = False
            self.busy = False

    def _save_pending(self, audio):
        PENDING_DIR.mkdir(parents=True, exist_ok=True)
        name = PENDING_DIR / f"audio_{datetime.now():%Y%m%d_%H%M%S}.wav"
        with wave.open(str(name), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.cfg["sample_rate"])
            w.writeframes(audio.tobytes())

    def process_pending(self):
        if not PENDING_DIR.exists():
            self.notify("Nenhum áudio pendente.")
            return
        files = sorted(PENDING_DIR.glob("*.wav"))
        if not files:
            self.notify("Nenhum áudio pendente.")
            return
        pipe = Pipeline(self.cfg)
        ok = 0
        for f in files:
            try:
                with open(f, "rb") as fh:
                    raw = pipe.transcribe(io.BytesIO(fh.read()))
                final = pipe.cleanup(raw)
                append_history({
                    "ts": datetime.now().isoformat(timespec="seconds"),
                    "bruto": raw, "final": final, "origem": f.name,
                })
                f.unlink()
                ok += 1
            except Exception as e:
                log(f"pendente {f.name} falhou: {e}")
        self.notify(f"{ok} áudio(s) transcrito(s). Veja no Histórico.")

    def notify(self, msg):
        try:
            if self.icon:
                self.icon.notify(msg, APP_NAME)
        except Exception:
            pass

    # ---------- hotkey
    def register_hotkey(self):
        # remove todos os hotkeys antigos (padrão + modos)
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        self._hotkey_handle = keyboard.add_hotkey(
            self.cfg["hotkey"], self.on_hotkey,
            suppress=bool(self.cfg.get("suppress_keys", True)),
        )
        # modos customizados (e-mail profissional, tradução etc.)
        for m in self.cfg.get("modes", []):
            if not m.get("ativo", True) or not m.get("hotkey"):
                continue
            try:
                keyboard.add_hotkey(
                    m["hotkey"], lambda m=m: self.on_hotkey(mode=m),
                    suppress=bool(self.cfg.get("suppress_keys", True)),
                )
            except Exception as e:
                log(f"falha registrando modo '{m.get('nome')}' ({m.get('hotkey')}): {e}")

    # ---------- atualização
    def do_update_check(self, silent=False):
        """Verifica a nuvem; se houver versão nova, pergunta e aplica."""
        remote, changelog = check_remote_version()
        if not remote:
            if not silent:
                self.notify("Não foi possível verificar atualizações (sem internet?).")
            return
        if version_tuple(remote) <= version_tuple(APP_VERSION):
            if not silent:
                self.notify(f"Você já está na versão mais recente ({APP_VERSION}).")
            return

        def ask_and_apply():
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            msg = (f"Nova versão disponível: {remote} (atual: {APP_VERSION})\n\n"
                   f"Novidades:\n{changelog or '(sem descrição)'}\n\n"
                   "Atualizar agora? O app reinicia sozinho.")
            ok = messagebox.askyesno(f"{APP_NAME} — Atualização", msg, parent=root)
            root.destroy()
            if not ok:
                return
            app_dir = Path(__file__).resolve().parent
            updated = download_update(app_dir)
            if "main.py" in updated:
                log(f"update: v{APP_VERSION} -> v{remote} ({', '.join(updated)})")
                self.notify(f"Atualizado para v{remote}! Reiniciando...")
                time.sleep(1.5)
                try:
                    if self.icon:
                        self.icon.stop()
                except Exception:
                    pass
                restart_app()
            else:
                self.notify("Falha ao baixar a atualização. Veja o app.log.")

        threading.Thread(target=ask_and_apply, daemon=True).start()

    # ---------- janelas (tkinter)
    def open_settings(self):
        threading.Thread(target=self._settings_window, daemon=True).start()

    def _settings_window(self):
        import tkinter as tk
        from tkinter import ttk

        win = tk.Tk()
        win.title(f"{APP_NAME} — Configurações")
        win.geometry("460x420")
        win.attributes("-topmost", True)
        pad = {"padx": 12, "pady": 6}

        frm = ttk.Frame(win)
        frm.pack(fill="both", expand=True, **pad)

        # Atalho
        ttk.Label(frm, text="Atalho (segure para falar):").grid(row=0, column=0, sticky="w")
        hot_var = tk.StringVar(master=win, value=self.cfg["hotkey"])
        hot_entry = ttk.Entry(frm, textvariable=hot_var, width=20)
        hot_entry.grid(row=0, column=1, sticky="w")

        def detect():
            hot_var.set("pressione as teclas...")
            win.update()
            try:
                combo = keyboard.read_hotkey(suppress=False)
                hot_var.set(combo)
            except Exception:
                hot_var.set(self.cfg["hotkey"])

        ttk.Button(frm, text="Detectar", command=detect).grid(row=0, column=2, padx=6)

        # Modo de ativação
        ttk.Label(frm, text="Modo de ativação:").grid(row=1, column=0, sticky="w")
        mode_var = tk.StringVar(master=win, value=self.cfg.get("mode", "segurar"))
        ttk.Combobox(frm, textvariable=mode_var, values=["segurar", "toggle"],
                     state="readonly", width=18).grid(row=1, column=1, sticky="w")
        ttk.Label(frm, text="toggle = mãos livres", foreground="#666").grid(
            row=1, column=2, sticky="w")

        # Provedor
        ttk.Label(frm, text="Provedor de IA:").grid(row=2, column=0, sticky="w")
        prov_var = tk.StringVar(master=win, value=self.cfg["provider"])
        ttk.Combobox(frm, textvariable=prov_var, values=["groq", "openai"],
                     state="readonly", width=18).grid(row=2, column=1, sticky="w")

        # API key
        ttk.Label(frm, text="Chave de API:").grid(row=3, column=0, sticky="w")
        key_var = tk.StringVar(master=win, value=self.cfg["api_key"])
        ttk.Entry(frm, textvariable=key_var, width=38, show="*").grid(
            row=3, column=1, columnspan=2, sticky="w")

        # Correção IA
        clean_var = tk.BooleanVar(master=win, value=self.cfg.get("cleanup", True))
        ttk.Checkbutton(frm, text="Correção por IA (remove muletas, corrige gramática)",
                        variable=clean_var).grid(row=4, column=0, columnspan=3, sticky="w")

        over_var = tk.BooleanVar(master=win, value=self.cfg.get("show_overlay", True))
        ttk.Checkbutton(frm, text="Mostrar indicador 'Escutando...' na tela",
                        variable=over_var).grid(row=9, column=0, columnspan=3, sticky="w")

        prev_var = tk.BooleanVar(master=win, value=self.cfg.get("live_preview", True))
        ttk.Checkbutton(frm, text="Prévia do texto ao vivo enquanto fala (na caixinha)",
                        variable=prev_var).grid(row=11, column=0, columnspan=3, sticky="w")

        sup_var = tk.BooleanVar(master=win, value=self.cfg.get("suppress_keys", True))
        ttk.Checkbutton(frm, text="Bloquear teclas do atalho (evita 'vvv' em alguns apps)",
                        variable=sup_var).grid(row=10, column=0, columnspan=3, sticky="w")

        ttk.Label(frm, text="Nível da correção:").grid(row=5, column=0, sticky="w")
        lvl_var = tk.StringVar(master=win, value=self.cfg.get("cleanup_level", "normal"))
        ttk.Combobox(frm, textvariable=lvl_var, values=["leve", "normal", "formal"],
                     state="readonly", width=18).grid(row=5, column=1, sticky="w")

        # Idioma
        ttk.Label(frm, text="Idioma (auto = detecta sozinho):").grid(row=6, column=0, sticky="w")
        lang_var = tk.StringVar(master=win, value=self.cfg.get("language", "auto"))
        ttk.Combobox(frm, textvariable=lang_var,
                     values=["auto", "pt", "en", "es"], state="readonly",
                     width=18).grid(row=6, column=1, sticky="w")

        # Modo de colagem
        ttk.Label(frm, text="Inserir texto via:").grid(row=7, column=0, sticky="w")
        paste_var = tk.StringVar(master=win, value=self.cfg.get("paste_mode", "clipboard"))
        ttk.Combobox(frm, textvariable=paste_var,
                     values=["clipboard", "type"], state="readonly",
                     width=18).grid(row=7, column=1, sticky="w")

        info = (f"Versão instalada: {APP_VERSION}\n"
                "Groq: crie uma chave gratuita em console.groq.com\n"
                "A chave fica salva somente neste computador.")
        ttk.Label(frm, text=info, foreground="#666").grid(
            row=8, column=0, columnspan=3, sticky="w", pady=(10, 0))

        ttk.Button(frm, text="🔄 Verificar atualizações",
                   command=lambda: self.do_update_check(silent=False)).grid(
            row=12, column=0, columnspan=3, pady=(4, 0))

        def salvar():
            self.cfg["hotkey"] = hot_var.get().strip() or "alt+v"
            self.cfg["mode"] = mode_var.get() or self.cfg.get("mode", "segurar")
            self.cfg["show_overlay"] = over_var.get()
            self.cfg["live_preview"] = prev_var.get()
            self.cfg["suppress_keys"] = sup_var.get()
            self.cfg["provider"] = prov_var.get() or self.cfg.get("provider", "groq")
            nova_chave = key_var.get().strip()
            if nova_chave:  # nunca apaga a chave por campo vazio
                self.cfg["api_key"] = nova_chave
            self.cfg["cleanup"] = clean_var.get()
            self.cfg["cleanup_level"] = lvl_var.get() or self.cfg.get("cleanup_level", "normal")
            self.cfg["language"] = lang_var.get() or "auto"
            self.cfg["paste_mode"] = paste_var.get() or "clipboard"
            save_config(self.cfg)
            self.register_hotkey()
            win.destroy()
            self.notify(f"Salvo! Atalho atual: {self.cfg['hotkey']}")

        ttk.Button(frm, text="Salvar", command=salvar).grid(
            row=11, column=0, columnspan=3, pady=16)

        win.mainloop()

    def open_history(self):
        threading.Thread(target=self._history_window, daemon=True).start()

    def open_modes(self):
        threading.Thread(target=self._modes_window, daemon=True).start()

    def _modes_window(self):
        import tkinter as tk
        from tkinter import ttk, messagebox

        win = tk.Tk()
        win.title(f"{APP_NAME} — Modos de ditado")
        win.geometry("680x460")
        win.attributes("-topmost", True)

        cols = ("nome", "atalho", "ativo")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=8)
        tree.heading("nome", text="Modo")
        tree.heading("atalho", text="Atalho")
        tree.heading("ativo", text="Ativo")
        tree.column("nome", width=300)
        tree.column("atalho", width=120)
        tree.column("ativo", width=60, anchor="center")
        tree.pack(fill="x", padx=10, pady=(10, 4))

        def refresh():
            tree.delete(*tree.get_children())
            for m in self.cfg.get("modes", []):
                tree.insert("", "end", values=(
                    m.get("nome", "?"), m.get("hotkey", "-"),
                    "sim" if m.get("ativo", True) else "não"))

        refresh()

        frm = ttk.LabelFrame(win, text="Editar modo selecionado / criar novo")
        frm.pack(fill="both", expand=True, padx=10, pady=6)

        ttk.Label(frm, text="Nome:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        nome_var = tk.StringVar(master=win)
        ttk.Entry(frm, textvariable=nome_var, width=34).grid(row=0, column=1, sticky="w")

        ttk.Label(frm, text="Atalho:").grid(row=0, column=2, sticky="w", padx=6)
        hot_var = tk.StringVar(master=win)
        ttk.Entry(frm, textvariable=hot_var, width=14).grid(row=0, column=3, sticky="w")

        ativo_var = tk.BooleanVar(master=win, value=True)
        ttk.Checkbutton(frm, text="Ativo", variable=ativo_var).grid(row=0, column=4, padx=6)

        ttk.Label(frm, text="Instrução (como a IA deve tratar a fala):").grid(
            row=1, column=0, columnspan=5, sticky="w", padx=6)
        prompt_txt = tk.Text(frm, height=7, width=80, wrap="word")
        prompt_txt.grid(row=2, column=0, columnspan=5, padx=6, pady=4, sticky="we")

        def on_select(_=None):
            sel = tree.selection()
            if not sel:
                return
            idx = tree.index(sel[0])
            m = self.cfg["modes"][idx]
            nome_var.set(m.get("nome", ""))
            hot_var.set(m.get("hotkey", ""))
            ativo_var.set(m.get("ativo", True))
            prompt_txt.delete("1.0", "end")
            prompt_txt.insert("1.0", m.get("prompt", ""))

        tree.bind("<<TreeviewSelect>>", on_select)

        def salvar_modo():
            nome = nome_var.get().strip()
            if not nome:
                messagebox.showwarning(APP_NAME, "Dê um nome ao modo.", parent=win)
                return
            novo = {
                "nome": nome,
                "hotkey": hot_var.get().strip().lower(),
                "ativo": ativo_var.get(),
                "prompt": prompt_txt.get("1.0", "end").strip(),
            }
            modes = self.cfg.setdefault("modes", [])
            sel = tree.selection()
            if sel:  # editar existente
                modes[tree.index(sel[0])] = novo
            else:    # criar novo
                modes.append(novo)
            save_config(self.cfg)
            self.register_hotkey()
            refresh()
            self.notify(f"Modo '{nome}' salvo ({novo['hotkey'] or 'sem atalho'}).")

        def excluir_modo():
            sel = tree.selection()
            if not sel:
                return
            idx = tree.index(sel[0])
            m = self.cfg["modes"].pop(idx)
            save_config(self.cfg)
            self.register_hotkey()
            refresh()
            self.notify(f"Modo '{m.get('nome')}' removido.")

        def novo_modo():
            tree.selection_remove(tree.selection())
            nome_var.set("")
            hot_var.set("")
            ativo_var.set(True)
            prompt_txt.delete("1.0", "end")

        btns = ttk.Frame(win)
        btns.pack(pady=8)
        ttk.Button(btns, text="Novo", command=novo_modo).pack(side="left", padx=4)
        ttk.Button(btns, text="Salvar modo", command=salvar_modo).pack(side="left", padx=4)
        ttk.Button(btns, text="Excluir", command=excluir_modo).pack(side="left", padx=4)

        win.mainloop()

    def _history_window(self):
        import tkinter as tk
        from tkinter import ttk

        win = tk.Tk()
        win.title(f"{APP_NAME} — Histórico")
        win.geometry("640x480")
        win.attributes("-topmost", True)

        cols = ("hora", "texto")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        tree.heading("hora", text="Quando")
        tree.heading("texto", text="Texto final")
        tree.column("hora", width=140, anchor="w")
        tree.column("texto", width=470, anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        entries = read_history(100)
        for e in entries:
            tree.insert("", "end", values=(e.get("ts", ""), e.get("final", "")))

        def copiar(_=None):
            sel = tree.selection()
            if sel:
                idx = tree.index(sel[0])
                pyperclip.copy(entries[idx].get("final", ""))

        tree.bind("<Double-1>", copiar)
        ttk.Label(win, text="Dica: duplo clique copia o texto para a área de transferência.").pack(pady=(0, 8))
        win.mainloop()

    # ---------- bandeja
    def _make_icon_image(self):
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([24, 8, 40, 38], radius=8, fill=(30, 144, 255, 255))
        d.arc([16, 20, 48, 48], start=0, end=180, fill=(30, 144, 255, 255), width=4)
        d.line([32, 48, 32, 56], fill=(30, 144, 255, 255), width=4)
        d.line([24, 56, 40, 56], fill=(30, 144, 255, 255), width=4)
        return img

    def run(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        self.overlay = Overlay()  # indicador visual flutuante
        if not self.cfg.get("api_key"):
            # primeira execução: abre configurações
            self.open_settings()

        self.register_hotkey()

        # checagem silenciosa de atualização ao iniciar (só avisa se houver nova)
        threading.Timer(8.0, lambda: self.do_update_check(silent=True)).start()

        menu = pystray.Menu(
            pystray.MenuItem(f"Atalho: segure {self.cfg['hotkey'].upper()} e fale",
                             None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Histórico", lambda: self.open_history()),
            pystray.MenuItem("Modos de ditado", lambda: self.open_modes()),
            pystray.MenuItem("Transcrever pendentes", lambda: self.process_pending()),
            pystray.MenuItem("Configurações", lambda: self.open_settings()),
            pystray.MenuItem("Verificar atualizações",
                             lambda: self.do_update_check(silent=False)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair", lambda: self.icon.stop()),
        )
        self.icon = pystray.Icon(APP_NAME, self._make_icon_image(), APP_NAME, menu)
        self.icon.run()


if __name__ == "__main__":
    try:
        DitadoApp().run()
    except Exception as e:
        log(f"fatal: {e}\n{traceback.format_exc()}")
        raise
