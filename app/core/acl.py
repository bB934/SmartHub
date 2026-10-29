"""权限计算：先用 SQL 得到有权限的 doc_id，再把结果下推进向量库/ES 的过滤条件。

为什么不能“先召回再过滤”：topK 会被无权限文档占满，过滤后可能只剩 0 条，
表现为“模型变笨”，实际是权限吃掉了召回。
"""

import json

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.context import RequestContext


def authorized_doc_ids(ctx: RequestContext, session: Session) -> list[int]:
    sql = text(
        """
        SELECT id FROM doc
        WHERE tenant_id = :tid
          AND (:space IS NULL OR space_id = :space)
          AND index_status = 1
          AND ( visibility = 0
             OR (visibility = 1 AND JSON_OVERLAPS(acl_group, CAST(:groups AS JSON)))
             OR (visibility = 2 AND created_by = :uid) )
        """
    )
    rows = session.execute(
        sql,
        {
            "tid": ctx.tenant_id,
            "space": ctx.space_id,
            "groups": json.dumps(ctx.groups),
            "uid": ctx.user_id,
        },
    )
    return [r[0] for r in rows]
