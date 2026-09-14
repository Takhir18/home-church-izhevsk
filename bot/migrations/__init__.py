"""Append migrations; never edit an already deployed migration."""
from sqlalchemy import select, text
from bot.models import metadata, versions

async def migrate(engine):
    async with engine.begin() as conn:
        if engine.dialect.name == 'postgresql':
            await conn.execute(text('SELECT pg_advisory_xact_lock(186401)'))
        await conn.run_sync(lambda c: versions.create(c, checkfirst=True))
        installed = set((await conn.execute(select(versions.c.version))).scalars())
        if 1 not in installed:
            # Initial schema. Future revisions must explicitly ALTER existing tables.
            await conn.run_sync(metadata.create_all)
            await conn.execute(versions.insert().values(version=1))
