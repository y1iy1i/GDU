# GDU Builder 接口与伪代码 v0（草案）

状态：内容已整体确认，尚未冻结；只定义可编码契约，不包含 Builder 实现。

上位设计：`GDU_BUILDER_MINIMAL_DESIGN_V0_DRAFT.md`。

## 1. 目标

大白话：规定 Builder 的四个零件怎样交接工作，以及整条流水线具体怎么走。

专业表述：定义 Builder v0 的运行配置、内部工作数据类型、组件接口、检查点契约、状态转移、错误分类和产物提交顺序，使后续实现不必临时发明流程规则。

本文件不改变 `gdu.schema.json` 或 `build_log.schema.json`。这里定义的多数运行对象只是内部工作对象，不是新的 GDU 持久化字段。

## 2. 设计原则

1. 模型提出候选理解，编排器掌握流程权力；
2. PDF 是唯一证据权威，抽取文本只用于导航；
3. 先使用临时候选句柄，规范 ID 由编排器统一分配；
4. 每个阶段返回结构化结果，不用自然语言暗示“应该继续”；
5. 内容不充分与技术故障分开计数；
6. 只有三联停止门全部通过才能冻结；
7. frozen 和 provisional 都可形成三文件完整性包，但只有 frozen 有 `freeze` 事件；
8. 不保存隐藏思维链，只保存可公开检查的理由、证据和变更摘要。

## 3. 运行配置 `BuilderRunSpec`

`BuilderRunSpec` 是一次运行开始前固定的配置。字段如下：

| 字段 | 类型 | 作用 |
|---|---|---|
| `run_id` | ID | 本次运行标识 |
| `source_pdf` | 路径 | 权威 PDF，只读 |
| `extracted_text` | 路径 | 已准备文本，只读、仅导航 |
| `gdu_schema` | 路径 + SHA-256 | 冻结 GDU v0 Schema |
| `build_log_schema` | 路径 + SHA-256 | 冻结 Build Log v0 Schema |
| `protocol` | 名称、版本、路径、SHA-256 | 冻结构建方法 |
| `config_or_prompt_sha256` | SHA-256 | 固定理解配置的身份 |
| `model_id` | 非空字符串 | 预登记模型；不可观测则诚实写明 |
| `reasoning_effort` | 非空字符串 | 预登记等级；不可观测则诚实写明 |
| `output_dir` | 路径 | 与输入、Gold 隔离的新输出目录 |
| `checkpoint_source_requests` | CP1–CP6 到 SourceRequest 的映射 | 必须恰好覆盖六个检查点，运行开始后不可变化 |
| `max_semantic_corrections` | 整数 | v0 必须等于 2 |
| `max_technical_retries` | 整数 | v0 必须等于 1 |
| `single_builder` | 布尔 | v0 必须为 true |
| `external_knowledge_allowed` | 布尔 | v0 必须为 false |

预检还要验证：文件存在、哈希匹配、PDF 页数可读、输出位置不包含非法输入、模型配置非空、固定上限未被放宽。

`BuilderRunSpec` 不进入 GDU 顶层；其中需要追溯的字段被编排器映射到 `manifest` 和 Build Log。

## 4. 核心内部数据类型

以下是语言无关的逻辑类型；后续可以用 Python dataclass、TypedDict 或 Pydantic 表达，但本阶段不选实现库。

### 4.1 `SourceRequest`

理解模块请求查看的来源范围：

```text
SourceRequest:
  purpose                 # 为什么需要这些来源
  page_ranges[]           # PDF 物理页范围
  modalities[]            # text/table/image/formula/mixed
  locator_hints[]         # 可选的章节、表号、图号或文本定位线索
```

页范围必须落在 PDF 实际页数内。理解模块不能用无限范围请求绕过既定阶段。

### 4.2 `SourcePacket`

SourceReader 返回的只读证据材料：

