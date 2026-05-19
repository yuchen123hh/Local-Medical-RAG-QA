from typing import List, Dict, Any
import torch
import os
import re
from dotenv import load_dotenv
from sentence_transformers import CrossEncoder
from modelscope import snapshot_download
from tqdm import tqdm
from app.core.logger_handler import logger

# 加载环境变量
load_dotenv()


def find_model_path(base_path: str) -> str:
    if os.path.exists(os.path.join(base_path, 'config.json')):
        return base_path
    
    for root, dirs, files in os.walk(base_path):
        if 'config.json' in files:
            return root
    
    logger.info(f"✅ 模型路径：{base_path}")
    return base_path


def check_and_download_reranker_model() -> None:
    """检查并重排序模型，在FastAPI启动时执行"""
    LOCAL_MODEL_PATH = os.getenv("RERANKER_MODEL_PATH", r"D:\Hugging_Face\models\Qwen3-Reranker-0.6B")
    MODELSCOPE_MODEL_NAME = "Qwen/Qwen3-Reranker-0.6B"

    try:
        if os.path.exists(LOCAL_MODEL_PATH) and os.path.isdir(LOCAL_MODEL_PATH):
            logger.info(f"✅ 检测到本地重排序模型：{LOCAL_MODEL_PATH}")
        else:
            logger.warning(f"⚠️  本地模型未找到：{LOCAL_MODEL_PATH}")
            logger.info(f"🔄 开始从魔搭社区下载模型：{MODELSCOPE_MODEL_NAME}")

            os.makedirs(LOCAL_MODEL_PATH, exist_ok=True)

            with tqdm(total=100, desc='下载模型', leave=True, bar_format='{l_bar}{bar}| {n_fmt}%') as pbar:
                pbar.update(10)
                snapshot_download(
                    model_id=MODELSCOPE_MODEL_NAME,
                    cache_dir=LOCAL_MODEL_PATH,
                    revision='master'
                )
                pbar.update(90)

            logger.info(f"✅ 模型下载完成，保存路径：{LOCAL_MODEL_PATH}")

    except Exception as e:
        logger.error(f"❌ 模型检查失败: {str(e)}")
        raise RuntimeError(f"重排序模型检查失败: {str(e)}")


