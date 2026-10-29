from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.models.doc import Base

# 所有模型模块都必须在这里 import，否则表不会注册到 Base.metadata，
# autogenerate 会生成一个空迁移（这是最容易被忽略的坑）。
import app.models.doc  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 从 settings 注入数据库 URL，alembic.ini 里保持 sqlalchemy.url 为空。
# ConfigParser 把 % 当插值符，密码里含 % 时必须转义成 %%，否则报 InterpolationSyntaxError。
config.set_main_option("sqlalchemy.url", settings.mysql_dsn.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL，不连库。alembic upgrade head --sql"""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连库执行。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,            # 字段类型变更也能被检出
            compare_server_default=True,  # 默认值变更也能被检出
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
