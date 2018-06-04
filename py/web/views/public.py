import logging

from asyncpg import Connection

from web.utils import raw_json_response

logger = logging.getLogger('nosht.web')


company_sql = """
SELECT json_build_object(
  'categories', categories,
  'highlight_events', highlight_events,
  'company', row_to_json(company)
)
FROM (
  SELECT array_to_json(array_agg(row_to_json(t))) AS categories FROM (
    SELECT id, name, slug, image, description
    FROM categories
    WHERE company=$1 AND live=TRUE
    ORDER BY sort_index
  ) AS t
) AS categories,
(
  SELECT array_to_json(array_agg(row_to_json(t))) AS highlight_events FROM (
    SELECT e.id, e.name, c.slug as cat_slug, e.slug, e.image, e.short_description, e.location, e.start_ts, 
      EXTRACT(epoch FROM e.duration)::int AS duration
    FROM events AS e
    JOIN categories as c on e.category = c.id
    WHERE c.company=$1 AND status='published' AND e.highlight IS TRUE AND e.start_ts > now()
    ORDER BY start_ts
  ) AS t
) AS highlight_events,
(
  SELECT id, name, image
  FROM companies
  WHERE id=$1
) AS company;
"""


async def index(request):
    conn: Connection = request['conn']
    company_id = request['company_id']
    json_str = await conn.fetchval(company_sql, company_id)
    return raw_json_response(json_str)


category_sql = """
SELECT json_build_object(
  'events', events
)
FROM (
  SELECT array_to_json(array_agg(row_to_json(t))) AS events FROM (
    SELECT e.id, e.name, c.slug as cat_slug, e.slug, e.image, e.short_description, e.location, e.start_ts, 
      EXTRACT(epoch FROM e.duration)::int AS duration
    FROM events AS e
    JOIN categories as c on e.category = c.id
    WHERE c.company=$1 AND c.slug=$2 AND status='published' AND e.start_ts > now()
    ORDER BY start_ts
  ) AS t
) AS events;
"""


async def category(request):
    conn: Connection = request['conn']
    company_id = request['company_id']
    category_slug = request.match_info['category']
    json_str = await conn.fetchval(category_sql, company_id, category_slug)
    return raw_json_response(json_str)