```text
SourcePacket:
  source_document_id
  request_identity
  pdf_fragments[]         # 带物理页和定位信息的权威片段
  navigation_text[]       # 可选；明确标为非权威导航材料
  retrieval_notes[]       # 缺页、图像不可读等公开说明
```

任何可提升为 GDU `evidence` 的内容必须来自 `pdf_fragments`，并能生成 `fragment_sha256`。仅出现在 `navigation_text` 中的内容必须回到 PDF 核验。

### 4.3 `CandidateBundle`

理解模块返回的候选对象包：

```text
CandidateBundle:
  stage
  candidates[]            # 当前阶段允许产生的对象
  local_handles[]         # 本次返回中使用的临时引用
  evidence_candidates[]
  public_rationales[]
  uncertainties[]
  proposed_source_requests[]
```

候选对象使用本地句柄相互引用，例如 `candidate:3`。编排器检查无歧义后再分配 `phys:*`、`unit:*`、`assert:*`、`rel:*`、`ev:*` 等规范 ID，并统一改写引用。理解模块不能指定最终 ID，避免重复和悬空引用。

### 4.4 `WorkingGDU`

运行中的公开工作状态：

```text
WorkingGDU:
  manifest
  physical_structure[]
  semantic_units[]
  assertions
  relations[]
  generative_plan
  evidence[]
  completed_checkpoints[]
  open_gaps[]
```

在早期阶段它可以暂时缺少后续区块，因此不冒充完整 `gdu.json`。每次提升候选后，编排器执行当前区块的局部结构检查、引用闭包检查和证据来源检查；只有最终输出才接受完整 GDU Schema 验证。

### 4.5 `CheckpointResult`

```text
CheckpointResult:
  checkpoint              # cp1 ... cp6
  outcome                 # completed / passed / failed
  promoted_refs[]
  rejected_candidate_handles[]
  evidence_refs[]
  gaps[]
  result_summary
```

CP1–CP5 正常完成使用 `completed`；CP6 的停止门使用 `passed` 或 `failed`。这些值可直接映射到 Build Log v0 的 checkpoint 事件。

### 4.6 `Gap`

```text
Gap:
  gap_id
  gate_dimension          # coverage / evidence / stability
  check_kind              # ordinary / cross_carrier / cross_section / negative_boundary
  affected_refs[]
  source_scope[]           # 已知页或待复核页范围
  reason
  earliest_checkpoint     # cp1 ... cp5
  requested_action
```

缺口必须足够具体，才能触发定向修正。不能只写“质量不够”或“再读一遍”。

### 4.7 `StopGateResult`

```text
StopGateResult:
  coverage                # passed / failed
  evidence                # passed / failed
  stability               # passed / failed
  mandatory_checks:
    cross_carrier         # passed / failed
    cross_section         # passed / failed
    negative_boundary     # passed / failed
  gaps[]
  summary
```

不变量：只要任一主维度或强制子检查失败，整体结果就是 failed，并且 `gaps` 不得为空；全部通过时 `gaps` 必须为空。

### 4.8 `CorrectionRequest`

```text
CorrectionRequest:
  correction_round        # 1 或 2
  target_checkpoint
  target_refs[]
  source_scope[]
  gaps[]
  immutable_run_identity  # 模型、参数、提示/配置哈希
```

它只允许处理缺口所指向的对象与来源范围。若多个缺口指向不同阶段，先回到最早的受影响检查点，然后重新执行其后确实受影响的依赖检查。

### 4.9 `BuilderRunResult`

```text
BuilderRunResult:
  outcome                 # frozen_complete / provisional_complete /
                          # input_rejected / technical_failed
  artifact_paths[]        # 有合法快照时为三项
  semantic_corrections_used
  technical_retries_used
  final_checkpoint
  public_summary
```

这是调用程序得到的进程级结果，不加入 `gdu.json`。

### 4.10 `ObjectMutation`

定向修正使用事务化对象操作：

