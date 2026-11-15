"""${message}"""

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}
