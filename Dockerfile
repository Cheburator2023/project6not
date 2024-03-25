FROM nexus-ci.corp.dev.vtb/sumd-docker-lib/ubi8-python39:v1.1

RUN groupadd -g 1000 user && useradd -m -d /home/user -s /bin/bash -c "User for Integration service" -u 1000 -g 1000 user

COPY requirements.txt /requirements.txt
ARG PIP_INDEX_URL
RUN pip3 install --no-cache -r /requirements.txt

COPY ./integration /app/integration
COPY ./start_service.sh /app/integration/start_service.sh
RUN chmod +x /app/integration/start_service.sh

RUN mkdir /app/tmp && mkdir /app/logs
RUN chown -R 1000:0 /app && chmod -R g=u /app

USER user
WORKDIR /app/integration

EXPOSE 5025

CMD ["./start_service.sh"]
#CMD ["gunicorn", "--workers", "5", "--bind", "0.0.0.0:5025", "wsgi:app"]
