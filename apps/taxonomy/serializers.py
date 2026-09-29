from rest_framework import serializers

from .models import Theme


class ThemeChildSerializer(serializers.ModelSerializer):
    """Shallow representation used for nesting — deliberately doesn't nest its own
    subthemes, since Theme is restricted to 2 levels (see Theme.clean())."""

    class Meta:
        model = Theme
        fields = ["id", "slug", "name"]


class ThemeSerializer(serializers.ModelSerializer):
    subthemes = ThemeChildSerializer(many=True, read_only=True)

    class Meta:
        model = Theme
        fields = ["id", "slug", "name", "description", "parent", "subthemes"]

    def validate_parent(self, parent):
        if parent is not None and parent.parent_id is not None:
            raise serializers.ValidationError(
                "A sub-theme's parent must itself be a top-level theme (max 2 levels)."
            )
        if self.instance is not None and parent is not None and parent.pk == self.instance.pk:
            raise serializers.ValidationError("A theme cannot be its own parent.")
        return parent


class SubThemeSerializer(serializers.ModelSerializer):
    """Used under the nested /themes/{theme_pk}/subthemes/ routes — `parent` comes from
    the URL (see SubThemeViewSet), not the request body, so it's read-only here."""

    class Meta:
        model = Theme
        fields = ["id", "slug", "name", "parent"]
        read_only_fields = ["parent"]
