"""rwt_wikiapi - Lightweight client for MediaWiki article and media transfer.

A small, ergonomic Python library (and companion CLI) for editing wikitext pages
and uploading/downloading media files on a MediaWiki site using the Action API
plus the REST API where needed.

Only dependency: requests.
"""

from __future__ import annotations

__version__ = "2.0.0"

__all__ = [
    "Client",
    "Error",
    "LoginError",
    "ApiError",
    "NotLoggedInError",
    "UploadError",
    "EditError",
    "image_extensions",
    "uploadable_image",
    "normalize_filename",
    "raw_media_url",
]

import contextlib as _contextlib
import hashlib as _hashlib
import os as _os
import re as _re
from typing import Iterator as _Iterator

import requests as _requests


# --------------------------------------------------------------------------- #
# Public helpers (also available as Client.* classmethods and module-level)
# --------------------------------------------------------------------------- #

IMAGE_EXTENSIONS: tuple[str, ...] = (
    ".png",
    ".gif",
    ".jpg",
    ".jpeg",
    ".svg",
    ".webp",
)


def image_extensions() -> list[str]:
    """Return a list of file extensions treated as uploadable media (File: namespace)."""
    return Client.image_extensions()


def uploadable_image(path: str | _os.PathLike[str]) -> bool:
    """Return True if the path has an extension that should be uploaded as a File:."""
    return Client.uploadable_image(path)


def normalize_filename(name: str) -> str:
    """Normalize a media filename for MediaWiki URLs and the REST file API.

    - Strips a leading "File:" or "File talk:" prefix (case-insensitive).
    - Replaces spaces with underscores.
    """
    return Client.normalize_filename(name)


def raw_media_url(base_url: str, filename: str) -> str:
    """Compute the canonical direct URL to a raw media file.

    Uses MediaWiki's default /images/x/xx/ layout. No network call and
    login is not required.

    Example:
        raw_media_url("https://wiki.example.com/w", "My Photo.png")
        # -> "https://wiki.example.com/w/images/3/3f/My_Photo.png"
    """
    return Client.raw_media_url(base_url, filename)


# --------------------------------------------------------------------------- #
# Exceptions (mirroring the Ruby version's hierarchy for parity)
# --------------------------------------------------------------------------- #


class Error(Exception):
    """Base class for all rwt_wikiapi errors."""


class LoginError(Error):
    """Raised when login fails."""


class ApiError(Error):
    """Raised for MediaWiki API errors (contains code + info)."""

    def __init__(self, code: str, info: str, response: dict | None = None) -> None:
        self.code = code
        self.info = info
        self.response = response
        super().__init__(f"API error: {code} - {info}")


class NotLoggedInError(Error):
    """Raised when an operation requires a login and none is present."""


class UploadError(Error):
    """Raised for problems during file uploads."""


class EditError(Error):
    """Raised for problems during page edits."""


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #


