# Local terminology image contract. Build/runtime validation is still required.
FROM python:3.13-slim
WORKDIR /app
ENV PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ICD10_CATALOGS=/app/data/catalogs.json \
    ICD10_TRANSPORT=stdio
COPY requirements/core.lock /app/requirements/core.lock
RUN python -m pip install --no-cache-dir --require-hashes -r /app/requirements/core.lock
COPY src/icd10_mcp /app/src/icd10_mcp
COPY deploy/catalogs.json /app/data/catalogs.json
COPY data/catalog.sqlite3 /app/data/catalog.sqlite3
COPY data/releases/2027/catalog.sqlite3 /app/data/releases/2027/catalog.sqlite3
RUN python -m icd10_mcp.cli smoke --database /app/data/catalog.sqlite3 > /dev/null \
    && python -m icd10_mcp.cli smoke --release icd10cm-2026-10-01 \
       --database /app/data/releases/2027/catalog.sqlite3 > /dev/null \
    && groupadd --gid 10001 icd10 \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin icd10 \
    && chmod -R a-w /app
USER 10001:10001
ENTRYPOINT ["python", "-m", "icd10_mcp.server"]
