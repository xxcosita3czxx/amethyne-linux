# Hyprbar Policy

## Native Wayland is different

For Wayland, it’s less safe to assume. A lot of native Wayland apps use client-side decorations.

So for native Wayland:

```text
if xdg-decoration says server-side:
    bar
if xdg-decoration says client-side:
    no bar
if unknown:
    manual/default policy
```

## Amethyne default could be

```text
if manual force rule:
    obey it

else if XWayland:
    if explicitly undecorated:
        no bar
    else:
        bar

else if Wayland:
    if xdg-decoration says client-side:
        no bar
    if xdg-decoration says server-side:
        bar
    else:
        bar by fallback, or manual policy
