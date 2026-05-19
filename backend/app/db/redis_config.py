import json
import fnmatch
import os
import time
from typing import Any

import redis.asyncio as redis

REDIS_BACKEND = os.getenv("REDIS_BACKEND", "redis").lower()
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "3"))

# 全局redis客户端对象
redis_client = None


class MemoryRedis:
    """Small async Redis-compatible cache for local development."""

    def __init__(self):
        self._data: dict[str, tuple[str, float | None]] = {}

    def _is_expired(self, key: str) -> bool:
        value = self._data.get(key)
        if value is None:
            return False
        _, expires_at = value
        if expires_at is not None and expires_at <= time.time():
            self._data.pop(key, None)
            return True
        return False

    async def ping(self):
        return True

    async def get(self, key: str):
        if self._is_expired(key):
            return None
        value = self._data.get(key)
        return value[0] if value else None

    async def set(self, key: str, value: Any, ex: int | None = None):
        expires_at = time.time() + ex if ex else None
        self._data[key] = (str(value), expires_at)
        return True

    async def setex(self, key: str, time_seconds: int, value: Any):
        return await self.set(key, value, ex=time_seconds)

    async def incr(self, key: str):
        current = await self.get(key)
        next_value = int(current or 0) + 1
        _, expires_at = self._data.get(key, ("", None))
        self._data[key] = (str(next_value), expires_at)
        return next_value

    async def delete(self, *keys: str):
        deleted = 0
        for key in keys:
            if key in self._data:
                self._data.pop(key, None)
                deleted += 1
        return deleted

    async def keys(self, pattern: str):
        for key in list(self._data):
            self._is_expired(key)
        return [key for key in self._data if fnmatch.fnmatch(key, pattern)]

    async def aclose(self):
        self._data.clear()


async def connect_redis():
    """连接Redis"""
    global redis_client
    if redis_client is None:
        if REDIS_BACKEND == "memory":
            redis_client = MemoryRedis()
        else:
            redis_client = redis.Redis(
                host=REDIS_HOST, # redis主机地址
                port=REDIS_PORT, # redis端口号
                db=REDIS_DB,     # redis数据库编号(0-15)
                decode_responses=True # 是否对返回值进行解码(True:返回字符串,False:返回字节)
            )
    return redis_client

async def close_redis():
    """关闭Redis连接"""
    global redis_client
    if redis_client:
        await redis_client.aclose()
        redis_client = None

async def check_redis_connection() -> bool:
    """检查Redis连接"""
    try:
        redis_client = await connect_redis()
        await redis_client.ping()
        return True
    except Exception as e:
        print(f"Redis连接失败: {e}")
        return False

# 设置和读取redis
async def get_redis_cache_str(key: str) -> str | None:
    """根据key获取redis缓存 (字符串类型)"""
    try:
        redis_client = await connect_redis()
        return await redis_client.get(key)
    except Exception as e:
        print(f"获取redis缓存失败: {e}")
        return None

async def get_redis_cache_json(key: str) -> dict | None:
    """根据key获取redis缓存 (字典或列表类型)"""
    try:
        redis_client = await connect_redis()
        data = await redis_client.get(key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        print(f"获取redis的JSON缓存失败: {e}")
        return None

async def set_redis_cache(key: str, value: Any, expire: int = 3600) -> bool:
    """
    根据key设置redis缓存

    :param key: 缓存键
    :param value: 缓存值
    :param expire: 过期时间(秒)
    :return: None
    """
    try:
        redis_client = await connect_redis()
        if isinstance(value, str):
            # 如果是字符串，直接设置缓存
            await redis_client.set(key, value, ex=expire)
        elif isinstance(value, (dict, list)):
            # 如果是字典或列表，转为json字符串在设置缓存
            await redis_client.set(key, json.dumps(value, ensure_ascii=False), ex=expire)
        else:
            # 其他类型，尝试转换为字符串
            await redis_client.set(key, str(value), ex=expire)
        return True

    except Exception as e:
        print(f"设置redis缓存失败: {e}")
        return False
