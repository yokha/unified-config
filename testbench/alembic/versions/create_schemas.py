from alembic import op

def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS configuration;")
    op.execute("CREATE SCHEMA IF NOT EXISTS function;")

def downgrade():
    op.execute("DROP SCHEMA IF EXISTS configuration CASCADE;")
    op.execute("DROP SCHEMA IF EXISTS function CASCADE;")
