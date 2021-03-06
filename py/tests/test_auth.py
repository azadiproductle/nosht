import base64
import hashlib
import hmac
import json
import re

import pytest
from cryptography import fernet
from pytest_toolbox.comparison import AnyInt, RegexStr

from .conftest import Factory


async def test_login_successful(cli, url, factory: Factory):
    await factory.create_company()
    await factory.create_user()

    r = await cli.get(url('event-categories'))
    assert r.status == 401, await r.text()

    assert len(cli.session.cookie_jar) == 0

    data = dict(
        email='frank@example.com',
        password='testing',
    )
    r = await cli.post(url('login'), data=json.dumps(data))
    assert r.status == 200, await r.text()
    data = await r.json()
    r = await cli.post(url('auth-token'), data=json.dumps({'token': data['auth_token']}))
    assert r.status == 200, await r.text()

    assert len(cli.session.cookie_jar) == 1

    r = await cli.get(url('event-categories'))
    assert r.status == 200, await r.text()


async def test_host_signup_email(cli, url, factory: Factory, db_conn, dummy_server, settings):
    await factory.create_company()
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM users')
    data = {
        'email': 'testing@GMAIL.com',
        'name': 'Jane Doe',
        'grecaptcha_token': '__ok__',
    }
    r = await cli.post(url('signup-host', site='email'), data=json.dumps(data))
    assert r.status == 200, await r.text()
    response_data = await r.json()

    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM users')
    user = await db_conn.fetchrow('SELECT id, company, first_name, last_name, email, role, status FROM users')

    assert response_data == {
        'user': {
            'id': user['id'],
            'name': 'Jane Doe',
            'email': 'testing@gmail.com',
            'role': 'host',
        },
    }
    assert dict(user) == {
        'id': AnyInt(),
        'company': factory.company_id,
        'first_name': 'Jane',
        'last_name': 'Doe',
        'email': 'testing@gmail.com',
        'role': 'host',
        'status': 'pending',
    }
    assert dummy_server.app['log'] == [
        ('grecaptcha', '__ok__'),
        (
            'email_send_endpoint',
            'Subject: "Testing Account Created (Action required)", To: "Jane Doe <testing@gmail.com>"',
        ),
    ]
    email = dummy_server.app['emails'][0]['part:text/plain']
    assert 'Confirm Email' in email
    assert 'Create &amp; Publish Events' not in email
    token = re.search('/set-password/\?sig=([^"]+)', email).group(1)
    token_data = json.loads(fernet.Fernet(settings.auth_key).decrypt(token.encode()).decode())
    assert token_data == {
        'user_id': user['id'],
        'nonce': RegexStr('.{20}'),
    }


async def test_host_signup_google(cli, url, factory: Factory, db_conn, mocker, dummy_server):
    await factory.create_company()
    data = {
        'id_token': 'good.test.token',
        'grecaptcha_token': '__ok__',
    }
    mock_jwt_decode = mocker.patch('web.auth.google_jwt.decode', return_value={
        'iss': 'accounts.google.com',
        'email_verified': True,
        'email': 'google-auth@EXAMPLE.com',
        'given_name': 'Foo',
        'family_name': 'Bar',
    })
    r = await cli.post(url('signup-host', site='google'), data=json.dumps(data))
    assert r.status == 200, await r.text()
    response_data = await r.json()

    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM users')
    user_id, user_company, status = await db_conn.fetchrow('SELECT id, company, status FROM users')

    assert response_data == {
        'user': {
            'id': user_id,
            'name': 'Foo Bar',
            'email': 'google-auth@example.com',
            'role': 'host',
        },
    }
    assert user_company == factory.company_id
    assert status == 'active'
    mock_jwt_decode.assert_called_once()

    assert dummy_server.app['log'] == [
        ('grecaptcha', '__ok__'),
        ('google_siw', None),
        (
            'email_send_endpoint',
            'Subject: "Testing Account Created", To: "Foo Bar <google-auth@example.com>"',
        ),
    ]
    email = dummy_server.app['emails'][0]['part:text/plain']
    assert 'Create &amp; Publish Events' in email
    assert 'Confirm Email' not in email


@pytest.fixture(name='signed_fb_request')
def _fix_signed_fb_request(settings):
    def f(data):
        raw_data = base64.urlsafe_b64encode(json.dumps(data, separators=(',', ':')).encode())[:-1]
        sig_raw = hmac.new(settings.facebook_siw_app_secret, raw_data, hashlib.sha256).digest()
        sig = base64.urlsafe_b64encode(sig_raw).decode()
        return sig[:-1] + '.' + raw_data.decode()

    return f


async def test_host_signup_facebook(cli, url, factory: Factory, db_conn, signed_fb_request):
    await factory.create_company()
    data = {
        'signedRequest': signed_fb_request({'user_id': '123456'}),
        'accessToken': '__ok__',
        'userID': 123456,
        'grecaptcha_token': '__ok__',
    }
    r = await cli.post(url('signup-host', site='facebook'), data=json.dumps(data))
    assert r.status == 200, await r.text()
    response_data = await r.json()

    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM users')
    user_id, user_company = await db_conn.fetchrow('SELECT id, company FROM users')

    assert response_data == {
        'user': {
            'id': user_id,
            'name': 'Book',
            'email': 'facebook-auth@example.com',
            'role': 'host',
        },
    }
    assert user_company == factory.company_id


async def test_host_signup_grecaptcha_invalid(cli, url, factory: Factory, db_conn, dummy_server, settings):
    await factory.create_company()
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM users')
    data = {
        'email': 'testing@gmail.com',
        'name': 'Jane Doe',
        'grecaptcha_token': '__low_score__',
    }
    r = await cli.post(url('signup-host', site='email'), data=json.dumps(data))
    assert r.status == 400, await r.text()
    response_data = await r.json()
    assert response_data == {
        'message': 'Invalid recaptcha value',
    }
