from typing import Optional, Type

from django.db import connection, connections, models

try:
    from django.db.models import JSONField
except:
    from django.contrib.postgres.fields import JSONField

from pgpubsub.channel import BaseChannel
import pgtrigger


MAX_POSTGRES_CHANNEL_LENGTH = 63


class Notification(models.Model):
    channel = models.CharField(max_length=MAX_POSTGRES_CHANNEL_LENGTH)
    payload = JSONField()
    # The field is made nullable to make sure the addition of the new field is backward
    # compatible. From the version this change is released the field is effectively non
    # nullable as in it always gets a value.
    # After some time the field should be made non nullable here.
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    # This is a FK for the migration id but ForeignKey cannot be used as migrations
    # is not a regular table in django, so FK is created manually.
    db_version = models.IntegerField(null=True)

    class Meta:
        triggers = [
            pgtrigger.Trigger(
                name="pgpubsub_notification_set_db_version",
                operation=pgtrigger.Insert,
                when=pgtrigger.Before,
                func="""
                    NEW.db_version := (
                        SELECT max(id)
                        FROM django_migrations
                        WHERE app = NEW.payload ->> 'app'
                    );
                    NEW.created_at := NOW();
                    RETURN NEW;
                """,
            )
        ]
        ordering = ['created_at']

    def __repr__(self):
        return (
            f'Notification('
            f'channel={self.channel},'
            f' payload={self.payload},'
            f' created_at={self.created_at},'
            f' db_version={self.db_version}'
            f')'
        )

    @classmethod
    def from_channel(cls, channel: Type[BaseChannel]):
        return cls.objects.filter(channel=channel.listen_safe_name())

    @classmethod
    def set_payload_extras_builder(
        cls, func_name: str, till_tx_end: bool = False, using: Optional[str] = None
    ) -> None:
        if using:
            conn = connections[using]
        else:
            conn = connection
        scope = "LOCAL" if till_tx_end else "SESSION"
        with conn.cursor() as cursor:
            cursor.execute(f"SET {scope} pgpubsub.get_payload_extras_func = %s", (func_name,))
