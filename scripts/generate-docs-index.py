#!/usr/bin/env python3
import os
import pathlib
import pprint
import sys
import traceback

import msgpack
from jinja2 import Template
from tqdm import tqdm

DISABLE_TQDM = "CI" in os.environ

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
LOCAL_CACHE_PATH = pathlib.Path(
    os.environ.get("LOCAL_CACHE_PATH") or REPO_ROOT.joinpath(".cache")
).resolve()
if not LOCAL_CACHE_PATH.is_dir():
    LOCAL_CACHE_PATH.mkdir(0o755)
PACKAGE_INFO_CACHE = LOCAL_CACHE_PATH / "packages-info"
if not PACKAGE_INFO_CACHE.is_dir():
    PACKAGE_INFO_CACHE.mkdir(0o755)
RESULTS_DIR = REPO_ROOT / "results"


print(f"Local Cache Path: {LOCAL_CACHE_PATH}", file=sys.stderr, flush=True)
print(f"Results Path: {RESULTS_DIR}", file=sys.stderr, flush=True)

if sys.version_info < (3, 7):
    print("This script is meant to only run on Py3.7+", file=sys.stderr, flush=True)


def set_progress_description(progress, message):
    progress.set_description(f"{message: <60}")


def collect_extensions_info():
    extensions = {}
    for path in sorted(PACKAGE_INFO_CACHE.glob("*.msgpack")):
        if path.stem == "salt-extensions":
            continue
        extension_data = msgpack.unpackb(path.read_bytes())
        extension = extension_data["info"]["name"]
        desciption = extension_data["info"]["description"].rstrip()
        extensions[extension] = desciption
    return extensions


def collect_extensions_results():
    results = {}
    results["osnames"] = []
    results["python_versions"] = []
    for extension in sorted(RESULTS_DIR.iterdir()):
        if not extension.is_dir():
            continue
        results[extension.name] = {}
        for salt_version in sorted(extension.iterdir()):
            results[extension.name][salt_version.name] = {}
            for ospath in sorted(salt_version.iterdir()):
                osname = ospath.name.replace("-latest", "")
                if osname not in results["osnames"]:
                    results["osnames"].append(osname)
                results[extension.name][salt_version.name][osname] = {}
                for python_version in sorted(ospath.iterdir()):
                    python_version_name = python_version.name
                    if python_version_name not in results["python_versions"]:
                        results["python_versions"].append(python_version_name)
                    url = python_version.joinpath("url").read_text().strip()
                    status = python_version.joinpath("status").read_text().strip()
                    results[extension.name][salt_version.name][osname][
                        python_version_name
                    ] = {"url": url, "status": status}
    return results


def main():
    results = collect_extensions_results()
    extensions = collect_extensions_info()
    sphinx_results_dir = REPO_ROOT / "docs" / "results"
    if not sphinx_results_dir.is_dir():
        sphinx_results_dir.mkdir(0o0755)
    table_template = REPO_ROOT / "templates" / "results.html.j2"
    sphinx_index = REPO_ROOT / "docs" / "index.rst"

    progress = tqdm(
        total=len(results),
        unit="pkg",
        unit_scale=True,
        desc=f"{' ' * 60} :",
        disable=DISABLE_TQDM,
    )

    with progress:
        progress.write(
            "Collected Extension Test Results:\n{}".format(pprint.pformat(results))
        )
        progress.write("Collected Extensions:\n{}".format(pprint.pformat(extensions)))
        contents = ""
        for extension in results:
            if extension in ("osnames", "python_versions"):
                progress.update()
                continue
            set_progress_description(progress, f"Processing {extension}")
            if extension not in extensions:
                progress.write(
                    f"The extension {extension!r} cannot be found in the extensions listing"
                )
                progress.update()
                continue
            title = extension
            header = "-" * len(title)
            description = extensions[extension].rstrip()
            context = dict(
                results=results[extension],
                python_versions=results["python_versions"],
                osnames=results["osnames"],
            )
            table_contents = Template(table_template.read_text()).render(**context)
            html_table_path = sphinx_results_dir.joinpath(f"{extension}.html")
            html_table_path.write_text(table_contents)
            relative_html_table_path = html_table_path.relative_to(REPO_ROOT / "docs")
            contents += f"{title}\n{header}\n{description}\n\n"
            contents += f".. raw:: html\n   :file: {relative_html_table_path}\n\n\n"
            progress.update()
        set_progress_description(progress, "Writing extenstions index")
        contents += ".. |date| date::\n\nLast Updated on |date|"
        sphinx_index.write_text(contents + "\n")
    progress.write("Complete")


if __name__ == "__main__":
    exitcode = 0
    try:
        main()
    except Exception:
        exitcode = 1
        traceback.print_exc()
    finally:
        sys.exit(exitcode)
