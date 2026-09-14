"""Central role policy; unknown roles fail closed."""
from enum import StrEnum

class Role(StrEnum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    OPERATOR = "operator"
    ADMINISTRATOR = "administrator"

class Permission(StrEnum):
    READ = "workspace:read"
    BUILD = "dataset:build"
    PREDICT = "prediction:run"
    COLLECT = "data:collect"
    IMPORT = "data:import"
    DEMO = "data:demo"
    TRAIN = "model:train"
    MANAGE_USERS = "users:manage"

_VIEWER = frozenset({Permission.READ})
_ANALYST = _VIEWER | {Permission.BUILD, Permission.PREDICT}
_OPERATOR = _ANALYST | {Permission.COLLECT, Permission.IMPORT, Permission.DEMO, Permission.TRAIN}
ROLE_PERMISSIONS = {Role.VIEWER: _VIEWER, Role.ANALYST: _ANALYST,
                    Role.OPERATOR: _OPERATOR, Role.ADMINISTRATOR: frozenset(Permission)}

def permissions_for(role: str) -> list[str]:
    return sorted(ROLE_PERMISSIONS.get(role, ()))
