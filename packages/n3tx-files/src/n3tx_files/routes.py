"""Package-local upload/download routes for file bytes.

Generated N3TX method routes are JSON-oriented. File upload/download needs
multipart input and binary/range output, so this module mounts explicit API
adapters that still delegate to the File model and preserve N3TX auth rules.
"""

from __future__ import annotations

from fastapi import APIRouter, File as FastAPIFile, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from n3tx_core.authorize import AccessContext, AccessDenied, DefaultResolver

from .file import File, get_file_store


_resolver = DefaultResolver()


def register_file_routes(router: APIRouter, file_model: type[File], *, tag: str) -> None:
    """Register byte-oriented routes for the File capability."""

    @router.post("/files/upload", tags=[tag], status_code=201, name="files_upload")
    async def upload_file(request: Request, upload: UploadFile = FastAPIFile(...)):
        user = _get_user(request)
        _authorize(file_model, "create", user=user)

        stat = await get_file_store().put_stream(
            upload,
            meta={"content_type": upload.content_type or "application/octet-stream"},
        )
        metadata = file_model(
            filename=upload.filename or stat.key,
            content_type=upload.content_type or stat.content_type,
            size=stat.size,
            sha256=stat.sha256,
            storage_key=stat.key,
            user_owner=user.get("user_id") if user else None,
        )
        created = file_model.create(metadata)
        if not created:
            raise HTTPException(status_code=409, detail="File create failed")
        return created.model_response()

    @router.get("/files/{id:int}/download", tags=[tag], name="files_download")
    @router.get("/File/{id:int}/download", tags=[tag], name="File_download")
    async def download_file(request: Request, id: int):
        file = file_model.get(id)
        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        user = _get_user(request)
        _authorize(file_model, "read", user=user, resource=file)

        start, end = _parse_range(request.headers.get("range"), file.size)
        if start is None:
            status_code = 200
            content_length = file.size
        else:
            status_code = 206
            content_length = end - start + 1

        headers = {
            "Content-Length": str(content_length),
            "ETag": file.sha256,
            "X-Content-Type-Options": "nosniff",
        }
        if start is not None:
            headers["Content-Range"] = f"bytes {start}-{end}/{file.size}"
        if file.filename:
            headers["Content-Disposition"] = f'attachment; filename="{file.filename}"'

        return StreamingResponse(
            get_file_store().open_stream(file.storage_key, start=start, end=end),
            status_code=status_code,
            media_type=file.content_type or "application/octet-stream",
            headers=headers,
        )


def _get_user(request: Request) -> dict:
    return getattr(request.state, "user", {}) or {}


def _authorize(model_class, action: str, *, user: dict, resource=None) -> None:
    try:
        _resolver.authorize(
            AccessContext(
                user=user,
                action=action,
                model_class=model_class,
                resource=resource,
            )
        )
    except AccessDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _parse_range(header: str | None, size: int) -> tuple[int | None, int | None]:
    if not header:
        return None, None
    if not header.startswith("bytes="):
        raise HTTPException(status_code=416, detail="Unsupported range")

    raw_start, _, raw_end = header[len("bytes="):].partition("-")
    try:
        if raw_start == "":
            # Suffix range: bytes=-N
            length = int(raw_end)
            if length <= 0:
                raise ValueError
            start = max(size - length, 0)
            end = size - 1
        else:
            start = int(raw_start)
            end = int(raw_end) if raw_end else size - 1
    except ValueError as exc:
        raise HTTPException(status_code=416, detail="Invalid range") from exc

    if start < 0 or end < start or start >= size:
        raise HTTPException(status_code=416, detail="Range not satisfiable")
    return start, min(end, size - 1)
