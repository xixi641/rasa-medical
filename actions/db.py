import os
import json
import subprocess
from openai import OpenAI
from neo4j import GraphDatabase
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

tag = {
    "error": "\033[1;31m[ERROR]\033[0m",
    "success": "\033[1;32m[SUCCESS]\033[0m",
    "processing": "\033[1;34m[PROCESSING]\033[0m",
}

MYSQL_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "123456",
    "database": "medical",
    "charset": "utf8mb4",
}
mysql_url = f"mysql+pymysql://{MYSQL_CONFIG['user']}:{MYSQL_CONFIG['password']}@{MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}/{MYSQL_CONFIG['database']}?charset=utf8"


def create_orm(output_path):
    """将表映射为 Python 类"""
    print(f"{tag['processing']} 生成数据库表映射")
    cmd = ["python", "-m", "sqlacodegen", mysql_url]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"{tag['error']} {result.stderr}")
        return
    with open(output_path, "w", encoding="utf-8") as ofile:
        ofile.write(result.stdout)
    print(f"{tag['success']} 数据库表映射已保存到 {output_path}")


# 保存到该文件同级目录下
orm_path = os.path.join(os.path.dirname(__file__), "orm.py")
if not os.path.exists(orm_path):
    create_orm(orm_path)

# 配置 MySQL 会话工厂
engine = create_engine(mysql_url)
mysql_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# 配置 Neo4j 驱动
NEO4J_URL = "neo4j://127.0.0.1"
NEO4J_AUTH = ("neo4j", "12345678")
neo4j_driver = GraphDatabase.driver(NEO4J_URL, auth=NEO4J_AUTH)

# # 连接嵌入模型
# embed_model = OpenAI(
#     api_key="what",
#     base_url="http://localhost:10010",
# )

# 连接语言模型
llm_model = OpenAI(
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=os.getenv("TONGYI_API_KEY"),
)


def process_feedback(feedback_content):
    model = "qwen3.6-flash-2026-04-16"
    messages = [
        {
            "role": "system",
            "content": '你是一名处理用户反馈的客服，需要将用户反馈内容分类为“建议”或“系统故障”，并为反馈生成摘要。输出结果格式为json，比如：{"type":"建议","title":"..."}',
        },
        {"role": "user", "content": feedback_content},
    ]
    response = llm_model.chat.completions.create(model=model, messages=messages)
    response_dict = json.loads(response.choices[0].message.content)
    return response_dict
