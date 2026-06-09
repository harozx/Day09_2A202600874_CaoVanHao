# 🎤 BÁO CÁO THỰC HÀNH — Xây Dựng Hệ Thống Pháp Lý Đa Tác Nhân

**Chủ đề:** Từ 1 LLM đơn giản đến hệ thống phân tán A2A — hành trình 5 stage  
**Ngày:** 09/06/2026  
**Thời gian thực hành:** ~2.5 giờ  

---

## 🧭 Bối cảnh bài toán

> **Tưởng tượng:** Bạn là một công ty luật. Khách hàng hỏi:
>
> *"Công ty tôi vi phạm NDA, bị rò rỉ dữ liệu, và chưa nộp thuế. Hậu quả pháp lý là gì?"*
>
> Câu hỏi này cần **3 chuyên gia khác nhau** trả lời: luật hợp đồng, thuế, và bảo mật dữ liệu.
> Một LLM đơn lẻ không thể xử lý tốt tất cả.

**Mục tiêu của codelab:** Xây dựng hệ thống AI pháp lý qua 5 giai đoạn, mỗi giai đoạn thêm 1 tầng phức tạp mới — từ gọi LLM trực tiếp đến hệ thống phân tán nhiều agent giao tiếp qua HTTP.

---

## 📋 Checklist hoàn thành

| Bài | Yêu cầu | ✅ |
|---|---|:---:|
| 1.1, 1.2 | Đọc hiểu code, temperature control | ✅ |
| 2.1 | Thêm KB entry luật lao động VN | ✅ |
| 2.2 | Tạo tool kiểm tra thời hiệu | ✅ |
| 3.1 | Thêm tool tra cứu án lệ | ✅ |
| 3.2 | Debug agent reasoning | ✅ |
| 4.1 | Implement privacy_agent | ✅ |
| 4.2 | Conditional routing | ✅ |
| 5.1 | Trace request flow | ✅ |
| 5.2 | Dynamic discovery test | ✅ |
| 5.3 | Modify agent behavior | ✅ |
| 🏆 | Đo + giảm latency | ✅ **32.27s → 23.36s** |

---

## Stage 1: "Hỏi thẳng LLM" — Điểm xuất phát

### 💡 Ý tưởng

Cách đơn giản nhất: gửi câu hỏi → LLM trả lời từ kiến thức training.

```
Người dùng: "Hậu quả pháp lý khi vi phạm NDA?"
    ↓
  [ LLM ]  ← chỉ dùng kiến thức từ training data
    ↓
Câu trả lời (có thể đúng... có thể không)
```

### 📂 File: `stages/stage_1_direct_llm/main.py`

Không cần sửa code. Chỉ đọc hiểu cấu trúc:

```python
# Khởi tạo LLM qua OpenRouter (tương thích OpenAI API)
llm = get_llm()   # → Gemini 2.5 Flash, temperature=0.3

# Gửi 2 tin nhắn:
messages = [
    SystemMessage("Bạn là chuyên gia pháp lý..."),  # Vai trò
    HumanMessage("Hậu quả vi phạm NDA?"),           # Câu hỏi
]
response = llm.invoke(messages)
```

### 🤔 Vấn đề của Stage 1

| Được | Chưa được |
|---|---|
| Nhanh (~2 giây) | Không tra cứu được luật thực tế |
| Code đơn giản (10 dòng) | Dễ bịa số liệu (hallucinate) |
| Không cần setup | Không nhớ cuộc hội thoại trước |

> **Nhận xét:** Stage 1 giống như hỏi ChatGPT — nhanh, tiện, nhưng không đáng tin cho tư vấn pháp lý thật.

---

## Stage 2: "Cho LLM tra cứu" — Thêm Tools & Knowledge Base

### 💡 Ý tưởng

Thay vì để LLM đoán, **cho nó tra cứu dữ liệu thật** bằng tools.

```
Người dùng: "Thời hiệu khởi kiện vi phạm hợp đồng?"
    ↓
  [ LLM ] → "Tôi cần gọi tool check_statute_of_limitations"
    ↓
  [ TOOL ] → Tra bảng: "contract" → "4 năm — UCC § 2-725"
    ↓
  [ LLM ] → Tổng hợp: "Thời hiệu là 4 năm theo UCC § 2-725 ..."
```

