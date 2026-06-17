from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.utils.field_mapping import get_nested_relation_kwargs

from camomilla.settings import SAFE_NESTING_SENSITIVE_USER_FIELDS


# Fail-closed fallback: used only when the configured user model exposes *none*
# of the sensitive fields below (an exotic ``AUTH_USER_MODEL`` that isn't a
# Django auth user). With nothing known to strip, expose just these instead of
# dumping the row verbatim.
SAFE_USER_FIELDS = ("id", "username", "first_name", "last_name")


def _user_nested_meta_attrs(user_model):
    """``Meta`` attrs for a safe nested serializer over the auth user model.

    Blacklist-first: strip the known-sensitive auth columns
    (:data:`camomilla.settings.SAFE_NESTING_SENSITIVE_USER_FIELDS`) and let
    everything else — including a project's own custom user columns — through
    automatically. This is the intended behaviour: sensitive *defaults* are
    skipped while bespoke profile data displays without per-project wiring.

    Only fields actually present on the model are excluded, because DRF raises
    if ``exclude`` names a field the model lacks — so a custom user without,
    say, ``is_staff`` would otherwise blow up at serializer-build time.

    If the model exposes none of the sensitive fields (so there is nothing
    known to strip), fall back to the conservative :data:`SAFE_USER_FIELDS`
    whitelist rather than exposing the row — ``exclude=()`` would dump every
    column, ``password`` included. The final fallback is the model's primary
    key (whatever it is named), which is always a valid serializer field.
    """
    model_fields = {f.name for f in user_model._meta.get_fields()}
    to_exclude = tuple(
        name for name in SAFE_NESTING_SENSITIVE_USER_FIELDS if name in model_fields
    )
    if to_exclude:
        return {"model": user_model, "exclude": to_exclude}
    safe = tuple(name for name in SAFE_USER_FIELDS if name in model_fields)
    return {"model": user_model, "fields": safe or (user_model._meta.pk.name,)}


def _build_safe_user_serializer(user_model):
    """A ``ModelSerializer`` subclass that strips the sensitive auth columns."""
    meta = type("Meta", (), _user_nested_meta_attrs(user_model))
    return type(
        f"{user_model.__name__}SafeNested",
        (serializers.ModelSerializer,),
        {"Meta": meta},
    )


class SafeNestingMixin:
    """Keep depth-based nested serialization from dumping sensitive related
    rows verbatim.

    A read serializer that auto-nests related models (``depth > 0``, or
    camomilla's :class:`~camomilla.serializers.mixins.nesting.NestMixin` which
    re-nests relations even at ``depth = 0``) pulls **every** column of each FK
    target. For a model with an ``author`` FK to ``AUTH_USER_MODEL`` that leaks
    the user's ``password`` hash, ``is_superuser``, email and permissions — on
    the public, unauthenticated page router in the worst case.

    DRF dispatches relations down two paths: ``build_nested_field`` (when the
    requested depth is ``> 0``) and ``build_relational_field`` (depth ``0`` /
    the recursion boundary). This mixin overrides **both** so a FK/O2O/M2M whose
    target is the auth user model always renders through the blacklist
    serializer (sensitive columns stripped, everything else kept), and it carries
    itself into every other nested serializer it builds so the protection holds
    at *every* depth, not just the top level.
    """

    def build_nested_field(self, field_name, relation_info, nested_depth):
        related_model = relation_info.related_model
        kwargs = get_nested_relation_kwargs(relation_info)

        if related_model is get_user_model():
            return _build_safe_user_serializer(related_model), kwargs

        # Non-user relation: build the usual nested serializer, but mix this
        # class in so deeper FKs to the user model stay protected too.
        class _SafeNestedSerializer(SafeNestingMixin, serializers.ModelSerializer):
            class Meta:
                model = related_model
                depth = nested_depth - 1
                fields = "__all__"

        _SafeNestedSerializer.__name__ = f"{related_model.__name__}SafeNested"
        return _SafeNestedSerializer, kwargs

    def build_relational_field(self, field_name, relation_info, *args, **kwargs):
        # The depth-0 / recursion-boundary branch: DRF calls this instead of
        # ``build_nested_field``, and ``NestMixin`` may re-attach a full
        # ``fields="__all__"`` serializer for the relation (it defaults the nest
        # depth even when ``Meta.depth`` is 0). Swap in the blacklist serializer
        # for any relation whose target is the auth user model, so the protection
        # holds on this branch too — not only the ``depth > 0`` nested branch.
        field_class, field_kwargs = super().build_relational_field(
            field_name, relation_info, *args, **kwargs
        )
        if (
            relation_info.related_model is get_user_model()
            and "serializer" in field_kwargs
        ):
            field_kwargs["serializer"] = _build_safe_user_serializer(
                relation_info.related_model
            )
        return field_class, field_kwargs