```text
ObjectMutation:
  operation                # replace / downgrade / withdraw
  target_ref               # 必须位于 Gap 允许范围
  replacement_fields       # replace 或 downgrade 的受限字段补丁
```

`retain_alternative` 通过新增候选断言或解释组并写对应 revision 表达。所有 mutation 先在工作副本执行；范围、引用和候选检查通过后才整体提交，失败不能消耗规范 ID 或污染 WorkingGDU。

## 5. 四个组件接口

### 5.1 `Orchestrator`

```text
verify_inputs(spec) -> VerifiedInputs | InputRejected
run_checkpoint(name, working_gdu, verified_inputs) -> CheckpointResult
promote(bundle, working_gdu) -> PromotionResult
allocate_ids(bundle) -> CanonicalizedBundle
evaluate_stop_gate(working_gdu) -> StopGateResult
plan_correction(stop_gate, round) -> CorrectionRequest[]
finalize(status, working_gdu, event_stream) -> BuilderRunResult
```

只有 Orchestrator 能改变运行状态、累计次数、分配规范 ID 和决定 finalize。

### 5.2 `SourceReader`

```text
inspect_document_identity(pdf, extracted_text) -> SourceIdentity
read(request, verified_inputs) -> SourcePacket | TechnicalFailure
verify_fragment(fragment, pdf) -> VerifiedEvidenceFragment | TechnicalFailure
```

接口只要求可按物理页和载体返回材料；它不规定长文档内部如何索引或切分。

### 5.3 `UnderstandingAdapter`

```text
propose(stage, source_packet, public_working_view)
  -> CandidateBundle | TechnicalFailure

revise(correction_request, source_packet, public_working_view)
  -> CandidateBundle | TechnicalFailure
```

`public_working_view` 只包含当前阶段必要的公开对象、缺口和证据，不包含 Gold、其他系统答案或隐藏思维。Adapter 不能返回“请跳过检查点”“请增加轮次”等控制命令。

`source_packet` 由 Orchestrator 根据预登记 SourceRequest 调用 SourceReader 获得。普通检查点使用固定六阶段计划；修正调用只使用 Gap 的 source_scope。Adapter 不接收 PDF 文件路径。

技术重试必须原样重放同一方法调用；不得借重试修改配置或扩大来源范围。

Adapter 可以回报其实际观察到的运行身份。若模型、推理等级或配置哈希与预登记身份不一致，编排器将其视为不可重试的策略违规，而不是接受换模后的结果。

### 5.4 `ArtifactWriterValidator`

```text
validate_partial(stage, working_gdu) -> ValidationResult
validate_build_log_event(event) -> ValidationResult
stage_package(status, complete_gdu, event_stream) -> StagedPackage
write_hash_manifest(staged_package) -> StagedPackage
validate_complete_package(staged_package) -> ValidationResult
publish_atomically(staged_package, output_dir) -> ArtifactPaths
```

`validate_partial` 使用内部阶段规则和适用的 Schema 子结构；不得错误地要求 CP1 工作状态已经具备完整七区块。`validate_complete_package` 才调用完整 GDU v0 Validator，并额外逐行检查 Build Log v0 事件与顺序规则。

## 6. 六个检查点的输入输出契约

| 检查点 | Adapter 可见内容 | 允许新增或修改 | 必须完成的确定性检查 |
|---|---|---|---|
| CP1 来源结构 | 来源身份、PDF 结构材料 | manifest、physical_structure、初始 evidence | 哈希、页数、父子引用、顺序、PDF 证据来源 |
| CP2 语义单元 | CP1 对象、相关来源 | semantic_units、function assertions、支撑功能判断的最小 basis assertions、evidence | 单元覆盖物理结构、主功能唯一、次功能最多 2 个、功能断言的 basis 引用闭合 |
| CP3 断言证据 | CP1–2 对象、相关来源 | 补全 assertions、interpretation groups、evidence，并完成断言评估 | 原子性检查结果、认识来源条件字段、证据回指、替代解释规则 |
| CP4 关系 | 单元、断言、证据 | relations、必要 evidence | 端点同层、端点存在、关系类型合法、认识来源条件字段 |
| CP5 全局计划 | 全部已提升对象 | 五段 generative_plan、必要 plan assertions | 五段齐全、每段至少有一种引用、全部引用闭合 |
| CP6 双向核验 | 当前完整工作 GDU、强制核验来源 | 不任意扩展内容；输出 stop gate 与 gaps | 三项强制子检查、覆盖/证据/稳定三联门、完整引用和 Schema 预检 |

