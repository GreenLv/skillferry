"""workspace.toml parsing, orthogonal overlay merging, and asset loading.

A workspace is target-neutral by construction: nothing in it is owned by any
agent, and the merge order ``base < target < platform < host < local
override`` makes every value's origin visible to ``plan``. The schema rejects
secrets at parse time (MCP env values must be ``secret:env/NAME`` or
``secret:file/PATH`` references) and rejects ``[protect]`` mis-declarations.
"""

from __future__ import annotations

import re
import socket
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import tomlkit
from tomlkit.items import Item

from .models import SUPPORTED_PLATFORMS, SUPPORTED_TARGETS

SCHEMA_VERSION = 1
RULE_STRATEGIES = ("marker", "copy", "include")
TRANSPORTS = ("stdio", "http", "sse")
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SERVER_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
VERSION_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.+-]*$")
IGNORED_SKILL_NAMES = {".gitkeep", ".DS_Store", "Thumbs.db"}

TOP_LEVEL_KEYS = (
    "schema_version",
    "skills",
    "instructions",
    "mcp",
    "extensions",
    "overlays",
    "protect",
)
OVERLAY_KEYS = ("skills", "instructions", "mcp", "extensions", "protect")
EXTENSION_SOURCE_KINDS = ("github", "marketplace", "local", "manual")


class WorkspaceError(ValueError):
    pass


def _plain(value: Any) -> Any:
    if isinstance(value, Item):
        return _plain(value.unwrap())
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkspaceError(f"{label} must be a table")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise WorkspaceError(f"{label} must be a string")
    return value


def _string_list(
    value: Any, label: str, *, choices: tuple[str, ...] | None = None
) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise WorkspaceError(f"{label} must be an array of strings")
    if len(set(value)) != len(value):
        raise WorkspaceError(f"{label} contains duplicate entries")
    if choices is not None:
        unknown = sorted(set(value) - set(choices))
        if unknown:
            raise WorkspaceError(f"{label} has unsupported values: {unknown}")
    return tuple(value)


def _safe_relative(root: Path, raw: str, label: str) -> Path:
    if not isinstance(raw, str) or not raw:
        raise WorkspaceError(f"{label} must be a non-empty relative path")
    pure = PurePosixPath(raw)
    if pure.is_absolute() or ".." in pure.parts:
        raise WorkspaceError(f"{label} must stay inside the workspace: {raw!r}")
    path = root.joinpath(*pure.parts)
    current = root
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise WorkspaceError(f"{label} may not traverse a symlink: {raw}")
    return path


def _no_symlinks_below(root: Path, label: str) -> None:
    if not root.exists():
        return
    if root.is_symlink():
        raise WorkspaceError(f"{label} may not be a symlink: {root}")
    for entry in root.rglob("*"):
        if entry.is_symlink():
            raise WorkspaceError(f"{label} may not contain symlinks: {entry}")


@dataclass(frozen=True)
class SkillsSection:
    directory: Path
    default_targets: tuple[str, ...]


@dataclass(frozen=True)
class InstructionsSection:
    common: Path | None
    blocks: dict[str, Path]
    strategy: str


@dataclass(frozen=True)
class McpSection:
    registry: Path


@dataclass(frozen=True)
class ExtensionsSection:
    manifest: Path


@dataclass(frozen=True)
class OverlaysSection:
    platform_dir: Path
    target_dir: Path
    host_dir: Path | None


@dataclass(frozen=True)
class ProtectSection:
    paths: tuple[str, ...]


@dataclass
class Workspace:
    root: Path
    target: str
    platform: str
    hostname: str
    skills: SkillsSection
    instructions: InstructionsSection
    mcp: McpSection
    extensions: ExtensionsSection
    overlays: OverlaysSection
    protect: ProtectSection
    mcp_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    extension_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    provenance: dict[str, list[str]] = field(default_factory=dict)
    overlay_sources: tuple[str, ...] = ()