### 📂 File: `exercises/exercise_2_tools.py`

### ✍️ Những gì mình đã làm

**Bài 2.1 — Thêm kiến thức luật Việt Nam:**

Knowledge base gốc chỉ có luật Mỹ. Mình thêm 1 entry về luật lao động VN:

```python
# THÊM MỚI vào LEGAL_KNOWLEDGE
{
    "id": "labor_law",
    "keywords": ["lao động", "sa thải", "labor", "termination", "wrongful"],
    "text": (
        "Theo BLLĐ 2019, sa thải trái pháp luật (Điều 41): "
        "bồi thường 2 tháng lương/năm làm việc, "
        "quyền yêu cầu nhận lại việc làm."
    ),
}
```

> **Tại sao?** Hệ thống pháp lý cần phục vụ được nhiều hệ thống luật. Nếu chỉ có UCC/DTSA (Mỹ) thì câu hỏi tiếng Việt về lao động sẽ không có kết quả.

---

**Bài 2.2 — Tạo tool kiểm tra thời hiệu:**

```python
@tool
def check_statute_of_limitations(case_type: str) -> str:
    """Kiểm tra thời hiệu khởi kiện theo loại vụ án."""
    limits = {
        "contract":     "4 năm — UCC § 2-725",
        "tort":         "2–3 năm tùy bang",
        "trade_secret": "3 năm — DTSA § 1836(d)",
        "nda":          "3 năm theo DTSA",
        "labor":        "1 năm — BLLĐ 2019 Điều 190",
        "fraud":        "3–6 năm tùy bang",
    }
    # LLM gọi tool này → nhận kết quả chính xác từ bảng tra
```

> **Điểm quan trọng:** LLM không cần đoán "thời hiệu là 3 hay 4 năm" — nó gọi tool và nhận đáp án chính xác.

### ✅ Kết quả chạy

```
🔧 Gọi tool: check_statute_of_limitations({'case_type': 'contract'})
   Kết quả: "4 năm — UCC § 2-725 (hàng hóa); 6 năm tại một số bang (dịch vụ)."

✅ Câu trả lời: Cite đúng điều luật, đúng con số — không hallucinate.
```

### 🔄 So sánh Stage 1 vs Stage 2

| | Stage 1 | Stage 2 |
|---|---|---|
| **Nguồn tin** | Training data (có thể sai) | Knowledge Base + Tools (chính xác) |
| **Ví dụ** | "Thời hiệu khoảng 3-5 năm" | "4 năm — UCC § 2-725" ← cite đúng |
| **Hạn chế** | — | Phải tự viết tool loop (50+ dòng code) |

---

## Stage 3: "Agent tự suy nghĩ" — ReAct Pattern

### 💡 Ý tưởng

Ở Stage 2, **mình phải tự viết vòng lặp** gọi tool. Stage 3 dùng pattern **ReAct** (Reasoning + Acting) — agent tự quyết định:

```
Agent nhận câu hỏi phức tạp
    ↓
[THINK] "Câu này liên quan đến data privacy VÀ tax. Cần search cả 2."
    ↓
[ACT]   → search_legal_database("data privacy")
        → search_legal_database("tax overseas")
        → calculate_penalty("data_privacy", "high", 5000000)
    ↓
[OBSERVE] Nhận kết quả từ 3 tools
    ↓
[THINK] "Đã đủ thông tin" → Viết câu trả lời cuối cùng
```

Chỉ cần **3 dòng code** để tạo agent:

```python
from langgraph.prebuilt import create_react_agent

llm = get_llm()
graph = create_react_agent(model=llm, tools=TOOLS, prompt=SYSTEM_PROMPT)
# Xong! Agent tự biết khi nào gọi tool, gọi bao nhiêu lần
```

### 📂 File: `stages/stage_3_single_agent/main.py`

### ✍️ Bài 3.1 — Thêm tool tra cứu án lệ

CODELAB cho sẵn 3 án lệ (breach, negligence, contract). Mình mở rộng lên **6 án lệ**, thêm fraud, privacy, tax:

