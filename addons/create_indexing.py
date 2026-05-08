import os
import re
import jieba
import logging
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
from neo4j_graphrag.indexes import (
    create_vector_index,
    upsert_vectors,
    create_fulltext_index,
)

# 配置控制台日志
logger = logging.getLogger("indexing")
logger.setLevel(logging.INFO)
if not logger.handlers:
    formatter = logging.Formatter("[%(levelname)s]%(asctime)s: %(message)s")
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

neo4j_url = "neo4j://127.0.0.1"
neo4j_auth = ("neo4j", "12345678")
vector_dim = 768
embed_batch_size = 64


def drop_index_without_constraint(driver):
    """删除所有没有约束的索引"""
    records = driver.execute_query("show index").records
    for record in records:
        if not record["owningConstraint"]:
            driver.execute_query(f"drop index {record['name']} if exists")


# --------- 创建向量索引 ---------
embed_model = SentenceTransformer(os.path.expanduser("~/models/base-zh-v1.5"))


def vector_indexing(driver, label, property="name"):
    """创建向量索引，并添加嵌入向量"""
    # 查询 embedding 为 null 的节点，获取 elementId 和 指定属性
    record_list = driver.execute_query(
        f"""match (n:{label}) where n.embedding is null
            return elementId(n) as id, n.{property} as text""",
    ).records
    record_tuple_list = [(r["id"], r["text"]) for r in record_list]
    if record_tuple_list:
        ids, texts = zip(*record_tuple_list)
        ids = list(ids)
        texts = list(texts)

        # 计算文本的嵌入向量
        logger.info(f"计算 {label} ({len(record_list)}) 的嵌入向量")
        embeddings = embed_model.encode(
            texts, batch_size=embed_batch_size, normalize_embeddings=True
        )

        # 按 elementId 添加嵌入向量属性
        logger.info(f"写入 {label} ({len(record_list)}) 的嵌入向量")
        upsert_vectors(
            driver,
            ids=ids,
            embedding_property="embedding",
            embeddings=embeddings,
        )
    else:
        logger.info(f"{label} 所有节点皆存在嵌入向量属性")

    # 创建向量索引
    create_vector_index(
        driver,
        name=f"{label.lower()}_vector",
        label=label,
        embedding_property="embedding",
        dimensions=vector_dim,
        similarity_fn="cosine",
    )


# --------- 创建全文索引 ---------
def fulltext_indexing(driver, label, property="name"):
    """创建全文索引，并添加节点属性"""
    # 查询 fulltext 为 null 的节点，获取 elementId 和 指定属性
    record_list = driver.execute_query(
        f"""match (n:{label}) where n.fulltext is null
            return elementId(n) as id, n.{property} as text""",
    ).records
    record_tuple_list = [(r["id"], r["text"]) for r in record_list]
    if record_tuple_list:
        # 文本分词，作为全文索引属性
        logger.info(f"计算 {label} ({len(record_list)}) 的全文索引")
        pattern = re.compile(r"[a-zA-Z0-9\u4e00-\u9fa5]+")
        ids, fulltexts = zip(
            *[
                (
                    id_,
                    " ".join(
                        [
                            word.strip()
                            for word in jieba.lcut(text)
                            if pattern.fullmatch(word.strip())
                        ]
                    ),
                )
                for id_, text in record_tuple_list
            ]
        )
        ids, fulltexts = list(ids), list(fulltexts)

        # 按 elementId 添加全文索引属性
        logger.info(f"写入 {label} ({len(fulltexts)}) 的全文索引")
        insert_batch_size = 1000
        for i in range(0, len(record_tuple_list), insert_batch_size):
            batch_rows = [
                {"id": id_, "fulltext": ft}
                for id_, ft in zip(
                    ids[i : i + insert_batch_size],
                    fulltexts[i : i + insert_batch_size],
                )
            ]
            driver.execute_query(
                "UNWIND $rows AS row "
                "MATCH (n) "
                "WHERE elementId(n) = row.id "
                "SET n.fulltext = row.fulltext ",
                {"rows": batch_rows},
            )
    else:
        logger.info(f"{label} 所有节点皆存在全文索引属性")

    # 创建全文索引
    create_fulltext_index(
        driver,
        name=f"{label.lower()}_fulltext",
        label=label,
        node_properties=["fulltext"],
    )


if __name__ == "__main__":
    with GraphDatabase.driver(neo4j_url, auth=neo4j_auth) as driver:
        # 清空所有没有约束的索引
        drop_index_without_constraint(driver)

        # 清空所有嵌入向量
        # driver.execute_query("match (n) remove n.embedding")
        # 创建向量索引
        vector_indexing(driver, "Disease")
        vector_indexing(driver, "Department")
        vector_indexing(driver, "Symptom")
        vector_indexing(driver, "Cause", "desc")
        vector_indexing(driver, "Drug")
        vector_indexing(driver, "Food")
        vector_indexing(driver, "Way")
        vector_indexing(driver, "Prevent", "desc")
        vector_indexing(driver, "Check")
        vector_indexing(driver, "Treat")
        vector_indexing(driver, "People")

        # 清空所有节点全文索引属性
        # driver.execute_query("match (n) remove n.fulltext")
        # 创建全文索引
        fulltext_indexing(driver, "Disease")
        fulltext_indexing(driver, "Department")
        fulltext_indexing(driver, "Symptom")
        fulltext_indexing(driver, "Cause", "desc")
        fulltext_indexing(driver, "Drug")
        fulltext_indexing(driver, "Food")
        fulltext_indexing(driver, "Way")
        fulltext_indexing(driver, "Prevent", "desc")
        fulltext_indexing(driver, "Check")
        fulltext_indexing(driver, "Treat")
        fulltext_indexing(driver, "People")
