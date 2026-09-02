"""Browse the object store from the dashboard.

The bucket is S3-compatible, so this is a thin, admin-only proxy over it. The
credentials stay in .env and are never sent to the browser: listing goes
through here, and a download is answered with a short-lived presigned URL so
the file itself travels straight from the store to the browser instead of
through gunicorn.

Object stores have no real folders. The convention everything here follows is
the usual one: a "folder" is a zero-byte object whose key ends in "/", and
listing with Delimiter='/' turns shared key prefixes back into folders.
"""
import os
from datetime import datetime

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from flask import jsonify, request, redirect

from main import app
from application.views import token_required, _is_admin

BUCKET = os.getenv('S3_BUCKET')
MAX_KEYS = 1000
# Long enough to click, short enough that a copied link is not a lasting key.
PRESIGN_SECONDS = 300
# Anything larger should not be going through a browser form.
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024


def _client():
    return boto3.client(
        's3',
        endpoint_url=os.getenv('S3_ENDPOINT'),
        aws_access_key_id=os.getenv('S3_ACCESS_KEY'),
        aws_secret_access_key=os.getenv('S3_SECRET_KEY'),
        region_name=os.getenv('S3_REGION', 'us-east-1'),
        config=Config(signature_version='s3v4',
                      s3={'addressing_style': 'path'},
                      retries={'max_attempts': 3}),
    )


def _configured():
    return bool(BUCKET and os.getenv('S3_ENDPOINT') and os.getenv('S3_ACCESS_KEY'))


def _admin_only(current_user):
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    if not _configured():
        return jsonify({'message': 'Object storage is not configured on this server.'}), 503
    return None


def _clean_prefix(raw):
    """A prefix that cannot climb out of the bucket or start with a slash."""
    p = (raw or '').strip().lstrip('/')
    if not p:
        return ''
    parts = [seg for seg in p.split('/') if seg not in ('', '.', '..')]
    out = '/'.join(parts)
    return (out + '/') if out else ''


def _clean_key(raw):
    k = (raw or '').strip().lstrip('/')
    if not k:
        return ''
    parts = [seg for seg in k.split('/') if seg not in ('', '.', '..')]
    # a trailing slash is meaningful: it is how a folder marker is addressed
    return '/'.join(parts) + ('/' if k.endswith('/') else '')


@app.route('/api/storage/list', methods=['GET'])
@token_required
def storage_list(current_user):
    """One level of the bucket: the folders and files directly under a prefix."""
    err = _admin_only(current_user)
    if err:
        return err

    prefix = _clean_prefix(request.args.get('prefix'))
    token = request.args.get('cursor') or None
    s3 = _client()
    kwargs = {'Bucket': BUCKET, 'Prefix': prefix, 'Delimiter': '/',
              'MaxKeys': MAX_KEYS}
    if token:
        kwargs['ContinuationToken'] = token
    try:
        r = s3.list_objects_v2(**kwargs)
    except ClientError as e:
        return jsonify({'message': 'Could not read the bucket: %s'
                        % e.response.get('Error', {}).get('Code', 'error')}), 502

    folders = []
    for p in r.get('CommonPrefixes', []):
        full = p['Prefix']
        folders.append({'prefix': full,
                        'name': full[len(prefix):].rstrip('/')})

    files = []
    for o in r.get('Contents', []):
        key = o['Key']
        if key == prefix or key.endswith('/'):
            continue                      # the folder marker itself
        mod = o.get('LastModified')
        files.append({
            'key': key,
            'name': key[len(prefix):],
            'size': o.get('Size', 0),
            'modified': mod.isoformat() if isinstance(mod, datetime) else None,
        })

    # Breadcrumbs, so the UI does not have to parse the prefix itself.
    crumbs, walked = [], ''
    for seg in [s for s in prefix.split('/') if s]:
        walked += seg + '/'
        crumbs.append({'name': seg, 'prefix': walked})

    return jsonify({
        'bucket': BUCKET,
        'prefix': prefix,
        'breadcrumbs': crumbs,
        'folders': sorted(folders, key=lambda x: x['name'].lower()),
        'files': sorted(files, key=lambda x: x['name'].lower()),
        'truncated': bool(r.get('IsTruncated')),
        'cursor': r.get('NextContinuationToken'),
    }), 200


@app.route('/api/storage/download', methods=['GET'])
@token_required
def storage_download(current_user):
    """Hand back a short-lived URL and let the browser fetch the file directly."""
    err = _admin_only(current_user)
    if err:
        return err
    key = _clean_key(request.args.get('key'))
    if not key or key.endswith('/'):
        return jsonify({'message': 'Please name a file to download.'}), 400

    s3 = _client()
    try:
        s3.head_object(Bucket=BUCKET, Key=key)
    except ClientError:
        return jsonify({'message': 'That file no longer exists.'}), 404

    filename = key.rsplit('/', 1)[-1]
    url = s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': BUCKET, 'Key': key,
                'ResponseContentDisposition': 'attachment; filename="%s"' % filename},
        ExpiresIn=PRESIGN_SECONDS)

    # ?redirect=1 for an <a href>; otherwise the URL, for fetch-based callers.
    if request.args.get('redirect') in ('1', 'true'):
        return redirect(url, code=302)
    return jsonify({'url': url, 'expires_in': PRESIGN_SECONDS,
                    'filename': filename}), 200


