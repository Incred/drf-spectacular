from drf_spectacular.extensions import OpenApiSerializerExtension
from drf_spectacular.plumbing import (
    ResolvedComponent, build_basic_type, build_object_type, is_patched_serializer, warn,
)
from drf_spectacular.settings import spectacular_settings
from drf_spectacular.types import OpenApiTypes


class PolymorphicSerializerExtension(OpenApiSerializerExtension):
    target_class = 'rest_polymorphic.serializers.PolymorphicSerializer'
    match_subclasses = True

    def map_serializer(self, auto_schema, direction):
        sub_components = []
        serializer = self.target

        for sub_model in serializer.model_serializer_mapping:
            sub_serializer = serializer._get_serializer_from_model_or_instance(sub_model)
            sub_serializer.partial = serializer.partial
            resource_type = serializer.to_resource_type(sub_model)
            component = auto_schema.resolve_serializer(sub_serializer, direction)
            if not component:
                continue
            typed_component = self.build_typed_component(
                auto_schema=auto_schema,
                component=component,
                resource_type_field_name=serializer.resource_type_field_name,
                patched=is_patched_serializer(sub_serializer, direction)
            )
            sub_components.append((resource_type, typed_component.ref))

            if not resource_type:
                warn(
                    f'discriminator mapping key is empty for {sub_serializer.__class__}. '
                    f'this might lead to code generation issues.'
                )

        return {
            'oneOf': [ref for _, ref in sub_components],
            'discriminator': {
                'propertyName': serializer.resource_type_field_name,
                'mapping': {resource_type: ref['$ref'] for resource_type, ref in sub_components},
            }
        }

    def build_typed_component(self, auto_schema, component, resource_type_field_name, patched):
        if spectacular_settings.COMPONENT_SPLIT_REQUEST and component.name.endswith('Request'):
            typed_component_name = component.name[:-len('Request')] + 'TypedRequest'
        else:
            typed_component_name = f'{component.name}Typed'

        component_typed = ResolvedComponent(
            name=typed_component_name,
            type=ResolvedComponent.SCHEMA,
            object=component.object,
            schema={
                'allOf': [
                    component.ref,
                    build_object_type(
                        properties={
                            resource_type_field_name: build_basic_type(OpenApiTypes.STR)
                        },
                        required=None if patched else [resource_type_field_name]
                    )
                ]
            }
        )
        auto_schema.registry.register_on_missing(component_typed)
        return component_typed
