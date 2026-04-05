# This file is part of https://github.com/KurtBoehm/periplus.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import datetime as dt
import os
from importlib.resources import files
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Final, Literal, override
from urllib.parse import quote, unquote

import click
import fast_html as fh
import magic
from flask import Flask, abort, redirect, request, send_file
from flask.cli import FlaskGroup
from pyvips import Image
from send2trash import send2trash
from werkzeug import Response
from werkzeug.datastructures import MultiDict
from werkzeug.utils import secure_filename

from .zip import ZipIO

UrlArgs = dict[str, bool | str | None]
Key = Callable[[Path], Any]

_static_mimetypes: Final[dict[str, str]] = {
    "css": "text/css",
    "svg": "image/svg+xml",
    "png": "image/png",
}


class Args:
    """Parsed query parameters for a request."""

    def __init__(self, args: MultiDict[str, str]) -> None:
        # Flag-style Boolean params.
        self._reverse: bool = "reverse" in args
        self.show_hidden: bool = "show-hidden" in args

        # Single-valued params.
        self._sort: str | None = args.get("sort")
        self.init: str | None = args.get("init")

        # Multi-valued selection param.
        self.selected: list[str] = args.getlist("s")

    @override
    def __str__(self) -> str:
        """Return a compact debug-style representation."""
        return (
            "Args("
            f"sort={self._sort},reverse={self._reverse},"
            f"show_hidden={self.show_hidden},init={self.init}"
            ")"
        )

    @property
    def reverse(self) -> bool:
        """Whether sort order is reversed."""
        return self._reverse

    @property
    def sort(self) -> str:
        """The active sort key (defaults to ``"name"``)."""
        return self._sort or "name"

    @property
    def inherit(self) -> UrlArgs:
        """
        Arguments to preserve across navigation.

        Currently keeps ``reverse``, ``show-hidden``, and ``sort``.
        """
        return {
            "reverse": self.reverse,
            "show-hidden": self.show_hidden,
            "sort": self._sort,
        }


def _args_str(args: UrlArgs) -> str:
    """
    Return a query-string representation of ``args``.

    ``True`` emits the bare key; ``False``/``None`` are omitted.
    """
    joined = "&".join(
        k if v is True else f"{k}={v}"
        for k, v in args.items()
        if v not in (None, False)
    )
    return f"?{joined}" if joined else ""


def _url(p: Path, args: UrlArgs) -> str:
    """Return an application URL for ``p`` with query arguments ``args``."""
    argstr = _args_str(args)
    if not p.parts:
        return f"/{argstr}"
    return "".join("/" + quote(part) for part in p.parts) + argstr


def _path_to_url(
    path: Path,
    args: UrlArgs | None = None,
    prefix: str = "/browse",
) -> str:
    """Return a URL for ``path`` under ``prefix`` with query arguments ``args``."""
    args = args or {}
    argstr = _args_str(args)
    if not path.parts:
        return f"{prefix}/{argstr.lstrip('?')}" if argstr else f"{prefix}/"
    encoded = "".join("/" + quote(part) for part in path.parts)
    return f"{prefix}{encoded}{argstr}"


def _browse_url(p: Path, args: UrlArgs) -> str:
    """Return a browse URL for ``p`` with query arguments ``args``."""
    return _path_to_url(p, args, prefix="/browse")


def _view_url(p: Path, args: UrlArgs) -> str:
    """
    Return a view URL for ``p`` with query arguments ``args``.

    Directories are routed to ``/browse`` instead.
    """
    return _browse_url(p, args) if p.is_dir() else _path_to_url(p, args, prefix="/view")


def _name_key(p: Path) -> str:
    """Return the sort key for ``p`` based on lowercase filename."""
    return p.name.lower()


def _date_key(p: Path) -> float:
    """Return the sort key for ``p`` based on modification time."""
    return p.stat().st_mtime


