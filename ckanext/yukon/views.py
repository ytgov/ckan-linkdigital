from __future__ import annotations

import base64
import json
from typing import Any

from flask import Blueprint
from flask.views import MethodView

import ckan.plugins.toolkit as tk
from ckan.views.user import login

__all__ = ["bp"]

bp = Blueprint("yukon", __name__)


# instead of catching exceptions inside every view, it's usually more
# convenient to register handlers for the exception class.
@bp.errorhandler(tk.ObjectNotFound)
def not_found_handler(error: tk.ObjectNotFound) -> tuple[str, int]:
    """Generic handler for ObjectNotFound exception."""
    return (
        tk.render(
            "error_document_template.html",
            {
                "code": 404,
                "content": f"Object not found: {error.message}",
                "name": "Not found",
            },
        ),
        404,
    )


# error handler renders standard error page. If you want to render
# view-specific page with a flash message instead, it's better it try/catch
# inside the view.
@bp.errorhandler(tk.NotAuthorized)
def not_authorized_handler(error: tk.NotAuthorized) -> tuple[str, int]:
    """Generic handler for NotAuthorized exception."""
    return (
        tk.render(
            "error_document_template.html",
            {
                "code": 403,
                "content": error.message or "Not authorized to view this page",
                "name": "Not authorized",
            },
        ),
        403,
    )


class SelectDatasetTypeView(MethodView):
    def post(self):
        type_ = tk.request.form["type"]
        return tk.redirect_to(f"{type_}.new")

    def get(self):
        extra_vars: dict[str, Any] = {
            "form_snippet": "package/snippets/yukon_select_dataset_type_form.html",
            "pkg_dict": {},
            "form_vars": {
                "package_types": [
                    {"value": "data", "text": tk._("Open data")},
                    {"value": "information", "text": tk._("Open information")},
                    {"value": "access-requests", "text": tk._("Completed access to information request")},
                    {"value": "pia-summaries", "text": tk._("Privacy impact assessment summary")},
                ],
            },
        }

        return tk.render("package/yukon_select_dataset_type.html", extra_vars)


@bp.route("/service/user/login", methods=["GET", "POST"])
def internal_login():
    return login()


bp.add_url_rule(
    "/dataset/new",
    view_func=SelectDatasetTypeView.as_view("select_dataset_type"),
)


@bp.route("/dataset/<id>/download-all")
def download_all(id: str):
    pkg = tk.get_action("package_show")({}, {"id": id})

    headers = {}
    if credentials := tk.config["yukon.http_auth"]:
        encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
        headers = {"Authorization": f"Basic {encoded}"}

    items = [
        {"id": res["id"], "url": res["url"], "headers": headers}
        for res in pkg["resources"]
        if res.get("url_type") == "upload" and not res.get("downloadall_metadata_modified")
    ]

    ticket = tk.get_action("fpx_order_ticket")(
        {},
        {
            "type": "zip",
            "items": base64.encodebytes(json.dumps(items).encode()).decode(),
        },
    )

    id_ = ticket["id"]

    return tk.redirect_to(tk.h.fpx_service_url() + f"ticket/{id_}/download")
