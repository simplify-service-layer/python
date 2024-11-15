import jsonschema
from jsonschema.validators import extend


def getValidator(schema) -> jsonschema.Draft202012Validator:
    return extend(jsonschema.Draft202012Validator)(schema)