def _size_key(p: Path) -> int:
    """Return the sort key for ``p`` based on size in bytes."""
    return p.stat().st_size


_sort_keys: dict[str, Key] = {"name": _name_key, "date": _date_key, "size": _size_key}


def _iterdir_sorted(fp: Path, args: Args) -> list[Path]:
    """
    Return children of ``fp`` with hiding and sorting applied.

    Directories are listed before files.
    """
    entries = list(fp.iterdir())

    # Optionally filter out dotfiles.
    if not args.show_hidden:
        entries = [p for p in entries if not p.name.startswith(".")]

    # Pick primary sort key.
    key = _sort_keys.get(args.sort, _name_key)

    # Directories first; stable sort with multiple keys.
    entries.sort(key=_name_key, reverse=args.reverse)
    entries.sort(key=key, reverse=args.reverse)
    entries.sort(key=lambda p: not p.is_dir())
    return entries


def _resources_text(rel: str) -> str:
    """Return UTF-8 text content of a package resource at ``rel``."""
    return (files("periplus") / rel).read_text(encoding="utf-8")


def _send_resources_file(rel: str, mimetype: str | None = None) -> Response:
    """
    Return a Flask response for a package resource file.

    :param rel: Relative path within the package.
    :param mimetype: Optional MIME type override.
    """
    return send_file(BytesIO((files("periplus") / rel).read_bytes()), mimetype=mimetype)


def _wrap_html(
    *contents: Any,
    head_add: list[Any] | None = None,
    body_classes: list[str] | None = None,
    title: str | None = None,
) -> str:
    """
    Return a full HTML document wrapping the given body contents.

    Always includes a viewport ``<meta>``, favicon links, and user CSS.
    Additional ``<head>`` children and optional body classes can be provided.

    :param contents: Body children tags.
    :param head_add: Extra elements to include in ``<head>``.
    :param body_classes: CSS classes to add to the ``<body>`` element.
    :param title: Document title text (without HTML tags).
    """
    head_add = head_add or []
    body_classes = body_classes or []

    # Only include class attribute if non-empty.
    body_kwargs = {"class_": " ".join(body_classes)} if body_classes else {}

    head = [
        fh.meta(name="viewport", content="width=device-width, initial-scale=1"),
        fh.title(title or "Periplus"),
        fh.link(
            rel="icon",
            type="image/svg+xml",
            href="/static/favicon.svg",
        ),
        fh.link(
            rel="icon",
            type="image/png",
            sizes="16x16",
            href="/static/favicon-16.png",
        ),
        fh.link(
            rel="icon",
            type="image/png",
            sizes="32x32",
            href="/static/favicon-32.png",
        ),
        fh.link(
            rel="icon",
            type="image/png",
            sizes="64x64",
            href="/static/favicon-64.png",
        ),
        fh.link(rel="stylesheet", href="/static/user.css"),
        *head_add,
    ]
    html = fh.render(fh.html([fh.head(head), fh.body(contents, **body_kwargs)]))
    return "<!DOCTYPE html>" + html


def _icon_span(icon: str, size: str = "normal") -> fh.Tag:
    """
    Return a Bulma/Font Awesome icon span.

    :param icon: Icon name (Font Awesome, without the ``fa-`` prefix).
    :param size: Bulma icon size modifier (for example, ``"small"`` or ``"large"``).
    """
    return fh.span(fh.i(class_=f"fas fa-{icon}"), class_=f"icon is-{size}")


def _icon_link(
    icon: str,
    href: str,
    size: str = "normal",
    classes: list[str] | None = None,
) -> fh.Tag:
    """
    Return a Bulma-styled icon button link.

    :param icon: Icon name (Font Awesome, without the ``fa-`` prefix).
    :param href: Target URL.
    :param size: Icon size specifier, forwarded to :func:`_icon_span`.
    :param classes: Extra Bulma button classes (``"is-link"`` by default).
    """
    classes = classes or ["is-link"]
    span = _icon_span(icon, size)
    return fh.a(span, href=href, class_=" ".join(["button", *classes]))


