#!/usr/bin/env python3
"""Confluence storage API helper; credentials stay out of files and arguments."""

import argparse
import getpass
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

import requests


def save(path, value):
    path = Path(path)
    with path.open("w", encoding="utf-8") as stream:
        os.chmod(path, 0o600)
        json.dump(value, stream, ensure_ascii=False, indent=2)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalize_base(value):
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("Use an HTTPS base URL without credentials, query or fragment")
    return value.rstrip("/")


def page_id(value):
    value = str(value)
    if not value.isascii() or not value.isdigit():
        raise ValueError("Page ID must contain ASCII digits only")
    return value


def location(page):
    return (page["space"]["key"],
            [str(item["id"]) for item in page.get("ancestors", [])])


def check_current(before, current):
    if (str(before["id"]) != str(current["id"])
            or before["version"]["number"] != current["version"]["number"]
            or before["title"] != current["title"]
            or location(before) != location(current)):
        raise RuntimeError("Page changed; reread and merge before writing")


def check_saved_view(page):
    view = page.get("body", {}).get("view", {}).get("value", "")
    if render_issue(view):
        raise RuntimeError("Write succeeded; readback has rendering errors, inspect receipt")


def render_issue(value):
    lowered = value.lower()
    if "wysiwyg-unknown-macro" in lowered or "unknown macro" in lowered:
        return "unsupported_macro"
    if "diagram attachment access error" in lowered:
        return "resource_required"
    if "error rendering macro" in lowered:
        return "render_error"
    if not value.strip():
        return "empty_render"
    return None


class WikiClient:
    def __init__(self, base, session):
        self.base = normalize_base(base)
        self.session = session

    def call(self, method, path, **kwargs):
        try:
            response = self.session.request(
                method, self.base + path, timeout=45,
                allow_redirects=False, **kwargs)
        except requests.RequestException:
            raise RuntimeError(
                "Network request failed; if writing, inspect remote state before retry") from None
        if not 200 <= response.status_code < 300:
            raise RuntimeError(f"{method} {path}: HTTP {response.status_code}")
        try:
            result = response.json()
        except ValueError:
            raise RuntimeError("Response is not JSON; check authentication") from None
        if not isinstance(result, dict):
            raise RuntimeError("Expected a JSON object")
        return result

    def read(self, identifier):
        return self.call("GET", "/rest/api/content/" + page_id(identifier),
                         params={"expand": "body.storage,body.view,version,ancestors,space"})

    def render(self, identifier, storage):
        result = self.call("POST", "/rest/api/contentbody/convert/view", json={
            "representation": "storage", "value": storage,
            "content": {"id": page_id(identifier)}})
        if not isinstance(result.get("value"), str):
            raise RuntimeError("Render response has no HTML value")
        return result

    def preview(self, identifier, storage):
        result = self.render(identifier, storage)
        issue = render_issue(result["value"])
        if issue:
            raise RuntimeError("Preview failed: " + issue)
        return result

    def snapshot(self, page):
        return {"base_url": self.base, "page": page}

    def update(self, snapshot, storage, out):
        if snapshot["base_url"] != self.base:
            raise RuntimeError("Snapshot belongs to a different site")
        before = snapshot["page"]
        identifier = page_id(before["id"])
        check_current(before, self.read(identifier))
        self.preview(identifier, storage)
        check_current(before, self.read(identifier))
        result = self.call("PUT", "/rest/api/content/" + identifier, json={
            "id": identifier, "type": "page", "title": before["title"],
            "version": {"number": before["version"]["number"] + 1,
                        "message": "Improve layout; preserve source content"},
            "body": {"storage": {"representation": "storage", "value": storage}}})
        # Persist the successful write receipt before any verification can fail.
        save(out, {"base_url": self.base, "write_response": result})
        saved = self.read(identifier)
        save(out, self.snapshot(saved))
        if (location(saved) != location(before) or saved["title"] != before["title"]
                or saved["version"]["number"] != before["version"]["number"] + 1):
            raise RuntimeError("Write succeeded; readback differs, inspect saved receipt")
        check_saved_view(saved)
        return saved

    def create(self, parent_id, title, storage, out):
        parent = self.read(parent_id)
        self.preview(parent_id, storage)
        result = self.call("POST", "/rest/api/content", json={
            "type": "page", "title": title,
            "space": {"key": parent["space"]["key"]},
            "ancestors": [{"id": page_id(parent_id)}],
            "body": {"storage": {"representation": "storage", "value": storage}}})
        save(out, {"base_url": self.base, "write_response": result})
        saved = self.read(result["id"])
        save(out, self.snapshot(saved))
        space, ancestors = location(saved)
        if (space != parent["space"]["key"] or not ancestors
                or ancestors[-1] != page_id(parent_id) or saved["title"] != title):
            raise RuntimeError("Create succeeded; location/title differ, inspect receipt")
        check_saved_view(saved)
        return saved


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--base-url", required=True)
    result.add_argument("--auth", choices=["basic", "bearer"], default="basic")
    result.add_argument("--user", default=os.environ.get("CONFLUENCE_USERNAME"))
    sub = result.add_subparsers(dest="command", required=True)
    for command in ["get", "render", "probe", "update", "create"]:
        child = sub.add_parser(command)
        child.add_argument("--out", required=True)
        if command in {"get", "render", "probe"}:
            child.add_argument("--page-id", required=True, type=page_id)
        if command in {"render", "update", "create"}:
            child.add_argument("--storage", required=True)
        if command == "probe":
            child.add_argument("--cases", default=str(
                Path(__file__).resolve().parents[1] / "assets/macro-probes.json"))
        if command == "update":
            child.add_argument("--before", required=True)
        if command == "create":
            child.add_argument("--parent-id", required=True, type=page_id)
            child.add_argument("--title", required=True)
    return result


