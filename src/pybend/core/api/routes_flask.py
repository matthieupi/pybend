# app/api/routes.py
import requests
from flask import Blueprint, request, jsonify
from flasgger import swag_from
from functools import wraps
import yaml

from models.storable_mixin import StorableMixin


def create_api_blueprint(registered_models):
    """
    Creates a Flask blueprint with routes for all registered models.

    Args:
        registered_models (dict): A dictionary of registered models.

    Returns:
        Blueprint: A Flask blueprint with all routes.
    """
    api_bp = Blueprint('api', __name__)

    for model_name, model_class in registered_models.items():
        # Endpoint base path
        endpoint_base = f'/{model_name}'
        is_storable = issubclass(model_class, StorableMixin)

        # Create instance
        def create_generator(model_class):
            @swag_from({
                'tags': [model_name],
                'parameters': [
                    {
                        'in': 'body',
                        'name': 'body',
                        'required': True,
                        'schema': model_class.model_json_schema()
                    }
                ],
                'responses': {
                    201: {
                        'description': 'Created',
                        'schema': model_class.model_json_schema()
                    },
                    400: {
                        'description': 'Invalid input'
                    }
                }
            })
            def create():
                data = request.json
                try:
                    instance = model_class(**data)
                    instance = model_class.create(instance)
                    return jsonify(instance.model_dump()), 201
                except Exception as e:
                    return jsonify({'error': str(e)}), 400
            return create

        if is_storable:
            create_instance_view = create_generator(model_class)
            api_bp.add_url_rule(
                endpoint_base,
                view_func=create_instance_view,
                methods=['POST'],
                endpoint=f'{model_name}_create'
            )

        # Get all instances
        def list_generator(model_class):
            @swag_from({
                'tags': [model_name],
                'responses': {
                    200: {
                        'description': f'A list of {model_name}',
                        'schema': {
                            'type': 'array',
                            'items': model_class.model_json_schema()
                        }
                    }
                }
            })
            def get_all_instances():
                instances = model_class.list()
                jsonables = [instance.model_dump() for instance in instances]
                return jsonables, 200
            return get_all_instances

        get_all_instances_view = list_generator(model_class)
        api_bp.add_url_rule(
            endpoint_base,
            view_func=get_all_instances_view,
            methods=['GET'],
            endpoint=f'{model_name}_get_all'
        )

        # Get instance by ID
        def get_generator(model_class):
            @swag_from({
                'tags': [model_name],
                'parameters': [
                    {
                        'name': 'id',
                        'in': 'path',
                        'required': True,
                        'type': 'integer'
                    }
                ],
                'responses': {
                    200: {
                        'description': f'A {model_name} object',
                        'schema': model_class.model_json_schema()
                    },
                    404: {
                        'description': 'Not found'
                    }
                }
            })
            def get_instance_by_id(id):
                instance = model_class.get(id)
                if instance:
                    return jsonify(instance.model_dump()), 200
                else:
                    return jsonify({'error': 'Not found'}), 404
            return get_instance_by_id

        if hasattr(model_class, 'get'):
            get_instance_by_id_view = get_generator(model_class)
            api_bp.add_url_rule(
                f'{endpoint_base}/<int:id>',
                view_func=get_instance_by_id_view,
                methods=['GET'],
                endpoint=f'{model_name}_get'
            )

        # Update instance
        def update_generator(model_class):
            @swag_from({
                'tags': [model_name],
                'parameters': [
                    {
                        'name': 'id',
                        'in': 'path',
                        'required': True,
                        'type': 'integer'
                    },
                    {
                        'in': 'body',
                        'name': 'body',
                        'required': True,
                        'schema': model_class.model_json_schema()
                    }
                ],
                'responses': {
                    200: {
                        'description': 'Updated successfully'
                    },
                    400: {
                        'description': 'Invalid input'
                    }
                }
            })
            def update_instance(id):
                data = request.json
                try:
                    instance = model_class(**data)
                    model_class.update(id, instance)
                    return jsonify({'message': 'Updated successfully'}), 200
                except Exception as e:
                    return jsonify({'error': str(e)}), 400
            return update_instance

        if hasattr(model_class, 'update'):
            update_instance_view = update_generator(model_class)
            api_bp.add_url_rule(
                f'{endpoint_base}/<int:id>',
                view_func=update_instance_view,
                methods=['PUT'],
                endpoint=f'{model_name}_update'
            )

        # Delete instance
        def delete_generator(model_class):
            @swag_from({
                'tags': [model_name],
                'parameters': [
                    {
                        'name': 'id',
                        'in': 'path',
                        'required': True,
                        'type': 'integer'
                    }
                ],
                'responses': {
                    200: {
                        'description': 'Deleted successfully'
                    }
                }
            })
            def delete_instance(id):
                model_class.delete(id)
                return jsonify({'message': 'Deleted successfully'}), 200
            return delete_instance

        if hasattr(model_class, 'delete'):
            delete_instance_view = delete_generator(model_class)
            api_bp.add_url_rule(
                f'{endpoint_base}/<int:id>',
                view_func=delete_instance_view,
                methods=['DELETE'],
                endpoint=f'{model_name}_delete'
            )

        # Register additional endpoints defined in the model
        for attr_name in dir(model_class):
            attr = getattr(model_class, attr_name)
            if callable(attr) and hasattr(attr, '__endpoint__'):
                endpoint_info = attr.__endpoint__
                route = endpoint_info['route']
                methods = endpoint_info['methods']
                full_route = f'{endpoint_base}{route}'

                # Capture the function and model_class in a closure
                def endpoint_generator(func):
                    @wraps(func)
                    def endpoint_function(*args, **kwargs):
                        if request.is_json and request.json:
                            data = request.json
                            output = func(data)
                        else:
                            output = func()
                        return output
                    # Attach the docstring for Swagger
                    endpoint_function.__doc__ = func.__doc__
                    return endpoint_function

                endpoint_function = endpoint_generator(attr)

                # Apply Swagger documentation
                if attr.__doc__:
                    tags = [model_name]
                    responses = {
                        200: {
                            'description': 'Success'
                        }
                    }
                # Set the endpoint name to avoid conflicts
                endpoint_name = f"{model_name}_{attr_name}"

                # Register the route
                api_bp.add_url_rule(
                    full_route,
                    endpoint=endpoint_name,
                    view_func=endpoint_function,
                    methods=methods
                )

    return api_bp