def _preview_route(fp: Path) -> Response:
    """
    Return a square PNG thumbnail response for ``fp``.

    Responds with 404 if a preview cannot be generated.
    """
    dim = 128
    try:
        img = Image.new_from_file(fp)
        if img.bands in (1, 3):
            img = img.addalpha()
        img = img.resize(dim / max(img.width, img.height))
        img = img.embed((dim - img.width) // 2, (dim - img.height) // 2, dim, dim)
    except Exception:
        return abort(404)
    buf = img.pngsave_buffer()
    return send_file(BytesIO(buf), mimetype="image/png")


def _full_preview_route(fp: Path) -> Response:
    """
    Return a full-resolution preview response for ``fp``.

    PNG/JPEG are sent as-is; other types are converted to PNG when possible,
    otherwise a redirect to a generic icon is returned.
    """
    if fp.suffix.lower() in (".png", ".jpg", ".jpeg"):
        return send_file(fp.resolve())
    try:
        buf = Image.new_from_file(fp).pngsave_buffer()
        return send_file(BytesIO(buf), mimetype="image/png")
    except Exception:
        return redirect("/static/file.svg")


def _file_view_route(fp: Path, args: Args) -> str:
    """
    Return the file viewer page for ``fp``.

    Displays the file using an appropriate HTML element and includes next/previous
    navigation arrows and keyboard navigation.
    """
    # Collect sibling files in sorted order.
    siblings = [f for f in _iterdir_sorted(fp.parent, args) if f.is_file()]
    if not siblings:
        return abort(404)

    idx = siblings.index(fp)
    ante = siblings[idx - 1]
    post = siblings[(idx + 1) % len(siblings)]

    # Navigation bar (title and download).
    nav_start = fh.div(
        fh.span(fp.name, class_="navbar-title"),
        class_="navbar-item navbar-item-title",
    )
    dl = _icon_link("download", _url(fp, {**args.inherit, "download": True}))
    nav_end = fh.div(fh.div(dl, class_="buttons"), class_="navbar-item")
    nav_menu = [
        fh.div(nav_start, class_="navbar-start"),
        fh.div(nav_end, class_="navbar-end"),
    ]

    # Viewer object/embed.
    img_url = _path_to_url(fp, {}, prefix="/full-preview")
    img = fh.img(src=img_url, fallback="View", class_="viewer-img")
    obj = fh.object_(
        img,
        data=_browse_url(fp, {}),
        type=magic.from_file(fp, mime=True),
        class_="viewer-obj",
    )

    def arrow(target: Path, direction: Literal["left", "right"]) -> fh.Tag:
        """
        Return a navigation arrow link within the viewer.

        :param target: Adjacent file path.
        :param direction: Arrow direction (``"left"`` or ``"right"``).
        """
        return _icon_link(
            f"arrow-{direction}",
            _view_url(target, args.inherit),
            classes=["arrow", f"is-{direction}"],
        )

    section_children = [obj, arrow(ante, "left"), arrow(post, "right")]
    style = "height: calc(100dvh - var(--bulma-navbar-height));"
    file_view = [
        fh.nav(fh.div(nav_menu, class_="navbar-menu"), class_="navbar has-shadow"),
        fh.section(section_children, class_="hero is-relative", style=style),
    ]

    # Embed per-file viewer navigation JS.
    ante_url = _view_url(ante, args.inherit)
    post_url = _view_url(post, args.inherit)
    viewer_js = _resources_text("static/viewer.js")
    script = f'const ante="{ante_url}";const post="{post_url}";{viewer_js}'

    return _wrap_html(
        fh.div(file_view),
        head_add=[fh.script(script)],
        title=f"{fp} – Periplus",
    )


def _breadcrumb(fp: Path, args: Args) -> fh.Tag:
    """
    Return a breadcrumb-style path starting with a root icon, where each
    component is a link to its directory, preserving navigation arguments.
    """

    # Root icon: always present.
    root_icon = fh.span(fh.i(class_="fas fa-house"))

    # If there is no deeper path, just show the root icon.
    fp_parts = fp.parts
    if not fp_parts:
        return fh.span([root_icon], class_="title-text")

    # Add a link to root.
    parts: list[fh.Tag | str] = [
        fh.a(
            root_icon,
            href=_browse_url(Path("."), args.inherit),
            class_="breadcrumb-link",
        )
    ]

    # For each component of fp, add "/" then that component as a link
    curr = Path(".")
    for i, part in enumerate(fp_parts):
        curr /= part
        parts.append("/")
        if i + 1 < len(fp_parts):
            parts.append(
                fh.a(
                    part,
                    href=_browse_url(curr, args.inherit),
                    class_="breadcrumb-link",
                )
            )
        else:
            parts.append(part)

    return fh.span(parts, class_="title-text")


def _col_title(name: str, sort: str, p: Path, args: Args) -> fh.Tag:
    """
    Return a sortable table header link for column ``name`` and sort key ``sort``.
    """
    if args.sort == sort:
        icon_dir = "up" if args.reverse else "down"
        ico = fh.span(fh.i(class_=f"fas fa-arrow-{icon_dir}"), class_="icon")
        href = _browse_url(
            p,
            {**args.inherit, "sort": sort, "reverse": not args.reverse},
        )
        return fh.a([name, ico], href=href, class_="variant-link")
    return fh.a(
        name,
        href=_browse_url(p, {**args.inherit, "sort": sort}),
        class_="variant-link",
    )


def _byte_hr(s: int) -> str:
    """Return byte count ``s`` formatted as a human-readable string."""
    if s > 2**30:
        return f"{s / 2**30:.1f} GiB"
    if s > 2**20:
        return f"{s / 2**20:.1f} MiB"
    if s > 2**10:
        return f"{s / 2**10:.1f} KiB"
    return f"{s} B"


def _folder_row(p: Path, args: UrlArgs) -> fh.Tag:
    """
    Return a table row representation for filesystem entry ``p``.

    Includes selection checkbox and action buttons.
    """
    # Per-row selection checkbox.
    cb = fh.input_(type="checkbox", class_="file-cb", id=quote(str(p)))

    # Preview icon (folder/file), clicks go to preview endpoint.
    url = _path_to_url(p, args, prefix="/preview")
    feather = _resources_text(f"static/{'folder' if p.is_dir() else 'file'}.svg")
    icon = fh.object_(feather, data=url, width=32, height=32)

    stat = p.stat()
    mod = dt.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")

    # Download and delete action buttons.
    dl = _icon_link("download", _path_to_url(p, args, prefix="/download"))
    delete = _icon_link(
        "trash-can",
        _path_to_url(p, args, prefix="/delete"),
        classes=["is-link", "action-button"],
    )
    buttons = fh.div([dl, delete], class_="buttons", style="flex-wrap: nowrap")

    return fh.tr(
        [
            fh.td(fh.label(cb, class_="checkbox"), class_="wd-32px"),
            fh.td(icon, class_="wd-32px"),
            fh.td(fh.a(p.name, href=_view_url(p, args))),
            fh.td(_byte_hr(stat.st_size), class_="num-cell"),
            fh.td(mod, class_="num-cell"),
            fh.td(buttons, style="width: 0"),
        ]
    )


def _folder_route(fp: Path, args: Args) -> str:
    """
    Return the main folder listing page for ``fp``.

    Provides sorting, per-file actions, upload, and folder creation.
    """
    # Folder header controls (hidden toggle and bulk download).
    hide_icon = "eye" if args.show_hidden else "eye-slash"
    hide_url = _browse_url(fp, {**args.inherit, "show-hidden": not args.show_hidden})
    hide = _icon_link(hide_icon, hide_url, classes=["is-link", "variant-link"])

    dl_url = _path_to_url(fp, {}, prefix="/download")
    dl = _icon_link("download", dl_url, classes=["is-link", "is-dl"])
    header_buttons = fh.div([hide, dl], class_="buttons")

    breadcrumb = fh.span(_breadcrumb(fp, args), class_="title-text")
    header = [breadcrumb, header_buttons]

    # Table header: selection, icon, name, size, modified, actions.
    head_cb = fh.input_(type="checkbox", class_="head-cb")
    thead_cells = [
        fh.td(fh.label(head_cb, class_="checkbox"), class_="wd-32px"),
        fh.td(),
        fh.td(_col_title("Name", "name", fp, args)),
        fh.td(_col_title("Size", "size", fp, args)),
        fh.td(_col_title("Modified", "date", fp, args)),
        fh.td(),
    ]

    # Folder entries.
    tbody_children = [_folder_row(p, args.inherit) for p in _iterdir_sorted(fp, args)]

    # Upload row (multi-file upload).
    upload_file = fh.input_(
        type_="file", multiple=True, id_="upload-file", name="upload-file"
    )
    upload_icon = _icon_span("upload")
    upload_btn = fh.button(upload_icon, type_="submit", class_="button is-link")
    upload_form = fh.form(
        fh.tr([fh.td(), fh.td(), fh.td(upload_file, colspan=3), fh.td(upload_btn)]),
        method="POST",
        enctype="multipart/form-data",
        onsubmit="handleUploadSubmit(event)",
    )
    tbody_children.append(upload_form)

    # Create-folder row.
    cfold_input = fh.div(
        fh.input_(
            class_="input",
            type_="text",
            id_="folder-name",
            name="folder-name",
            placeholder="Folder Name",
        ),
        class_="control",
    )
    cfold_btn = fh.button(_icon_span("folder"), type_="submit", class_="button is-link")
    cfold_form = fh.form(
        fh.tr([fh.td(), fh.td(), fh.td(cfold_input, colspan=3), fh.td(cfold_btn)]),
        method="POST",
        enctype="multipart/form-data",
        onsubmit="handlecfoldSubmit(event)",
    )
    tbody_children.append(cfold_form)

    table = [fh.thead(fh.tr(thead_cells)), fh.tbody(tbody_children)]
    body = [fh.h1(header, class_="title"), fh.table(table, class_="table is-fullwidth")]

    return _wrap_html(
        fh.section(fh.div(body, class_="container"), class_="section"),
        head_add=[fh.script(_resources_text("static/folder.js"))],
        title=f"{fp} – Periplus",
    )


def _create_app() -> Flask:
    """
    Create and configure the Flask application.

    Registers all routes for the file explorer.
    """
    app = Flask(__name__)

    def url2path(path: str) -> Path:
        """Return the filesystem path corresponding to a URL subpath."""
        # Unquote each segment and drop empties.
        parts = [unquote(p) for p in path.split("/") if p]
        return Path(*parts) if parts else Path(".")

    @app.route("/static/<fname>")
    def static_file(fname: str) -> Response:
        """Return a static asset bundled in the periplus package."""
        mimetype = _static_mimetypes.get(fname.rsplit(".", 1)[-1])
        return _send_resources_file(f"static/{fname}", mimetype)

    @app.route("/browse/", defaults={"path": ""})
    @app.route("/browse/<path:path>")
    def browse(path: str) -> Response | str:
        """
        Return a directory listing for ``path`` or the file itself if not a directory.
        """
        args = Args(request.args)
        fp = url2path(path)

        if not fp.exists():
            return abort(404)

        if not fp.is_dir():
            return send_file(fp.resolve())

        return _folder_route(fp, args)

    @app.route("/preview/<path:path>")
    def preview(path: str) -> Response:
        """Return a thumbnail preview for the requested file at ``path``."""
        fp = url2path(path)
        if not fp.exists():
            return abort(404)
        return _preview_route(fp)

    @app.route("/full-preview/<path:path>")
    def full_preview(path: str) -> Response:
        """Return a full-resolution preview for the requested file at ``path``."""
        fp = url2path(path)
        if not fp.exists():
            return abort(404)
        return _full_preview_route(fp)

    @app.route("/view/<path:path>")
    def view(path: str) -> str | Response:
        """Return the file viewer page for the requested file at ``path``."""
        args = Args(request.args)
        fp = url2path(path)
        if not fp.exists():
            return abort(404)
        if fp.is_dir():
            return "Folders cannot be viewed"
        return _file_view_route(fp, args)

    @app.route("/download/<path:path>")
    def download(path: str) -> Response:
        """
        Return a download response for a single file or zipped directory/selection.
        """
        args = Args(request.args)
        fp = url2path(path)

        if not fp.exists():
            return abort(404)

        if not fp.is_dir():
            return send_file(fp.resolve(), as_attachment=True)

        # Folder download: whole folder or selection.
        if args.selected:
            selected_paths = [Path(p) for p in args.selected]
            io = ZipIO(fp, paths=selected_paths)
        else:
            io = ZipIO(fp)
        return send_file(io, mimetype="application/zip", download_name=fp.name)

    @app.route("/delete/<path:path>")
    def delete(path: str) -> Response:
        """
        Move the file or directory at ``path`` to trash and redirect to its parent.
        """
        fp = url2path(path)
        if not fp.exists():
            return abort(404)

        parent = fp.parent
        send2trash(fp)

        # Preserve sort/show-hidden from query args
        args = Args(request.args)
        return redirect(_browse_url(parent, args.inherit))

    @app.route("/")
    def root() -> Response:
        """Redirect the root URL to ``/browse/``."""
        return redirect("/browse/")

    def create_folder_route(path: str) -> Response:
        """
        Handle folder creation POST for the folder at ``path``.

        Always redirects back to the folder view.
        """
        names = request.form.getlist("folder-name")
        if not names:
            return redirect(request.url)

        [name] = names
        folder = url2path(path)
        (folder / name).mkdir(exist_ok=True)
        return redirect(request.url)

    def upload_route(path: str) -> Response:
        """
        Handle file upload POST into the folder at ``path``.

        Uploaded filenames are sanitized and deduplicated. If matching
        ``last-modified`` values are supplied, the file’s modification time is
        set accordingly. Always redirects back to the folder view.
        """
        fs = request.files.getlist("upload-file")
        ms = request.form.getlist("last-modified")

        # If counts mismatch, ignore timestamps.
        if len(fs) != len(ms):
            ms = [None] * len(fs)

        folder = url2path(path)

        for f, m in zip(fs, ms):
            if not f.filename:
                continue

            # Sanitize filename and avoid collisions.
            fname = secure_filename(f.filename)
            target = folder / fname
            i = 1
            while target.exists():
                target = folder / f"{fname}_{i}"
                i += 1

            f.save(target)

            if m is not None:
                # ``m`` is ms since epoch; keep access time, override mtime.
                os.utime(target, ns=(target.stat().st_atime_ns, int(m) * 1_000_000))
        return redirect(request.url)

    @app.route("/browse/", methods=["POST"], defaults={"path": ""})
    @app.route("/browse/<path:path>", methods=["POST"])
    def post_browse(path: str) -> Response:
        """Dispatch folder POSTs to either upload or create-folder handlers."""
        if "folder-name" in request.form:
            return create_folder_route(path)
        return upload_route(path)

    return app


@click.group(cls=FlaskGroup, create_app=_create_app)
def cli() -> None:
    """
    CLI entry point for the Periplus application.

    Exposes the Flask app created by :func:`_create_app` via
    :class:`flask.cli.FlaskGroup`.
    """
