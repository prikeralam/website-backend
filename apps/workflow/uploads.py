"""Uploaded images (person photos, project images, publication covers), shared by the content apps."""

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from rest_framework import serializers

IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def validate_image_size(file):
    if file.size > MAX_IMAGE_BYTES:
        raise ValidationError("Images must be 5 MB or smaller.")


IMAGE_VALIDATORS = [FileExtensionValidator(IMAGE_EXTENSIONS), validate_image_size]


class ImageUploadField(serializers.FileField):
    """An optional image upload. Reads as the file's URL (presigned on S3); writing null removes the upload."""

    def __init__(self, **kwargs):
        super().__init__(required=False, allow_null=True, validators=IMAGE_VALIDATORS, **kwargs)

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
