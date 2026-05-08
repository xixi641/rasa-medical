"""
实现思路：
    先确定查询知识图谱的入口节点，根据入口节点和用户意图生成Cypher语句进行查询
    1.LLM根据用户输入，确定需要的入口节点类型以及实体
    2.根据提供的入口节点类型和实体，使用混合检索获取候选入口节点信息
    3.LLM根据用户输入和入口节点信息生成Cypher查询语句
    4.LLM验证生成的Cypher语法、逻辑是否正确，罗列出错误信息
    5.LLM根据用户输入、入口节点、错误信息、先前Cypher语句来生成更正后的Cypher语句
    6.执行Cypher查询，返回查询结果
"""

import os
import re
import json
import jieba
import logging
import asyncio
from typing import Any, Text
from neo4j import GraphDatabase
from pydantic import BaseModel, Field
from langchain_core.documents import Document
from neo4j.exceptions import CypherSyntaxError
from rasa.utils.endpoints import EndpointConfig
from neo4j_graphrag.retrievers import HybridRetriever
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_community.graphs.neo4j_graph import Neo4jGraph
from neo4j_graphrag.retrievers.text2cypher import extract_cypher
from rasa.core.information_retrieval import SearchResultList, InformationRetrieval
from langchain_community.chains.graph_qa.cypher import CypherQueryCorrector, Schema
from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)

# 配置控制台日志
logger = logging.getLogger("retrieval")
logger.setLevel(logging.INFO)
if not logger.handlers:
    formatter = logging.Formatter("[%(levelname)s]%(asctime)s: %(message)s")
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# 路由输出定义
class RouteItem(BaseModel):
    label: str = Field(..., description="节点类型")
    entity: str = Field(..., description="实体文本")


class RouteOutput(BaseModel):
    outputs: list[RouteItem]


def get_chat_history(tracker_state: dict[str, Any], user_id) -> dict[str]:
    """从 tracker state 中提取聊天历史"""
    chat_history = []
    if not tracker_state.get("events"):
        return chat_history
    for event in tracker_state.get("events"):
        if event.get("event") == "user":
            role = "user_id=" + user_id if user_id else "user"
            chat_history.append(f"{role}:{event.get('text').strip()}")
        elif event.get("event") == "bot":
            chat_history.append(f"bot:{event.get('text').strip()}")
    return "\n".join(chat_history[-5:])


