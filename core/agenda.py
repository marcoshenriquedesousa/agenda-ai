from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timedelta
from pathlib import Path
from core.paths import BASE_DIR
import re

DB_PATH = BASE_DIR / "data" / "agenda.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Session = sessionmaker(bind=engine)
Base = declarative_base()


class Evento(Base):
    __tablename__ = "eventos"

    id = Column(Integer, primary_key=True)
    titulo = Column(String, nullable=False)
    descricao = Column(String, default="")
    data_hora = Column(DateTime, nullable=False)
    lembrete_minutos = Column(Integer, default=15)
    concluido = Column(Boolean, default=False)
    criado_em = Column(DateTime, default=datetime.now)


class Lembrete(Base):
    __tablename__ = "lembretes"

    id = Column(Integer, primary_key=True)
    texto = Column(String, nullable=False)
    data_limite = Column(DateTime, nullable=True)
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.now)
    ultima_notificacao = Column(DateTime, nullable=True)


def init_db():
    Base.metadata.create_all(engine)


def criar_evento(titulo: str, data_hora: datetime, descricao: str = "", lembrete_minutos: int = 15) -> Evento:
    with Session() as session:
        evento = Evento(
            titulo=titulo,
            data_hora=data_hora,
            descricao=descricao,
            lembrete_minutos=lembrete_minutos,
        )
        session.add(evento)
        session.commit()
        session.refresh(evento)
        return evento


def listar_eventos_hoje() -> list[Evento]:
    hoje = datetime.now().date()
    with Session() as session:
        return (
            session.query(Evento)
            .filter(
                Evento.data_hora >= datetime(hoje.year, hoje.month, hoje.day),
                Evento.data_hora < datetime(hoje.year, hoje.month, hoje.day + 1),
                Evento.concluido == False,
            )
            .order_by(Evento.data_hora)
            .all()
        )


def listar_proximos_eventos(limite: int = 10) -> list[Evento]:
    with Session() as session:
        return (
            session.query(Evento)
            .filter(Evento.data_hora >= datetime.now(), Evento.concluido == False)
            .order_by(Evento.data_hora)
            .limit(limite)
            .all()
        )


def marcar_concluido(evento_id: int):
    with Session() as session:
        evento = session.get(Evento, evento_id)
        if evento:
            evento.concluido = True
            session.commit()


def buscar_eventos_por_titulo(titulo: str) -> list[Evento]:
    """Busca eventos ativos com palavras-chave do título (até 1 dia atrás)."""
    palavras = [p for p in re.split(r"\s+", titulo.lower()) if len(p) > 2]
    corte = datetime.now() - timedelta(days=1)
    with Session() as session:
        todos = (
            session.query(Evento)
            .filter(Evento.data_hora >= corte, Evento.concluido == False)
            .all()
        )
        return [e for e in todos if any(p in e.titulo.lower() for p in palavras)]


def deletar_evento(evento_id: int):
    with Session() as session:
        evento = session.get(Evento, evento_id)
        if evento:
            evento.concluido = True
            session.commit()


def editar_evento(evento_id: int, titulo: str | None = None, data_hora: datetime | None = None, descricao: str | None = None):
    with Session() as session:
        evento = session.get(Evento, evento_id)
        if not evento:
            return
        if titulo:
            evento.titulo = titulo
        if data_hora:
            evento.data_hora = data_hora
        if descricao is not None:
            evento.descricao = descricao
        session.commit()


def criar_lembrete(texto: str, data_limite: datetime | None = None) -> Lembrete:
    with Session() as session:
        lembrete = Lembrete(texto=texto, data_limite=data_limite)
        session.add(lembrete)
        session.commit()
        session.refresh(lembrete)
        return lembrete


def listar_lembretes_ativos() -> list[Lembrete]:
    with Session() as session:
        return (
            session.query(Lembrete)
            .filter(Lembrete.ativo == True)
            .order_by(Lembrete.criado_em)
            .all()
        )


def remover_lembrete_por_id(lembrete_id: int):
    with Session() as session:
        lembrete = session.get(Lembrete, lembrete_id)
        if lembrete:
            lembrete.ativo = False
            session.commit()


def buscar_lembretes_por_texto(texto: str) -> list[Lembrete]:
    """Busca lembretes ativos que contenham palavras-chave do texto."""
    palavras = [p for p in re.split(r"\s+", texto.lower()) if len(p) > 3]
    with Session() as session:
        todos = session.query(Lembrete).filter(Lembrete.ativo == True).all()
        return [l for l in todos if any(p in l.texto.lower() for p in palavras)]


def editar_lembrete(lembrete_id: int, texto: str | None = None, data_limite: datetime | None = None):
    with Session() as session:
        lembrete = session.get(Lembrete, lembrete_id)
        if not lembrete:
            return
        if texto:
            lembrete.texto = texto
        if data_limite is not None:
            lembrete.data_limite = data_limite
        session.commit()


def atualizar_notificacao_lembrete(lembrete_id: int):
    with Session() as session:
        lembrete = session.get(Lembrete, lembrete_id)
        if lembrete:
            lembrete.ultima_notificacao = datetime.now()
            session.commit()
