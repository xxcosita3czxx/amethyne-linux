#!/usr/bin/env bash
set -euo pipefail

LIVE_USER="amethyne"
LIVE_PASSWORD="amethyne"

if ! id -u "${LIVE_USER}" >/dev/null 2>&1; then
    useradd \
        --create-home \
        --groups wheel,audio,video,render,input,storage,network \
        --shell /bin/bash \
        "${LIVE_USER}"
fi

echo "${LIVE_USER}:${LIVE_PASSWORD}" | chpasswd

install -d -m 0755 "/home/${LIVE_USER}"
cp -a /etc/skel/. "/home/${LIVE_USER}/"
chown -R "${LIVE_USER}:${LIVE_USER}" "/home/${LIVE_USER}"

install -d -m 0750 /etc/sudoers.d
cat > /etc/sudoers.d/99-amethyne-live-user <<'EOF'
%wheel ALL=(ALL:ALL) NOPASSWD: ALL
EOF
chmod 0440 /etc/sudoers.d/99-amethyne-live-user

systemctl set-default graphical.target
