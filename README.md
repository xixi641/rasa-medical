Rasa Medical AI 是一个基于 Rasa 框架与大语言模型（LLM）深度结合的医疗垂直领域智能对话问答系统。/d
本项目摒弃了传统的单一问答模式，采用了图检索增强生成（GraphRAG）与微服务解耦的架构设计，旨在模拟真实医疗场景下的智能分诊、疾病咨询、电子病历（EMR）查询与挂号预约服务。/d
项目不仅具备自然语言理解能力，还能通过底层的关系型与图数据库，精准映射复杂的医疗知识网络。
医疗知识图谱 (Neo4j + GraphRAG): 底层接入 Neo4j 图数据库，构建包含疾病、症状、药物等实体的医疗知识图谱。通过引入 GraphRAG 技术，使大模型在生成医学建议时能够基于真实的图谱关系进行推理

独立的向量化微服务 (Embedding Service): 为了提升系统性能与扩展性，项目将文本向量化（Embedding）功能单独抽离。通过运行在 10010 端口的独立服务处理高并发的向量计算请求，实现了计算密集型任务与对话业务逻辑的解耦。

真实医疗业务流接入 (MySQL + Action Server): 结合关系型数据库 MySQL，通过 Rasa 的自定义动作（Custom Actions: action_emr.py, action_appointment.py）打通了结构化医疗数据。机器人能够实时查询患者电子病历、处理挂号预约逻辑，完成闭环的医疗服务体验。


在运行项目之前，请确保已安装 Python 3.10 并在虚拟环境中安装以下核心依赖库，并且在.env输入千问apikey，rasa——pro密钥。
**data.py 中使用的依赖**
neo4j：Neo4j 图数据库驱动
neo4j-graphrag：Neo4j 图检索增强生成库（用于 HybridRetriever 等）
**大模型与向量嵌入**
openai：用于兼容 OpenAI 接口的 LLM 调用（项目中用于调用阿里云通义千问）
langchain 和 langchain-community：用于构建 LLM 应用、Prompt 管理、ChatTongyi 集成等
sentence-transformers：用于本地加载和运行中文嵌入模型（base-zh-v1.5）
**Web 服务与工具**
fastapi：用于构建嵌入模型服务接口（embed_service.py）
uvicorn：FastAPI 的 ASGI 服务器
pydantic：数据验证和设置管理（FastAPI 和 LangChain 依赖）
python-dotenv：加载 .env 文件中的环境变量
**数据处理与工具**
jieba：中文分词库，用于混合检索中的文本处理
faker：生成模拟医疗数据（患者、医生信息等）
numpy：数值计算
tqdm：进度条显示
cryptography：用于生成电子病历的数字签名


为了保证 Rasa 对话和图检索策略（GraphRAG）能够正常运转，请严格按照以下顺序启动各项基础设施和服务。

**第一步：启动底层数据库引擎**
医疗数据的存储与图谱查询依赖于本地或云端的数据库服务。请先确保这两个数据库后台已处于运行状态：
**启动 MySQL 服务**
用于支持 action_emr.py 和 action_appointment.py 中的结构化数据查询。
**启动 Neo4j 服务**
操作方法： 在终端使用命令neo4j.bat console
默认端口： 7474 (HTTP) / 7687 (Bolt)
**启动gen_medical_data.py生成数据**

**第二步：启动独立向量化服务 (Embedding Service)**
该项目将文本向量化功能抽离为了独立的微服务，为大模型意图识别和知识库检索提供支撑。
打开一个新的终端 (Terminal)，激活项目的虚拟环境，并执行以下命令：
python embed_service.py
状态检查： 启动成功后，服务将挂载并监听在 http://localhost:10010。你可以通过浏览器或 Postman 访问 http://localhost:10010/docs（如果使用的是 FastAPI）来查看接口文档并测试文本向量化功能是否正常。

**第三步：启动 Rasa 核心组件**
rasa train进行模型训练
在数据库和向量接口都处于 Ready 状态后，即可启动 Rasa 的核心业务流。
打开一个新的终端，启动负责处理病历查询、挂号预约以及调用知识图谱的 Action 服务：
rasa run actions
启动 Rasa 对话交互端
再打开最后一个新的终端，启动模型并进入对话界面：
rasa shell

