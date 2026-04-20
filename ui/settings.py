import json
import shutil
import subprocess
import threading
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QTabWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import QTime

BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "config.json"
VOICE_REF_DIR = BASE_DIR / "assets" / "voice_reference"


def _load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_config(config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


class SettingsWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.config = _load_config()
        self.setWindowTitle("Agenda AI — Configurações")
        self.setMinimumWidth(480)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        tabs = QTabWidget()
        tabs.addTab(self._tab_geral(), "Geral")
        tabs.addTab(self._tab_voz(), "Voz")
        tabs.addTab(self._tab_modelo(), "Modelo")
        tabs.addTab(self._tab_agenda(), "Agenda")
        layout.addWidget(tabs)

        # botões
        btns = QHBoxLayout()
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        btn_salvar = QPushButton("Salvar")
        btn_salvar.setDefault(True)
        btn_salvar.clicked.connect(self._salvar)
        btns.addStretch()
        btns.addWidget(btn_cancelar)
        btns.addWidget(btn_salvar)
        layout.addLayout(btns)

    # ── Aba Geral ────────────────────────────────────────────────────────

    def _tab_geral(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(10)

        self.txt_nome = QLineEdit(self.config["app"].get("assistant_name", "Aria"))
        self.txt_nome.setPlaceholderText("ex: Aria, Luna, Max...")
        form.addRow("Nome da assistente:", self.txt_nome)

        self.chk_autostart = QCheckBox("Iniciar com o Windows")
        self.chk_autostart.setChecked(self.config["app"]["autostart"])
        form.addRow(self.chk_autostart)

        self.chk_briefing = QCheckBox("Falar agenda ao iniciar")
        self.chk_briefing.setChecked(self.config["app"]["morning_briefing"])
        form.addRow(self.chk_briefing)

        self.time_briefing = QTimeEdit()
        h, m = map(int, self.config["app"]["morning_briefing_time"].split(":"))
        self.time_briefing.setTime(QTime(h, m))
        self.time_briefing.setDisplayFormat("HH:mm")
        form.addRow("Horário do briefing:", self.time_briefing)

        self.txt_hotkey = QLineEdit(self.config["app"]["hotkey"])
        self.txt_hotkey.setPlaceholderText("ex: ctrl+alt+a")
        form.addRow("Atalho de ativação:", self.txt_hotkey)

        return w

    # ── Aba Voz ──────────────────────────────────────────────────────────

    # Vozes edge-tts PT-BR disponíveis
    _EDGE_VOICES = [
        ("pt-BR-FranciscaNeural", "Francisca (feminino)"),
        ("pt-BR-AntonioNeural",   "Antonio (masculino)"),
        ("pt-BR-ThalitaNeural",   "Thalita (feminino)"),
        ("pt-BR-BrendaNeural",    "Brenda (feminino)"),
        ("pt-BR-HumbertoNeural",  "Humberto (masculino)"),
        ("pt-BR-MacerioNeural",   "Macerio (masculino)"),
    ]

    def _tab_voz(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(10)

        # microfone
        grp_mic = QGroupBox("Microfone (entrada de voz)")
        mic_layout = QFormLayout(grp_mic)

        self.cmb_mic = QComboBox()
        self._dispositivos = []
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            for i, d in enumerate(devices):
                if d["max_input_channels"] > 0:
                    self.cmb_mic.addItem(d["name"], i)
                    self._dispositivos.append(i)
        except Exception:
            self.cmb_mic.addItem("Padrão do sistema", None)

        atual = self.config["stt"].get("input_device_id")
        for idx in range(self.cmb_mic.count()):
            if self.cmb_mic.itemData(idx) == atual:
                self.cmb_mic.setCurrentIndex(idx)
                break

        mic_layout.addRow("Dispositivo:", self.cmb_mic)
        layout.addWidget(grp_mic)

        # provedor TTS
        grp_tts = QGroupBox("Síntese de voz (TTS)")
        tts_form = QFormLayout(grp_tts)

        self.cmb_provider = QComboBox()
        self.cmb_provider.addItems(["edge-tts", "pyttsx3", "xtts"])
        self.cmb_provider.setCurrentText(self.config["tts"].get("provider", "edge-tts"))
        tts_form.addRow("Provedor:", self.cmb_provider)

        # seletor de voz edge-tts
        self.cmb_edge_voice = QComboBox()
        for voice_id, label in self._EDGE_VOICES:
            self.cmb_edge_voice.addItem(label, voice_id)
        atual_voz = self.config["tts"].get("edge_voice", "pt-BR-FranciscaNeural")
        for idx in range(self.cmb_edge_voice.count()):
            if self.cmb_edge_voice.itemData(idx) == atual_voz:
                self.cmb_edge_voice.setCurrentIndex(idx)
                break
        self._lbl_edge_voice = QLabel("Voz (edge-tts):")
        tts_form.addRow(self._lbl_edge_voice, self.cmb_edge_voice)

        # referência de voz XTTS
        self._lbl_ref_header = QLabel("Voz de referência (XTTS v2):")
        ref_path = self.config["tts"].get("voice_reference", "")
        self.lbl_ref = QLabel(ref_path or "Nenhum arquivo selecionado")
        self.lbl_ref.setWordWrap(True)
        btns_ref = QHBoxLayout()
        btn_importar = QPushButton("Importar WAV...")
        btn_importar.clicked.connect(self._importar_voz)
        btn_gravar = QPushButton("Gravar agora...")
        btn_gravar.clicked.connect(self._gravar_voz)
        btns_ref.addWidget(btn_importar)
        btns_ref.addWidget(btn_gravar)
        self._ref_widget = QWidget()
        ref_inner = QVBoxLayout(self._ref_widget)
        ref_inner.setContentsMargins(0, 0, 0, 0)
        ref_inner.addWidget(self.lbl_ref)
        ref_inner.addLayout(btns_ref)
        tts_form.addRow(self._lbl_ref_header, self._ref_widget)

        layout.addWidget(grp_tts)

        # atualiza visibilidade conforme provedor
        def _atualizar_campos_tts(provider: str):
            is_edge = provider == "edge-tts"
            is_xtts = provider == "xtts"
            self._lbl_edge_voice.setVisible(is_edge)
            self.cmb_edge_voice.setVisible(is_edge)
            self._lbl_ref_header.setVisible(is_xtts)
            self._ref_widget.setVisible(is_xtts)

        self.cmb_provider.currentTextChanged.connect(_atualizar_campos_tts)
        _atualizar_campos_tts(self.cmb_provider.currentText())

        # velocidade
        grp_vel = QGroupBox("Velocidade da fala")
        vel_layout = QHBoxLayout(grp_vel)
        self.sld_velocidade = QSlider(Qt.Orientation.Horizontal)
        self.sld_velocidade.setMinimum(5)
        self.sld_velocidade.setMaximum(20)
        self.sld_velocidade.setValue(int(self.config["tts"]["speed"] * 10))
        self.lbl_vel = QLabel(f'{self.config["tts"]["speed"]:.1f}x')
        self.sld_velocidade.valueChanged.connect(
            lambda v: self.lbl_vel.setText(f"{v / 10:.1f}x")
        )
        vel_layout.addWidget(self.sld_velocidade)
        vel_layout.addWidget(self.lbl_vel)
        layout.addWidget(grp_vel)

        # teste
        btn_testar = QPushButton("Testar voz")
        btn_testar.clicked.connect(self._testar_voz)
        layout.addWidget(btn_testar)
        layout.addStretch()

        return w

    # ── Aba Modelo ───────────────────────────────────────────────────────

    def _tab_modelo(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(10)

        self.txt_modelo = QLineEdit(self.config["llm"]["model"])
        self.txt_modelo.setPlaceholderText("ex: qwen2.5:14b")
        form.addRow("Modelo Ollama:", self.txt_modelo)

        self.txt_url = QLineEdit(self.config["llm"]["base_url"])
        form.addRow("URL do Ollama:", self.txt_url)

        self.sld_temp = QSlider(Qt.Orientation.Horizontal)
        self.sld_temp.setMinimum(0)
        self.sld_temp.setMaximum(10)
        self.sld_temp.setValue(int(self.config["llm"]["temperature"] * 10))
        self.lbl_temp = QLabel(f'{self.config["llm"]["temperature"]:.1f}')
        self.sld_temp.valueChanged.connect(
            lambda v: self.lbl_temp.setText(f"{v / 10:.1f}")
        )
        temp_row = QHBoxLayout()
        temp_row.addWidget(self.sld_temp)
        temp_row.addWidget(self.lbl_temp)
        temp_widget = QWidget()
        temp_widget.setLayout(temp_row)
        form.addRow("Temperatura:", temp_widget)

        # STT
        self.cmb_stt = QComboBox()
        self.cmb_stt.addItems(["tiny", "small", "medium", "large"])
        self.cmb_stt.setCurrentText(self.config["stt"]["model"])
        form.addRow("Modelo Whisper (STT):", self.cmb_stt)

        self.cmb_device = QComboBox()
        self.cmb_device.addItems(["cpu", "cuda"])
        self.cmb_device.setCurrentText(self.config["stt"]["device"])
        form.addRow("Dispositivo STT:", self.cmb_device)

        return w

    # ── Aba Agenda ───────────────────────────────────────────────────────

    def _tab_agenda(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(10)

        self.cmb_lembrete = QComboBox()
        opcoes = [5, 10, 15, 30, 60]
        for o in opcoes:
            self.cmb_lembrete.addItem(f"{o} minutos antes", o)
        atual = self.config["notifications"]["reminder_minutes_before"]
        idx = opcoes.index(atual) if atual in opcoes else 2
        self.cmb_lembrete.setCurrentIndex(idx)
        form.addRow("Lembrete antecipado:", self.cmb_lembrete)

        self.chk_som = QCheckBox("Som na notificação")
        self.chk_som.setChecked(self.config["notifications"]["sound"])
        form.addRow(self.chk_som)

        return w

    # ── Ações ────────────────────────────────────────────────────────────

    def _importar_voz(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar áudio de referência", "", "Áudio (*.wav *.mp3)"
        )
        if path:
            VOICE_REF_DIR.mkdir(parents=True, exist_ok=True)
            dest = VOICE_REF_DIR / "minha_voz.wav"
            shutil.copy(path, dest)
            ref = str(dest.relative_to(BASE_DIR))
            self.lbl_ref.setText(ref)
            self.config["tts"]["voice_reference"] = ref

    def _gravar_voz(self):
        script = BASE_DIR / "tools" / "gravar_voz_referencia.py"
        subprocess.Popen(["python", str(script)], creationflags=subprocess.CREATE_NEW_CONSOLE)

    def _testar_voz(self):
        provider = self.cmb_provider.currentText()
        edge_voice = self.cmb_edge_voice.currentData()
        speed = self.sld_velocidade.value() / 10

        def _falar():
            import asyncio
            import io
            import sounddevice as sd
            import soundfile as sf

            if provider == "edge-tts":
                import edge_tts

                rate = f"+{int((speed - 1) * 100)}%" if speed >= 1 else f"{int((speed - 1) * 100)}%"

                async def _play():
                    audio_bytes = bytearray()
                    communicate = edge_tts.Communicate("Olá! Estou pronto para gerenciar sua agenda.", edge_voice, rate=rate)
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            audio_bytes.extend(chunk["data"])
                    if audio_bytes:
                        data, sr = sf.read(io.BytesIO(bytes(audio_bytes)))
                        sd.play(data, sr)
                        sd.wait()

                asyncio.run(_play())
            else:
                from core.voice_out import falar, recarregar_engine
                recarregar_engine()
                falar("Olá! Estou pronto para gerenciar sua agenda.")

        threading.Thread(target=_falar, daemon=True).start()

    def _salvar(self):
        from core.autostart import ativar, desativar

        self.config["app"]["assistant_name"] = self.txt_nome.text().strip() or "Aria"
        self.config["app"]["autostart"] = self.chk_autostart.isChecked()
        self.config["app"]["morning_briefing"] = self.chk_briefing.isChecked()
        t = self.time_briefing.time()
        self.config["app"]["morning_briefing_time"] = f"{t.hour():02d}:{t.minute():02d}"
        self.config["app"]["hotkey"] = self.txt_hotkey.text().strip()

        self.config["tts"]["provider"] = self.cmb_provider.currentText()
        self.config["tts"]["edge_voice"] = self.cmb_edge_voice.currentData()
        self.config["tts"]["speed"] = self.sld_velocidade.value() / 10

        self.config["llm"]["model"] = self.txt_modelo.text().strip()
        self.config["llm"]["base_url"] = self.txt_url.text().strip()
        self.config["llm"]["temperature"] = self.sld_temp.value() / 10
        self.config["stt"]["model"] = self.cmb_stt.currentText()
        self.config["stt"]["device"] = self.cmb_device.currentText()
        self.config["stt"]["input_device_id"] = self.cmb_mic.currentData()

        self.config["notifications"]["reminder_minutes_before"] = self.cmb_lembrete.currentData()
        self.config["notifications"]["sound"] = self.chk_som.isChecked()

        _save_config(self.config)

        from core.config import invalidate
        invalidate()

        if self.config["app"]["autostart"]:
            ativar()
        else:
            desativar()

        self.accept()


def abrir_configuracoes():
    import sys
    app = QApplication.instance()
    criou_app = False
    if app is None:
        app = QApplication(sys.argv)
        criou_app = True
    win = SettingsWindow()
    win.exec()
    if criou_app:
        app.quit()


if __name__ == "__main__":
    abrir_configuracoes()
