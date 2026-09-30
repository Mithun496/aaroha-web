from pathlib import Path
import os
from pathlib import PurePosixPath
from uuid import uuid4

from werkzeug.utils import secure_filename


ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_DOCUMENT_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "webp"}
CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "pdf": "application/pdf",
}


def _read_validated_upload(file_storage, allowed_extensions: set[str]):
    if not file_storage or not file_storage.filename:
        raise ValueError("File is required.")
    original = secure_filename(file_storage.filename)
    if not original or "." not in original:
        raise ValueError("File extension is required.")
    extension = original.rsplit(".", 1)[1].lower()
    if extension not in allowed_extensions:
        raise ValueError("Unsupported file type.")

    max_bytes = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    body = file_storage.stream.read(max_bytes + 1)
    file_storage.stream.seek(0)
    if len(body) > max_bytes:
        raise ValueError("File is too large.")
    signatures = {
        "jpg": lambda value: value.startswith(b"\xff\xd8\xff"),
        "jpeg": lambda value: value.startswith(b"\xff\xd8\xff"),
        "png": lambda value: value.startswith(b"\x89PNG\r\n\x1a\n"),
        "webp": lambda value: len(value) >= 12 and value[:4] == b"RIFF" and value[8:12] == b"WEBP",
        "pdf": lambda value: value.startswith(b"%PDF-"),
    }
    if not signatures[extension](body):
        raise ValueError("File content does not match its extension.")
    return extension, body


def _safe_storage_key(key: str, expected_prefix: str) -> str:
    if not isinstance(key, str) or "\\" in key or "\x00" in key:
        raise FileNotFoundError("Private file was not found.")
    path = PurePosixPath(key)
    if path.is_absolute() or len(path.parts) < 2 or any(part in {"", ".", ".."} for part in path.parts) or path.parts[0] != expected_prefix:
        raise FileNotFoundError("Private file was not found.")
    return path.as_posix()


class S3Storage:
    def __init__(self):
        import boto3

        self.bucket = os.getenv("STORAGE_BUCKET", "").strip()
        if not self.bucket:
            raise RuntimeError("STORAGE_BUCKET is required for S3 storage.")
        self.client = boto3.client(
            "s3",
            endpoint_url=os.getenv("STORAGE_ENDPOINT", "").strip() or None,
            region_name=os.getenv("STORAGE_REGION", "").strip() or None,
            aws_access_key_id=os.getenv("STORAGE_ACCESS_KEY", "").strip() or None,
            aws_secret_access_key=os.getenv("STORAGE_SECRET_KEY", "").strip() or None,
        )

    def save(self, file_storage, key: str, private=True):
        allowed = ALLOWED_DOCUMENT_EXTENSIONS if private else ALLOWED_IMAGE_EXTENSIONS
        expected_prefix = "private" if private else "public"
        key = _safe_storage_key(key, expected_prefix)
        extension, body = _read_validated_upload(file_storage, allowed)
        if PurePosixPath(key).suffix.lower() != f".{extension}":
            raise ValueError("Storage key extension does not match file content.")
        self.client.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=CONTENT_TYPES[extension])
        return key

    def get_private(self, key: str):
        key = _safe_storage_key(key, "private")
        return self._get_bytes(key)

    def get_public(self, key: str):
        key = _safe_storage_key(key, "public")
        return self._get_bytes(key)

    def _get_bytes(self, key: str):
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except Exception as error:
            code = getattr(error, "response", {}).get("Error", {}).get("Code")
            if code in {"NoSuchKey", "NotFound", "404"}:
                raise FileNotFoundError("Private file was not found.") from error
            raise RuntimeError("Private file storage is unavailable.") from error

    def delete(self, key: str):
        self.client.delete_object(Bucket=self.bucket, Key=_safe_storage_key(key, "private"))


def _use_s3():
    return os.getenv("STORAGE_PROVIDER", "local").strip().lower() == "s3"


def _save(file_storage, root: Path, subdir: str, allowed_extensions: set[str]) -> str:
    extension, body = _read_validated_upload(file_storage, allowed_extensions)
    root = root.resolve()
    target_dir = (root / subdir).resolve()
    if root not in target_dir.parents:
        raise ValueError("Storage directory must be inside the upload root.")
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}.{extension}"
    destination = target_dir / filename
    destination.write_bytes(body)
    return str(destination.relative_to(root)).replace("\\", "/")