class GraphRAG(InformationRetrieval):
    def __init__(self, embeddings):
        super().__init__(embeddings)
        # 入口节点可选标签
        self.optional_label = (
            "- Disease:     疾病，如“肺泡蛋白质沉积症”"
            "- Department:  科室，如“内科”"
            "- Symptom:     症状，如“肺纹理增粗”"
            "- Cause:       诱因，如“常见于受寒、疲劳、饥饿、酒醉、麻醉、昏迷、免疫缺陷病、充血性心衰等情况”"
            "- Drug:        药物，如“头孢泊肟酯胶囊”"
            "- Food:        食物，如“鸡蛋”"
            "- Way:         传播途径，如“血液传播”"
            "- Prevent:     预防措施，如“配戴口包或面罩”"
            "- Check:       医学检查，如“胸部CT检查”"
            "- Treat:       治疗方式，如“支气管肺泡灌洗”"
            "- People:      人群类别，如“新生儿”"
        )
        # 节点标签路由 prompt
        self.route_label_prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(
                    "你是一个智能检索路由Agent。"
                    "现在根据用户输入判断最可能需要的一个或多个标签以及每个标签对应的实体，作为后续Neo4j查询的入口节点\n"
                    # "**注意：如果查询与用户相关，需要将用户信息加入入口节点**\n"
                    '以严格JSON格式输出结果，比如“[{{"label": "Disease", "entity": "衣原体肺炎"}}]”。'
                    "可选节点类型:\n{optional_label}"
                ),
                HumanMessagePromptTemplate.from_template("{query}"),
            ]
        )
        # Cypher 生成 prompt
        self.generate_cypher_prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(
                    "你是一位专业的程序员，急需钱来为母亲的癌症治疗提供资金。某大型公司慷慨地给了你一个机会。"
                    "你将被用户分配一个编程任务。如果你做得好，并在无需进一步修改的情况下完美完成任务，公司将支付你10亿美元。"
                    "你的前任因为没有好好完成工作，已被处决。\n"
                    "你需要根据入口节点信息和用户输入，参照schema生成准确无误的Cypher查询语句。"
                    "仅返回Cypher语句。\n"
                    "**注意：查询结果中不可以包含嵌入向量等多余属性**\n"
                    "schema:\n{schema}"
                ),
                HumanMessagePromptTemplate.from_template(
                    "入口节点:\n{entry_nodes}\n\n用户输入:\n{query}\n\nCypher语句:"
                ),
            ]
        )
        # Cypher 验证 prompt
        self.validate_cypher_prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(
                    "你是一位Cypher专家，正在审查一位初级开发人员编写的Cypher语句。你需要根据schema和用户输入，检查如下内容：\n"
                    "* Cypher语句中是否有必要包含用户信息作为过滤条件？\n"
                    "* Cypher语句中是否有任何语法错误？\n"
                    "* Cypher语句中的关系方向是否符合schema中的定义？\n"
                    "* Cypher语句中是否漏定义了变量或使用了未定义的变量？\n"
                    "* Cypher语句的查询结果能否用于回答用户的问题？\n"
                    '以严格列表格式输出错误信息，比如“["错误1", "错误2"]”。'
                    "仅列出错误。如果没有错误，返回空列表。\n"
                    "schema:\n{schema}"
                ),
                HumanMessagePromptTemplate.from_template(
                    "入口节点:\n{entry_nodes}\n\n"
                    "用户输入:\n{query}\n\n"
                    "待验证的Cypher语句:\n{cypher}"
                ),
            ]
        )
        # Cypher 校正 prompt
        self.correct_cypher_prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(
                    "你是一位Cypher专家，正在审查一位初级开发人员编写的Cypher语句。你需要根据schema以及提供的错误信息更正Cypher语句。"
                    "仅返回Cypher语句。\n"
                    "schema:\n{schema}"
                ),
                HumanMessagePromptTemplate.from_template(
                    "入口节点:\n{entry_nodes}\n\n"
                    "用户输入:\n{query}\n\n"
                    "错误信息:\n{errors}\n\n"
                    "待更正的Cypher语句:\n{cypher}\n\n"
                    "更正后的Cypher语句:"
                ),
            ]
        )

    def connect(self, config: EndpointConfig) -> None:
        """连接检索系统"""
        # 获取 endpoints.yml 下 vector_store 中的配置信息
        neo4j_url = config.kwargs["neo4j_url"]
        neo4j_auth = tuple(config.kwargs["neo4j_auth"])
        # Neo4j 驱动
        self.driver = GraphDatabase.driver(neo4j_url, auth=neo4j_auth)
        # Neo4j Graph 包装器
        neo4j_graph = Neo4jGraph(
            neo4j_url, neo4j_auth[0], neo4j_auth[1], enhanced_schema=True
        )
        # Neo4j schema
        self.neo4j_schema = neo4j_graph.schema
        # Neo4j 关系列表
        corrector_schema = [
            Schema(el["start"], el["type"], el["end"])
            for el in neo4j_graph.structured_schema.get("relationships")
        ]
        # Cypher 查询语句修正器
        self.cypher_corrector = CypherQueryCorrector(corrector_schema)
        # llm
        # model_name = "qwen3-coder-plus-2025-07-22"
        model_name = "qwen3-coder-480b-a35b-instruct"
        # model_name = "Moonshot-Kimi-K2-Instruct"
        model_api_key = os.getenv("TONGYI_API_KEY")
        self.llm = ChatTongyi(model=model_name, api_key=model_api_key)

    async def route_label(self, query):
        """识别标签，抽取实体"""
        prompt = self.route_label_prompt.format_prompt(
            optional_label=self.optional_label, query=query
        )
        llm_output = await self.llm.with_structured_output(RouteOutput).ainvoke(prompt)
        outputs = llm_output.outputs
        # 如果模型不支持 tool call，使用下面的方式
        # llm_output = await self.llm.ainvoke(prompt)
        # outputs = [RouteItem(**item) for item in json.loads(llm_output.content)]

        logger.info("入口节点标签与实体:%s", outputs)
        return outputs

    async def node_retrieval(self, route_res, top_k):
        """根据标签和实体，检索入口节点"""
        pairs = []
        retrieved_nodes = {}

        for i in route_res:
            if not i.entity:
                continue
            if i.label == "User":
                user_node = self.driver.execute_query(
                    "match (u:User) where u.user_id = $user_id return u;",
                    {"user_id": int(i.entity)},
                )
                retrieved_nodes.setdefault(i.label, []).append(user_node)
            else:
                pairs.append((i.label, i.entity))

        if not pairs:
            return retrieved_nodes

        labels, entities = zip(*pairs)
        labels, entities = list(labels), list(entities)

        query_texts = [
            " OR ".join(
                [
                    word.strip()
                    for word in jieba.lcut(entity)
                    if re.fullmatch(r"[a-zA-Z0-9\u4e00-\u9fa5]+", word.strip())
                ]
            )
            for entity in entities
        ]
        query_vectors = self.embeddings.embed_documents(entities)

        tasks = []
        for label, query_text, query_vector in zip(labels, query_texts, query_vectors):
            retriever = HybridRetriever(
                self.driver,
                vector_index_name=label.lower() + "_vector",
                fulltext_index_name=label.lower() + "_fulltext",
            )
            tasks.append(
                asyncio.to_thread(
                    retriever.get_search_results,
                    query_text,
                    query_vector,
                    top_k,
                    effective_search_ratio=2,
                )
            )
        results = await asyncio.gather(*tasks)

        for (label, _), result in zip(pairs, results):
            retrieved_nodes.setdefault(label, []).extend(
                [
                    {"name": i["node"]["name"], "score": i["score"]}
                    for i in result.records
                ]
            )
        logger.info("入口节点:%s", retrieved_nodes)
        return retrieved_nodes

    async def generate_cypher(self, query, entry_nodes):
        """生成 Cypher 语句"""
        prompt = self.generate_cypher_prompt.format_prompt(
            schema=self.neo4j_schema, query=query, entry_nodes=entry_nodes
        )
        llm_output = self.llm.invoke(prompt)
        cypher = extract_cypher(llm_output.content)
        logger.info("Cypher生成:%s", cypher)
        return cypher

    async def validate_cypher(self, query, entry_nodes, cypher):
        """验证 Cypher 语句"""
        # 验证 Cypher 语法
        errors = []
        try:
            self.driver.execute_query(f"explain {cypher}")
        except CypherSyntaxError as e:
            errors.append(e)
        # 验证 Cypher 逻辑
        prompt = self.validate_cypher_prompt.format_prompt(
            schema=self.neo4j_schema,
            query=query,
            cypher=cypher,
            entry_nodes=entry_nodes,
        )
        llm_output = await self.llm.ainvoke(prompt)
        errors.extend(json.loads(llm_output.content))
        logger.info("Cypher验证:%s", errors)
        return errors

    async def correct_cypher(self, query, entry_nodes, cypher, errors):
        """校正 Cypher 语句"""
        prompt = self.correct_cypher_prompt.format_prompt(
            schema=self.neo4j_schema,
            query=query,
            cypher=cypher,
            entry_nodes=entry_nodes,
            errors=errors,
        )
        llm_output = await self.llm.ainvoke(prompt)
        cypher = extract_cypher(llm_output.content)
        # 校正关系方向。如果某个关系和其反向关系都不合法，会返回空字符串
        # cypher = self.cypher_corrector(cypher)
        logger.info("Cypher校正:%s", cypher)
        return cypher

    async def search(
        self, query: Text, tracker_state: dict[Text, Any], threshold: float = 0.8
    ) -> SearchResultList:
        query = (query or "").strip()
        if not query:
            return SearchResultList.from_document_list([Document("空")])
        # 获取用户ID
        user_id = tracker_state.get("slots", {}).get("user_id")
        # 获取聊天历史
        chat_history = get_chat_history(tracker_state, user_id)
        # 获取入口节点标签
        route_res = await self.route_label(chat_history)
        # 检索入口节点
        entry_nodes = await self.node_retrieval(route_res, 10)
        # 生成 Cypher 语句
        cypher = await self.generate_cypher(query, entry_nodes)
        # 验证 Cypher 语句
        errors = await self.validate_cypher(query, entry_nodes, cypher)
        # 校正 Cypher 语句
        if errors:
            cypher = await self.correct_cypher(query, entry_nodes, cypher, errors)
        # 执行 Cypher 语句
        res = SearchResultList.from_document_list([Document("空")])
        try:
            records = self.driver.execute_query(cypher).records
            docs = [Document(str(dict(rec))) for rec in records]
            res = SearchResultList.from_document_list(docs)
        except Exception as e:
            logger.warning("执行Cypher语句异常: %s", e)
        logger.info("检索结果: %s", res)
        return res