def run(args, client):
    out = Path(args.out)
    if out.exists():
        raise ValueError("Output already exists; choose a new file to preserve snapshots")
    # Catch invalid/unwritable output locations before issuing mutations.
    with out.open("x", encoding="utf-8") as stream:
        stream.write("{}\n")
    os.chmod(out, 0o600)
    storage = (Path(args.storage).read_text(encoding="utf-8")
               if hasattr(args, "storage") else None)
    if args.command == "get":
        save(out, client.snapshot(client.read(args.page_id)))
    elif args.command == "render":
        rendered = client.render(args.page_id, storage)
        save(out, rendered)
        if render_issue(rendered["value"]):
            raise RuntimeError("Render has errors; inspect output before publishing")
    elif args.command == "probe":
        results = []
        for case in load(args.cases):
            rendered = client.render(args.page_id, case["storage"])
            results.append({"name": case["name"],
                            "status": render_issue(rendered["value"]) or "inspect_rendered_output",
                            "response": rendered})
            save(out, {"base_url": client.base, "results": results})
    elif args.command == "update":
        client.update(load(args.before), storage, out)
    elif args.command == "create":
        client.create(args.parent_id, args.title, storage, out)
    print(json.dumps({"command": args.command, "output": str(out),
                      "next": "Inspect content and rendering; HTTP success is not visual verification"}))


def main():
    os.umask(0o077)
    args = parser().parse_args()
    normalize_base(args.base_url)
    with requests.Session() as session:
        if args.auth == "basic":
            if not args.user:
                raise ValueError("Set --user or CONFLUENCE_USERNAME")
            secret = os.environ.get("CONFLUENCE_PASSWORD") or getpass.getpass("Wiki password: ")
            session.auth = (args.user, secret)
        else:
            token = os.environ.get("CONFLUENCE_TOKEN") or getpass.getpass("Wiki token: ")
            session.headers["Authorization"] = "Bearer " + token
        run(args, WikiClient(args.base_url, session))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