```python
@tool
def search_case_law(keywords: str) -> str:
    """Tìm kiếm án lệ theo từ khóa."""
    cases = {
        "breach":     "Hadley v. Baxendale (1854) — Consequential damages",
        "negligence": "Donoghue v. Stevenson (1932) — Duty of care",
        "contract":   "Carlill v. Carbolic Smoke Ball Co (1893)",
        "fraud":      "Derry v. Peek (1889) — False representation",     # MỚI
        "privacy":    "Carpenter v. United States (2018) — Fourth Amendment", # MỚI
        "tax":        "Cheek v. United States (1991) — Tax law defense",    # MỚI
    }
```

Thêm vào danh sách tools:
```python
TOOLS = [search_legal_database, calculate_penalty,
         check_compliance_requirements, search_case_law]  # 3 → 4 tools
```

> **Agent tự quyết định** có gọi `search_case_law` hay không — mình không cần viết if-else.

### ✅ Kết quả chạy

```
[Step 1] Agent gọi 5 tools cùng lúc:
  - search_legal_database("data privacy")
  - search_legal_database("tax overseas revenue")
  - calculate_penalty("data_privacy", "high", 5000000)   → $500,000
  - calculate_penalty("tax_evasion", "high", 5000000)     → $500,000
  - check_compliance_requirements("technology", "startup") → CCPA, SOC 2

[Step 7] FINAL ANSWER → Phân tích 500 từ: CCPA, GDPR, 26 U.S.C § 7201...
```

### 🤔 Vấn đề còn lại

Tuy agent thông minh, nhưng vẫn là **1 agent duy nhất** xử lý TẤT CẢ domains. Giống 1 luật sư biết tất cả — trong thực tế, người ta chia chuyên môn.

---

## Stage 4: "Chia chuyên môn" — Multi-Agent Song Song

### 💡 Ý tưởng

Thay vì 1 agent biết tất cả, **chia thành nhiều agent chuyên gia**, mỗi agent 1 domain:

```
                    law_agent (phân tích tổng quát)
                        ↓
                   check_routing (xem câu hỏi về gì)
                        ↓
          ┌─────────────┼─────────────┐
     tax_agent    compliance_agent   privacy_agent ← MỚI
     (chuyên thuế) (chuyên tuân thủ) (chuyên GDPR)
          └─────────────┼─────────────┘
                        ↓  ← TẤT CẢ CHẠY SONG SONG
                  aggregate_results
```

### 📂 File: `exercises/exercise_4_multiagent.py`

### ✍️ Bài 4.1 — Implement `privacy_agent`

Đây là agent hoàn toàn mới, chuyên về bảo mật dữ liệu:

```python
def privacy_agent(state: State) -> dict:
    """Agent chuyên về GDPR, CCPA, Luật An ninh mạng VN."""
    llm = get_llm()
    prompt = f"""Bạn là chuyên gia bảo vệ dữ liệu cá nhân.

Câu hỏi gốc: {state['question']}
Phân tích pháp lý: {state.get('law_analysis', 'N/A')}

Hãy phân tích:
- GDPR: phạt đến 4% doanh thu toàn cầu hoặc €20M
- CCPA/CPRA: phạt $7,500/vi phạm cố ý
- Luật An ninh mạng VN 2018 và Nghị định 13/2023
- Quyền của người dùng bị ảnh hưởng
- Nghĩa vụ thông báo vi phạm dữ liệu"""

    response = llm.invoke([HumanMessage(content=prompt)])
    return {"privacy_analysis": response.content}
```

### ✍️ Bài 4.2 — Conditional Routing (chỉ gọi agent khi cần)

Không phải lúc nào cũng cần cả 3 chuyên gia. Routing bằng keyword:

