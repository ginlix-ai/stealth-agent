import os
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

def upload_and_cleanup_charts_by_prefix(chart_save_dir: str, file_prefix: str) -> List[str]:
    """
    根据文件前缀上传图表目录中的图片到OSS并删除本地文件
    
    Args:
        chart_save_dir: 图表保存目录
        file_prefix: 文件前缀，如 "a1b2c3d4"
        
    Returns:
        List[str]: 成功上传的OSS文件URLs列表
    """
    try:
        from src.utils.storage.oss import upload_file
        OSS_AVAILABLE = True
    except ImportError:
        logger.warning("无法导入 OSS 上传功能，跳过图片上传")
        return []
    
    if not os.path.exists(chart_save_dir):
        logger.debug(f"图表目录不存在: {chart_save_dir}")
        return []
    
    # 支持的图片格式
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp'}
    uploaded_urls = []
    
    try:
        # 遍历目录中的所有文件，查找匹配前缀的文件
        chart_dir = Path(chart_save_dir)
        for file_path in chart_dir.iterdir():
            if (file_path.is_file() and 
                file_path.suffix.lower() in image_extensions and
                file_path.name.startswith(file_prefix)):
                
                try:
                    # 构造OSS文件名
                    original_filename = file_path.name
                    oss_filename = f"financial_charts/{original_filename}"
                    
                    logger.debug(f"正在上传图片: {original_filename} -> {oss_filename}")
                    
                    # 上传到OSS
                    upload_file(oss_filename, str(file_path))
                    
                    # 构造OSS访问URL
                    oss_url = f"https://gilin-data.oss-cn-beijing.aliyuncs.com/{oss_filename}"
                    uploaded_urls.append(oss_url)
                    
                    # 删除本地文件
                    file_path.unlink()
                    logger.debug(f"图片上传成功并删除本地文件: {original_filename}")
                    
                except Exception as e:
                    logger.error(f"处理图片文件失败 {file_path.name}: {str(e)}")
                    continue
                    
    except Exception as e:
        logger.error(f"遍历图表目录失败: {str(e)}")
        return uploaded_urls
    
    if uploaded_urls:
        logger.debug(f"成功上传 {len(uploaded_urls)} 张图片到OSS")
    else:
        logger.debug(f"没有找到前缀为 '{file_prefix}' 的图片文件")
    
    return uploaded_urls


def upload_and_cleanup_charts(chart_save_dir: str = "src/tools/temp_data") -> List[str]:
    """
    上传图表目录中的所有图片到OSS并删除本地文件（保留原函数兼容性）
    
    Args:
        chart_save_dir: 图表保存目录，默认为 "src/tools/temp_data"
        
    Returns:
        List[str]: 成功上传的OSS文件URLs列表
    """
    try:
        from src.utils.storage.oss import upload_file
        OSS_AVAILABLE = True
    except ImportError:
        logger.warning("无法导入 OSS 上传功能，跳过图片上传")
        return []
    
    if not os.path.exists(chart_save_dir):
        logger.debug(f"图表目录不存在: {chart_save_dir}")
        return []
    
    # 支持的图片格式
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp'}
    uploaded_urls = []
    
    try:
        # 遍历目录中的所有文件
        chart_dir = Path(chart_save_dir)
        for file_path in chart_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                try:
                    # 构造OSS文件名
                    original_filename = file_path.name
                    oss_filename = f"financial_charts/{original_filename}"
                    
                    logger.debug(f"正在上传图片: {original_filename} -> {oss_filename}")
                    
                    # 上传到OSS
                    upload_file(oss_filename, str(file_path))
                    
                    # 构造OSS访问URL
                    oss_url = f"https://gilin-data.oss-cn-beijing.aliyuncs.com/{oss_filename}"
                    uploaded_urls.append(oss_url)
                    
                    # 删除本地文件
                    file_path.unlink()
                    logger.debug(f"图片上传成功并删除本地文件: {original_filename}")
                    
                except Exception as e:
                    logger.error(f"处理图片文件失败 {file_path.name}: {str(e)}")
                    continue
                    
    except Exception as e:
        logger.error(f"遍历图表目录失败: {str(e)}")
        return uploaded_urls
    
    if uploaded_urls:
        logger.debug(f"成功上传 {len(uploaded_urls)} 张图片到OSS")
    else:
        logger.debug("没有找到需要上传的图片文件")
    
    return uploaded_urls


if __name__ == "__main__":
    # 测试函数
    print("测试图表上传功能...")
    
    # 测试前缀匹配上传
    urls = upload_and_cleanup_charts_by_prefix("src/tools/temp_data", "a1b2c3d4")
    print(f"前缀匹配上传结果: {urls}")
    
    # 测试批量上传
    urls = upload_and_cleanup_charts("src/tools/temp_data")
    print(f"批量上传结果: {urls}")