@app.route('/api/storage/preview', methods=['GET'])
@token_required
def storage_preview(current_user):
    """Same as download, but inline -- so audio can play in the page."""
    err = _admin_only(current_user)
    if err:
        return err
    key = _clean_key(request.args.get('key'))
    if not key or key.endswith('/'):
        return jsonify({'message': 'Please name a file.'}), 400
    s3 = _client()
    try:
        url = s3.generate_presigned_url('get_object',
                                        Params={'Bucket': BUCKET, 'Key': key},
                                        ExpiresIn=PRESIGN_SECONDS)
    except ClientError:
        return jsonify({'message': 'Could not build a link for that file.'}), 502
    return jsonify({'url': url, 'expires_in': PRESIGN_SECONDS}), 200


@app.route('/api/storage/folder', methods=['POST'])
@token_required
def storage_create_folder(current_user):
    err = _admin_only(current_user)
    if err:
        return err
    data = request.get_json() or {}
    prefix = _clean_prefix(data.get('prefix'))
    name = (data.get('name') or '').strip().strip('/')
    if not name or '/' in name:
        return jsonify({'message': 'Give the folder a name without slashes.'}), 400

    key = '%s%s/' % (prefix, name)
    s3 = _client()
    try:
        # An empty object whose key ends in "/" is what makes a folder appear.
        s3.put_object(Bucket=BUCKET, Key=key, Body=b'')
    except ClientError as e:
        return jsonify({'message': 'Could not create the folder: %s'
                        % e.response.get('Error', {}).get('Code', 'error')}), 502
    return jsonify({'message': 'Folder created.', 'prefix': key}), 201


@app.route('/api/storage/upload', methods=['POST'])
@token_required
def storage_upload(current_user):
    err = _admin_only(current_user)
    if err:
        return err
    prefix = _clean_prefix(request.form.get('prefix'))
    files = request.files.getlist('files') or []
    if not files:
        return jsonify({'message': 'No file was attached.'}), 400

    s3 = _client()
    saved, failed = [], []
    for f in files:
        name = os.path.basename(f.filename or '').strip()
        if not name:
            continue
        key = prefix + name
        try:
            f.stream.seek(0, os.SEEK_END)
            size = f.stream.tell()
            f.stream.seek(0)
            if size > MAX_UPLOAD_BYTES:
                failed.append({'name': name, 'error': 'larger than the 2 GB limit'})
                continue
            extra = {}
            if f.mimetype:
                extra['ContentType'] = f.mimetype
            # upload_fileobj streams in parts, so a big file is not held in memory
            s3.upload_fileobj(f.stream, BUCKET, key, ExtraArgs=extra or None)
            saved.append({'name': name, 'key': key, 'size': size})
        except ClientError as e:
            failed.append({'name': name,
                           'error': e.response.get('Error', {}).get('Code', 'error')})
        except Exception as e:                      # noqa: BLE001
            failed.append({'name': name, 'error': str(e)[:120]})

    status = 200 if saved else 502
    return jsonify({'uploaded': saved, 'failed': failed,
                    'message': '%d uploaded%s' % (
                        len(saved),
                        ', %d failed' % len(failed) if failed else '')}), status


@app.route('/api/storage/object', methods=['DELETE'])
@token_required
def storage_delete(current_user):
    """Delete one file, or a folder and everything inside it."""
    err = _admin_only(current_user)
    if err:
        return err
    key = _clean_key(request.args.get('key'))
    if not key:
        return jsonify({'message': 'Nothing named to delete.'}), 400

    s3 = _client()
    try:
        if key.endswith('/'):
            # Walk the prefix; an object store has no recursive delete.
            removed, token = 0, None
            while True:
                kw = {'Bucket': BUCKET, 'Prefix': key, 'MaxKeys': MAX_KEYS}
                if token:
                    kw['ContinuationToken'] = token
                page = s3.list_objects_v2(**kw)
                batch = [{'Key': o['Key']} for o in page.get('Contents', [])]
                if batch:
                    s3.delete_objects(Bucket=BUCKET, Delete={'Objects': batch})
                    removed += len(batch)
                token = page.get('NextContinuationToken')
                if not token:
                    break
            return jsonify({'message': 'Deleted %d item(s).' % removed,
                            'deleted': removed}), 200
        s3.delete_object(Bucket=BUCKET, Key=key)
        return jsonify({'message': 'Deleted.', 'deleted': 1}), 200
    except ClientError as e:
        return jsonify({'message': 'Could not delete: %s'
                        % e.response.get('Error', {}).get('Code', 'error')}), 502


@app.route('/api/storage/usage', methods=['GET'])
@token_required
def storage_usage(current_user):
    """Object count and total size, for the header strip."""
    err = _admin_only(current_user)
    if err:
        return err
    s3 = _client()
    total = count = 0
    token = None
    try:
        while True:
            kw = {'Bucket': BUCKET, 'MaxKeys': MAX_KEYS}
            if token:
                kw['ContinuationToken'] = token
            page = s3.list_objects_v2(**kw)
            for o in page.get('Contents', []):
                if o['Key'].endswith('/'):
                    continue
                total += o.get('Size', 0)
                count += 1
            token = page.get('NextContinuationToken')
            if not token:
                break
    except ClientError as e:
        return jsonify({'message': 'Could not read the bucket: %s'
                        % e.response.get('Error', {}).get('Code', 'error')}), 502
    return jsonify({'bucket': BUCKET, 'objects': count, 'bytes': total}), 200