```python
def route_to_specialists(state: State) -> list[Send]:
    question_lower = state["question"].lower()
    tasks = []

    if any(kw in question_lower for kw in ["tax", "irs", "thuế"]):
        tasks.append(Send("tax_agent", state))          # Gọi thuế

    if any(kw in question_lower for kw in ["compliance", "sec", "regulation"]):
        tasks.append(Send("compliance_agent", state))    # Gọi tuân thủ

    # MỚI: chỉ gọi privacy_agent khi câu hỏi liên quan
    if any(kw in question_lower for kw in ["data", "privacy", "gdpr",
                                            "dữ liệu", "rò rỉ", "bảo mật"]):
        tasks.append(Send("privacy_agent", state))       # Gọi bảo mật

    return tasks if tasks else [Send("aggregate_results", state)]
```

> **Ví dụ:** Hỏi "hậu quả vi phạm hợp đồng" → chỉ gọi law_agent (không gọi privacy hay tax = tiết kiệm thời gian).

### ⚠️ Bug đã gặp và cách fix

LangGraph yêu cầu:
- **Node function** phải trả `dict`
- **Edge function** phải trả `list[Send]`

Ban đầu dùng chung 1 function → crash: `InvalidUpdateError: Expected dict, got list[Send]`

**Fix:** Tách thành 2 function riêng:

```python
def check_routing(state) -> dict:         # NODE → trả dict
    return {}

def route_to_specialists(state) -> list[Send]:  # EDGE → trả list[Send]
    # ... logic routing ở trên ...

# Wiring:
graph.add_node("check_routing", check_routing)
graph.add_conditional_edges("check_routing", route_to_specialists, [...])
```

### ✅ Kết quả chạy

```
Câu hỏi: "Nếu công ty bị rò rỉ dữ liệu khách hàng, hậu quả pháp lý và thuế?"

[law_agent]       ✅ Phân tích tổng quát (1509 ký tự)
[check_routing]   "thuế" → tax_agent | "rò rỉ","dữ liệu" → privacy_agent
[tax_agent]       ✅ ─┐
[privacy_agent]   ✅ ─┘  ← CHẠY SONG SONG (tiết kiệm thời gian)
[aggregate]       ✅ Tổng hợp cả 3 phân tích
```

---

## Stage 5: "Hệ thống phân tán" — Distributed A2A

### 💡 Ý tưởng

Stage 4 chạy tất cả agents trong **1 process**. Stage 5 tách mỗi agent thành **1 server riêng**, giao tiếp qua HTTP theo chuẩn A2A (Agent-to-Agent).

```
┌────────────────────────────────────────────────────────┐
│  Registry :10000   ← Tất cả agents đăng ký khi start  │
│      ↕                                                  │
│  Customer Agent :10100  ← User hỏi ở đây              │
│      ↓ HTTP POST                                        │
│  Law Agent :10101  ← Phân tích + điều phối             │
│      ↓ HTTP POST (song song)                            │
│  ┌─────────────┬────────────────┐                       │
│  Tax :10102    Compliance :10103                        │
│  └─────────────┴────────────────┘                       │
└────────────────────────────────────────────────────────┘
  5 servers · 5 ports · giao tiếp qua HTTP · có thể scale riêng
```

### 📂 Files đã sửa

| File | Thay đổi |
|---|---|
| `common/llm.py` | Thêm `max_tokens` parameter |
| `law_agent/graph.py` | Keyword routing + max_tokens=512 |
| `tax_agent/graph.py` | max_tokens=512 |
| `compliance_agent/graph.py` | max_tokens=512 |
| `test_client_latency.py` | **MỚI** — test client có đo latency |

### ✍️ Bài 5.1 — Trace `trace_id` xuyên suốt hệ thống

Mỗi request tạo 1 `trace_id` duy nhất, truyền qua mọi agent:

```
[customer_agent]   trace=4a545ae0-3e59-... depth=0   ← User hỏi
[law_agent]        trace=4a545ae0-3e59-... depth=1   ← Law phân tích
[tax_agent]        trace=4a545ae0-3e59-... depth=2   ← Tax nhận từ Law
[compliance_agent] trace=4a545ae0-3e59-... depth=2   ← Compliance nhận từ Law
```

> **Tác dụng:** Khi debug, tìm 1 trace_id là thấy toàn bộ hành trình request qua tất cả services.

### ✍️ Bài 5.2 — Dynamic Discovery (dừng 1 agent)

Khi dừng Tax Agent và gọi lại → Law Agent bắt exception → trả kết quả partial:

