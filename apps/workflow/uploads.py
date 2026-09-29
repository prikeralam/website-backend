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
