import json
import time
from typing import List

from flask import request
from jsonschema import ValidationError, SchemaError, validate

from app import app
from app.config import Configuration as Conf
from app.data_models import SEND_EMAIL_SCHEMA
from app.mail import check_and_recovery_service, async_send_email, celery, sync_send_email, async_send_emails
from app.redis_cache import Cache, TaskStatus


@app.route('/notification/send-email', methods=['POST'])
def send_email_view():
    """Set email to celery queue

    :return:
    """
    request_data = request.get_json()
    try:
        validate(request_data, SEND_EMAIL_SCHEMA)
    except (ValidationError, SchemaError) as e:
        app.logger.exception(f"Validation error: {e.message}")
        return app.response_class(
            response=json.dumps({"status": "error", "message": e.message}),
            status=400,
            mimetype="application/json"
        )

    email_from: str = request_data['email_from']
    emails_to: List[str] = request_data['email_to']
    subject: str = request_data['subject']
    text_content: str = request_data['text_content']

    check_and_recovery_service()
    emails_count = len(emails_to)
    if emails_count == 1:
        for email_to in emails_to:
            task = async_send_email.delay(email_from,
                                          emails_to,
                                          subject,
                                          text_content)
            app.logger.info(
                f'Created task to send email <<id: {task.id}, email_from: {email_from}, email_to: {email_to}, '
                f'subject: {subject}>>')
    elif emails_count > 1:
        async_send_emails.delay(email_from,
                                emails_to,
                                subject,
                                text_content)
        app.logger.info(
            f'Created tasks to send email <<email_from: {email_from}, email_to: {emails_to}, subject: {subject}>>')

    return app.response_class(
        response=json.dumps(
            {
                "status": "ok",
                "message": "Messages was successfully sent to queue"
            }
        ),
        status=200,
        mimetype="application/json"
    )


@app.route("/cache-list", methods=["GET"])
def list_cache():
    """Returns items from cache with status 200. If cache is empty, return status 400

    :return:
    """
    all_cache = Cache(Conf.CACHE_PREFIX).get_all()
    if not all_cache:
        msg = (
            "Failed to get the list of messages in the cache, maybe there is "
            "no connection to the redis server or cache is empty."
        )
        return app.response_class(
            response=json.dumps({"status": "error", "message": msg}),
            status=400,
            mimetype="application/json"
        )
    return app.response_class(
        response=json.dumps(all_cache),
        status=200,
        mimetype="application/json"
    )


@app.route("/cache-invalidate/<string:message_id>", methods=["DELETE"])
def invalidate_entry_cache(message_id):
    """Remove message with message_id from cache. Returns status 400 if cache is empty and status 200 if operation is ok

    :param message_id:
    :return:
    """
    if not Cache(Conf.CACHE_PREFIX).delete_by_id(message_id):
        msg = (
            "Failed to delete cache entry, possibly not connected to redis "
            "server"
        )
        return app.response_class(
            response=json.dumps({"status": "error", "message": msg}),
            status=400,
            mimetype="application/json"
        )
    return app.response_class(
        response=json.dumps(
            {
                "status": "ok",
                "message": "The cache is successfully invalidated"
            }
        ),
        status=200,
        mimetype="application/json"
    )


@app.route("/cache-invalidate", methods=["DELETE"])
def invalidate_cache():
    """Removes all items from cache

    :return:
    """
    if not Cache(Conf.CACHE_PREFIX).delete_all():
        msg = (
            "Failed to invalidate the cache, maybe there is no connection "
            "to the redis server"
        )
        return app.response_class(
            response=json.dumps({"status": "error", "message": msg}),
            status=400,
            mimetype="application/json"
        )
    return app.response_class(
        response=json.dumps({
            "status": "ok", "message": "The cache is successfully invalidated"
        }),
        status=200,
        mimetype="application/json"
    )


@app.route("/retry-message/<string:message_id>", methods=["POST"])
def retry_message(message_id):
    """Try to repeat send message from cache by message_id code with delay

    :param message_id:
    :return:
    """
    cache = Cache(Conf.CACHE_PREFIX, message_id)
    data = cache.get_by_id(message_id)
    if data is None:
        msg = f"Message with id '{message_id}' not found in cache"
        return app.response_class(
            response=json.dumps({"status": "error", "message": msg}),
            status=404,
            mimetype="application/json"
        )

    # revoke old task in celery
    celery.control.revoke(message_id)

    data = json.loads(data)
    email_to = data['email_to']
    email_from = data['email_from']
    subject = data['subject']
    text_content = data['text_content']

    check_and_recovery_service()
    status = async_send_email.delay(email_from,
                                    email_to,
                                    subject,
                                    text_content)

    result = [{"key": status.id, "status": "send"}]
    cache.save_cache(TaskStatus.Canceled)
    return app.response_class(
        response=json.dumps(result),
        status=200,
        mimetype="application/json"
    )


@app.route("/list-undelivered", methods=["GET"])
def list_undelivered():
    """List all undelivered messages from cache

    :return:
    """
    cache = Cache(Conf.CACHE_PREFIX)
    all_cache = cache.get_all_by_error()
    if not all_cache:
        msg = (
            "Failed to get the list of messages in the cache, maybe there is "
            "no connection to the redis server or cache is empty."
        )
        return app.response_class(
            response=json.dumps({"status": "error", "message": msg}),
            status=400,
            mimetype="application/json"
        )
    return app.response_class(
        response=json.dumps(all_cache),
        status=200,
        mimetype="application/json"
    )


@app.route("/send-email-manual/<string:message_id>", methods=["GET"])
def send_email_view_manual(message_id):
    """Resend email from cache by message_id manually without delay

    :param message_id:
    :return:
    """
    cache = Cache(Conf.CACHE_PREFIX, message_id)

    data = cache.get_by_id(message_id)
    if not data:
        msg = f"Message with id '{message_id}' not found in cache"
        return app.response_class(
            response=json.dumps({"status": "error", "message": msg}),
            status=404,
            mimetype="application/json"
        )
    data = json.loads(data)
    try:
        email_from: str = data['email_from']
        email_to: str = data['email_to']
        subject: str = data['subject']
        text_content: str = data['text_content']
    except KeyError as e:
        app.logger.exception(e)
        msg = f"KeyError exception, {e}"
        return app.response_class(
            response=json.dumps({"status": "error", "message": msg}),
            status=500,
            mimetype="application/json"
        )
    result = sync_send_email(message_id, email_from, email_to, subject, text_content)
    status = 200 if result['status'] == 'ok' else 500
    if status == 200:
        cache.save_cache(TaskStatus.ResentManually)
    return app.response_class(
        response=json.dumps(
            result
        ),
        status=status,
        mimetype="application/json"
    )
