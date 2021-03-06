import datetime
import json
import logging
from typing import Optional

from arq import concurrent

from ..utils import display_cash, password_reset_link, static_map_link
from .defaults import Triggers
from .plumbing import BaseEmailActor, UserEmail

logger = logging.getLogger('nosht.email.main')


class EmailActor(BaseEmailActor):
    @concurrent
    async def send_event_conf(self, paid_action_id: int):
        async with self.pg.acquire() as conn:
            data = await conn.fetchrow(
                """
                SELECT t.user_id,
                  full_name(u.first_name, u.last_name, u.email) AS user_name,
                  e.slug, cat.slug as cat_slug, e.name, e.short_description,
                  e.location_name, e.location_lat, e.location_lng,
                  e.start_ts, e.duration, e.price, cat.company, co.currency, a.extra
                FROM tickets AS t
                JOIN actions AS a ON t.paid_action = a.id
                JOIN users AS u ON t.user_id = u.id
                JOIN events AS e ON t.event = e.id
                JOIN categories AS cat ON e.category = cat.id
                JOIN companies co on cat.company = co.id
                WHERE t.paid_action=$1
                LIMIT 1
                """,
                paid_action_id
            )
            buyer_user_id = data['user_id']
            r = await conn.fetch('SELECT user_id FROM tickets WHERE paid_action=$1', paid_action_id)
            other_user_ids = {r_[0] for r_ in r}
            other_user_ids.remove(buyer_user_id)

        duration: Optional[datetime.timedelta] = data['duration']
        ctx = {
            'event_link': '/{cat_slug}/{slug}/'.format(**data),
            'event_name': data['name'],
            'event_short_description': data['short_description'],
            'event_start': data['start_ts'] if duration else data['start_ts'].date(),
            'event_duration': int(duration.total_seconds()) if duration else 'All day',
            'event_location': data['location_name'],
            'ticket_price': display_cash(data['price'], data['currency']),
            'buyer_name': data['user_name']
        }
        lat, lng = data['location_lat'], data['location_lng']
        if lat and lng:
            ctx.update(
                static_map=static_map_link(lat, lng, settings=self.settings),
                google_maps_url=f'https://www.google.com/maps/place/{lat},{lng}/@{lat},{lng},13z',
            )

        ticket_count = len(other_user_ids) + 1
        ctx_buyer = {
            **ctx,
            'ticket_count': ticket_count,
            'ticket_count_plural': ticket_count > 1,
            'total_price': display_cash(data['price'] * ticket_count, data['currency']),
        }
        if data['extra']:
            action_extra = json.loads(data['extra'])
            ctx_buyer['card_details'] = '{card_expiry} - ending {card_last4}'.format(**action_extra)

        await self.send_emails.direct(
            data['company'],
            Triggers.ticket_buyer,
            [UserEmail(id=buyer_user_id, ctx=ctx_buyer)]
        )
        if other_user_ids:
            await self.send_emails.direct(
                data['company'],
                Triggers.ticket_other,
                [UserEmail(id=user_id, ctx=ctx) for user_id in other_user_ids]
            )

    @concurrent
    async def send_account_created(self, user_id: int):
        async with self.pg.acquire() as conn:
            company_id, status = await conn.fetchrow('SELECT company, status FROM users WHERE id=$1', user_id)
        ctx = dict(my_events_link='/my-events/')
        if status == 'pending':
            ctx['confirm_email_link'] = password_reset_link(user_id, auth_fernet=self.auth_fernet)

        await self.send_emails.direct(company_id, Triggers.account_created, [UserEmail(id=user_id, ctx=ctx)])
