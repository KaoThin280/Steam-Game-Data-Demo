"""
Data Files router — serves sandbox-generated artifacts (HTML charts, CSV data, PNG images).

Endpoints:
  GET /data-files              → List all files in temp_data/
  GET /data-files/{filename}   → Serve file content (HTML inline, CSV/PNG download)
  GET /tables/{filename}       → Return CSV data as JSON {columns, data, num_rows}

Uses StaticFiles mount at /api/v1/temp_data for direct file serving.
This router provides additional metadata and JSON table data.
"""
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.params import Path as FastAPIPath
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.api.dependencies import get_current_active_user
from app.core.config import settings
from app.models.user import AppUser
from app.services.session_service import session_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Data Files"])

TEMP_DIR = Path(settings.TEMP_DATA_DIR)
ALLOWED_EXTENSIONS = {".html", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".csv", ".json", ".txt", ".md"}


def _validate_path(filename: str) -> Path:
    """Validate filename, prevent path traversal, return full path."""
    if not filename or filename.startswith("/") or ".." in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path. Path traversal is not allowed.",
        )
    full_path = (TEMP_DIR / filename).resolve()
    # Ensure it's inside TEMP_DIR
    try:
        full_path.relative_to(TEMP_DIR.resolve())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Access denied. File must be inside the data directory.",
        )
    return full_path


@router.get(
    "/data-files",
    summary="List all generated files in temp_data",
    response_description="List of filenames with metadata",
)
async def list_data_files(
    ext: str = Query(None, description="Filter by extension (e.g. 'html', 'csv', 'png')"),
    current_user: AppUser = Depends(get_current_active_user),
) -> Dict[str, List[Dict[str, Any]]]:
    """Return a list of all files in temp_data directory."""
    if not TEMP_DIR.exists():
        return {"files": []}

    files = []
    for fname in sorted(TEMP_DIR.iterdir()):
        if not fname.is_file():
            continue
        ext_lower = fname.suffix.lower()
        if ext and ext_lower != f".{ext.lstrip('.')}":
            continue
        if ext_lower not in ALLOWED_EXTENSIONS:
            continue
        stat = fname.stat()
        files.append({
            "name": fname.name,
            "size_bytes": stat.st_size,
            "modified": stat.st_mtime,
            "extension": ext_lower,
        })

    return {"files": files}


@router.get(
    "/data-files/{filename:path}",
    summary="Download or view a generated file (HTML chart, CSV, PNG)",
    response_description="File content with appropriate Content-Type",
)
async def get_data_file(
    filename: str = FastAPIPath(..., description="Filename in temp_data/"),
):
    """
    Serve a file from temp_data. HTML files are served inline for iframe rendering.
    Public endpoint — no auth required so PlotlyHtmlRenderer iframes work.
    """
    full_path = _validate_path(filename)

    if not full_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File '{filename}' not found.",
        )

    ext = full_path.suffix.lower()

    # HTML → serve inline (for Plotly iframe)
    if ext == ".html":
        try:
            html_content = full_path.read_text(encoding="utf-8")
            return HTMLResponse(content=html_content, status_code=200)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to read HTML: {exc}",
            )

    # PNG/JPEG/GIF → serve with inline disposition for <img> tags
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".svg"):
        media_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
        }.get(ext, "application/octet-stream")
        return FileResponse(
            path=str(full_path),
            filename=filename,
            media_type=media_type,
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )

    # CSV → download
    if ext == ".csv":
        return FileResponse(
            path=str(full_path),
            filename=filename,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # Other → download
    return FileResponse(
        path=str(full_path),
        filename=filename,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/tables/{filename:path}",
    summary="Get CSV table data as JSON",
    response_description="JSON with columns, data rows, and row count",
)
async def get_table_data(
    filename: str = FastAPIPath(..., description="CSV filename (e.g. 'metadata.csv')"),
    current_user: AppUser = Depends(get_current_active_user),
):
    """Return CSV data as JSON for the frontend DataTableViewer."""
    full_path = _validate_path(filename)

    if not full_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table '{filename}' not found.",
        )

    if full_path.suffix.lower() != ".csv":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files can be queried as tables.",
        )

    try:
        import pandas as pd

        df = pd.read_csv(full_path)
        columns = {col: {"dtype": str(df[col].dtype), "business_meaning": f"Column: {col}"} for col in df.columns}
        # Convert to records format, handling NaN/NaT
        data = json.loads(df.to_json(orient="records", date_format="iso", default_handler=str))

        return JSONResponse(content={
            "columns": columns,
            "data": data,
            "num_rows": len(data),
            "file_name": filename,
        })
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="pandas is required for table data endpoint.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read CSV: {exc}",
        )