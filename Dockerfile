# Frappe v15 with the doom_manager app layered on top of the official image.
# Build context is this app's root (the directory containing setup.py).

# Stage 1: build the frappe-ui SPA (frontend/ -> doom_manager/public/frontend
# and doom_manager/www/doom.html). Done here so `docker compose build` needs
# no node on the host; a host build with `npm run build` produces the same files.
FROM node:22-alpine AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json frontend/
RUN cd frontend && npm ci --no-audit --no-fund
COPY . .
RUN cd frontend && npm run build

FROM frappe/erpnext:v15.121.1

USER frappe
WORKDIR /home/frappe/frappe-bench
COPY --chown=frappe:frappe --from=frontend /src /home/frappe/frappe-bench/apps/doom_manager
# At container start the entrypoint links sites/assets -> /home/frappe/frappe-bench/assets,
# so the app's asset symlink is baked into that directory here (no `bench build` needed:
# the app ships plain files only).
RUN env/bin/pip install --no-cache-dir -e apps/doom_manager \
 && ln -sfn /home/frappe/frappe-bench/apps/doom_manager/doom_manager/public assets/doom_manager
