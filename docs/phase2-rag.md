# 阶段 2：智能加工、向量检索与咨询

本阶段补齐 1024 维 BGE-M3 索引、pgvector/Qdrant 镜像、FTS 混合检索、LlamaIndex 问答、5 轮历史、SSE 和来源卡片。PostgreSQL 保留文章审核状态、原文定位、向量与同步队列；Qdrant 返回的候选必须回查 SQL，撤回或版本过期的文章不会作为向量证据。

## 本地文件与模型配置

`.env` 放在 `miningintel/.env`，与 README.md 同级。不存在时从 `.env.example` 复制一次，已有文件不要覆盖。填入 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL；模型服务须兼容 `/chat/completions` 与 JSON object 输出。密钥不进入 Git、源码压缩包或日志。修改后重启 API/worker。

LLM 用于翻译、摘要、结构化中文问答。BGE-M3 与 bge-reranker-v2-m3 是本地模型，无需商业 API Key，但首次运行需下载权重。只配置 LLM 时可以用关键词检索和引用问答；只有同时安装 backend 的 ml extra 并启用 ML_ENABLED 才会生成真实向量。ML_DISABLED 时绝不写入随机向量或零向量。

本地单进程预览没有 Redis 时可显式设置 RATE_LIMIT_BACKEND=memory：每 IP/功能组每分钟 10 次，咨询的新旧路径共用配额。生产必须使用 Redis，APP_ENV=production 会拒绝 memory；采集多进程协调和 Celery 仍需要真正的 Redis。MODEL_CACHE_DIR 可以指定已有模型缓存，ML_DEVICE 默认 cpu，可配置 cuda:0。

```powershell
# miningintel 根目录，固定使用项目 Python 3.12
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e backend
# 准备 CPU/GPU 与模型空间后，安装模型依赖
.\.venv\Scripts\python.exe -m pip install -e 'backend[ml]'
```

如果此环境没有 pip，先执行 `.\.venv\Scripts\python.exe -m ensurepip --upgrade`；可用项目外层 `.tools/bin/uv.exe pip install --python .venv/Scripts/python.exe ...`。Python 3.14 不在当前模型依赖支持范围内。CPU 环境可先从 PyTorch CPU 软件源安装 torch，再安装 ml extra，避免下载不需要的 CUDA 运行库。

启用模型：设置 `ML_ENABLED=true`，容器构建同时设置 `INSTALL_ML=true`。本地配置 DATABASE_URL/REDIS_URL/CELERY URLs 为实际服务地址；容器使用 `.env.example` 中 postgres、redis、qdrant 主机名。QDRANT_URL 为空时仅使用 pgvector，同步任务保留等待日后配置；Docker 的内部地址为 `http://qdrant:6333`。Qdrant 不公开端口，可用 QDRANT_API_KEY 配置内部认证。

## 迁移、索引和调度

迁移 0003 添加 updated_at、indexed_at、embedding_model、embedding_hash 和 vector_sync_jobs。前两阶段的文章、会话、价格与引用片段不删除。

```powershell
# 使用原生 PostgreSQL；在 miningintel 根目录
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m app.rag.indexer --rebuild --batch-size 100
.\.venv\Scripts\python.exe -m app.rag.indexer --sync-only --batch-size 100
```

`--rebuild` 按 UUID keyset 分批重新计算 processed/published 文章，原文片段未改变时保留 chunk_id。中文输入顺序为 title_zh、summary_zh、content_zh；tokenizer 的 max_length=512（含特殊 token）负责截断，结果必须为 1024 个有限且非零的数值。原文分块单独编码，用于原文引用。英文缺少中文标题或正文会记为 untranslated，先重新加工，不伪造译文。可用 `--source-id UUID` 限定全量重建范围。

在配置 Key 前采集的英文文章可从原文补加工，无需重复抓取。以下命令预览候选并分批重试 pending 或尚未翻译的 processed 记录；不重开已发布文章。处理失败保留原文和错误类型，状态保持 pending 便于恢复。成功后的发布仍遵循 AUTO_PUBLISH 与审核设置：

翻译将数字替换为可还原占位符，恢复后核对原始数值和次数；英文明确的数量词（如 five）转换为数字 5 属于同一事实。新增数值、丢失价格或日期仍会被拒绝。摘要长度和正文数字校验失败各提供一次带原因的重试，不把失败结果写成成功译文。

```powershell
.\.venv\Scripts\python.exe -m pipeline.reprocess --source 'Resource World' --dry-run
.\.venv\Scripts\python.exe -m pipeline.reprocess --source 'Resource World' --limit 10
# 也可以用 --article-id UUID 只处理一篇
```

