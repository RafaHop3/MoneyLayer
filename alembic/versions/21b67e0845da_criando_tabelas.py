"""criando tabelas

Revision ID: 21b67e0845da
Revises: aa992a6ea611
Create Date: 2025-12-27 08:22:23.264373

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '21b67e0845da'
down_revision: Union[str, Sequence[str], None] = 'aa992a6ea611'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