如 CP6 发现新事实本身，应先形成 Gap 并进入受限修正，不允许 CP6 在没有 revision 记录的情况下暗改前面区块。

GDU v0 要求语义单元的功能断言必须引用其依据断言。因此 CP2 允许建立“支撑功能判断所必需的最小 basis assertions”；CP3 再补全断言集合和认识状态评估。这是 Schema 引用闭包要求，不是提前把 CP3 整体塞进 CP2。

## 7. Build Log 写入规则

Builder 维护从 1 开始严格递增的 `logical_time`；事件 ID 由编排器分配。四类事件的触发边界如下：

- `checkpoint`：每个检查点完成、通过或失败时写；
- `revision`：新证据使已提升理解发生 promote、replace、downgrade、retain_alternative 或 withdraw 时写；
- `technical`：真实技术问题被解决、绕过或仍未解决时写；
- `freeze`：仅在三联门全部通过时写，必须是最后一条事件。

revision 必须有非空 `trigger_evidence_refs`。若只是发现缺口但尚无触发新证据，记录 failed checkpoint，不伪造 revision。

时间戳记录现实时间，`logical_time` 表示因果顺序；后续比较和重放以逻辑时间为主。

## 8. 主状态机伪代码

```text
function build_gdu(spec):
    state = initialized
    corrections_used = 0
    technical_retries_used = 0
    events = empty append-only stream

    verified = verify_inputs(spec)
    if verified is InputRejected:
        return BuilderRunResult(input_rejected)
    state = input_verified

    working = new public WorkingGDU

    for checkpoint in [cp1, cp2, cp3, cp4, cp5]:
        result = execute_with_one_technical_retry(checkpoint, working, verified)
        if result is UnresolvedTechnicalFailure:
            return finish_technical_failed_if_possible(working, events)

        promote only structurally valid candidates
        append validated checkpoint event
        state = checkpoint_complete

    while true:
        gate = execute_cp6_with_one_technical_retry(working, verified)
        if gate is UnresolvedTechnicalFailure:
            return finish_technical_failed_if_possible(working, events)

        append validated cp6 checkpoint event

        if gate fully passed:
            set GDU status = frozen
            append freeze event as final event
            return stage_validate_hash_and_publish(frozen, working, events)

        if corrections_used == 2:
            set GDU status = provisional
            preserve gate gaps in public run result and checkpoint log
            return stage_validate_hash_and_publish(provisional, working, events)

        corrections_used += 1
        requests = plan bounded corrections from concrete gaps
        revise only requested objects and source scopes
        append revision events only for evidence-triggered changes
        rerun affected deterministic checks
```

这里的 `execute_with_one_technical_retry` 不是每个检查点都各有一次额度，而是整次主运行共享最多一次技术重试。

## 9. 技术故障伪代码

```text
function execute_with_one_technical_retry(call):
    result = call with immutable run configuration
    if result is not TechnicalFailure:
        return result

    if global technical retry already used:
        append unresolved technical event
        return UnresolvedTechnicalFailure

    mark global technical retry used
    retry exact same call once

    if retry succeeds:
        append resolved or workaround technical event
        return retry result

    append unresolved technical event
    return UnresolvedTechnicalFailure
```

以下属于技术故障：文件不可读、读取器中断、调用中断、结构化传输损坏、返回内容无法解析。

以下不属于技术故障：证据不足、断言过宽、关系解释薄弱、GenerativePlan 不稳定、返回结构合法但语义质量不足。这些进入 checkpoint failure 或定向修正。