```python
async def call_tax(state):
    try:
        endpoint = await discover("tax_question")  # Hỏi Registry
        result = await delegate(endpoint=endpoint, ...)
        return {"tax_result": result}
    except Exception as exc:
        return {"tax_result": f"[Tax unavailable: {exc}]"}  # Graceful degradation
```

> **Nhận xét:** Hệ thống không crash khi 1 agent chết — vẫn trả kết quả (thiếu phần thuế).

### ✍️ Bài 5.3 — Modify Agent Behavior

Sửa `tax_agent/graph.py` để trả lời ngắn gọn hơn:

```diff
- llm = get_llm()                    # max_tokens=1024
+ llm = get_llm(max_tokens=512)      # Ngắn gọn hơn, nhanh hơn
```

Kết quả: response giảm 4300 → 2631 ký tự (−39%).

---

## 🏆 Bài Tập Cộng Điểm: Đo và Giảm Latency

### Câu 1: Latency gốc là bao nhiêu?

Tạo file `test_client_latency.py` để đo:

```python
start_time = time.time()
response = await client.send_message(request)
latency = time.time() - start_time
print(f">>> TOTAL LATENCY: {latency:.2f} seconds <<<")
```

**Kết quả: 32.27 giây** cho 1 câu hỏi.

### Câu 2: Tại sao chậm? Làm sao giảm?

**Phân tích pipeline — 6 LLM calls tuần tự:**

```
Thời gian (giây):
0s          2s          10s         18s        20s       32s
│───────────│───────────│───────────│──────────│─────────│
│ Customer  │ Law Agent │ ROUTING   │ Tax+Comp │Aggregate│
│ Agent     │ phân tích │ (LLM!!!)  │ (song song)│ tổng hợp│
│ (LLM #1)  │ (LLM #2)  │ (LLM #3)  │(LLM #4+5)│(LLM #6) │
                         ↑↑↑↑↑↑↑↑↑
                         BOTTLENECK!
                    8 GIÂY chỉ để LLM output:
                    {"needs_tax": true, "needs_compliance": true}
```

> **Phát hiện:** Check_routing gọi LLM chỉ để ra 1 JSON `{"needs_tax": true}` — mất 8 giây cho việc mà keyword matching làm trong 0ms!

---

### Optimization 1: Bỏ LLM call routing → Keyword matching

**File:** `law_agent/graph.py`

```diff
  async def check_routing(state):
-     # GỐC: Gọi LLM để output JSON — mất ~8 giây!!!
-     llm = get_llm()
-     result = await llm.ainvoke([
-         SystemMessage("Reply ONLY JSON: {needs_tax, needs_compliance}"),
-         HumanMessage(question),
-     ])
-     parsed = json.loads(result.content)

+     # OPTIMIZED: Keyword matching — ~0 giây
+     TAX_KEYWORDS = ["tax", "taxes", "irs", "evasion", "thuế", "avoid"]
+     needs_tax = any(kw in question.lower() for kw in TAX_KEYWORDS)
+     needs_compliance = any(kw in question.lower() for kw in COMPLIANCE_KEYWORDS)
```

**Tiết kiệm: ~8 giây** (bỏ hoàn toàn 1 LLM API call).

### Optimization 2: Giảm max_tokens 1024 → 512

```diff
  # common/llm.py — cho phép mỗi agent chọn max_tokens riêng
- def get_llm() -> ChatOpenAI:
-     return ChatOpenAI(max_tokens=1024, ...)

+ def get_llm(max_tokens: int = 1024) -> ChatOpenAI:
+     return ChatOpenAI(max_tokens=max_tokens, ...)

  # Áp dụng cho law_agent, tax_agent, compliance_agent:
+ llm = get_llm(max_tokens=512)   # Ngắn gọn hơn = generate nhanh hơn
```

**Tiết kiệm: ~3–5 giây** (LLM generate ít tokens hơn).

### Kết quả

```
Pipeline SAU optimization:
0s        2s        4s        12s      14s     23s
│─────────│─────────│─────────│────────│───────│
│Customer │  Law    │Tax+Comp │Aggregate│Customer│
│  Agent  │ Analyze │(parallel)│(512tok)│ Present│
                ↑
           routing = 0ms ✨ (keyword matching)
```

