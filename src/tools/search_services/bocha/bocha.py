import logging
import httpx
import json
import os
import time
from typing import Dict, Any, Tuple, List, Optional

# 获取 logger 实例
logger = logging.getLogger(__name__)

class BochaAPI:
    """豆包(Bocha) API封装类，提供网页搜索等功能"""

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化豆包(Bocha) API客户端
        从环境变量 BOCHA_API_KEY 读取 API Key，如果未设置则使用默认值。
        Args:
            api_key: 可选，直接提供 API Key
        """
        self.api_key = api_key or os.getenv('BOCHA_API_KEY', 'sk-c4a28d458ff54b5f9ff1a467d4fe9314')
        self.base_url = "https://api.bochaai.com/v1"
        # Updated to use AI search endpoint
        self.ai_search_endpoint = f"{self.base_url}/ai-search"
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        self.stats = {
            "total_searches": 0,
            "successful_searches": 0,
            "total_results": 0
        }

        logger.debug("Bocha API 客户端初始化完成 (使用 AI Search 端点)。")
    
    async def _make_request(self, query: str, count: int = 10, freshness: Optional[str] = None, answer: bool = False) -> dict:
        """
        发送 AI Search 请求到 Bocha API (POST)

        Args:
            query: 搜索查询
            count: 返回结果数量
            freshness: 时间范围过滤参数
            answer: 是否请求LLM生成的答案 (默认 False)

        Returns:
            API响应的JSON字典
        """
        payload_dict = {
            "query": query,
            "count": count,
            "answer": answer,  # AI Search endpoint parameter
            "stream": False    # AI Search endpoint parameter
        }

        # Add freshness parameter if provided and not "noLimit"
        if freshness and freshness != "noLimit":
            payload_dict["freshness"] = freshness

        payload = json.dumps(payload_dict)

        logger.debug(f"Bocha AI Search POST 请求 URL: {self.ai_search_endpoint}")
        logger.debug(f"Bocha AI Search POST 请求体: {payload}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.ai_search_endpoint, headers=self.headers, data=payload)
            response.raise_for_status()
            json_response = response.json()

            if json_response.get("code") != 200:
                error_msg = f"Bocha API 返回业务错误: Code={json_response.get('code')}, Msg={json_response.get('msg')}"
                logger.error(error_msg)
                return {"error": error_msg}

            logger.debug("Bocha AI Search 请求成功。")
            return json_response

        except httpx.HTTPStatusError as e:
            logger.error(f"Bocha API HTTP 错误: {e.response.status_code} - {e.response.text}", exc_info=True)
            return {"error": f"HTTP error {e.response.status_code}: {e.response.text}"}
        except httpx.TimeoutException as e:
            logger.error(f"Bocha API 请求超时: {e}", exc_info=True)
            return {"error": f"请求超时: {e}"}
        except httpx.RequestError as e:
            logger.error(f"Bocha API 请求失败: {e}", exc_info=True)
            return {"error": str(e)}
        except json.JSONDecodeError as e:
            logger.error(f"解析 Bocha API 响应 JSON 失败: {e}", exc_info=True)
            return {"error": f"无法解析 API 响应: {e}"}

    async def web_search(self, query: str, count: int = 10, freshness: Optional[str] = None, answer: bool = False) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        执行 AI Search 并返回详细结果 (用于 artifact 支持)。

        Args:
            query: 搜索查询
            count: 返回结果数量
            freshness: 时间范围过滤参数
                - "noLimit": 不限制时间（默认）
                - "oneDay": 一天内
                - "oneWeek": 一周内
                - "oneMonth": 一个月内
                - "oneYear": 一年内
                - "YYYY-MM-DD..YYYY-MM-DD": 日期范围
                - "YYYY-MM-DD": 指定日期
            answer: 是否请求LLM生成的答案 (默认 False)

        Returns:
            Tuple[List[Dict[str, Any]], Dict[str, Any]]:
            - 第一个元素: 详细结果列表，包含所有字段 (用于构建 content 和 artifact)
            - 第二个元素: 原始响应元数据 (query, response_time, conversation_id 等)
        """
        self.stats["total_searches"] += 1
        logger.info(f"执行 Bocha AI 搜索: {query[:50]}... (freshness={freshness}, answer={answer})")

        # Track response time
        start_time = time.time()
        data = await self._make_request(query, count, freshness, answer)
        response_time = time.time() - start_time

        detailed_results_list = []
        image_results_list = []

        if "error" in data:
            logger.warning(f"Bocha AI 搜索返回错误: {data['error']}")
            return detailed_results_list, {
                "query": query,
                "response_time": response_time,
                "error": data["error"]
            }

        try:
            messages = data.get("messages", [])

            # Parse webpage results from messages[0]
            webpage_msg = next((m for m in messages if m.get("content_type") == "webpage"), None)
            if webpage_msg:
                webpage_content = json.loads(webpage_msg["content"])
                results = webpage_content.get("value", [])

                for item in results:
                    detailed_results_list.append({
                        "type": "webpage",
                        "title": item.get('name', ''),
                        "url": item.get('url', ''),
                        "summary": item.get('summary', ''),
                        "snippet": item.get('snippet', ''),
                        "site_name": item.get('siteName', ''),
                        "site_icon": item.get('siteIcon', ''),
                        "publish_time": item.get('datePublished', ''),
                        "id": item.get('id', '')
                    })

            # Parse image results from messages[1]
            image_msg = next((m for m in messages if m.get("content_type") == "image"), None)
            if image_msg:
                try:
                    image_content = json.loads(image_msg["content"])
                    images = image_content.get("value", [])

                    for img in images:
                        image_results_list.append({
                            "type": "image",
                            "content_url": img.get('contentUrl', ''),
                            "thumbnail_url": img.get('thumbnailUrl', ''),
                            "host_page_url": img.get('hostPageUrl', ''),
                            "host_page_display_url": img.get('hostPageDisplayUrl', ''),
                            "width": img.get('width', 0),
                            "height": img.get('height', 0)
                        })
                except (json.JSONDecodeError, KeyError) as e:
                    logger.debug(f"解析图片结果失败: {e}")

            # Combine webpage and image results
            all_results = detailed_results_list + image_results_list

            result_count = len(all_results)
            self.stats["total_results"] += result_count
            if result_count > 0:
                self.stats["successful_searches"] += 1
            logger.info(f"Bocha AI 搜索成功，返回 {len(detailed_results_list)} 个网页和 {len(image_results_list)} 张图片。")

            # Return results and metadata
            metadata = {
                "query": query,
                "response_time": round(response_time, 2),
                "total_results": result_count,
                "conversation_id": data.get("conversation_id", ""),
                "log_id": data.get("log_id", "")
            }

            return all_results, metadata

        except (AttributeError, KeyError, json.JSONDecodeError) as e:
             logger.error(f"解析 Bocha AI Search 响应结构时出错: {e}", exc_info=True)
             logger.debug(f"原始 messages 字段: {data.get('messages')}")
             return detailed_results_list, {
                 "query": query,
                 "response_time": response_time,
                 "error": str(e)
             }
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取API调用统计信息
        
        Returns:
            包含调用统计的字典
        """
        success_rate = (self.stats["successful_searches"] / self.stats["total_searches"] * 100) if self.stats["total_searches"] > 0 else 0
        
        return {
            "total_searches": self.stats["total_searches"],
            "successful_searches": self.stats["successful_searches"],
            "total_results": self.stats["total_results"],
            "success_rate": f"{success_rate:.2f}%"
        }
    
    def reset_stats(self) -> None:
        """重置统计信息"""
        self.stats = {
            "total_searches": 0,
            "successful_searches": 0,
            "total_results": 0
        }

if __name__ == "__main__":
    # 异步函数需要在一个事件循环中运行
    import asyncio
    async def main():
        bocha = BochaAPI()
        # web_search 现在返回一个元组 (results_list, metadata)
        results, metadata = await bocha.web_search("特斯拉最新股价", count=3)
        print("--- Results (包含网页和图片) ---")
        for i, result in enumerate(results):
            print(f"\n[{i+1}] Type: {result.get('type')}")
            if result.get('type') == 'webpage':
                print(f"    Title: {result.get('title')}")
                print(f"    URL: {result.get('url')}")
                print(f"    Site: {result.get('site_name')}")
                print(f"    Summary: {result.get('summary')[:100]}...")
            elif result.get('type') == 'image':
                print(f"    Image URL: {result.get('content_url')}")
                print(f"    Source: {result.get('host_page_url')}")

        print("\n--- Metadata ---")
        print(json.dumps(metadata, indent=2, ensure_ascii=False))

        print("\n--- Stats ---")
        print(bocha.get_stats())

    asyncio.run(main())
    
    