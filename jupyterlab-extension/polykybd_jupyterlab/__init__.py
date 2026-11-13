# SPDX-License-Identifier: GPL-3.0-or-later
"""PolyKybd Context Reporter for JupyterLab: the server extension that forwards
the page's reports to PolyKybdHost, and the prebuilt labextension."""
import os

from .report import Sender, payload, settings

__version__ = "1.0.0"


def _jupyter_labextension_paths():
    return [{"src": "labextension", "dest": "polykybd-jupyterlab-context-reporter"}]


def _jupyter_server_extension_points():
    return [{"module": "polykybd_jupyterlab"}]


def _load_jupyter_server_extension(server_app):
    from jupyter_server.base.handlers import APIHandler
    from jupyter_server.utils import url_path_join
    from tornado import web

    try:
        config = dict(server_app.config.get("PolyKybdReporter", {}))
    except Exception:   # noqa: BLE001 -- a broken config falls back to defaults
        config = {}
    port, token = settings(config)
    sender = Sender()
    pid = os.getpid()

    class ReportHandler(APIHandler):
        @web.authenticated
        def post(self):
            body = payload(self.get_json_body(), pid=pid, token=token)
            if body is None:
                raise web.HTTPError(400, "not a report")
            sender.submit(port, body)
            self.set_status(204)
            self.finish()

    web_app = server_app.web_app
    route = url_path_join(web_app.settings["base_url"], "polykybd", "report")
    web_app.add_handlers(".*$", [(route, ReportHandler)])
    server_app.log.info("polykybd_jupyterlab: reports go to 127.0.0.1:%d%s",
                        port, " [token]" if token else "")


# Older jupyter_server / notebook servers look for this name.
load_jupyter_server_extension = _load_jupyter_server_extension
