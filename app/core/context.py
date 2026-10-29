"""租户上下文：从请求头解析，缺失时用演示默认值，保证前端零配置可跑。"""

from dataclasses import dataclass, field

from fastapi import Header


@dataclass
class RequestContext:
    tenant_id: int = 1
    space_id: int | None = 1
    user_id: int = 1
    groups: list[int] = field(default_factory=list)


def _parse_groups(raw: str) -> list[int]:
    return [int(x) for x in raw.replace(" ", "").split(",") if x]


async def current_ctx(
    x_tenant_id: int = Header(1, alias="X-Tenant-Id"),
    x_space_id: int = Header(1, alias="X-Space-Id"),
    x_user_id: int = Header(1, alias="X-User-Id"),
    x_groups: str = Header("", alias="X-Groups"),
) -> RequestContext:
    return RequestContext(
        tenant_id=x_tenant_id,
        space_id=x_space_id,
        user_id=x_user_id,
        groups=_parse_groups(x_groups),
    )
