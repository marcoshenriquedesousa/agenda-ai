from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from pathlib import Path
from core.paths import BASE_DIR

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