def save_image(file_storage, root: Path, subdir: str = "images") -> str:
    public_subdir = subdir.replace("\\", "/").strip("/")
    if public_subdir != "public" and not public_subdir.startswith("public/"):
        public_subdir = f"public/{public_subdir}"
    return save_public_media(file_storage, root, public_subdir)


def save_document(file_storage, root: Path, subdir: str = "documents") -> str:
    return _save(file_storage, root, subdir, ALLOWED_DOCUMENT_EXTENSIONS)


def save_private_file(file_storage, root: Path, subdir: str = "private") -> str:
    """Store a randomized private file path; callers must authorize retrieval."""
    subdir = subdir.replace("\\", "/").strip("/")
    if subdir != "private" and not subdir.startswith("private/"):
        raise ValueError("Private files must be stored under the private directory.")
    if any(part in {"", ".", ".."} for part in PurePosixPath(subdir).parts):
        raise ValueError("Invalid private storage directory.")
    if _use_s3():
        original = secure_filename(file_storage.filename or "")
        extension = original.rsplit(".", 1)[1].lower() if "." in original else ""
        return S3Storage().save(file_storage, f"{subdir}/{uuid4().hex}.{extension}", private=True)
    return _save(file_storage, root, subdir, ALLOWED_DOCUMENT_EXTENSIONS)


def get_private_file(relative_path: str, root: Path) -> Path:
    if _use_s3():
        raise RuntimeError("Use get_private_file_bytes for S3 storage.")
    _safe_storage_key(relative_path, "private")
    candidate = (root / relative_path).resolve()
    private_root = (root / "private").resolve()
    if private_root not in candidate.parents or not candidate.is_file():
        raise FileNotFoundError("Private file was not found.")
    return candidate


def delete_private_file(relative_path: str, root: Path) -> None:
    if _use_s3():
        S3Storage().delete(relative_path)
        return
    path = get_private_file(relative_path, root)
    path.unlink()


def save_public_media(file_storage, root: Path, subdir: str = "public") -> str:
    subdir = subdir.replace("\\", "/").strip("/")
    if subdir != "public" and not subdir.startswith("public/"):
        subdir = f"public/{subdir}"
    if any(part in {"", ".", ".."} for part in PurePosixPath(subdir).parts):
        raise ValueError("Invalid public storage directory.")
    if _use_s3():
        original = secure_filename(file_storage.filename or "")
        extension = original.rsplit(".", 1)[1].lower() if "." in original else ""
        return S3Storage().save(file_storage, f"{subdir}/{uuid4().hex}.{extension}", private=False)
    return _save(file_storage, root, subdir, ALLOWED_IMAGE_EXTENSIONS)


def get_public_media_url(relative_path: str) -> str:
    relative_path = _safe_storage_key(relative_path, "public")
    base_url = os.getenv("STORAGE_PUBLIC_BASE_URL", "").strip()
    if base_url:
        return f"{base_url.rstrip('/')}/{relative_path.lstrip('/')}"
    return f"/media/{relative_path.lstrip('/')}"


def get_public_media_bytes(relative_path: str, root: Path):
    if _use_s3():
        return S3Storage().get_public(relative_path)
    if not isinstance(relative_path, str) or "\\" in relative_path or "\x00" in relative_path:
        raise FileNotFoundError("Public media was not found.")
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise FileNotFoundError("Public media was not found.")
    if relative.parts[0] == "private" or relative.suffix.lower().lstrip(".") not in ALLOWED_IMAGE_EXTENSIONS:
        raise FileNotFoundError("Public media was not found.")
    root = root.resolve()
    candidate = (root / Path(*relative.parts)).resolve()
    if root not in candidate.parents or (root / "private").resolve() in candidate.parents or not candidate.is_file():
        raise FileNotFoundError("Public media was not found.")
    return candidate.read_bytes()


def get_private_file_bytes(relative_path: str, root: Path):
    if _use_s3():
        return S3Storage().get_private(relative_path)
    return get_private_file(relative_path, root).read_bytes()