def _deep_merge(
    base: dict[str, Any],
    overlay: dict[str, Any],
    provenance: dict[str, list[str]],
    label: str,
    path: str = "",
) -> None:
    for key, value in overlay.items():
        dotted = f"{path}.{key}" if path else key
        provenance.setdefault(dotted, []).append(label)
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value, provenance, label, dotted)
        else:
            base[key] = value  # lists replace wholesale; documented in the contract


def _load_document(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        return {}
    if path.is_symlink():
        raise WorkspaceError(f"{label} may not be a symlink: {path}")
    try:
        return _plain(tomlkit.parse(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        raise WorkspaceError(f"cannot parse {label}: {exc}") from exc


def _parse_protect(value: Any, label: str) -> ProtectSection:
    table = _require_mapping(value, label) if value else {}
    paths = _string_list(table.get("paths", []), f"{label}.paths")
    for path in paths:
        pure = PurePosixPath(path)
        if pure.is_absolute() or ".." in pure.parts or "*" in path:
            raise WorkspaceError(
                f"{label}.paths entries must be relative, literal paths: {path!r}"
            )
    return ProtectSection(paths)


def _parse_sections(
    root: Path, data: dict[str, Any], provenance: dict[str, list[str]]
) -> dict[str, Any]:
    skills = _require_mapping(data.get("skills", {}), "skills")
    instructions = _require_mapping(data.get("instructions", {}), "instructions")
    mcp = _require_mapping(data.get("mcp", {}), "mcp")
    extensions = _require_mapping(data.get("extensions", {}), "extensions")
    overlays = _require_mapping(data.get("overlays", {}), "overlays")

    skills_directory = _safe_relative(
        root, str(skills.get("directory", "skills")), "skills.directory"
    )
    default_targets = _string_list(
        skills.get("default_targets", list(SUPPORTED_TARGETS)),
        "skills.default_targets",
        choices=SUPPORTED_TARGETS,
    )
    if not default_targets:
        raise WorkspaceError("skills.default_targets may not be empty")

    strategy = str(instructions.get("strategy", "marker"))
    if strategy not in RULE_STRATEGIES:
        raise WorkspaceError(f"instructions.strategy must be one of {RULE_STRATEGIES}")
    common = (
        _safe_relative(root, str(instructions["common"]), "instructions.common")
        if instructions.get("common")
        else None
    )
    blocks_table = _require_mapping(instructions.get("blocks", {}), "instructions.blocks")
    blocks: dict[str, Path] = {}
    for name, raw in blocks_table.items():
        if not isinstance(name, str) or not name or name != name.strip():
            raise WorkspaceError(f"instructions.blocks keys must be non-empty names: {name!r}")
        blocks[name] = _safe_relative(root, str(raw), f"instructions.blocks.{name}")
    if common is None and not blocks:
        raise WorkspaceError("instructions must declare 'common' or at least one block")

    registry = _safe_relative(root, str(mcp.get("registry", "mcp/servers.toml")), "mcp.registry")
    manifest = _safe_relative(
        root, str(extensions.get("manifest", "extensions/manifest.toml")),
        "extensions.manifest",
    )
    platform_dir = _safe_relative(
        root, str(overlays.get("platform_dir", "overlays/platform")),
        "overlays.platform_dir",
    )
    target_dir = _safe_relative(
        root, str(overlays.get("target_dir", "overlays/target")), "overlays.target_dir"
    )
    host_dir = (
        _safe_relative(root, str(overlays["host_dir"]), "overlays.host_dir")
        if overlays.get("host_dir")
        else None
    )
    return {
        "skills": SkillsSection(skills_directory, default_targets),
        "instructions": InstructionsSection(common, blocks, strategy),
        "mcp": McpSection(registry),
        "extensions": ExtensionsSection(manifest),
        "overlays": OverlaysSection(platform_dir, target_dir, host_dir),
        "protect": _parse_protect(data.get("protect", {}), "protect"),
    }


def _split_mcp_overlay(value: Any, label: str) -> dict[str, dict[str, Any]]:
    """Overlay ``[mcp]`` may only contain ``servers.<name>`` partial tables."""
    table = _require_mapping(value, label)
    servers = _require_mapping(table.get("servers", {}), f"{label}.servers")
    overrides: dict[str, dict[str, Any]] = {}
    for name, spec in servers.items():
        if not SERVER_NAME_RE.fullmatch(str(name)):
            raise WorkspaceError(f"{label}.servers has an invalid server name: {name!r}")
        overrides[str(name)] = _require_mapping(spec, f"{label}.servers.{name}")
    return overrides


def _split_extension_overlay(value: Any, label: str) -> dict[str, dict[str, Any]]:
    table = _require_mapping(value, label)
    overrides: dict[str, dict[str, Any]] = {}
    for name, spec in table.items():
        if not isinstance(name, str) or not name.strip():
            raise WorkspaceError(f"{label} has an invalid extension name: {name!r}")
        overrides[name] = _require_mapping(spec, f"{label}.{name}")
    return overrides


def load_workspace(
    root: Path,
    *,
    target: str,
    platform: str,
    hostname: str | None = None,
    allow_local: bool = True,
) -> Workspace:
    if target not in SUPPORTED_TARGETS:
        raise WorkspaceError(f"unsupported target: {target}")
    if platform not in SUPPORTED_PLATFORMS:
        raise WorkspaceError(f"unsupported platform: {platform}")
    root = root.expanduser().absolute()
    if root.is_symlink():
        raise WorkspaceError(f"workspace root may not be a symlink: {root}")
    root = root.resolve()
    manifest = root / "workspace.toml"
    if not manifest.is_file():
        raise WorkspaceError(f"not a skillferry workspace (missing workspace.toml): {root}")

    provenance: dict[str, list[str]] = {}
    base = _load_document(manifest, "workspace.toml")
    if base.get("schema_version") != SCHEMA_VERSION:
        raise WorkspaceError("workspace.toml schema_version must be 1")
    unknown = sorted(set(base) - set(TOP_LEVEL_KEYS))
    if unknown:
        raise WorkspaceError(f"workspace.toml has unknown keys: {unknown}")
    for key in TOP_LEVEL_KEYS:
        provenance.setdefault(key, ["workspace.toml"])

    sections = _parse_sections(root, base, provenance)
    overlays = sections["overlays"]

    merged = {key: value for key, value in base.items() if key != "schema_version"}
    merged.pop("mcp", None)
    merged.pop("extensions", None)
    mcp_overrides: dict[str, dict[str, Any]] = {}
    extension_overrides: dict[str, dict[str, Any]] = {}
    overlay_sources: list[str] = []

    def apply_overlay(path: Path, label: str) -> None:
        if not path.exists():
            return
        document = _load_document(path, label)
        unknown_overlay = sorted(set(document) - set(OVERLAY_KEYS))
        if unknown_overlay:
            raise WorkspaceError(f"{label} has unsupported keys: {unknown_overlay}")
        mcp_part = document.pop("mcp", None)
        ext_part = document.pop("extensions", None)
        _deep_merge(merged, document, provenance, label)
        if mcp_part:
            for name, spec in _split_mcp_overlay(mcp_part, f"{label}.mcp").items():
                current = mcp_overrides.setdefault(name, {})
                _deep_merge(current, spec, provenance, label, f"mcp.servers.{name}")
        if ext_part:
            for name, spec in _split_extension_overlay(ext_part, f"{label}.extensions").items():
                current = extension_overrides.setdefault(name, {})
                _deep_merge(current, spec, provenance, label, f"extensions.{name}")
        overlay_sources.append(label)

    apply_overlay(overlays.target_dir / f"{target}.toml", f"overlays/target/{target}.toml")
    apply_overlay(
        overlays.platform_dir / f"{platform}.toml", f"overlays/platform/{platform}.toml"
    )
    if overlays.host_dir is not None:
        host = hostname if hostname is not None else socket.gethostname()
        apply_overlay(overlays.host_dir / f"{host}.toml", f"overlays/host/{host}.toml")
    if allow_local:
        apply_overlay(root / "workspace.local.toml", "workspace.local.toml")

    sections = _parse_sections(root, merged, provenance)
    return Workspace(
        root=root,
        target=target,
        platform=platform,
        hostname=hostname if hostname is not None else socket.gethostname(),
        skills=sections["skills"],
        instructions=sections["instructions"],
        mcp=sections["mcp"],
        extensions=sections["extensions"],
        overlays=sections["overlays"],
        protect=sections["protect"],
        mcp_overrides=mcp_overrides,
        extension_overrides=extension_overrides,
        provenance=provenance,
        overlay_sources=tuple(overlay_sources),
    )


def _validate_protect_declarations(ws: Workspace) -> None:
    managed: list[tuple[str, Path]] = [
        ("skills.directory", ws.skills.directory),
        ("mcp.registry", ws.mcp.registry),
        ("extensions.manifest", ws.extensions.manifest),
        ("overlays.platform_dir", ws.overlays.platform_dir),
        ("overlays.target_dir", ws.overlays.target_dir),
    ]
    if ws.instructions.common is not None:
        managed.append(("instructions.common", ws.instructions.common))
    managed.extend(
        (f"instructions.blocks.{name}", path) for name, path in ws.instructions.blocks.items()
    )
    if ws.overlays.host_dir is not None:
        managed.append(("overlays.host_dir", ws.overlays.host_dir))
    for declared in ws.protect.paths:
        protected = (ws.root / declared).resolve()
        for label, path in managed:
            resolved = path.resolve()
            if resolved == protected or protected in resolved.parents:
                raise WorkspaceError(
                    f"[protect] mis-declaration: '{declared}' covers managed path "
                    f"{label} ({path.relative_to(ws.root)})"
                )


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Skill:
    name: str
    directory: Path
    description: str
    targets: tuple[str, ...] | None
    version: str | None
    files: dict[str, Path]  # relative posix path -> absolute source file


def _read_skill_frontmatter(skill_md: Path) -> dict[str, Any]:
    text = skill_md.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise WorkspaceError(f"{skill_md}: SKILL.md must start with YAML frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise WorkspaceError(f"{skill_md}: missing closing YAML delimiter") from exc
    fields: dict[str, Any] = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.+)$", line)
        if not match:
            raise WorkspaceError(f"{skill_md}: unsupported frontmatter line: {line!r}")
        fields[match.group(1)] = match.group(2).strip()
    return fields


def _parse_targets_field(raw: str | None, label: str) -> tuple[str, ...] | None:
    if raw is None:
        return None
    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1]
        items = [item.strip().strip("'\"") for item in inner.split(",") if item.strip()]
    else:
        items = [item.strip().strip("'\"") for item in value.split(",") if item.strip()]
    unknown = sorted(set(items) - set(SUPPORTED_TARGETS))
    if unknown:
        raise WorkspaceError(f"{label}: unsupported targets {unknown}")
    if not items:
        raise WorkspaceError(f"{label}: empty targets list")
    return tuple(items)


def load_skills(ws: Workspace) -> dict[str, Skill]:
    directory = ws.skills.directory
    if not directory.exists():
        return {}
    _no_symlinks_below(directory, "skills.directory")
    skills: dict[str, Skill] = {}
    for child in sorted(directory.iterdir()):
        if not child.is_dir():
            if child.name not in IGNORED_SKILL_NAMES:
                raise WorkspaceError(f"skills.directory may only contain skill dirs: {child}")
            continue
        if child.name in IGNORED_SKILL_NAMES:
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.is_file():
            raise WorkspaceError(f"{child}: missing SKILL.md")
        front = _read_skill_frontmatter(skill_md)
        name = str(front.get("name", "")).strip()
        if not SKILL_NAME_RE.fullmatch(name) or len(name) > 64:
            raise WorkspaceError(f"{skill_md}: invalid skill name {name!r}")
        if name != child.name:
            raise WorkspaceError(f"{skill_md}: name {name!r} does not match folder")
        description = str(front.get("description", "")).strip()
        if not description:
            raise WorkspaceError(f"{skill_md}: empty description")
        if set(front) - {"name", "description", "targets", "version"}:
            raise WorkspaceError(
                f"{skill_md}: unsupported frontmatter keys "
                f"{sorted(set(front) - {'name', 'description', 'targets', 'version'})}"
            )
        targets = _parse_targets_field(front.get("targets"), f"{skill_md}: targets")
        version = front.get("version")
        if version is not None and not VERSION_RE.fullmatch(str(version)):
            raise WorkspaceError(f"{skill_md}: invalid version {version!r}")
        files: dict[str, Path] = {}
        for path in sorted(child.rglob("*")):
            if path.is_file() and path.name not in IGNORED_SKILL_NAMES:
                files[path.relative_to(child).as_posix()] = path
        skills[name] = Skill(
            name=name,
            directory=child,
            description=description,
            targets=targets,
            version=str(version) if version is not None else None,
            files=files,
        )
    return skills


# ---------------------------------------------------------------------------
# MCP registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServerSpec:
    name: str
    command: str
    args: tuple[str, ...]
    env: dict[str, str]  # key -> secret reference
    transport: str
    targets: tuple[str, ...] | None


def _parse_server_spec(
    name: str, table: dict[str, Any], *, ws: Workspace, label: str
) -> dict[str, Any]:
    if not SERVER_NAME_RE.fullmatch(name):
        raise WorkspaceError(f"{label}: invalid server name {name!r}")
    command = _string(table.get("command"), f"{label}.command")
    if not command.strip():
        raise WorkspaceError(f"{label}.command may not be empty")
    args = _string_list(table.get("args", []), f"{label}.args")
    transport = str(table.get("transport", "stdio"))
    if transport not in TRANSPORTS:
        raise WorkspaceError(f"{label}.transport must be one of {TRANSPORTS}")
    env_table = _require_mapping(table.get("env", {}), f"{label}.env")
    env: dict[str, str] = {}
    for key, value in env_table.items():
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise WorkspaceError(f"{label}.env has an invalid variable name: {key!r}")
        if not isinstance(value, str):
            raise WorkspaceError(f"{label}.env.{key} must be a string secret reference")
        from .secrets import validate_secret_ref  # local import avoids a cycle

        validate_secret_ref(value, workspace_root=ws.root, label=f"{label}.env.{key}")
        env[key] = value.strip()
    targets = (
        _string_list(table["targets"], f"{label}.targets", choices=SUPPORTED_TARGETS)
        if table.get("targets") is not None
        else None
    )
    platform_table = _require_mapping(table.get("platform", {}), f"{label}.platform")
    unknown_platforms = sorted(set(platform_table) - set(SUPPORTED_PLATFORMS))
    if unknown_platforms:
        raise WorkspaceError(f"{label}.platform has unsupported platforms: {unknown_platforms}")
    unknown_keys = sorted(
        set(table) - {"command", "args", "transport", "env", "targets", "platform"}
    )
    if unknown_keys:
        raise WorkspaceError(f"{label} has unknown keys: {unknown_keys}")
    return {
        "name": name,
        "command": command,
        "args": args,
        "env": env,
        "transport": transport,
        "targets": targets,
        "platform": {
            platform_name: _parse_platform_override(
                platform_name, spec, ws=ws, label=f"{label}.platform.{platform_name}"
            )
            for platform_name, spec in platform_table.items()
        },
    }


def _parse_platform_override(
    platform: str, table: Any, *, ws: Workspace, label: str
) -> dict[str, Any]:
    mapping = _require_mapping(table, label)
    unknown = sorted(set(mapping) - {"command", "args", "transport", "env"})
    if unknown:
        raise WorkspaceError(f"{label} has unknown keys: {unknown}")
    result: dict[str, Any] = {}
    if "command" in mapping:
        result["command"] = _string(mapping["command"], f"{label}.command")
    if "args" in mapping:
        result["args"] = _string_list(mapping["args"], f"{label}.args")
    if "transport" in mapping:
        transport = _string(mapping["transport"], f"{label}.transport")
        if transport not in TRANSPORTS:
            raise WorkspaceError(f"{label}.transport must be one of {TRANSPORTS}")
        result["transport"] = transport
    if "env" in mapping:
        env_table = _require_mapping(mapping["env"], f"{label}.env")
        from .secrets import validate_secret_ref

        env: dict[str, str] = {}
        for key, value in env_table.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise WorkspaceError(f"{label}.env must map names to secret references")
            validate_secret_ref(value, workspace_root=ws.root, label=f"{label}.env.{key}")
            env[key] = value.strip()
        result["env"] = env
    return result


def load_mcp_registry(ws: Workspace) -> dict[str, ServerSpec]:
    registry = ws.mcp.registry
    if not registry.exists():
        if ws.mcp_overrides:
            raise WorkspaceError(
                f"mcp.registry file is missing but overlays declare servers: {registry}"
            )
        return {}
    if registry.is_symlink():
        raise WorkspaceError(f"mcp.registry may not be a symlink: {registry}")
    try:
        document = _plain(tomlkit.parse(registry.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        raise WorkspaceError(f"cannot parse {registry}: {exc}") from exc
    servers = _require_mapping(document.get("servers", {}), f"{registry}: servers")
    unknown_top = sorted(set(document) - {"servers"})
    if unknown_top:
        raise WorkspaceError(f"{registry} has unknown keys: {unknown_top}")

    result: dict[str, ServerSpec] = {}
    for name, table in servers.items():
        parsed = _parse_server_spec(
            str(name), _require_mapping(table, f"servers.{name}"), ws=ws,
            label=f"servers.{name}",
        )
        platform_override = parsed["platform"].get(ws.platform, {})
        spec: dict[str, Any] = {
            key: value for key, value in parsed.items() if key != "platform"
        }
        _deep_merge(
            spec, platform_override, {}, f"mcp/servers.toml servers.{name}.platform.{ws.platform}",
            f"servers.{name}",
        )
        override = ws.mcp_overrides.get(str(name))
        if override:
            _deep_merge(spec, override, {}, f"overlay mcp.servers.{name}", f"servers.{name}")
        spec["name"] = str(name)
        result[str(name)] = ServerSpec(
            name=str(name),
            command=str(spec["command"]),
            args=tuple(spec.get("args", ())),
            env=dict(spec.get("env", {})),
            transport=str(spec.get("transport", "stdio")),
            targets=tuple(spec["targets"]) if spec.get("targets") is not None else None,
        )
    return result


# ---------------------------------------------------------------------------
# Extensions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Extension:
    name: str
    version: str
    source_kind: str
    repo: str | None
    path: str | None
    ref: str | None
    instructions: str | None
    targets: tuple[str, ...] | None


def load_extensions(ws: Workspace) -> dict[str, Extension]:
    manifest = ws.extensions.manifest
    if not manifest.exists():
        if ws.extension_overrides:
            raise WorkspaceError(
                f"extensions.manifest is missing but overlays declare extensions: {manifest}"
            )
        return {}
    if manifest.is_symlink():
        raise WorkspaceError(f"extensions.manifest may not be a symlink: {manifest}")
    try:
        document = _plain(tomlkit.parse(manifest.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        raise WorkspaceError(f"cannot parse {manifest}: {exc}") from exc
    extensions = _require_mapping(document.get("extensions", {}), f"{manifest}: extensions")
    unknown_top = sorted(set(document) - {"extensions"})
    if unknown_top:
        raise WorkspaceError(f"{manifest} has unknown keys: {unknown_top}")

    result: dict[str, Extension] = {}
    for name, raw in extensions.items():
        spec = _require_mapping(raw, f"extensions.{name}")
        override = ws.extension_overrides.get(str(name), {})
        if override:
            spec = {**spec, **override}
        if not isinstance(name, str) or not name.strip():
            raise WorkspaceError(f"{manifest}: invalid extension name {name!r}")
        version = str(spec.get("version", ""))
        if not VERSION_RE.fullmatch(version):
            raise WorkspaceError(f"extensions.{name}.version is required and version-like")
        source = _require_mapping(spec.get("source", {}), f"extensions.{name}.source")
        kind = str(source.get("kind", ""))
        if kind not in EXTENSION_SOURCE_KINDS:
            raise WorkspaceError(
                f"extensions.{name}.source.kind must be one of {EXTENSION_SOURCE_KINDS}"
            )
        repo = ref = path = instructions = None
        if kind in ("github", "marketplace"):
            repo = _string(source.get("repo"), f"extensions.{name}.source.repo")
        if kind == "github":
            path = source.get("path")
            if path is not None:
                path = _string(path, f"extensions.{name}.source.path")
            ref = source.get("ref")
            if ref is not None:
                ref = _string(ref, f"extensions.{name}.source.ref")
        if kind == "local":
            path = _string(source.get("path"), f"extensions.{name}.source.path")
            local = _safe_relative(ws.root, path, f"extensions.{name}.source.path")
            if not local.is_dir():
                raise WorkspaceError(f"extensions.{name}.source.path is missing: {local}")
            path = str(local.relative_to(ws.root))
        if kind == "manual":
            instructions = _string(
                source.get("instructions"), f"extensions.{name}.source.instructions"
            )
        targets = (
            _string_list(spec["targets"], f"extensions.{name}.targets", choices=SUPPORTED_TARGETS)
            if spec.get("targets") is not None
            else None
        )
        unknown = sorted(set(spec) - {"version", "source", "targets"})
        if unknown:
            raise WorkspaceError(f"extensions.{name} has unknown keys: {unknown}")
        unknown_source = sorted(set(source) - {"kind", "repo", "path", "ref", "instructions"})
        if unknown_source:
            raise WorkspaceError(f"extensions.{name}.source has unknown keys: {unknown_source}")
        result[str(name)] = Extension(
            name=str(name),
            version=version,
            source_kind=kind,
            repo=repo,
            path=path,
            ref=ref,
            instructions=instructions,
            targets=targets,
        )
    return result


# ---------------------------------------------------------------------------
# Full validation entry point (used by scripts/validate_workspace.py and tests)
# ---------------------------------------------------------------------------


def validate_workspace(
    root: Path,
    *,
    targets: tuple[str, ...] = SUPPORTED_TARGETS,
    platform: str | None = None,
    hostname: str | None = None,
    allow_local: bool = True,
) -> list[str]:
    """Validate the workspace for every requested target; return info lines."""
    if platform is None:
        import sys

        platform = (
            "macos"
            if sys.platform == "darwin"
            else "windows"
            if sys.platform.startswith("win")
            else "linux"
        )
    lines: list[str] = []
    for target in targets:
        ws = load_workspace(
            root, target=target, platform=platform, hostname=hostname, allow_local=allow_local
        )
        _validate_protect_declarations(ws)
        skills = load_skills(ws)
        servers = load_mcp_registry(ws)
        extensions = load_extensions(ws)
        lines.append(
            f"[OK] workspace({target}/{platform}): {len(skills)} skill(s), "
            f"{len(servers)} MCP server(s), {len(extensions)} extension(s), "
            f"overlays={','.join(ws.overlay_sources) or 'none'}"
        )
    return lines
