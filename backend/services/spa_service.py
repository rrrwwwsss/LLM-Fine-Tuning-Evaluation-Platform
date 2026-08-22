from pathlib import Path
from typing import Optional


def resolve_spa_file(frontend_dist: Path, request_path: str) -> Optional[Path]:
    """Resolve a static file or Vue's index.html for a client-side route."""
    frontend_dist = frontend_dist.resolve()
    normalized = str(request_path or "").replace("\\", "/").lstrip("/")
    if normalized == "api" or normalized.startswith("api/"):
        return None

    candidate = (frontend_dist / normalized).resolve()
    if (candidate == frontend_dist or frontend_dist in candidate.parents) and candidate.is_file():
        return candidate

    # Missing files should remain 404. Extensionless paths such as /dataset/1
    # are Vue Router history routes and must receive index.html on refresh.
    if Path(normalized).suffix:
        return None
    index_path = frontend_dist / "index.html"
    return index_path if index_path.is_file() else None
