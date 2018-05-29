import asyncio
import logging
import os
from datetime import datetime

import asyncpg
from async_timeout import timeout

from .settings import Settings
from .utils import slugify

logger = logging.getLogger('nosht.db')
patches = []


async def lenient_conn(settings: Settings, with_db=True):
    if with_db:
        dsn = settings.pg_dsn
    else:
        dsn, _ = settings.pg_dsn.rsplit('/', 1)

    for retry in range(8, -1, -1):
        try:
            async with timeout(2):
                conn = await asyncpg.connect(dsn=dsn)
        except (asyncpg.PostgresError, OSError) as e:
            if retry == 0:
                raise
            else:
                logger.warning('pg temporary connection error "%s", %d retries remaining...', e, retry)
                await asyncio.sleep(1)
        else:
            logger.info('pg connection successful, version: %s', await conn.fetchval('SELECT version()'))
            return conn


DROP_CONNECTIONS = """
SELECT pg_terminate_backend(pg_stat_activity.pid)
FROM pg_stat_activity
WHERE pg_stat_activity.datname = $1 AND pid <> pg_backend_pid();
"""


async def prepare_database(settings: Settings, overwrite_existing: bool) -> bool:
    """
    (Re)create a fresh database and run migrations.
    :param settings: settings to use for db connection
    :param overwrite_existing: whether or not to drop an existing database if it exists
    :return: whether or not a database has been (re)created
    """
    # the db already exists on heroku and never has to be created
    if settings.on_heroku:
        conn = await lenient_conn(settings, with_db=True)
        try:
            tables = await conn.fetchval("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
            logger.info('existing tables: %d', tables)
            if tables > 0:
                if overwrite_existing:
                    logger.debug('database already exists...')
                else:
                    logger.info('database already exists ✓')
                    return False
        finally:
            await conn.close()
    else:
        conn = await lenient_conn(settings, with_db=False)
        try:
            await conn.execute(DROP_CONNECTIONS, settings.pg_name)
            logger.debug('attempting to create database "%s"...', settings.pg_name)
            try:
                await conn.execute('CREATE DATABASE {}'.format(settings.pg_name))
            except (asyncpg.DuplicateDatabaseError, asyncpg.UniqueViolationError):
                if overwrite_existing:
                    logger.debug('database already exists...')
                else:
                    logger.info('database already exists, skipping creation')
                    return False
            else:
                logger.debug('database did not exist, now created')

            logger.debug('settings db timezone to utc...')
            await conn.execute(f"ALTER DATABASE {settings.pg_name} SET TIMEZONE TO 'UTC';")
        finally:
            await conn.close()

    conn = await asyncpg.connect(dsn=settings.pg_dsn)
    try:
        logger.debug('creating tables from model definition...')
        async with conn.transaction():
            await conn.execute(settings.models_sql + '\n' + settings.logic_sql)
    finally:
        await conn.close()
    logger.info('database successfully setup ✓')
    return True


def reset_database(settings: Settings):
    if not (os.getenv('CONFIRM_DATABASE_RESET') == 'confirm' or input('Confirm database reset? [yN] ') == 'y'):
        print('cancelling')
    else:
        print('resetting database...')
        loop = asyncio.get_event_loop()
        loop.run_until_complete(prepare_database(settings, True))
        print('done.')


def run_patch(settings: Settings, live, patch_name):
    if patch_name is None:
        print('available patches:\n{}'.format(
            '\n'.join('  {}: {}'.format(p.__name__, p.__doc__.strip('\n ')) for p in patches)
        ))
        return
    patch_lookup = {p.__name__: p for p in patches}
    try:
        patch_func = patch_lookup[patch_name]
    except KeyError as e:
        raise RuntimeError(f'patch "{patch_name}" not found in patches: {[p.__name__ for p in patches]}') from e

    print(f'running patch {patch_name} live {live}')
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_run_patch(settings, live, patch_func))


async def _run_patch(settings, live, patch_func):
    conn = await lenient_conn(settings)
    tr = conn.transaction()
    await tr.start()
    print('=' * 40)
    try:
        await patch_func(conn, settings=settings, live=live)
    except BaseException as e:
        print('=' * 40)
        await tr.rollback()
        raise RuntimeError('error running patch, rolling back') from e
    else:
        print('=' * 40)
        if live:
            print('live, committed patch')
            await tr.commit()
        else:
            print('not live, rolling back')
            await tr.rollback()
    finally:
        await conn.close()


def patch(func):
    patches.append(func)
    return func


@patch
async def run_logic_sql(conn, settings, **kwargs):
    """
    run logic.sql code.
    """
    await conn.execute(settings.logic_sql)


CATS = [
    {
        'name': 'Supper Club',
        'image': 'https://nosht.scolvin.com/cat/mountains/options/yQt1XLAPDm',
        'events': [

            {
                'cat': 'supper-club',
                'status': 'published',
                'highlight': True,
                'name': "Frank's Great Supper",
                'start': datetime(2020, 1, 28),
                'price': 30,
                'ticket_limit': 40,
                'image': 'https://nosht.scolvin.com/cat/mountains/options/yQt1XLAPDm',
            },
            {
                'cat': 'supper-club',
                'status': 'published',
                'highlight': True,
                'name': "Jane's Great Supper",
                'start': datetime(2020, 2, 10),
                'price': 25,
                'ticket_limit': None,
                'image': 'https://nosht.scolvin.com/cat/mountains/options/YEcz6kUlsc',
            }
        ]
    },
    {

        'name': 'Singing',
        'image': 'https://nosht.scolvin.com/cat/mountains/options/zwaxBXpsyu',
        'events': [
            {
                'cat': 'singing',
                'status': 'published',
                'highlight': True,
                'name': 'Loud Singing',
                'start': datetime(2020, 2, 15),
                'price': 25,
                'ticket_limit': None,
                'image': 'https://nosht.scolvin.com/cat/mountains/options/g3I6RDoZtE',
            },
            {
                'cat': 'singing',
                'status': 'published',
                'highlight': True,
                'name': 'Quiet Singing',
                'start': datetime(2020, 2, 15),
                'price': 25,
                'ticket_limit': None,
                'image': 'https://nosht.scolvin.com/cat/mountains/options/g3I6RDoZtE',
            },
        ]
    }
]


@patch
async def create_demo_data(conn, settings, **kwargs):
    """
    Create some demo data for manual testing.
    """

    company_id = await conn.fetchval("""
    INSERT INTO companies (name, domain) VALUES ('testing', 'localhost:3000') RETURNING id""")

    await conn.execute("""
    INSERT INTO users (company, type, status, first_name, last_name, email)
    VALUES ($1, 'admin', 'active', 'joe', 'blogs', 'joe.blogs@example.com')
        """, company_id)

    for cat in CATS:
        cat_id = await conn.fetchval("""
    INSERT INTO categories (company, name, slug, image) VALUES ($1, $2, $3, $4) RETURNING id
    """, company_id, cat['name'], slugify(cat['name']), cat['image'])
        events = [
            [company_id, cat_id, e['name'], e['status'], slugify(e['name']), e['start'], e['price'], e['ticket_limit']]
            for e in cat['events']
        ]
        await conn.executemany("""
INSERT INTO events (company, category, name, status, slug, start_ts, price, ticket_limit) 
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""", events)
