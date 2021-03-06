import asyncio
import logging
import random
import re
import string
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from typing import Set

import aiobotocore
from PIL import Image

from .settings import Settings

logger = logging.getLogger('nosht.images')
LARGE_SIZE = 3840, 1000
SMALL_SIZE = 1920, 500


@contextmanager
def check_size_save(image_data: bytes):
    try:
        img = Image.open(BytesIO(image_data))
    except OSError:
        raise ValueError('invalid image')
    width, height = SMALL_SIZE
    if img.width < width or img.height < height:
        raise ValueError(f'too small: {img.width}x{img.height}<{SMALL_SIZE[0]}x{SMALL_SIZE[1]}')


def create_s3_session(settings: Settings):
    auth = dict(
        aws_access_key_id=settings.aws_access_key,
        aws_secret_access_key=settings.aws_secret_key,
    )
    session = aiobotocore.get_session()
    return session.create_client('s3', region_name='eu-west-1', **auth)


async def list_images(path: Path, settings: Settings) -> Set[str]:
    files = set()
    async with create_s3_session(settings) as s3:
        paginator = s3.get_paginator('list_objects_v2')
        async for result in paginator.paginate(Bucket=settings.s3_bucket, Prefix=str(path)):
            for c in result.get('Contents', []):
                p = re.sub(r'/(?:main|thumb)\.jpg$', '', c['Key'])
                url = f'{settings.s3_domain}/{p}'
                files.add(url)
    return files


async def delete_image(image: str, settings: Settings):
    path = Path(re.sub('^https?://.*?/', '', image))
    async with create_s3_session(settings) as s3:
        await asyncio.gather(
            s3.delete_object(Bucket=settings.s3_bucket, Key=str(path / 'main.jpg')),
            s3.delete_object(Bucket=settings.s3_bucket, Key=str(path / 'thumb.jpg')),
        )


async def _upload(upload_path: Path, main_img: bytes, thumb_img: bytes, settings: Settings) -> str:
    r = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(10))
    upload_path = upload_path / r

    async with create_s3_session(settings) as s3:
        logger.info('uploading to %s', upload_path)
        await asyncio.gather(
            s3.put_object(
                Bucket=settings.s3_bucket,
                Key=str(upload_path / 'main.jpg'),
                Body=main_img,
                ContentType='image/jpeg',
                ACL='public-read',
            ),
            s3.put_object(
                Bucket=settings.s3_bucket,
                Key=str(upload_path / 'thumb.jpg'),
                Body=thumb_img,
                ContentType='image/jpeg',
                ACL='public-read'
            ),
        )
    return f'{settings.s3_domain}/{upload_path}'


async def resize_upload(image_data: bytes, upload_path: Path, settings: Settings) -> str:
    img = Image.open(BytesIO(image_data))

    for width, height in (LARGE_SIZE, SMALL_SIZE):
        if img.width >= width and img.height >= height:
            if img.size != (width, height):
                aspect_ratio = img.width / img.height
                if aspect_ratio > 3.84:
                    # wide image
                    resize_to = int(round(height * aspect_ratio)), height
                    extra = (resize_to[0] - width) / 2
                    crop_box = extra, 0, extra + width, height
                else:
                    # tall image
                    resize_to = width, int(round(width / aspect_ratio))
                    extra = (resize_to[1] - height) / 2
                    crop_box = 0, extra, width, extra + height
                img = img.resize(resize_to, Image.ANTIALIAS)
                img = img.crop(crop_box)
            break
    else:
        raise ValueError(f'image too small: {img.size}')
    main_stream, thumb_stream = BytesIO(), BytesIO()
    img.save(main_stream, 'JPEG', optimize=True, quality=95)

    thumb = img.resize((768, 200), Image.ANTIALIAS)  # same shape, height 200
    thumb = thumb.crop((184, 0, 584, 200))  # height staying at 200, width 400 (middle)
    thumb.save(thumb_stream, 'JPEG', optimize=True, quality=95)

    return await _upload(upload_path, main_stream.getvalue(), thumb_stream.getvalue(), settings)
