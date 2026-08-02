FROM archlinux:latest

RUN pacman -Syu --noconfirm \
        archiso \
        base-devel \
        git \
        grub \
        gtk4 \
        gtk4-layer-shell \
        gdk-pixbuf2 \
        python-gobject \
        python-pip \
        zstd \
    && python -m pip install --break-system-packages --no-cache-dir pyinstaller \
    && rm -rf /var/cache/pacman/pkg/*

WORKDIR /work