class Client:
    """Ergonomic client for the narrow use-case of pushing/pulling articles
    and media files to/from a MediaWiki site.

    Usage (recommended):

        with Client.session(base_url, username, password) as client:
            client.edit("Project:Sandbox", "Hello from Python!")
            client.upload_file("diagram.svg", comment="new diagram")
            text = client.fetch_wikitext("Main Page")
            data = client.fetch_media("Logo.png")

    The constructor takes a *base URL* (the directory containing api.php),
    exactly like the Ruby reference:

        Client("https://mywiki.example.com/w")
    """

    IMAGE_EXTENSIONS = IMAGE_EXTENSIONS

    def __init__(self, base_url: str) -> None:
        if not base_url or not str(base_url).strip():
            raise ValueError("base_url is required")

        base = str(base_url).rstrip("/")
        self.api_url: str = f"{base}/api.php"
        self.rest_url: str = f"{base}/rest.php"

        self._csrf_token: str | None = None
        self._session = _requests.Session()

    # --- Classmethods (also available at module level) -----------------------

    @classmethod
    def uploadable_image(cls, path: str | _os.PathLike[str]) -> bool:
        ext = _os.path.splitext(str(path))[1].lower()
        return ext in IMAGE_EXTENSIONS

    @classmethod
    def image_extensions(cls) -> list[str]:
        return list(IMAGE_EXTENSIONS)

    @classmethod
    def normalize_filename(cls, name: str) -> str:
        if not name:
            return name
        name = _re.sub(r"^File:", "", name, flags=_re.IGNORECASE)
        name = _re.sub(r"^File talk:", "", name, flags=_re.IGNORECASE)
        return name.replace(" ", "_")

    @classmethod
    def raw_media_url(cls, base_url: str, filename: str) -> str:
        name = cls.normalize_filename(filename)
        digest = _hashlib.md5(name.encode("utf-8")).hexdigest()
        dir_part = f"{digest[0]}/{digest[:2]}/"
        base = base_url.rstrip("/")
        return f"{base}/images/{dir_part}{name}"

    # --- Session / login handling --------------------------------------------

    @classmethod
    @_contextlib.contextmanager
    def session(cls, base_url: str, username: str, password: str) -> _Iterator[Client]:
        """Context manager that logs in, yields the client, and guarantees logout.

        Equivalent to the Ruby WikiAPI::Client.session block form.
        """
        client = cls(base_url)
        client.login(username, password)
        try:
            yield client
        finally:
            client.logout()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, exc_type, exc_value, exc_tb) -> None:
        self.logout()

    def login(self, username: str, password: str) -> Client:
        """Perform the three-step MediaWiki login and obtain a CSRF token."""
        # Step 1: login token
        data = self._api_get(action="query", meta="tokens", type="login")
        login_token = self._dig_or_error(data, "query", "tokens", "logintoken")

        # Step 2: perform login
        login_data = self._api_post_form(
            action="login",
            lgname=username,
            lgpassword=password,
            lgtoken=login_token,
        )
        result = login_data.get("login", {})
        if result.get("result") != "Success":
            raise LoginError(f"login failed: {result}")

        # Step 3: CSRF token for subsequent writes
        csrf_data = self._api_get(action="query", meta="tokens")
        self._csrf_token = self._dig_or_error(csrf_data, "query", "tokens", "csrftoken")
        return self

    def logout(self) -> Client:
        """Log out if we have a token. Errors are swallowed (best-effort)."""
        if self._csrf_token is None:
            return self
        try:
            self._api_post_form(action="logout", token=self._csrf_token)
        except Exception:
            pass
        self._csrf_token = None
        return self

    def _ensure_logged_in(self) -> None:
        if self._csrf_token is None:
            raise NotLoggedInError("not logged in")

    # --- Editing -------------------------------------------------------------

    def edit(
        self,
        title: str,
        text: str,
        *,
        summary: str = "",
        mode: str = "replace",
    ) -> None:
        """Replace, prepend, or append wikitext on a page.

        mode: "replace" (default), "prepend", or "append".
        """
        self._ensure_logged_in()

        key = {
            "replace": "text",
            "prepend": "prependtext",
            "append": "appendtext",
        }.get(mode)
        if key is None:
            # also accept the raw MediaWiki keys for convenience
            if mode in ("text", "prependtext", "appendtext"):
                key = mode
            else:
                raise ValueError(f"invalid mode: {mode!r}")

        data = self._api_post_form(
            action="edit",
            title=title,
            token=self._csrf_token,
            summary=summary,
            **{key: text},
        )
        edit = data.get("edit", {})
        if edit.get("result") != "Success":
            raise EditError(f"edit failed: {data}")
        return None

    def prepend(self, title: str, text: str, *, summary: str = "") -> None:
        """Convenience wrapper for edit(..., mode='prepend')."""
        return self.edit(title, text, summary=summary, mode="prepend")

    def append(self, title: str, text: str, *, summary: str = "") -> None:
        """Convenience wrapper for edit(..., mode='append')."""
        return self.edit(title, text, summary=summary, mode="append")

    def edit_file(
        self,
        path: str | _os.PathLike[str],
        *,
        title: str | None = None,
        summary: str = "",
        mode: str = "replace",
    ) -> None:
        """Edit a page from the contents of a local text file.

        If title is omitted it is derived from the basename (extension stripped,
        underscores turned into spaces).
        """
        self._ensure_logged_in()
        if self.uploadable_image(path):
            raise UploadError(f"refusing to edit article using image file {path}")

        content = open(path, encoding="utf-8").read()
        derived = title or self._derive_article_title(path)
        self.edit(
            derived,
            content,
            summary=self._summary_with_filename(summary, path),
            mode=mode,
        )

    # --- Uploading media -----------------------------------------------------

    def upload_file(
        self,
        path: str | _os.PathLike[str],
        *,
        comment: str = "",
        title: str | None = None,
    ) -> None:
        """Upload a media file (png, jpg, svg, etc.)."""
        self._ensure_logged_in()
        if not self.uploadable_image(path):
            raise UploadError(
                f"refusing to upload non-image file {path} "
                f"(allowed: {', '.join(IMAGE_EXTENSIONS)})"
            )

        upload_title = title or self._derive_upload_title(path)
        basename = _os.path.basename(upload_title)

        with open(path, "rb") as f:
            files = {"file": (basename, f)}
            data = self._api_post_form(
                action="upload",
                filename=upload_title,
                comment=self._summary_with_filename(comment, path),
                token=self._csrf_token,
                ignorewarnings="1",
                files=files,  # type: ignore[arg-type]  # requests accepts this in data=
            )
            # The helper already parsed JSON; we just need the 'upload' key present
            if not isinstance(data.get("upload"), dict):
                raise UploadError(f"upload failed: {data}")

    # --- Fetching ------------------------------------------------------------

    def fetch_wikitext(self, title: str) -> str:
        """Return the wikitext of an article."""
        self._ensure_logged_in()
        data = self._api_get(action="parse", page=title, prop="wikitext")
        return self._dig_or_error(data, "parse", "wikitext", "*")

    def fetch_html(self, title: str) -> str:
        """Return the rendered HTML of an article."""
        self._ensure_logged_in()
        data = self._api_get(action="parse", page=title, prop="text")
        return self._dig_or_error(data, "parse", "text", "*")

    def fetch_media(self, title: str) -> bytes:
        """Return the raw bytes of a media file using the REST file endpoint.

        The title may contain spaces or a "File:" prefix; it will be normalized.
        """
        self._ensure_logged_in()
        safe = self.normalize_filename(title)

        info_url = f"{self.rest_url}/v1/file/File:{safe}"
        resp = self._session.get(info_url)
        data = self._handle_response(resp)
        original_url = self._dig_or_error(data, "original", "url")

        bin_resp = self._session.get(original_url)
        if bin_resp.status_code != 200:
            raise Error(f"HTTP error fetching media: {bin_resp.status_code} {bin_resp.reason}")
        return bin_resp.content

    # --- Instance convenience ------------------------------------------------

    def raw_media_url_for(self, filename: str) -> str:
        """Instance convenience: compute the raw media URL using this client's base URL.

        Equivalent to:
            Client.raw_media_url(client.api_url.rsplit("/api.php", 1)[0], filename)
        """
        base = self.api_url.removesuffix("/api.php").rstrip("/")
        return Client.raw_media_url(base, filename)


    # --- Internal helpers ----------------------------------------------------

    def _api_get(self, **params: str) -> dict:
        resp = self._session.get(self.api_url, params={**params, "format": "json"})
        return self._handle_response(resp)

    def _api_post_form(self, **params: object) -> dict:
        # requests accepts a 'files' key inside the data dict for multipart
        files = params.pop("files", None) if "files" in params else None
        data = {**params, "format": "json"}
        if files:
            resp = self._session.post(self.api_url, data=data, files=files)
        else:
            resp = self._session.post(self.api_url, data=data)
        return self._handle_response(resp)

    def _handle_response(self, resp: _requests.Response) -> dict:
        if resp.status_code != 200:
            raise Error(f"HTTP error: {resp.status_code} {resp.reason}")

        try:
            data: dict = resp.json()
        except Exception as e:  # JSONDecodeError etc.
            raise Error(f"invalid JSON from server: {e}") from e

        if err := data.get("error"):
            code = err.get("code") or "unknown"
            info = err.get("info") or str(err)
            raise ApiError(code, info, data)
        return data

    def _dig_or_error(self, d: dict, *keys: str) -> object:
        val = d
        for k in keys:
            if not isinstance(val, dict) or k not in val:
                raise Error(f"missing {'.'.join(keys)} in response: {d}")
            val = val[k]
        return val

    def _derive_article_title(self, path: str | _os.PathLike[str]) -> str:
        base = _os.path.basename(str(path))
        stem, _ = _os.path.splitext(base)
        return stem.replace("_", " ")

    def _derive_upload_title(self, path: str | _os.PathLike[str]) -> str:
        base = _os.path.basename(str(path))
        return base.replace("_", " ")

    def _summary_with_filename(self, summary: str, path: str | _os.PathLike[str]) -> str:
        return str(summary).replace("{}", _os.path.basename(str(path)))


# The four pure helpers are already defined as top-level functions above
# and are listed in __all__.  Client.* classmethods provide the same
# functionality for people who prefer the Ruby-like "WikiAPI.uploadable_image"
# style.
