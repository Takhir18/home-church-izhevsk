"""Uses only a disposable TEST_DATABASE_URL, never the production DATABASE_URL."""
import asyncio
import os
import uuid
import pytest
from sqlalchemy import text
from bot.database import Database

@pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='Dedicated PostgreSQL test database not configured')
async def test_postgres_migration_concurrency_persistence_and_polling_lock():
    db=Database(os.environ['TEST_DATABASE_URL'])
    try:
        await asyncio.gather(db.initialize(seed=True),db.initialize(seed=True))
        catalog=await db.list_churches()
        assert catalog
        uid=uuid.uuid4().int % 10**12
        user={'id':uid,'name':'CI Test'}
        results=await asyncio.gather(*(db.join(catalog[0]['id'],user,'telegram') for _ in range(6)))
        assert sum(created for _,created in results)==1
        assert len({r['id'] for r,_ in results})==1
        other=Database(os.environ['TEST_DATABASE_URL'])
        try:
            await other.initialize(seed=True)
            item,new=await other.join(catalog[0]['id'],user,'mini_app')
            assert not new and item['id']==results[0][0]['id']
            async with db.engine.connect() as a,other.engine.connect() as b:
                key=uid
                assert await a.scalar(text('SELECT pg_try_advisory_lock(:k)'),{'k':key})
                assert not await b.scalar(text('SELECT pg_try_advisory_lock(:k)'),{'k':key})
                await a.execute(text('SELECT pg_advisory_unlock(:k)'),{'k':key})
                assert await b.scalar(text('SELECT pg_try_advisory_lock(:k)'),{'k':key})
                await b.execute(text('SELECT pg_advisory_unlock(:k)'),{'k':key})
        finally:
            await other.close()
    finally:
        await db.close()
