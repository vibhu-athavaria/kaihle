from typing import Any, cast

from fastapi import Request
from redis.asyncio import Redis


def get_redis(request: Request) -> Redis[Any]:
    return cast(Redis[Any], request.app.state.redis)
