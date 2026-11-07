from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

NAMING_CONVENTION = {
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def build_session_factory(database_url: str, connect_timeout: int = 5) -> sessionmaker[Session]:
    # Without a timeout, psycopg on Windows waits forever on a refused connection, so a stopped
    # Postgres would hang requests instead of returning 503.
    engine = create_engine(
        database_url, pool_pre_ping=True, connect_args={"connect_timeout": connect_timeout}
    )
    return sessionmaker(engine)
