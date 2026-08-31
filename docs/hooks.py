from __future__ import annotations


def on_page_context(context, page, config, nav):
    repo_url = str(config.get("repo_url", "")).rstrip("/")

    if page.file.src_uri == "index.md":
        page.edit_url = f"{repo_url}/edit/main/README.md"
    elif page.file.src_uri == "spec.md":
        page.edit_url = f"{repo_url}/edit/main/SPEC.md"
