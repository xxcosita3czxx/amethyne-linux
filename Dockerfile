FROM archlinux:latest

RUN pacman-key --init \
    && pacman-key --populate archlinux \
    && pacman-key --recv-key 3056513887B78AEB --keyserver keyserver.ubuntu.com \
    && pacman-key --lsign-key 3056513887B78AEB \
    && pacman -U --noconfirm \
        'https://cdn-mirror.chaotic.cx/chaotic-aur/chaotic-keyring.pkg.tar.zst' \
        'https://cdn-mirror.chaotic.cx/chaotic-aur/chaotic-mirrorlist.pkg.tar.zst' \
    && printf '\n[chaotic-aur]\nInclude = /etc/pacman.d/chaotic-mirrorlist\n' >> /etc/pacman.conf \
    && pacman -Syu --noconfirm \
        archiso \
        base-devel \
        git \
        grub \
        gtk4 \
        gtk4-layer-shell \
        gdk-pixbuf2 \
        python-gobject \
        python-pip \
        sudo \
        zstd \
    && python -m pip install --break-system-packages --no-cache-dir pyinstaller \
    && rm -rf /var/cache/pacman/pkg/*

WORKDIR /work
