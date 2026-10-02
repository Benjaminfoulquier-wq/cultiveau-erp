# Cultiveau ERP construit depuis le code open source d'Odoo 18 (sous-module ./odoo, branche 18.0,
# licence LGPL-3) et les modules Cultiveau (./addons). Variante de l'image officielle `odoo:18`,
# qui contient exactement le même code : à utiliser quand on veut lire, corriger ou figer Odoo lui-même.
#   git submodule update --init --depth 1 odoo
#   docker compose -f docker-compose.yml -f docker-compose.source.yml up -d --build
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LANG=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential libpq-dev libldap2-dev libsasl2-dev libxml2-dev libxslt1-dev libjpeg-dev zlib1g-dev \
      fonts-dejavu-core fonts-liberation node-less npm git curl xz-utils \
    && curl -fsSL -o /tmp/wk.deb https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_amd64.deb \
    && apt-get install -y --no-install-recommends /tmp/wk.deb && rm /tmp/wk.deb \
    && npm install -g rtlcss && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/odoo
COPY odoo/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY odoo /opt/odoo
COPY addons /mnt/extra-addons
RUN useradd --uid 101 --create-home odoo && mkdir -p /var/lib/odoo && chown -R odoo /var/lib/odoo /opt/odoo
USER odoo
EXPOSE 8069 8072
ENTRYPOINT ["python", "/opt/odoo/odoo-bin", "-c", "/etc/odoo/odoo.conf"]
