#!/usr/bin/env python3
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DIST = ROOT / "dist"
INTEGRATION_MANIFEST = ROOT.parent / "custom_components" / "rhi_energy" / "manifest.json"
SOURCE_MANIFEST = SRC / "manifest.json"

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def digest(data: bytes) -> str:
    return sha256(data).hexdigest()

def inject_modules(template: str, manifest: dict) -> str:
    output = template
    for group in manifest["module_groups"]:
        placeholder = group["placeholder"]
        if output.count(placeholder) != 1:
            raise SystemExit(f"Expected exactly one placeholder {placeholder!r}")
        chunks = []
        for rel in group["modules"]:
            path = SRC / rel
            if not path.is_file():
                raise SystemExit(f"Missing canonical module: src/{rel}")
            content = path.read_text(encoding="utf-8").strip()
            if "BEGIN GENERATED MODULE:" in content or "END GENERATED MODULE:" in content:
                raise SystemExit(f"Canonical module still contains generated-copy markers: src/{rel}")
            chunks.append(f"// ---- src/{rel} ----\n{content}")
        output = output.replace(placeholder, "\n\n".join(chunks))
    return output

def copy_assets(asset_root: Path, target_root: Path) -> list[str]:
    categories = []
    for entry in sorted(asset_root.iterdir()):
        if not entry.is_dir():
            raise SystemExit(f"Asset root may contain category directories only: {entry.name}")
        categories.append(entry.name)
        shutil.copytree(entry, target_root / entry.name)
    return categories

def inventory(root: Path) -> list[dict]:
    rows = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if path.name == "PACKAGE_MANIFEST.json":
            continue
        rows.append({
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": digest(path.read_bytes()),
        })
    return rows

def main() -> None:
    integration = read_json(INTEGRATION_MANIFEST)
    manifest = read_json(SOURCE_MANIFEST)
    version = str(integration["version"])

    template_path = SRC / manifest["template"]
    template = template_path.read_text(encoding="utf-8")
    if template.count("__RHI_UX_VERSION__") != 1:
        raise SystemExit("Energy app template must contain exactly one UX version placeholder")

    bundle = inject_modules(template, manifest).replace("__RHI_UX_VERSION__", f"R{version}")
    if "__RHI_" in bundle:
        raise SystemExit("Unresolved build placeholder remains in Energy bundle")
    if "/local/homebrain/infrastructure/energy/" in bundle:
        raise SystemExit("Legacy /local Energy asset path remains in generated bundle")

    shutil.rmtree(DIST, ignore_errors=True)
    DIST.mkdir(parents=True, exist_ok=True)

    runtime_path = DIST / "rhi-energy-ux.js"
    runtime_path.write_text(bundle, encoding="utf-8", newline="\n")
    runtime_hash = digest(runtime_path.read_bytes())
    (DIST / "rhi-energy-ux.js.sha256").write_text(
        f"{runtime_hash}  rhi-energy-ux.js\n", encoding="utf-8"
    )

    asset_root = SRC / manifest["assets_root"]
    target_assets = DIST / "assets"
    target_assets.mkdir(parents=True, exist_ok=True)
    categories = copy_assets(asset_root, target_assets)

    package_manifest = {
        "schema_version": 1,
        "product": "rhi_energy",
        "version": version,
        "source_manifest_schema": manifest["schema_version"],
        "bundle_filename": "rhi-energy-ux.js",
        "assets_root": "assets",
        "asset_categories": categories,
        "runtime_sha256": runtime_hash,
        "files": inventory(DIST),
    }
    (DIST / "PACKAGE_MANIFEST.json").write_text(
        json.dumps(package_manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"Built Energy UX {version}: {len(manifest['module_groups'])} module groups, "
        f"{len(categories)} asset categories, SHA256 {runtime_hash}"
    )

if __name__ == "__main__":
    main()
