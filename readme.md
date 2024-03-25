# Сервис пересылки email сообщений

## Описание использования методов кэширования в ендпоинтах сервиса

### send_email_view (кэш не используется)

Отправка email сообщения в очередь celery

endpoint:
```POST /send-email```

Пример payload схемы для POST запроса

```json
{
  "email_from": "email_from@mail.ru",
  "email_to": [
    "email_to1@mail.ru",
    "email_to2@mail.ru"
  ],
  "subject": "Subject of message",
  "text_content": "Full text of message"
}
```

reponse для статуса 200:

```json
{
  "status": "ok",
  "message": "Messages was successfully sent to queue"
}
```

### list_cache

Возвращает весь список элементов из кэша (статус 200). Если кэш пустой, то сообщение о том что кэш пуст или не удалось
подключитсья к redis (статус 400)

endpoint:
```GET /cache-list```

response для статуса 200

```json
[
  {
    "key": "5f47bd22-2730-4abb-b92b-ce666e68051b",
    "status": "ok",
    "cache": {
      "email_from": "super-mail1.com",
      "email_to": "super-duper-mail2@inbox.com",
      "subject": "Hello test",
      "text_content": "New message test"
    }
  },
  {
    "key": "1011bb1f-342f-4024-aa87-cdbcb1dd90df",
    "status": "ok",
    "cache": {
      "email_from": "super-mail1.com",
      "email_to": "1name@box.ru",
      "subject": "Hello test",
      "text_content": "New message test example"
    }
  }
]
```

response для статуса 400

```json
{
  "status": "error",
  "message": "Error getting all cache entries. Error connecting to redis server. error"
}
```

### invalidate_entry_cache

Удаляет сообщение с message_id из кэша. Если успешно, то статус 200, если кэш пуст, то статус 400

endpoint: ```DELETE /cache-invalidate/<string:message_id>```

**message_id** - id сообщения

reponse для статуса 200

```json
{
  "status": "ok",
  "message": "The cache is successfully invalidated"
}
```

reponse для статуса 400

```json
{
  "status": "error",
  "message": "Failed to delete cache entry, possibly not connected to redis server"
}
```

### invalidate_cache

Удаляет все элементы из кэша. Возвращает статус 200 если удалил, если кэш пуст, то статус 400.

endpoint:
```DELETE /cache-invalidate```

response для статуса 200

```json
{
  "status": "ok",
  "message": "The cache is successfully invalidated"
}
```

response для статуса 400

```json
{
  "status": "error",
  "message": "Failed to invalidate the cache, maybe there is no connection to the redis server"
}
```

### retry_message

Пытается повторно отправить сообщение из кэша по его message_id путем отправки сообщения в очередь celery.

endpoint: ```POST /retry-message/<string:message_id>```

response для статуса 200

```json
[
  {
    "key": "a7e7b284-18a4-4f3c-a53c-f599b55c78f4",
    "status": "send"
  }
]
```

response для статуса 404

```json
{
  "status": "error",
  "message": "Message with id 'message_id' not found in cache"
}
```

### list_undelivered

Возвращает список сообщений из кэш которые не были доставлены. Статус 200 если есть сообщения и статус 400 если кэш пуст

endpoint: ```GET /list-undelivered```

response для статуса 200

```json
[
  {
    "key": "d7ecfe3d-72b1-4d99-8703-ef8b828c9a2b",
    "status": "target service unavailable",
    "cache": {
      "email_from": "super-mail1.com",
      "email_to": "notexistingemail@mail.com",
      "subject": "Hello test",
      "text_content": "New message test"
    }
  }
]
```

response для статуса 400

```json
{
  "status": "error",
  "message": "Failed to get the list of messages in the cache, maybe there is no connection to the redis server or cache is empty."
}
```

### send_email_view_manual

Отправка сообщения по его message_id из кэша в синхронном режиме.

endpoint: ```GET /send-email-manual/<string:message_id>```

response для статуса 200

```json
{
  "status": "ok",
  "message": "successfully send email <<id: d7ecfe3d-72b1-4d99-8703-ef8b828c9a2b, email_from: super-mail1.com, email_to: notexistingemail@mail.com, subject: Hello test>>"
}
```
response для статуса 400

```json
{
    "status": "error",
    "message": "Message with id 'd7ecfe3d-72b1-4d99-8703-ef8b828c9a21' not found in cache"
}
```

response для статуса 500

```json
{
  "status": 500,
  "message": ""
}
```

## Тестирование

Для тестирования использовуюется файл docker-compose.yaml  
Для корректной работы mailhog необходимо поправить файл smtp_client.py Необходимо **smtplib.SMTP_SSL** заменить на **
smtplib.SMTP**

```python
import smtplib

...


def start_connection(self) -> None:
    self.smtp_obj = smtplib.SMTP(self.smtp_host, self.smtp_port)
    ...
```

и в файле **config.py** задать значения для **SMTP_RELAY_HOST** и **SMTP_RELAY_PORT** или использовать файл с
виртуальным окружением .env

```python
SMTP_RELAY_HOST = 'mailhog'
SMTP_RELAY_PORT = 1025
```

## Пример сборки для тестирования

```shell
docker-compose build
docker-compose up
```

## Пример запуска

```shell
docker build -t notification .
docker run --env-file .env -p 5025:5025 notification
```

| **Что бы посмотреть работу в тестовом режиме:** |  
|-------------------------------------------------|
| [Flower]                                        |  
| [MailHog]                                       |

[Flower]: <http://localhost:8888/>

[MailHog]: <http://localhost:8025/>
