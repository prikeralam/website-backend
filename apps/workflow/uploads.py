"""Uploaded images (person photos, project images, publication covers), shared by the content apps."""

from html.parser import HTMLParser

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.crypto import get_random_string
from rest_framework import serializers

IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def validate_image_size(file):
    if file.size > MAX_IMAGE_BYTES:
        raise ValidationError("Images must be 5 MB or smaller.")


IMAGE_VALIDATORS = [FileExtensionValidator(IMAGE_EXTENSIONS), validate_image_size]


class ImageUploadField(serializers.FileField):
    """An optional image upload. Reads as the file's URL (presigned on S3); writing null removes the upload."""

    default_validators_list = IMAGE_VALIDATORS

    def __init__(self, **kwargs):
        super().__init__(required=False, allow_null=True, validators=self.default_validators_list, **kwargs)

    def run_validators(self, value):
        if value:
            super().run_validators(value)

    def to_internal_value(self, data):
        # Multipart forms can't send null, so an empty value also means "remove".
        if data in ("", None):
            return ""
        return super().to_internal_value(data)

    def validate_empty_values(self, data):
        if data is None:
            return (True, "")
        return super().validate_empty_values(data)


# Documents people send in (CVs, statements of purpose). Checked by extension, size and the file's first bytes,
# since a renamed file of another kind would otherwise pass.
DOCUMENT_EXTENSIONS = ["pdf", "doc", "docx"]
MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
_DOCUMENT_SIGNATURES = {
    "pdf": (b"%PDF",),
    "doc": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),  # OLE compound file (Word 97-2003)
    "docx": (b"PK\x03\x04",),  # ZIP container (Office Open XML)
}


def validate_document_size(file):
    if file.size > MAX_DOCUMENT_BYTES:
        raise ValidationError("Files must be 5 MB or smaller.")


def validate_document_content(file):
    extension = file.name.rsplit(".", 1)[-1].lower() if "." in file.name else ""
    signatures = _DOCUMENT_SIGNATURES.get(extension)
    if not signatures:
        return
    position = file.tell() if hasattr(file, "tell") else 0
    file.seek(0)
    head = file.read(8)
    file.seek(position)
    if not head.startswith(signatures):
        raise ValidationError(f"This doesn't look like a .{extension} file.")


DOCUMENT_VALIDATORS = [FileExtensionValidator(DOCUMENT_EXTENSIONS), validate_document_size, validate_document_content]

# Files PRI publishes for people to download and share, such as a job description: PDF only, same size and content
# checks as documents.
PDF_VALIDATORS = [FileExtensionValidator(["pdf"]), validate_document_size, validate_document_content]


# Data story bodies: one self-contained HTML file per publication. The frontend shows it in a sandboxed iframe, so
# these checks are about keeping stories portable (scripts only from the two pinned CDNs), not about isolation.
STORY_EXTENSIONS = ["html", "htm"]
MAX_STORY_BYTES = 5 * 1024 * 1024
STORY_SCRIPT_HOSTS = ("https://cdnjs.cloudflare.com/", "https://cdn.jsdelivr.net/npm/")


class _ScriptSources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sources = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            src = dict(attrs).get("src")
            if src is not None:
                self.sources.append(src.strip())


def _read_text(file):
    position = file.tell() if hasattr(file, "tell") else 0
    file.seek(0)
    raw = file.read()
    file.seek(position)
    try:
        return raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
    except UnicodeDecodeError:
        raise ValidationError("Save the story as UTF-8 text.") from None


def validate_story_size(file):
    if file.size > MAX_STORY_BYTES:
        raise ValidationError("Story files must be 5 MB or smaller.")


def validate_story_content(file):
    parser = _ScriptSources()
    parser.feed(_read_text(file))
    refused = [src for src in parser.sources if not src.startswith(STORY_SCRIPT_HOSTS)]
    if refused:
        raise ValidationError(
            f"Scripts may only load from cdnjs.cloudflare.com or cdn.jsdelivr.net/npm. Refused: {', '.join(refused)}"
        )


STORY_VALIDATORS = [FileExtensionValidator(STORY_EXTENSIONS), validate_story_size, validate_story_content]


def story_upload_to(instance, filename):
    # Stored as plain text: the raw file URL then shows the source instead of running the page on the bucket's
    # origin. The frontend reads it as text either way.
    return f"stories/{get_random_string(12)}.txt"


class StoryUploadField(ImageUploadField):
    """An optional story upload: same null/empty handling as images, with the story validators."""

    default_validators_list = STORY_VALIDATORS


class PdfUploadField(ImageUploadField):
    """An optional PDF upload (e.g. a job description): same null/empty handling as images, PDF validators."""

    default_validators_list = PDF_VALIDATORS
