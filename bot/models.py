from sqlalchemy import (MetaData, Table, Column, Integer, BigInteger, String, Text,
                        Float, Boolean, JSON, DateTime, ForeignKey, UniqueConstraint,
                        CheckConstraint, Index)

metadata = MetaData()
churches = Table('churches', metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String(120), nullable=False),
    Column('leader', String(120), nullable=False),
    Column('leader_username', String(32)),
    Column('district', String(120), nullable=False),
    Column('address', String(300), nullable=False),
    Column('meeting', String(160), nullable=False),
    Column('age', String(80), nullable=False),
    Column('participants', Integer, nullable=False),
    Column('interests', JSON, nullable=False),
    Column('description', Text, nullable=False),
    Column('lat', Float, nullable=False), Column('lon', Float, nullable=False),
    Column('is_test', Boolean, nullable=False, default=True),
    Column('active', Boolean, nullable=False, default=True),
    CheckConstraint('participants >= 0'),
    CheckConstraint('lat >= -90 AND lat <= 90'),
    CheckConstraint('lon >= -180 AND lon <= 180'))
requests = Table('join_requests', metadata,
    Column('id', Integer, primary_key=True),
    Column('church_id', ForeignKey('churches.id', ondelete='RESTRICT'), nullable=False),
    Column('telegram_id', BigInteger, nullable=False),
    Column('name', String(200), nullable=False),
    Column('username', String(32)),
    Column('status', String(20), nullable=False),
    Column('source', String(20), nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False),
    UniqueConstraint('church_id', 'telegram_id', name='uq_request_church_user'),
    CheckConstraint("status IN ('new', 'contacted', 'closed')"))
Index('ix_requests_created', requests.c.created_at)
versions = Table('schema_migrations', metadata,
    Column('version', Integer, primary_key=True))