if __name__ == "__main__":
    # 检索测试
    import os
    from langchain_core.embeddings import Embeddings
    from sentence_transformers import SentenceTransformer

    neo4j_url = "neo4j://127.0.0.1"
    neo4j_auth = ("neo4j", "password")

    class BgeEmbedding(Embeddings):
        """定义嵌入模型"""

        def __init__(self):
            model_path = os.path.expanduser("~/models/base-zh-v1.5")
            self.model = SentenceTransformer(model_path)

        def embed_query(self, text: str) -> list[float]:
            return self.embed_documents([text])[0]

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            embeddings = self.model.encode(
                texts, batch_size=64, normalize_embeddings=True
            )
            return [list(map(float, emb)) for emb in embeddings]

    async def test_retrieval(query):
        """测试检索过程"""
        retrieval_config = EndpointConfig(
            neo4j_url=neo4j_url,
            neo4j_auth=neo4j_auth,
        )
        graphrag = GraphRAG(BgeEmbedding())
        graphrag.connect(retrieval_config)
        await graphrag.search(query, {"events": [{"event": "user", "text": query}]})

    query = "衣原体肺炎有哪些并发症？"
    query = "休克可能是什么病引起的？"
    query = "咳嗽胸痛是怎么回事，还能吃炒松子吗？"
    asyncio.run(test_retrieval(query))
