FROM python:3.11-slim-buster AS builder

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
WORKDIR /opt/venv
RUN python -m venv .
ENV PATH="/opt/venv/bin:$PATH"

COPY ./requirements.txt /app/requirements.txt
WORKDIR /app
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim-buster AS final

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY ./app /app/app
COPY ./alembic /app/alembic
COPY ./.env /app/.env
COPY ./alembic.ini /app/alembic.ini

EXPOSE 8080

COPY ./start.sh /app/start.sh
RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]