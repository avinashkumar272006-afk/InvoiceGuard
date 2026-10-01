import magic
from fastapi import UploadFile, HTTPException, status

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}

async def validate_file(file: UploadFile) -> str:
    """
    Validates file size, MIME type, and magic bytes.
    Returns the mapped file extension (e.g. '.pdf') on success.
    Raises HTTPException 413 or 415 on failure.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Empty filename",
        )

    # 1. Validate declared MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported media type: {file.content_type}",
        )
    
    # 2. Read prefix for magic bytes and size checking
    prefix = await file.read(2048)
    if not prefix:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Empty file",
        )

    # 3. Validate magic bytes (file signature)
    mime = magic.Magic(mime=True)
    detected_mime = mime.from_buffer(prefix)
    
    # Special fallback for magic library inconsistencies with certain PDFs
    if file.content_type == "application/pdf":
        if not prefix.startswith(b"%PDF"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File signature does not match PDF",
            )
    elif file.content_type == "image/png":
        if not prefix.startswith(b"\x89PNG\r\n\x1a\n"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File signature does not match PNG",
            )
    elif file.content_type == "image/jpeg":
        if not prefix.startswith(b"\xff\xd8\xff"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File signature does not match JPEG",
            )
    else:
        # Fallback to magic if not caught by explicit headers above
        if detected_mime != file.content_type:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"File signature mismatch. Detected: {detected_mime}, Expected: {file.content_type}",
            )

    # 4. Check file size
    # We read chunks to determine total size without loading entirely into memory at once
    total_size = len(prefix)
    if total_size > MAX_FILE_SIZE:
        await file.seek(0)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of 10 MB",
        )
        
    while chunk := await file.read(8192):
        total_size += len(chunk)
        if total_size > MAX_FILE_SIZE:
            await file.seek(0)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum size of 10 MB",
            )
            
    # Reset file pointer for caller
    await file.seek(0)
    
    return ALLOWED_MIME_TYPES[file.content_type]
