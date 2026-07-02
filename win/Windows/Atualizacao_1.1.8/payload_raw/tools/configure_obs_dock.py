#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configura automaticamente o Browser Dock do OBS para o FrameZero Clips.

OBS guarda os docks personalizados em user.ini, seção [BasicWindow], chave
ExtraBrowserDocks. Em algumas instalações antigas/portable também pode existir
em global.ini, então este script atualiza os dois com backup.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import sys
from pathlib import Path

DOCK_TITLE = "FrameZero Clips"
DOCK_URL = "https://clips.framezeroai.com.br/obs"
DOCK_ITEM = {"title": DOCK_TITLE, "url": DOCK_URL}


def obs_config_dir() -> Path:
    system = platform.system().lower()
    if system == "windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "obs-studio"
    if system == "darwin":
        return Path.home() / "Library" / "Application Support" / "obs-studio"
    # Linux fallback, não usado pelo instalador atual, mas útil para testes.
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "obs-studio"


def split_sections(lines: list[str]) -> dict[str, tuple[int, int]]:
    sections: dict[str, tuple[int, int]] = {}
    current = None
    start = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if current is not None and start is not None:
                sections[current] = (start, idx)
            current = stripped[1:-1]
            start = idx
    if current is not None and start is not None:
        sections[current] = (start, len(lines))
    return sections


def parse_docks(value: str) -> list[dict[str, str]]:
    value = value.strip()
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            docks = []
            for item in parsed:
                if isinstance(item, dict):
                    title = str(item.get("title", "")).strip()
                    url = str(item.get("url", "")).strip()
                    if title and url:
                        docks.append({"title": title, "url": url})
            return docks
    except Exception:
        pass
    return []


def add_or_update_dock(docks: list[dict[str, str]]) -> list[dict[str, str]]:
    cleaned = []
    for item in docks:
        title = str(item.get("title", "")).strip()
        url = str(item.get("url", "")).strip()
        # Remove versões antigas/duplicadas do FrameZero, inclusive docks antigos apontando
        # para painel local (obs-panel.html / 127.0.0.1 / localhost).
        lu = url.lower()
        lt = title.lower()
        if (lt == DOCK_TITLE.lower() or "framezero" in lt or
            "clips.framezeroai.com.br/obs" in lu or
            "obs-panel.html" in lu or
            "127.0.0.1" in lu or
            "localhost" in lu):
            continue
        cleaned.append({"title": title, "url": url})
    cleaned.append(DOCK_ITEM)
    return cleaned


def update_ini(path: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        # Backup só uma vez por arquivo.
        bak = path.with_suffix(path.suffix + ".framezero.bak")
        if not bak.exists():
            try:
                shutil.copy2(path, bak)
            except Exception:
                pass
    else:
        lines = []

    sections = split_sections(lines)
    if "BasicWindow" not in sections:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("[BasicWindow]")
        sections = split_sections(lines)

    start, end = sections["BasicWindow"]
    key_idx = None
    old_docks: list[dict[str, str]] = []

    for idx in range(start + 1, end):
        if lines[idx].lower().startswith("extrabrowserdocks="):
            key_idx = idx
            old_docks = parse_docks(lines[idx].split("=", 1)[1])
            break

    new_docks = add_or_update_dock(old_docks)
    new_line = "ExtraBrowserDocks=" + json.dumps(new_docks, ensure_ascii=False, separators=(",", ":"))

    if key_idx is not None:
        lines[key_idx] = new_line
    else:
        lines.insert(end, new_line)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def main() -> int:
    cfg = obs_config_dir()
    # user.ini é o arquivo atual onde o OBS guarda DockState/ExtraBrowserDocks.
    # global.ini só é alterado se já existir, para compatibilidade com instalações antigas.
    targets = [cfg / "user.ini"]
    legacy_global = cfg / "global.ini"
    if legacy_global.exists():
        targets.append(legacy_global)

    ok_any = False
    for target in targets:
        try:
            update_ini(target)
            print(f"OK: dock configurado em {target}")
            ok_any = True
        except Exception as exc:
            print(f"AVISO: não consegui configurar {target}: {exc}", file=sys.stderr)
    if ok_any:
        print(f"Dock OBS: {DOCK_TITLE} -> {DOCK_URL}")
        print("Feche e abra o OBS para o dock aparecer no menu Exibir > Docks.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