## 10. 产物提交顺序

为避免半成品冒充正式包，所有写入先在同一文件系统的隔离暂存目录完成：

```text
1. 组装完整 GDU，并设置 provisional 或 frozen
2. 组装完整 build_log；只有 frozen 添加最后一条 freeze
3. 分别验证 GDU 结构、日志逐行结构和日志顺序
4. 写入暂存 gdu.json 与 build_log.jsonl
5. 根据这两个已关闭文件生成 ARTIFACTS.sha256
6. 对暂存三文件包运行完整 Validator
7. 全部通过后一次性发布到 output_dir
```

freeze 事件只引用 `ARTIFACTS.sha256` 的相对路径，不把 GDU 或日志自身哈希写回日志，因此不会形成循环哈希。

如果 provisional 的完整 GDU Schema 验证失败，它不能被发布为正式 provisional 包；这属于 Builder 实现错误或无法形成合法快照，而不是停止门语义失败。

## 11. 三类主要结束状态

| 状态 | 含义 | 是否有三文件包 | 是否有 freeze |
|---|---|---:|---:|
| `frozen_complete` | 三联门全通过且完整验证通过 | 是 | 是，唯一且最后 |
| `provisional_complete` | 两次定向修正后仍有明确缺口，但形成合法快照 | 是 | 否 |
| `technical_failed` | 一次同配置技术重试后仍无法继续 | 仅在已有合法完整快照时才可能有 provisional 包 | 否 |

另有前置状态 `input_rejected`：输入或隔离规则不合法，通常不创建正式产物包。

技术失败时不得为了凑齐三文件而制造虚假 GDU。进程级返回值必须说明最后成功检查点和故障摘要。

## 12. 实现时的最小模块建议

这不是当前要创建的代码，只用于检查接口是否能自然落地：

```text
src/gdu/builder_v0/
  types.py                 # 内部运行类型
  orchestrator.py          # 状态机和额度
  source_reader.py         # 接口，不绑定分段方案
  understanding_adapter.py# 接口，不绑定模型 API
  artifact_writer.py       # 暂存、验证、哈希、发布
  id_allocator.py          # 规范 ID 和引用改写
  log_writer.py            # 四类事件与逻辑时间
```

第一轮实现应先使用固定测试 Adapter，而不是直接接真实模型。这样可以先证明状态机、上限、日志和冻结逻辑没有错误，再研究模型与长文档读取能力。

## 13. 契约一致性审计

| 检查项 | 结论 |
|---|---|
| 是否增加 GDU 顶层字段 | 否；运行对象只存在于内部或进程返回值 |
| 是否修改 frozen/provisional 语义 | 否；仅 frozen 要求完整 assessment，provisional 仍必须 Schema 合法 |
| 是否引入第五种日志事件 | 否；全部映射到四种冻结事件 |
| 是否允许无限修正或重试 | 否；语义修正 2 次、全局技术重试 1 次 |
| 是否允许模型控制运行 | 否；模型只返回候选包 |
| 是否把抽取文本当权威证据 | 否；所有 evidence 必须回到 PDF fragment |
| 是否要求修改 Validator v0 | 否；完整包调用现有 Validator，日志事件另按冻结 Schema 验证 |
| provisional 是否可复核 | 是；三文件都有，但没有 freeze |
| 是否提前绑定长文档技术 | 否；SourceReader 仅定义按页和载体读取的接口 |

## 14. 本草案需要整体确认的内容

本阶段没有新增 Schema 字段。需要确认的是整套职责分界：

- 编排器拥有规范 ID、运行状态、修正额度、日志与冻结权；
- 理解 Adapter 只提交使用临时句柄的候选内容；
- 第一个实现先用固定测试 Adapter 验证流水线，不直接连接真实模型；
- 接口草案确认后，先做测试设计，再决定是否开始写 Builder 骨架代码。
