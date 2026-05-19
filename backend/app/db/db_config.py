import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text
from app.models.chat_history import Base

# 加载环境变量
load_dotenv()

DB_ENGINE = os.getenv("DB_ENGINE", "mysql").lower()

if DB_ENGINE == "sqlite":
    sqlite_path = Path(os.getenv("SQLITE_DATABASE", "data/chat_history.sqlite3"))
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    ASYNC_DATABSE_URL = f"sqlite+aiosqlite:///{sqlite_path.as_posix()}"
else:
    ASYNC_DATABSE_URL = f"mysql+aiomysql://{os.getenv('MYSQL_USER', 'root')}:{os.getenv('MYSQL_PASSWORD', '')}@{os.getenv('MYSQL_HOST', 'localhost')}:{os.getenv('MYSQL_PORT', '3306')}/{os.getenv('MYSQL_DATABASE', 'chat_history')}?charset=utf8mb4"

# 创建异步引擎
engine_kwargs = {"echo": True}
if DB_ENGINE != "sqlite":
    engine_kwargs.update(
        {
            "pool_size": 10, # 连接池中保持的持久连接数
            "max_overflow": 20, # 连接池中允许创建的额外连接数
        }
    )

async_engine = create_async_engine(ASYNC_DATABSE_URL, **engine_kwargs)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 初始化数据库，创建所有表
async def init_db():
    async with async_engine.begin() as conn:
        # 先删除旧表，然后创建新表
        # await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

# 依赖项
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()

        except Exception:
            await session.rollback()
            raise

        finally:
            await session.close()




async def check_mysql_connection() -> bool:
    """检查当前数据库连接"""
    try:
        async with async_engine.connect() as conn:
            # 执行简单查询
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"MySQL连接失败: {e}")
        return False
