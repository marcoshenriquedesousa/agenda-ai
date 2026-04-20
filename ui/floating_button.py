"""Botão flutuante sempre visível — acesso rápido aos comandos principais."""
import math
import sys
import threading
from pathlib import Path

from PyQt6.QtCore import Qt, QPoint, QTimer, QObject, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QCursor
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QFrame, QLabel, QSizePolicy,
)

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Estados do botão ─────────────────────────────────────────────────────────
# Cada estado tem: cor de fundo, emoji, texto do tooltip, anima pulso?

_STATES = {
    "loading":   ("#6c5ce7", "⚙️",  True),
    "idle":      ("#3a7bd5", "🎙️",  False),
    "listening": ("#e74c3c", "🎤",  True),
    "thinking":  ("#e67e22", "⏳",  True),
    "speaking":  ("#27ae60", "🔊",  True),
}


class _Signal(QObject):
    state_changed = pyqtSignal(str)

_signal = _Signal()


def set_state(state: str):
    """Chamado de qualquer thread para atualizar o estado do botão."""
    _signal.state_changed.emit(state)


# ── Painel dropdown ───────────────────────────────────────────────────────────

class DropdownPanel(QFrame):
    def __init__(self, on_action_start, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._on_action_start = on_action_start
        self._build()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor("#141c27"))
        p.setPen(QColor("#263045"))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 13, 13)

    def _build(self):
        self.setFixedWidth(230)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        header = QLabel("  Agenda AI")
        header.setStyleSheet(
            "color: #7c9cbf; font-size: 11px; font-weight: 600;"
            "letter-spacing: 1px; padding: 2px 6px 6px 6px;"
        )
        layout.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2d3f55; margin: 0 2px;")
        layout.addWidget(sep)

        for icon, label, handler in [
            ("💬", "Falar",            self._escutar),
            ("📅", "Agenda de hoje",   self._agenda_hoje),
            ("📌", "Meus lembretes",   self._lembretes),
        ]:
            layout.addWidget(self._make_btn(icon, label, handler))

        self.setStyleSheet("QFrame { background: transparent; border: none; }")

    def _make_btn(self, icon, label, handler):
        btn = QPushButton(f"  {icon}  {label}")
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setFixedHeight(42)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.setStyleSheet("""
            QPushButton {
                text-align: left; padding: 0 12px; border: none;
                border-radius: 8px; color: #c9d8ee; font-size: 13px;
                font-family: 'Segoe UI', sans-serif; background: transparent;
            }
            QPushButton:hover   { background: #1e2d40; }
            QPushButton:pressed { background: #253548; }
        """)
        btn.clicked.connect(handler)
        btn.clicked.connect(self.hide)
        return btn

    # ── Ações ─────────────────────────────────────────────────────────────────

    def _run_bg(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    def _escutar(self):
        self._on_action_start()

        def _do():
            set_state("listening")
            from core.agenda import init_db
            from core.voice_in import escutar
            init_db()
            texto = escutar(duracao_max=20)

            if not texto.strip():
                set_state("idle")
                return

            set_state("thinking")
            from core.assistente import processar_comando
            resposta = processar_comando(texto)

            set_state("speaking")
            from core.voice_out import falar
            falar(resposta)
            set_state("idle")

        self._run_bg(_do)

    def _agenda_hoje(self):
        self._on_action_start()

        def _do():
            set_state("thinking")
            from core.agenda import init_db, listar_eventos_hoje
            from core.llm import formatar_briefing_matinal
            from core.voice_out import falar
            init_db()
            texto = formatar_briefing_matinal(listar_eventos_hoje())

            set_state("speaking")
            falar(texto)
            set_state("idle")

        self._run_bg(_do)

    def _lembretes(self):
        self._on_action_start()

        def _do():
            set_state("thinking")
            from core.agenda import init_db, listar_lembretes_ativos
            from core.llm import formatar_lembretes_para_fala
            from core.voice_out import falar
            init_db()
            texto = formatar_lembretes_para_fala(listar_lembretes_ativos())

            set_state("speaking")
            falar(texto)
            set_state("idle")

        self._run_bg(_do)


# ── Botão principal ───────────────────────────────────────────────────────────

class FloatingButton(QWidget):
    _SIZE = 62        # tamanho base do widget (inclui margem para o anel de pulso)
    _BTN  = 50        # diâmetro do círculo visível

    def __init__(self):
        super().__init__()
        self._drag_pos: QPoint | None = None
        self._drag_moved = False
        self._hovered = False

        self._state = "idle"
        self._pulse_phase = 0.0       # 0..2π
        self._pulse_radius = 0        # raio extra do anel animado

        self._dropdown = DropdownPanel(on_action_start=self._dropdown_hide)

        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(30)          # ~33fps
        self._pulse_timer.timeout.connect(self._tick_pulse)

        _signal.state_changed.connect(self._on_state_changed)

        self._setup_window()

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self._SIZE, self._SIZE)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.width() - self._SIZE - 24, screen.height() - self._SIZE - 24)

    # ── Estado ────────────────────────────────────────────────────────────────

    def _on_state_changed(self, state: str):
        self._state = state
        _, _, animated = _STATES.get(state, _STATES["idle"])
        if animated:
            self._pulse_phase = 0.0
            self._pulse_timer.start()
        else:
            self._pulse_timer.stop()
            self._pulse_radius = 0
        self.update()

    def _tick_pulse(self):
        self._pulse_phase = (self._pulse_phase + 0.18) % (2 * math.pi)
        # anel expande e encolhe suavemente entre 0 e 10px
        self._pulse_radius = int(5 + 5 * math.sin(self._pulse_phase))
        self.update()

    # ── Pintura ───────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        color_hex, emoji, animated = _STATES.get(self._state, _STATES["idle"])
        color = QColor(color_hex)
        cx = self._SIZE // 2
        cy = self._SIZE // 2
        r  = self._BTN // 2

        # anel de pulso (só quando animado)
        if animated and self._pulse_radius > 0:
            ring_r = r + self._pulse_radius
            alpha  = max(0, 160 - self._pulse_radius * 14)
            ring_color = QColor(color)
            ring_color.setAlpha(alpha)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(ring_color)
            from PyQt6.QtGui import QPen
            pen = QPen(ring_color, 2)
            p.setPen(pen)
            p.drawEllipse(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2)

        # sombra
        shadow = QColor(0, 0, 0, 50)
        p.setBrush(shadow)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(cx - r + 2, cy - r + 4, r * 2, r * 2)

        # círculo principal
        if self._hovered and self._state == "idle":
            color = color.lighter(120)
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # emoji
        p.setPen(QColor(255, 255, 255))
        font = QFont("Segoe UI Emoji", 20)
        p.setFont(font)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, emoji)

    # ── Mouse ─────────────────────────────────────────────────────────────────

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._drag_moved = False

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.frameGeometry().topLeft() - self._drag_pos
            if delta.manhattanLength() > 5:
                self._drag_moved = True
            if self._drag_moved:
                self._clamp_to_screen(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._drag_moved:
                self._toggle_dropdown()
            self._drag_pos = None
            self._drag_moved = False

    def _clamp_to_screen(self, pos: QPoint):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            max(0, min(pos.x(), screen.width()  - self._SIZE)),
            max(0, min(pos.y(), screen.height() - self._SIZE)),
        )

    # ── Dropdown ──────────────────────────────────────────────────────────────

    def _dropdown_hide(self):
        self._dropdown.hide()

    def _toggle_dropdown(self):
        # não abre o menu enquanto estiver processando
        if self._state != "idle":
            return

        if self._dropdown.isVisible():
            self._dropdown.hide()
            return

        self._dropdown.adjustSize()
        btn_global = self.mapToGlobal(QPoint(0, 0))
        dw = self._dropdown.sizeHint().width()
        dh = self._dropdown.sizeHint().height()
        screen = QApplication.primaryScreen().availableGeometry()

        x = btn_global.x() + self._SIZE - dw
        y = btn_global.y() - dh - 10

        if y < screen.top():
            y = btn_global.y() + self._SIZE + 10
        if x < screen.left():
            x = btn_global.x()

        self._dropdown.move(x, y)
        self._dropdown.show()


# ── Entry point ───────────────────────────────────────────────────────────────

def _preload():
    """Pré-carrega Whisper e TTS em background para eliminar delay no primeiro clique."""
    set_state("loading")
    try:
        from core.agenda import init_db
        from core.voice_in import _get_model
        from core.voice_out import _get_engine
        init_db()
        _get_model()
        _get_engine()
    finally:
        set_state("idle")


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    btn = FloatingButton()
    btn.show()

    threading.Thread(target=_preload, daemon=True).start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
