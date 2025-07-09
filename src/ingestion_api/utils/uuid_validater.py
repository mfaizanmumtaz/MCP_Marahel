import uuid


def validate_uuid(uuid_string):
    try:
        # Attempt to create a UUID from the string
        uuid_obj = uuid.UUID(uuid_string)
        return str(uuid_obj) == uuid_string
    except ValueError:
        return False
