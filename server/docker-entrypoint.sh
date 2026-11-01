#!/bin/sh
set -eu

secret_file=/run/secrets/github_token
if [ -e "$secret_file" ] && [ ! -r "$secret_file" ]; then
    echo "remote-agent: GH token secret is not readable; check REMOTE_UID/REMOTE_GID and file permissions" >&2
fi

if [ -r "$secret_file" ]; then
    token="$(tr -d '\r\n' < "$secret_file")"
    if [ -n "$token" ]; then
        export GH_TOKEN="$token"
        export GITHUB_TOKEN="$token"

        # Keep GitHub HTTPS operations on the GitHub CLI credential helper.
        gh auth setup-git --hostname github.com --force >/dev/null 2>&1 \
            || git config --global credential.https://github.com.helper '!gh auth git-credential'
    fi
fi

unset token 2>/dev/null || true
exec "$@"
