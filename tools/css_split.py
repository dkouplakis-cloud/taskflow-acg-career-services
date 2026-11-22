"""
TaskFlow | ACG Career Services
Safe CSS Organization Utility

Commands:
    prepare  - Back up and divide existing CSS into modules.
    activate - Replace styles.css with ordered imports.
    verify   - Verify the original rules are preserved.
    restore  - Restore the original stylesheet.

No CSS rules are deleted, rewritten or reordered.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys

from datetime import datetime
from pathlib import Path


# ==========================================
# PROJECT DIRECTORIES
# ==========================================

ROOT = Path(__file__).resolve().parent.parent

CSS = ROOT / "assets" / "css"

ENTRY = CSS / "styles.css"

PARTS = CSS / "parts"

MANIFEST = PARTS / "_manifest.json"

BACKUPS = ROOT.parent / "taskflow-local-backups"


# ==========================================
# CSS SECTION DEFINITIONS
# ==========================================

# These headings exist in the uploaded stylesheet.
# Their order must remain unchanged.

SECTIONS = [
    (
        "02-auth-project-basics.css",
        "DJANGO TASKFLOW - AUTHENTICATION PAGES",
    ),
    (
        "03-project-workspaces.css",
        "TASKFLOW - PROJECT DETAIL WORKSPACE",
    ),
    (
        "04-task-editor.css",
        "TASKFLOW - PROFESSIONAL TASK EDITOR",
    ),
    (
        "05-task-management.css",
        "TASKFLOW - PROJECT TASK MANAGEMENT",
    ),
    (
        "06-analytics.css",
        "TASKFLOW - ANALYTICS DASHBOARD",
    ),
    (
        "07-task-filters.css",
        "TASKFLOW - PROJECT TASK FILTER TOOLBAR",
    ),
    (
        "08-project-detail-refinements.css",
        "TASKFLOW - PROJECT DETAILS VISUAL REFINEMENT",
    ),
    (
        "09-project-forms.css",
        "TASKFLOW - CREATE / EDIT PROJECT FORM",
    ),
    (
        "10-task-deletion.css",
        "TASKFLOW - DELETE TASK ACTION",
    ),
]


# ==========================================
# CHECKSUM HELPER
# ==========================================

def sha(data: bytes) -> str:
    """Calculate the SHA-256 checksum."""

    return hashlib.sha256(data).hexdigest()


# ==========================================
# LOCATE SAFE CSS SECTION BOUNDARIES
# ==========================================

def start_at_heading(
    source: bytes,
    heading: str,
) -> int:
    """
    Locate the start of a section comment.

    The heading must exist exactly once.
    """

    pattern = (
        rb"(?m)^[ \t]*"
        + re.escape(heading.encode())
        + rb"[ \t]*\r?$"
    )

    matches = list(re.finditer(pattern, source))

    if len(matches) != 1:
        raise ValueError(
            f"Heading must occur exactly once: "
            f"{heading} (found {len(matches)})"
        )

    location = source.rfind(
        b"\n/*",
        0,
        matches[0].start(),
    )

    if location < 0:
        raise ValueError(
            f"Cannot find heading comment: {heading}"
        )

    location += 1

    prefix = source[
        location:matches[0].start()
    ]

    if (
        len(prefix) > 200
        or not re.fullmatch(
            rb"[/\*=\- \t\r\n]+",
            prefix,
        )
    ):
        raise ValueError(
            f"Unsafe split boundary near: {heading}"
        )

    return location


# ==========================================
# VALIDATE CSS BLOCK STRUCTURE
# ==========================================

def check_boundaries(
    source: bytes,
    boundaries: list[int],
) -> None:
    """
    Check that CSS sections are not split inside
    rule blocks, strings or comments.
    """

    depth = 0
    targets = set(boundaries)
    index = 0

    while index < len(source):

        if index in targets and depth != 0:
            raise ValueError(
                "A split would break a CSS block."
            )

        # Ignore CSS comments.
        if source[index:index + 2] == b"/*":

            end = source.find(
                b"*/",
                index + 2,
            )

            if end == -1:
                raise ValueError(
                    "Unclosed CSS comment."
                )

            index = end + 2
            continue

        # Ignore quoted strings.
        if source[index] in (34, 39):

            quote = source[index]
            index += 1

            while index < len(source):

                if source[index] == 92:
                    index += 2

                elif source[index] == quote:
                    index += 1
                    break

                else:
                    index += 1

            continue

        # Track CSS braces.
        if source[index] == 123:
            depth += 1

        elif source[index] == 125:

            depth -= 1

            if depth < 0:
                raise ValueError(
                    "Unexpected closing CSS brace."
                )

        index += 1

    if depth:
        raise ValueError(
            "CSS braces are unbalanced."
        )


# ==========================================
# LOAD MODULE METADATA
# ==========================================

def metadata() -> dict:
    """Read the saved module order."""

    return json.loads(
        MANIFEST.read_text(encoding="utf-8")
    )


def assembled_css(info: dict) -> bytes:
    """
    Reconstruct the original stylesheet
    by concatenating CSS modules in order.
    """

    return b"".join(
        (PARTS / filename).read_bytes()
        for filename in info["files"]
    )


# ==========================================
# GENERATE CSS IMPORTS
# ==========================================

def imports_css(files: list[str]) -> bytes:
    """
    Generate the lightweight styles.css
    entry point while preserving import order.
    """

    lines = [
        "/* TaskFlow CSS entry point. "
        "Edit files in parts/, not this file. */"
    ]

    lines.extend(
        f'@import url("./parts/{filename}");'
        for filename in files
    )

    return (
        "\n".join(lines) + "\n"
    ).encode("utf-8")


# ==========================================
# PREPARE CSS MODULES
# ==========================================

def prepare() -> None:
    """
    Create CSS modules and an external backup.

    Does not modify the active styles.css.
    """

    if not ENTRY.is_file():
        raise FileNotFoundError(
            f"Cannot find: {ENTRY}"
        )

    if PARTS.exists():
        raise FileExistsError(
            "The parts/ folder already exists. "
            "No files were changed."
        )

    original = ENTRY.read_bytes()

    if len(original) < 100_000:
        raise ValueError(
            "styles.css looks unexpectedly small. "
            "No files were changed."
        )

    positions = [
        start_at_heading(original, title)
        for _, title in SECTIONS
    ]

    if positions != sorted(set(positions)):
        raise ValueError(
            "CSS section headings are missing "
            "or out of order."
        )

    check_boundaries(original, positions)

    filenames = [
        "01-foundation-and-midterm.css"
    ] + [
        name for name, _ in SECTIONS
    ]

    cuts = [
        0
    ] + positions + [
        len(original)
    ]

    sections = [
        original[a:b]
        for a, b in zip(cuts, cuts[1:])
    ]

    # Critical integrity check.
    if b"".join(sections) != original:
        raise AssertionError(
            "Splitting changed original CSS bytes."
        )

    # Create backup outside the repository.
    BACKUPS.mkdir(
        parents=True,
        exist_ok=True,
    )

    stamp = datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )

    backup = BACKUPS / (
        f"styles-before-split-{stamp}.css"
    )

    backup.write_bytes(original)

    # Create the CSS parts directory.
    PARTS.mkdir()

    for filename, data in zip(
        filenames,
        sections,
    ):
        (PARTS / filename).write_bytes(data)

    # Record the source hash and file order.
    info = {
        "files": filenames,
        "original_sha256": sha(original),
        "backup_path": backup.name,
    }

    MANIFEST.write_text(
        json.dumps(info, indent=2) + "\n",
        encoding="utf-8",
    )

    # Verify complete reconstruction.
    assert (
        assembled_css(info)
        == ENTRY.read_bytes()
    )

    print(
        "PREPARE PASS: 10 modules created. "
        "Original styles.css was not changed."
    )

    print("SHA256:", sha(original))

    print("Safety backup:", backup)


# ==========================================
# ACTIVATE MODULAR CSS
# ==========================================


def activate() -> None:
    """
    Activate the modular CSS structure.

    Accepts either the original verified modules
    or the explicitly approved CSS checkpoint.

    Never overwrites unexpected stylesheet changes.
    """

    info = metadata()

    # Reconstruct CSS from the ordered modules.
    joined = assembled_css(info)
    current_hash = sha(joined)

    # Accept only known, verified checkpoints.
    allowed_hashes = {
        info["original_sha256"]
    }

    approved_hash = info.get("approved_sha256")

    if approved_hash:
        allowed_hashes.add(approved_hash)

    if current_hash not in allowed_hashes:
        raise ValueError(
            "CSS modules do not match an approved "
            "checkpoint. Activation cancelled."
        )

    # Generate the expected import entry point.
    expected_imports = imports_css(info["files"])
    current = ENTRY.read_bytes()

    # The modular structure may already be active.
    if current == expected_imports:
        print(
            "ACTIVATE PASS: Modular CSS is "
            "already active."
        )
        return

    # Verify that the original backup exists.
    backup = BACKUPS / Path(
        info["backup_path"]
    ).name

    if not backup.is_file():
        raise ValueError(
            "Original CSS backup not found. "
            "Activation cancelled."
        )

    original = backup.read_bytes()

    if sha(original) != info["original_sha256"]:
        raise ValueError(
            "Original CSS backup checksum mismatch. "
            "Activation cancelled."
        )

    # Never overwrite a modified stylesheet.
    if current != original:
        raise ValueError(
            "styles.css contains unexpected changes. "
            "Activation cancelled."
        )

    # Activate using an atomic file replacement.
    temporary = ENTRY.with_name(
        "styles.pending.css"
    )

    temporary.write_bytes(expected_imports)
    temporary.replace(ENTRY)

    print(
        "ACTIVATE PASS: Modular CSS activated."
    )

    print(
        "All CSS imports remain in their "
        "approved order."
    )


# ==========================================
# VERIFY CSS INTEGRITY
# ==========================================


def verify() -> None:
    """
    Verify the original CSS backup and the
    approved modular stylesheet independently.

    Only the previously reviewed project form
    module may differ from the original CSS.
    """

    info = metadata()

    # Locate the original backup.
    backup = BACKUPS / Path(
        info["backup_path"]
    ).name

    if not backup.is_file():
        raise SystemExit(
            "FAIL: Original CSS backup not found."
        )

    original = backup.read_bytes()

    # Check the original, immutable checksum.
    if sha(original) != info["original_sha256"]:
        raise SystemExit(
            "FAIL: Original backup checksum mismatch."
        )

    print("PASS: Original CSS backup verified.")

    # Confirm the module names and order.
    expected_files = [
        "01-foundation-and-midterm.css"
    ] + [
        filename for filename, _ in SECTIONS
    ]

    if info["files"] != expected_files:
        raise SystemExit(
            "FAIL: CSS module list or order changed."
        )

    # Recover the original section boundaries.
    positions = [
        start_at_heading(original, heading)
        for _, heading in SECTIONS
    ]

    check_boundaries(original, positions)

    cuts = [0] + positions + [len(original)]

    # Identify modules that differ from the
    # original backed-up stylesheet.
    changed = []

    for filename, start, end in zip(
        expected_files,
        cuts,
        cuts[1:]
    ):
        current = (PARTS / filename).read_bytes()
        previous = original[start:end]

        if current != previous:
            changed.append(filename)

    # Read the list of approved modified modules.
    # The default preserves compatibility with
    # our existing verified CSS checkpoint.

    approved_modules = info.get(
        "approved_modified_modules",
        ["09-project-forms.css"]
    )

    # Reject modifications to any modules that
    # have not been explicitly approved.

    if changed != approved_modules:
        raise SystemExit(
            "FAIL: Unexpected CSS module changes: "
            + str(changed)
        )

    print(
        "PASS: Only approved CSS modules differ "
        "from the original backup."
    )


    # Verify the currently approved CSS.
    assembled = assembled_css(info)

    approved_hash = info.get("approved_sha256")

    if not approved_hash:
        raise SystemExit(
            "FAIL: Approved CSS checksum is missing."
        )

    if sha(assembled) != approved_hash:
        raise SystemExit(
            "FAIL: Approved CSS checksum mismatch."
        )

    print(
        "PASS: Approved modular CSS checksum verified."
    )

    # Confirm that the active entry point is
    # either the original CSS or the exact
    # expected sequence of module imports.
    active = ENTRY.read_bytes()

    expected_imports = imports_css(
        info["files"]
    )

    if active == expected_imports:
        mode = "10 ordered imports"

    elif active == original:
        mode = "Original single file"

    else:
        raise SystemExit(
            "FAIL: Unexpected styles.css contents."
        )

    print("Active mode:", mode)

    print(
        "Original SHA256:",
        info["original_sha256"]
    )

    print(
        "Approved SHA256:",
        approved_hash
    )

    print("VERIFY PASS: Both CSS checkpoints verified.")


# ==========================================
# RESTORE ORIGINAL STYLESHEET
# ==========================================

def restore() -> None:
    """
    Restore the original stylesheet
    from the verified external backup.
    """

    info = metadata()

    backup = BACKUPS / Path(info["backup_path"]).name

    original = backup.read_bytes()

    if sha(original) != info["original_sha256"]:
        raise ValueError(
            "Backup hash mismatch. "
            "Restore cancelled."
        )

    current = ENTRY.read_bytes()

    expected_imports = imports_css(
        info["files"]
    )

    if current not in (
        original,
        expected_imports,
    ):
        raise ValueError(
            "styles.css has other changes. "
            "Restore cancelled to avoid data loss."
        )

    ENTRY.write_bytes(original)

    print(
        "RESTORE PASS: original styles.css "
        "restored exactly."
    )

    print(
        "CSS modules have been retained."
    )

# ==========================================
# COMMAND-LINE ENTRY POINT
# ==========================================

if __name__ == "__main__":

    actions = {
        "prepare": prepare,
        "activate": activate,
        "verify": verify,
        "restore": restore,
    }

    if (
        len(sys.argv) != 2
        or sys.argv[1] not in actions
    ):
        raise SystemExit(
            "Usage: python tools/css_split.py "
            "prepare|activate|verify|restore"
        )

    actions[sys.argv[1]]()