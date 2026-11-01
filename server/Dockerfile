FROM debian:trixie-slim

ARG DEBIAN_FRONTEND=noninteractive
ARG REMOTE_UID=1000
ARG REMOTE_GID=1000

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        git \
        gh \
        nodejs \
        npm \
        passwd \
        python-is-python3 \
        python3 \
        python3-pip \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid "${REMOTE_GID}" remote-agent \
    && useradd \
        --uid "${REMOTE_UID}" \
        --gid remote-agent \
        --create-home \
        --shell /bin/bash \
        remote-agent

ENV VIRTUAL_ENV=/opt/remote-agent-venv \
    PATH="/opt/remote-agent-venv/bin:${PATH}" \
    HOME=/home/remote-agent \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN python3 -m venv "${VIRTUAL_ENV}"

WORKDIR /opt/remote_agent_server
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir .

RUN mkdir -p /workspace \
    && chown "${REMOTE_UID}:${REMOTE_GID}" /workspace

COPY docker-entrypoint.sh /usr/local/bin/remote-agent-entrypoint
RUN chmod 0755 /usr/local/bin/remote-agent-entrypoint

USER remote-agent
WORKDIR /workspace

EXPOSE 8421
ENTRYPOINT ["/usr/local/bin/remote-agent-entrypoint"]
CMD ["python", "-m", "src"]
