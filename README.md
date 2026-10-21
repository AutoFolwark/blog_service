# Blog Service

HTTP API for the Bidmax blog.

## Base path

Public endpoints are under:

```
/public/v1
```

## Health

```
GET /health
```

## Local development

```
poetry install
poetry run uvicorn main:app --host localhost --port 8002 --reload
```

Without Infisical credentials the service uses SQLite (`db.sqlite`) and skips remote secrets. Set `INFISICAL_CLIENT_ID`, `INFISICAL_AUTH_SECRET`, `INFISICAL_PROJECT_ID`, and `INFISICAL_ENV` to load secrets the same way as `api_service`.
