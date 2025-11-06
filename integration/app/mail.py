import os
import random
from typing import List

from celery import Celery
from celery.exceptions import MaxRetriesExceededError

from app import app
from app.config import Configuration as Conf
from app.redis_cache import Cache, TaskStatus
from app.smtp_client import SMTPClient

smtp = SMTPClient.create_from_object(app)

celery = Celery(app.name, namespace='CELERY')
celery.config_from_object(Conf, force=True)


@celery.task(bind=True,
             retry_kwargs={'max_retries': Conf.max_retries})
def async_send_email(self, email_from: str, email_to: str, subject: str, text_content: str) -> str:
    countdown = Conf.time_to_retries + random.randint(0, Conf.time_to_retries_range)
    data = {
        'email_from': email_from,
        'email_to': email_to,
        'subject': subject,
        'text_content': text_content,
    }
    cache = Cache(Conf.CACHE_PREFIX, self.request.id, data)
    try:
        smtp.send_msg(email_from,
                      email_to,
                      subject,
                      text_content)
    except Exception as exc:
        app.logger.exception(
            f'error <<{exc}>> with email: <<id: {self.request.id}, email_from: {email_from}, '
            f'email_to: {email_to}, subject: {subject}>>, '
            f'worker will try to send the email again in {countdown} seconds')
        cache.save_cache(TaskStatus.ServiceUnavailable)
        try:
            raise self.retry(countdown=countdown)
        except MaxRetriesExceededError as exc:
            app.logger.exception(f'{exc} <<id: {self.request.id}, email_from: {email_from}, email_to: {email_to}, '
                                 f'subject: {subject}>>')
            cache.save_cache(TaskStatus.RetryCountExceeded)
            raise exc
    cache.save_cache(TaskStatus.Ok)
    return f'successfully send email <<id: {self.request.id}, email_from: {email_from}, ' \
           f'email_to: {email_to}, subject: {subject}>>'


@celery.task(bind=True, retry_kwargs={'max_retries': Conf.max_retries}, soft_time_limit=30, time_limit=40)
def async_send_emails(self, email_from: str, emails_to: List[str], subject: str, text_content: str):
    # create temporary_items list for store emails
    if hasattr(self, 'temporary_items') and len(self.temporary_items) > 0:
        emails_to = list(self.temporary_items)
    else:
        self.temporary_items = list(emails_to)

    countdown = Conf.time_to_retries + random.randint(0, Conf.time_to_retries_range)
    smtp.start_connection()
    try:
        for email_to in emails_to:
            data = {
                'email_from': email_from,
                'email_to': email_to,
                'subject': subject,
                'text_content': text_content,
            }
            cache = Cache(Conf.CACHE_PREFIX, self.request.id, data)
            try:
                smtp.send_msg2(email_from,
                               email_to,
                               subject,
                               text_content)
            except Exception as exc:
                app.logger.exception(
                    f'error <<{exc}>> with email: <<id: {self.request.id}, email_from: {email_from}, '
                    f'email_to: {email_to}, subject: {subject}>>, '
                    f'worker will try to send the email again in {countdown} seconds')
                cache.save_cache(TaskStatus.ServiceUnavailable)
                try:
                    raise self.retry(countdown=countdown)
                except MaxRetriesExceededError as exc:
                    app.logger.exception(
                        f'{exc} <<id: {self.request.id}, email_from: {email_from}, email_to: {email_to}, '
                        f'subject: {subject}>>')
                    cache.save_cache(TaskStatus.RetryCountExceeded)
                    raise exc
            cache.save_cache(TaskStatus.Ok)
            # delete from temporary_items list if delivery is successful
            del self.temporary_items[self.temporary_items.index(email_to)]

            app.logger.error(f'successfully send email <<id: {self.request.id}, email_from: {email_from}, '
                             f'email_to: {email_to}, subject: {subject}>>')
    finally:
        smtp.close_connection()


def sync_send_email(message_id: str, email_from: str, email_to: str, subject: str, text_content: str) -> dict:
    try:
        smtp.send_msg(email_from,
                      email_to,
                      subject,
                      text_content)
    except Exception as exc:
        return {'status': 'error',
                'message': f'error <<{exc}>> with email: <<id: {message_id}, email_from: {email_from}, '
                           f'email_to: {email_to}, subject: {subject}>>'}

    return {'status': 'ok',
            'message': f'successfully send email <<id: {message_id}, email_from: {email_from}, email_to: {email_to}, '
                       f'subject: {subject}>>'}


def check_and_recovery_service():
    res = os.popen('ps -C celery').read()
    if 'celery' not in res:
        app.logger.warning('celery is not working')
        app.logger.warning('starting celery')
        os.system("celery -A app.mail.celery worker -l DEBUG -c4 &")
        app.logger.warning('celery was started')


if __name__ == '__main__':
    app.run()

app.logger.info("Mail module initialized successfully")
app.logger.info("Test message: TSLG logging is working correctly")