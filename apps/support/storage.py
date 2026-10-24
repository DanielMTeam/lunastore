import io
import time
import warnings
from pathlib import PurePath
from urllib.parse import urlencode, urlsplit

import jwt
import requests
from PIL import Image
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import Attachment

MAX_SIZE = 5 * 1024 * 1024


def validate_upload(upload):
    if not upload.size or upload.size > MAX_SIZE:
        raise ValidationError(_('ERROR_SUPPORT_ATTACHMENT_SIZE'))
    ext = PurePath(upload.name.replace('\\', '/')).suffix.lower()
    data = upload.read(MAX_SIZE + 1)
    upload.seek(0)
    if len(data) > MAX_SIZE:
        raise ValidationError(_('ERROR_SUPPORT_ATTACHMENT_TOO_LARGE'))
    if ext in ('.png', '.jpg', '.jpeg'):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as image:
                    expected = 'PNG' if ext == '.png' else 'JPEG'
                    if image.format != expected or image.width * image.height > 25000000:
                        raise ValueError('invalid image')
                    image.verify()
        except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise ValidationError(_('ERROR_SUPPORT_INVALID_IMAGE'))
        upload.support_mimetype = 'image/png' if ext == '.png' else 'image/jpeg'
    elif ext in ('.txt', '.log'):
        # Logs may use a legacy encoding. Reject binary/control bytes and active documents.
        sample = data.lstrip().lower()
        if (any(byte < 32 and byte not in (9, 10, 13) for byte in data)
                or sample.startswith((b'mz', b'pk\x03\x04', b'%pdf', b'\x7felf'))
                or any(tag in sample for tag in (b'<html', b'<!doctype', b'<script', b'<svg'))):
            raise ValidationError(_('ERROR_SUPPORT_PLAIN_TEXT_ONLY'))
        upload.support_mimetype = 'text/plain'
    else:
        raise ValidationError(_('ERROR_SUPPORT_ATTACHMENT_FORMAT'))


def sign(payload, lifetime=60):
    now = int(time.time())
    return jwt.encode(dict(payload, iat=now, exp=now + lifetime), settings.LUNASPIRE_SECRET_KEY, algorithm='HS256')


def server_url():
    url = settings.LUNASPIRE_URL.rstrip('/')
    if url.startswith('//'):
        return 'https:' + url
    return url if '://' in url else 'http://' + url


def object_name(attachment):
    return f'support-upload:{attachment.object_key}'


def stage_uploads(user, uploads):
    staged = []
    for upload in uploads:
        validate_upload(upload)
        name = PurePath(upload.name.replace('\\', '/')).name[:255]
        row = Attachment.objects.create(uploader=user, original_name=name, size=upload.size,
                                        mimetype=upload.support_mimetype)
        token = sign({'type': 'cdn-upload', 'object': object_name(row), 'user': str(user.pk),
                      'guard': str(row.object_key), 'mode': 'private'}, lifetime=300)
        try:
            response = requests.post(server_url() + '/cdn/upload', data={'token': token},
                                     files={'file': (name, upload, row.mimetype)}, timeout=(5, 30))
            response.raise_for_status()
            confirmation = jwt.decode(response.json()['confirm_token'], settings.LUNASPIRE_SECRET_KEY,
                                      algorithms=['HS256'])
            if confirmation.get('type') != 'cdn-confirm' or confirmation.get('guard') != str(row.object_key):
                raise ValueError('invalid storage confirmation')
            file_id = int(confirmation['file_id'])
            if file_id <= 0:
                raise ValueError('invalid storage file id')
            # Fail closed against old LunaSpire versions that reused public records by hash.
            info_token = sign({'type': 'cdn-info', 'search_field': 'id', 'search_values': [str(file_id)],
                               'send': 'id;object_id;user_id;visibility;size;mimetype'})
            info_response = requests.get(server_url() + '/cdn/info', params={'token': info_token}, timeout=5)
            info_response.raise_for_status()
            info = info_response.json()['info'][0]
            if (info.get('visibility') != 'private' or info.get('object_id') != object_name(row)
                    or str(info.get('user_id')) != str(user.pk) or int(info.get('size', -1)) != upload.size
                    or not str(info.get('mimetype', '')).startswith(row.mimetype)):
                raise ValueError('Storage did not isolate the private upload')
            row.file_id = file_id
            row.save(update_fields=['file_id'])
            staged.append(row.pk)
        except (requests.RequestException, jwt.InvalidTokenError, KeyError, IndexError, ValueError, TypeError):
            # Keep the row, including an uncertain upload, for recovery by object key.
            raise ValidationError(_('ERROR_SUPPORT_UPLOAD_FAILED'))
    return staged


def download_url(file_id, request):
    base = getattr(request, 'geo_domains', {}).get('SPIRE_URL', settings.LUNASPIRE_URL)
    parsed = urlsplit(base if '://' in base or base.startswith('//') else '//' + base)
    return '//' + parsed.netloc + parsed.path.rstrip('/') + '/cdn/download?' + urlencode({
        'token': sign({'type': 'cdn-download', 'file_id': file_id}),
    })


def delete_staged(row):
    ids = [row.file_id] if row.file_id else []
    if not ids:
        token = sign({'type': 'cdn-info', 'search_field': 'object_id',
                      'search_values': [object_name(row)], 'send': 'id'})
        response = requests.get(server_url() + '/cdn/info', params={'token': token}, timeout=5)
        response.raise_for_status()
        ids = [item['id'] for item in response.json().get('info', [])]
    if ids:
        token = sign({'type': 'cdn-delete', 'file_ids': ids, 'reason': 'Unattached support upload expired'})
        response = requests.delete(server_url() + '/cdn/delete', params={'token': token}, timeout=5)
        response.raise_for_status()
        if response.json().get('failed'):
            raise ValueError('Storage did not delete every staged file')
    row.delete()
