# Deployment credentials

Create `deploy/.htpasswd` with Apache `htpasswd` or a compatible password manager before starting Compose. Never commit it. The nginx UI and API use the same basic authentication gate.

Compose binds to `127.0.0.1:8080`. Place an HTTPS reverse proxy on the host in front of this address for remote use. Do not expose document-processing endpoints publicly without the access controls and data-retention measures described in the root README.
