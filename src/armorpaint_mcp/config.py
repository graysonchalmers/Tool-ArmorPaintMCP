import os
from dataclasses import dataclass, field
from dotenv import dotenv_values

# Config is env-var-first (an MCP client sets AP_* in its server "env" block).
# A .env file is a dev convenience only: looked up at AP_DOTENV if set, else in
# the current working directory. Path defaults are intentionally empty so a
# stranger with no config gets an actionable message from require_valid()
# rather than a stale path baked in at build time.
_DEFAULTS = {
    "AP_BINARY": "",
    "AP_OUTPUT_DIR": "",
    "AP_ALLOWED_ROOTS": "",
}


def _dotenv_path() -> str:
    override = os.environ.get("AP_DOTENV")
    if override:
        return override
    return os.path.join(os.getcwd(), ".env")


@dataclass
class Config:
    binary: str
    output_dir: str
    allowed_roots: list[str] = field(default_factory=list)


def require_valid(cfg: "Config") -> None:
    """Fail fast with an actionable message if required config is missing or
    wrong. Called at MCP server startup, not from load_config()."""
    if not os.path.isfile(cfg.binary):
        raise FileNotFoundError(
            f"ArmorPaint binary does not exist: '{cfg.binary}'. "
            "Set the AP_BINARY environment variable (or .env entry) to a "
            "valid ArmorPaint.exe path."
        )


def load_config(overrides: dict | None = None) -> Config:
    env = dict(_DEFAULTS)
    env.update({k: v for k, v in dotenv_values(_dotenv_path()).items() if v})
    env.update({k: v for k, v in os.environ.items() if k.startswith("AP_")})
    if overrides:
        env.update(overrides)
    output_dir = env["AP_OUTPUT_DIR"] or os.path.join(os.getcwd(), "output")
    allowed_roots = [p for p in env["AP_ALLOWED_ROOTS"].split(os.pathsep) if p]
    return Config(
        binary=env["AP_BINARY"],
        output_dir=output_dir,
        allowed_roots=allowed_roots,
    )
