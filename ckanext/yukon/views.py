from __future__ import annotations

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
        extra_vars = {
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