| Metric | Trước | Sau | Cải thiện |
|---|---|---|---|
| **Tổng latency** | **32.27s** | **23.36s** | **−27.6%** |
| Số LLM calls | 6 | 5 | −1 call |
| Routing time | ~8s (LLM) | ~0ms (keyword) | **−8 giây** |
| Max tokens/agent | 1024 | 512 | −50% |
| Tax response length | 4300 chars | 2631 chars | −39% |

---

## 📊 Tổng kết: Hành trình 5 Stage

```
Stage 1         Stage 2         Stage 3         Stage 4         Stage 5
Direct LLM  →   RAG+Tools  →  ReAct Agent →  Multi-Agent →  Distributed
                                                              A2A
 1 LLM call     LLM + Tools   Agent tự suy    Nhiều agent     Mỗi agent
 không tools    tra cứu DB     nghĩ + gọi     chuyên môn     = 1 server
 dễ sai         chính xác      tools tự động   chạy song song  HTTP + Registry

 ⭐              ⭐⭐            ⭐⭐⭐           ⭐⭐⭐⭐          ⭐⭐⭐⭐⭐
```

### Files đã thay đổi

| File | Thay đổi | Liên quan bài |
|---|---|---|
| `common/llm.py` | +max_tokens parameter | 5.3, Cộng điểm |
| `stages/stage_2_rag_tools/main.py` | +labor_law KB, +SOL tool | 2.1, 2.2 |
| `stages/stage_3_single_agent/main.py` | +search_case_law (6 án lệ) | 3.1, 3.2 |
| `exercises/exercise_2_tools.py` | Điền code hoàn chỉnh | 2.1, 2.2 |
| `exercises/exercise_4_multiagent.py` | +privacy_agent, +routing, +graph | 4.1, 4.2 |
| `law_agent/graph.py` | Keyword routing, max_tokens=512 | Cộng điểm |
| `tax_agent/graph.py` | max_tokens=512 | 5.3, Cộng điểm |
| `compliance_agent/graph.py` | max_tokens=512 | Cộng điểm |
| `test_client_latency.py` | **MỚI** — test client đo latency | Cộng điểm |

---

## 💬 Câu hỏi ôn tập

**1. Khi nào dùng single agent vs multi-agent?**

- **Single agent:** Câu hỏi đơn giản, 1 domain. Ví dụ: "Thời hiệu khởi kiện hợp đồng?"
- **Multi-agent:** Câu hỏi phức tạp, nhiều domain. Ví dụ: "Vi phạm NDA + trốn thuế + rò rỉ data — hậu quả?"
- **Rule of thumb:** Nếu cần >2 chuyên gia khác nhau trả lời → multi-agent.

**2. Ưu điểm A2A so với REST thông thường?**

| REST thường | A2A Protocol |
|---|---|
| Tự định nghĩa format | Chuẩn hóa: AgentCard, Task, Artifact |
| Hardcode URL | Dynamic discovery qua Registry |
| Tự implement tracing | `trace_id` + `context_id` built-in |
| Không giới hạn delegation | `delegation_depth` guard chống loop |

**3. Làm sao chống infinite delegation loops?**

```python
MAX_DELEGATION_DEPTH = 3   # Tối đa 3 tầng delegation

# Mỗi agent check trước khi delegate:
depth = state.get("delegation_depth", 0)
if depth >= MAX_DELEGATION_DEPTH:
    return {"needs_tax": False}   # Dừng, không delegate thêm
```

**4. Tại sao cần Registry? Hardcode URL được không?**

- **Demo:** Hardcode được (localhost:10101, 10102...)
- **Production:** Không nên, vì:
  - Container restart → IP mới
  - Scale out → cần load balancing
  - Agent chết → cần health check
- **Registry giải quyết tất cả:** agents tự đăng ký khi start, clients discover lúc runtime.

---

*✅ Hoàn thành toàn bộ codelab + bài tập cộng điểm.*  
*🚀 Live demo: chạy `uv run python proxy_server.py` → mở `http://localhost:8888/report.html`*
