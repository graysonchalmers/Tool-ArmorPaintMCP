# build_stamp.py -- vendored from _agent-commons/reference/build-stamp/build_stamp.py.
# Must produce byte-identical stamps to the JS reference (Tool-3dViewer).
# Spec: _agent-commons/reference/build-stamp-standard.md
import json, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).parent
EMOJI_LIST = [
  '🦑','🐙','🦐','🦀','🐡','🐠','🐟','🐬','🐳','🐋','🦈','🐊','🐢','🦎','🐍','🦖',
  '🦕','🐉','🦩','🦚','🦜','🦉','🦅','🐧','🐦','🐤','🦆','🦢','🕊','🦇','🐺','🦊',
  '🦝','🐱','🦁','🐯','🐴','🦄','🦓','🦌','🐮','🐷','🐗','🐫','🦙','🦒','🐘','🦏',
  '🐭','🐹','🐰','🐿','🦔','🦥','🦦','🦨','🐾','🦋','🐌','🐛','🐜','🐝','🐞','🦗',
  '🌵','🌲','🌳','🌴','🌱','🍀','🍁','🍄','🌰','🦂','🌸','🌼','🌻','🌙','⭐','🔥',
  '❄','🌈','💧','🌊','⚡','☄','🪐','🌍','🍎','🍊','🍋','🍉','🍇','🍓','🍒','🍑',
  '🥝','🍍','🥥','🌽','🥕','🥭','🌶','🧀','🍰','🍩','🍪','🍫','🍬','🍭','☕','🍵',
  '⚓','🚀','🛸','🎈','🎲','🧭','🔑','💎','🔔','🎁','🪁','🎯','🧩','🎸','🎺','🥁',
]

WORD_LIST = [w.strip() for w in (HERE / "bip39-1024.txt").read_text(encoding="utf8").splitlines() if w.strip()]

def derive_stamp(sha: str, date: str, version=None) -> dict:
    full = sha.lower()
    assert len(full) == 40 and all(c in "0123456789abcdef" for c in full), f"not a 40-hex sha: {sha}"
    emoji = EMOJI_LIST[int(full[0:8], 16) % len(EMOJI_LIST)]
    codeword = WORD_LIST[int(full[8:16], 16) % len(WORD_LIST)].upper()
    short = full[0:6]
    ver = version.strip() if version else ""
    prefix = f"v{ver} " if ver else ""
    return {"sha": full, "shortSha": short, "date": date, "version": ver or None, "emoji": emoji,
            "codeword": codeword, "stamp": f"{prefix}{emoji} {codeword} · {short} · {date}"}

def _git(args): return subprocess.check_output(["git", *args], cwd=HERE, text=True).strip()

def _resolve_version():
    if os.environ.get("BUILD_STAMP_VERSION"): return os.environ["BUILD_STAMP_VERSION"]
    vf = HERE.parent / "VERSION"
    return vf.read_text(encoding="utf8").strip() if vf.exists() else None

def read_stamp() -> dict:
    """Read the baked stamp, falling back to dev/unknown if never built."""
    stamp_path = HERE.parent / "build-stamp.json"
    if stamp_path.exists():
        return json.loads(stamp_path.read_text(encoding="utf8"))
    return {"sha": None, "shortSha": None, "date": None, "version": None,
            "emoji": None, "codeword": None, "stamp": "dev/unknown"}

if __name__ == "__main__":
    sha = _git(["rev-parse", "HEAD"]); date = _git(["show", "-s", "--format=%cd", "--date=short", "HEAD"])
    stamp = derive_stamp(sha, date, _resolve_version())
    out = HERE.parent / "build-stamp.json"
    # Windows consoles are often cp1252, which can't encode the emoji -- write
    # the real stamp (with emoji) to the JSON file, but keep console output
    # ASCII-safe so this never crashes on a plain `python build_stamp.py` run.
    ascii_stamp = f"{stamp['codeword']} \xb7 {stamp['shortSha']} \xb7 {stamp['date']}"
    if "--print" in sys.argv:
        print(ascii_stamp)
    else:
        out.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf8")
        print("[build-stamp] wrote build-stamp.json:", ascii_stamp)