增量索引先排除未翻译或空白正文，再应用批次上限，避免旧的未翻译记录阻塞新文章。

索引时间、模型版本和 SHA256 内容/元数据摘要识别新增与修改；计算模型时不持有数据库事务，提交前再次校验文章快照。写入 PostgreSQL 的文章向量、原文向量和 Qdrant 任务原子提交。同步按 article_id 串行，使用 skip locked 和有上限的 HTTP 超时；服务失败保留任务并指数退避，重复请求幂等。Qdrant collection 不会在重建时被删除，旧片段由当前文章同步移除。

Celery Beat 每小时触发 dispatch_index，默认每次至多 INDEX_BATCH_SIZE=100 篇，积压会在后续扫描继续处理；大量历史语料先用全量 CLI。sync_vectors 每 30 秒恢复同步任务，编码任务在 nlp 队列执行。Beat 只运行一个实例：

```powershell
.\.venv\Scripts\python.exe -m pipeline.worker --queues=celery,nlp --loglevel=INFO
.\.venv\Scripts\python.exe -m celery -A app.tasks.celery_app:celery_app beat --loglevel=INFO
```

生产使用 Linux worker；Windows 的 `pipeline.worker` 选择 solo。Prometheus 指标 miningintel_index_articles_total、miningintel_vector_sync_total 记录真实索引与同步结果；日志不会包含密钥。

## 检索与证据

已发布状态与 minerals/regions/category/时间窗口在召回前过滤。pgvector 余弦和 FTS 各取 20，Qdrant 可提供同模型、同版本的片段候选，RRF(k=60) 融合去重。最多 20 个进入 BGE reranker，返回 5 个，每篇至多 2 个。结果含原文 chunk、文章/来源/日期/链接/标签和分数。ML 服务缺失或失败时明确降级为关键词/RRF，模型失败不会终止有证据的查询。

咨询当前语料范围为已发布文章。用户指定年份会转为 [该年1月1日, 次年1月1日) 的新闻发布时间范围；此筛选不等同价格观测年份。价格问题还要求正文有报价数字/币种或价格变动描述，仅有“核对价格口径”的方法说明不算行情证据，不用项目建设报道推断价格走势。生产仍需真实价格文章和质量评估集来校准召回阈值。

LLM 收到最近 5 轮历史和编号原文证据，历史只解析指代，不作为事实来源。没有证据或 claims=[] 时回复“根据现有资料，未找到相关信息”。句子逐条插入 [n]，引用片段必须逐字出现在来源，数值不得脱离引文或新闻日期。回答末尾列出标题、来源、日期、URL；sources.snippet 对应原文字符位置。引用存在与数值存在不等同独立语义事实核查，模型解释仍须结合原文判断。

## API 与前端

`POST /api/chat`：question、可选 session_id/筛选条件；返回 answer、sources、session_id，以及兼容字段 message_id/mode。`GET /api/chat/history/{session_id}` 返回本人最新 200 轮；`DELETE /api/chat/session/{session_id}` 删除本人会话及消息。不存在与其他人的会话均返回 404。以上接口和 /api/v1/chat 同时可用，均需登录。

`POST /api/chat/stream` 返回 SSE。status 和 heartbeat 在处理时发出，sources/delta 在生成、引文校验并提交后发出，done 是完整响应。此处是校验后文本流，不透传尚未核验的模型 token。断线取消尚未保存的工作；提交后断线可在历史恢复。

打开 http://127.0.0.1:3000/chat 登录后提问。点击 [1] 会展开并滚动到来源卡片，“查看原文”打开源页面。支持历史切换、追问、加载/错误状态、停止接收和删除会话。浏览器请求通过 Next 的同源代理转发，Nginx 关闭 API 响应缓冲。

## 验收的环境边界

数据库与前端测试使用明确标注的虚构价格资料和注入的测试编码器/LLM，不作为真实矿价结论。实际价格走势问答需要已发布、带日期和币种单位的真实文章，以及可用 LLM。真实模型和当前环境验证记录见 [阶段 2 验证记录](phase2-verification.md)。Qdrant 服务端 HNSW 性能、Linux Redis/Celery 并发与 Docker 运行需在对应环境验证；本地 Qdrant 模式可以验证数据写入、过滤、替换，不能代表服务端索引性能。

参考实现接口：[BGE-M3 模型说明](https://huggingface.co/BAAI/bge-m3)、[Qdrant 过滤说明](https://qdrant.tech/documentation/concepts/filtering/)、[LlamaIndex RetrieverQueryEngine](https://developers.llamaindex.ai/python/framework-api-reference/query_engine/retriever/)。