class ReorderService:
    """文档重排序服务"""
    
    def __init__(self):
        self.LOCAL_MODEL_PATH = os.getenv("RERANKER_MODEL_PATH", r"D:\Hugging_Face\models\Qwen3-Reranker-0.6B")
        self.MODELSCOPE_MODEL_NAME = "Qwen/Qwen3-Reranker-0.6B"
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = None

    @staticmethod
    def _env_enabled(name: str) -> bool:
        return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _extract_query_terms(query: str) -> list[str]:
        terms = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,12}", query or "")
        for size in (4, 3, 2):
            terms.extend(
                query[index:index + size]
                for index in range(0, max(len(query) - size + 1, 0))
                if re.search(r"[\u4e00-\u9fff]", query[index:index + size])
            )

        stopwords = {
            "患者", "应该", "怎么", "如何", "判断", "处理", "治疗", "诊疗", "建议",
            "需要", "是否", "可以", "可能", "什么", "方法",
        }
        cleaned = []
        for term in terms:
            term = term.strip()
            if len(term) < 2 or term in stopwords:
                continue
            if term not in cleaned:
                cleaned.append(term)
        return cleaned[:40]

    def _fallback_reorder(self, query: str, documents: List[str]) -> Dict[str, Any]:
        terms = self._extract_query_terms(query)
        scored_documents = []
        for index, doc in enumerate(documents):
            score = 0.0
            first_line = doc.splitlines()[0] if doc else ""
            for term in terms:
                occurrences = doc.count(term)
                if occurrences:
                    score += min(occurrences * 0.04, 0.2)
                if term in first_line:
                    score += 0.1

            # 保持原始检索顺序的轻微优势，避免同分时顺序抖动。
            score += max(0, len(documents) - index) * 0.0001
            scored_documents.append({
                "document": doc,
                "similarity": min(score, 1.0),
            })

        return {
            "success": True,
            "documents": sorted(scored_documents, key=lambda item: item["similarity"], reverse=True),
            "error": "",
            "fallback": True,
        }
    
    async def _get_model(self):
        """懒加载模型实例"""
        if self._model is None:
            actual_model_path = find_model_path(self.LOCAL_MODEL_PATH)
            if not os.path.exists(actual_model_path):
                raise FileNotFoundError(f"本地重排序模型不存在: {actual_model_path}")

            logger.info(f"✅ 加载重排序模型：{actual_model_path}")
            self._model = CrossEncoder(
                actual_model_path,
                max_length=512,
                device=self.device,
                local_files_only=True
            )
            self._model.eval()
            logger.info(f"✅ 模型加载成功，使用设备：{self.device}")
        return self._model
    
    @property
    async def model(self):
        """获取模型实例（懒加载）"""
        return await self._get_model()
    
    async def reorder_documents(self, query: str, documents: List[str], thinking_callback=None) -> Dict[str, Any]:
        """
        对文档进行重排序
        :param query: 查询语句
        :param documents: 文档列表
        :param thinking_callback: 思考过程回调函数
        :return: 包含重排序结果的字典，格式为：
                 {"success": bool, "documents": List[Dict], "error": str}
        """
        try:
            if not documents:
                return {
                    "success": True,
                    "documents": [],
                    "error": ""
                }

            if self._env_enabled("SKIP_RERANKER_MODEL_CHECK") and not os.path.exists(self.LOCAL_MODEL_PATH):
                logger.info("【重排序服务】未检测到本地重排序模型，使用轻量关键词排序降级")
                result = self._fallback_reorder(query, documents)
                if thinking_callback:
                    await thinking_callback({
                        "type": "thinking",
                        "stage": "reorder",
                        "content": f"本地重排序模型未配置，已使用关键词相关性完成 {len(documents)} 个文档排序",
                        "details": {
                            "scores": [
                                {
                                    "index": i,
                                    "score": round(doc.get("similarity", 0), 4),
                                    "preview": doc.get("document", "")[:100] + "..." if len(doc.get("document", "")) > 100 else doc.get("document", "")
                                }
                                for i, doc in enumerate(result["documents"], 1)
                            ]
                        }
                    })
                return result
            
            if thinking_callback:
                await thinking_callback({
                    "type": "thinking",
                    "stage": "reorder",
                    "content": f"正在计算 {len(documents)} 个文档的相关性分数..."
                })
            
            # 构造查询+文档对
            pairs = [(query, doc) for doc in documents]
            
            # 使用模型进行批量预测（batch_size=1避免padding令牌报错）
            model = await self.model
            # 禁用梯度计算，提高推理性能
            with torch.no_grad():
                scores = model.predict(pairs, batch_size=1)
            
            # 构建结果列表
            scored_documents = []
            for doc, score in zip(documents, scores):
                scored_documents.append({
                    "document": doc,
                    "similarity": float(score)
                })
                logger.info(f"【重排序服务】文档相似度分数: {score:.4f}")
            
            if thinking_callback:
                score_details = []
                for i, (doc, score) in enumerate(zip(documents, scores), 1):
                    score_details.append({
                        "index": i,
                        "score": round(float(score), 4),
                        "preview": doc[:100] + "..." if len(doc) > 100 else doc
                    })
                await thinking_callback({
                    "type": "thinking",
                    "stage": "reorder",
                    "content": f"已计算完成 {len(documents)} 个文档的相关性分数，按分数降序排序",
                    "details": {
                        "scores": score_details
                    }
                })
            
            # 按相似度分数降序排序
            sorted_docs = sorted(scored_documents, key=lambda x: x["similarity"], reverse=True)
            logger.info(f"【重排序服务】文档重排序成功，返回 {len(sorted_docs)} 个文档")
            
            return {
                "success": True,
                "documents": sorted_docs,
                "error": ""
            }
        except Exception as e:
            error_msg = str(e)
            logger.error(f"【重排序服务】重排序失败: {error_msg}")
            return {
                "success": False,
                "documents": [],
                "error": error_msg
            }

    @staticmethod
    async def format_reorder_result(sorted_docs: List[Dict]) -> str:
        """
        格式化重排序结果
        :param sorted_docs: 重排序后的文档列表
        :return: 格式化后的字符串
        """
        formatted_result = "重排序后的文档列表：\n"
        for i, doc in enumerate(sorted_docs, 1):
            formatted_result += f"{i}. 相似度: {doc.get('similarity', 0):.4f}\n"
            formatted_result += f"   内容: {doc.get('document', '')}\n\n"
        return formatted_result


# 全局重排序服务实例
reorder_service = ReorderService()
