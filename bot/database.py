import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, text, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from bot.models import churches, requests
from bot.migrations import migrate

class Database:
    def __init__(self, url):
        if not url:
            raise RuntimeError('DATABASE_URL must be set')
        if url.startswith(('postgres://', 'postgresql://')):
            url = 'postgresql+asyncpg://' + url.split('://', 1)[1]
        if not url.startswith(('postgresql+asyncpg://', 'sqlite+aiosqlite://')):
            raise RuntimeError('Unsupported DATABASE_URL')
        if os.getenv('RENDER') and not url.startswith('postgresql+asyncpg://'):
            raise RuntimeError('Render requires PostgreSQL')
        self.engine = create_async_engine(url, pool_pre_ping=True, hide_parameters=True)
        if self.engine.dialect.name == 'sqlite':
            @event.listens_for(self.engine.sync_engine, 'connect')
            def foreign_keys(conn, _):
                conn.execute('PRAGMA foreign_keys=ON')

    async def initialize(self, seed=False):
        await migrate(self.engine)
        if seed:
            async with self.engine.begin() as conn:
                if self.engine.dialect.name == 'postgresql':
                    await conn.execute(text('SELECT pg_advisory_xact_lock(186402)'))
                # Only seed an empty catalog; never overwrite administrator edits.
                if not (await conn.execute(select(churches.c.id).limit(1))).first():
                    items = json.loads(Path(__file__).with_name('seed_churches.json').read_text())
                    await conn.execute(churches.insert(), items)

    async def close(self):
        await self.engine.dispose()

    async def ping(self):
        async with self.engine.connect() as conn:
            await conn.execute(select(churches.c.id).limit(1))

    async def list_churches(self, district=None, include_inactive=False):
        query = select(churches).order_by(churches.c.id)
        if not include_inactive:
            query = query.where(churches.c.active.is_(True))
        if district:
            query = query.where(churches.c.district == district)
        async with self.engine.connect() as conn:
            return [dict(r) for r in (await conn.execute(query)).mappings()]

    async def church(self, church_id, include_inactive=False):
        query = select(churches).where(churches.c.id == church_id)
        if not include_inactive:
            query = query.where(churches.c.active.is_(True))
        async with self.engine.connect() as conn:
            row = (await conn.execute(query)).mappings().first()
            return dict(row) if row else None

    async def save_church(self, data, church_id=None):
        async with self.engine.begin() as conn:
            if church_id is None:
                query = churches.insert().values(**data)
            else:
                query = churches.update().where(churches.c.id == church_id).values(**data)
            row = (await conn.execute(query.returning(churches))).mappings().first()
            return dict(row) if row else None

    async def join(self, church_id, user, source):
        async with self.engine.begin() as conn:
            church = (await conn.execute(select(churches).where(
                churches.c.id == church_id, churches.c.active.is_(True)).with_for_update())).mappings().first()
            if not church:
                raise LookupError('Church not found')
            query = select(requests).where(requests.c.church_id == church_id,
                                          requests.c.telegram_id == user['id'])
            existing = (await conn.execute(query)).mappings().first()
            if existing:
                return dict(existing), False
            data = dict(church_id=church_id, telegram_id=user['id'], name=user['name'],
                        username=user.get('username'), status='new', source=source,
                        created_at=datetime.now(timezone.utc))
            try:
                async with conn.begin_nested():
                    row = (await conn.execute(requests.insert().values(**data).returning(requests))).mappings().one()
            except IntegrityError:
                row = (await conn.execute(query)).mappings().one()
                return dict(row), False
            return dict(row), True

    async def list_requests(self, limit=50, offset=0, status=None, request_id=None):
        query = select(requests, churches.c.name.label('church_name'), churches.c.is_test).join(churches)
        if status:
            query = query.where(requests.c.status == status)
        if request_id is not None:
            query = query.where(requests.c.id == request_id)
        query = query.order_by(requests.c.id.desc()).limit(limit).offset(offset)
        async with self.engine.connect() as conn:
            return [dict(r) for r in (await conn.execute(query)).mappings()]

    async def request_status(self, request_id, status):
        async with self.engine.begin() as conn:
            row = (await conn.execute(requests.update().where(requests.c.id == request_id)
                .values(status=status).returning(requests))).mappings().first()
            return dict(row) if row else None

async def initialize():
    db = Database(os.getenv('DATABASE_URL'))
    try:
        await db.initialize(seed=os.getenv('SEED_TEST_DATA', 'false').lower() == 'true')
    finally:
        await db.close()

if __name__ == '__main__':
    asyncio.run(initialize())
