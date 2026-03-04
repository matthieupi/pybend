from n3tx.core.storage.sqlite_migration import Migration


class SetDefaultGrantOwner(Migration):
    """Set user_owner to 1 (Alice) for existing grants that lack an owner."""

    def up(self, cursor):
        cursor.execute(
            "UPDATE grants SET user_owner = 1 "
            "WHERE user_owner IS NULL OR user_owner = '' OR user_owner = 0"
        )

    def down(self, cursor):
        cursor.execute("UPDATE grants SET user_owner = NULL")
