# Lab Solution — Day 09: Multi-Agent & A2A Protocol

> **Sinh viên:** Cao Văn Hào — 2A202600874  
> **Ngày:** 09/06/2026

---

## Exercise 1: Direct LLM (Stage 1)

### 1.1 — Chạy Stage 1 và quan sát

**File:** `stages/stage_1_direct_llm/main.py`

Chạy lệnh:
```bash
uv run python stages/stage_1_direct_llm/main.py
```

**Quan sát:**
- LLM trả lời trực tiếp từ training data, không tra cứu nguồn nào.
- Câu trả lời có thể chính xác nhưng **không có citation** — không thể xác minh.
- Nếu hỏi về luật mới (sau knowledge cutoff), LLM sẽ hallucinate.

### 1.2 — Cấu hình `temperature=0.3`

**File:** `common/llm.py`

```python
def get_llm(max_tokens: int = 1024) -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash"),
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),
        openai_api_base="https://openrouter.ai/api/v1",
        max_tokens=max_tokens,
        temperature=0.3,  # ← giữ output ổn định, ít ngẫu nhiên
    )
```

**Giải thích:** `temperature=0.3` giúp output nhất quán hơn cho domain pháp lý — nơi cần sự chính xác, không cần sáng tạo.

---

## Exercise 2: RAG + Tools (Stage 2)

### 2.1 — Thêm `labor_law` vào Knowledge Base

**File:** `stages/stage_2_rag_tools/main.py` (dòng 92–107) và `exercises/exercise_2_tools.py` (dòng 31–44)

```python
{
    "id": "labor_law",
    "keywords": ["lao động", "sa thải", "hợp đồng lao động", "labor",
                 "termination", "wrongful", "employment", "fired", "dismiss"],
    "text": (
        "Theo Bộ luật Lao động Việt Nam 2019 (BLLĐ 2019), người sử dụng lao động "
        "có thể đơn phương chấm dứt hợp đồng trong các trường hợp hợp pháp: "
        "(1) người lao động thường xuyên không hoàn thành công việc; "
        "(2) bị ốm đau, tai nạn đã điều trị 12 tháng liên tục chưa khỏi; "
        "(3) thiên tai, hỏa hoạn, dịch bệnh — bắt buộc thu hẹp sản xuất; "
        "(4) người lao động đủ tuổi nghỉ hưu. "
        "Sa thải trái pháp luật (Điều 41 BLLĐ): được quyền yêu cầu nhận lại "
        "việc làm, bồi thường 2 tháng lương cho mỗi năm làm việc."
    ),
},
```

### 2.2 — Tool `check_statute_of_limitations`

**File:** `stages/stage_2_rag_tools/main.py` (dòng 175–204) và `exercises/exercise_2_tools.py` (dòng 59–80)

```python
@tool
def check_statute_of_limitations(case_type: str) -> str:
    """Kiểm tra thời hiệu khởi kiện theo loại vụ án."""
    limits = {
        "contract":     "4 năm — UCC § 2-725",
        "tort":         "2–3 năm tùy bang",
        "trade_secret": "3 năm — DTSA (18 U.S.C. § 1836(d))",
        "nda":          "3 năm theo DTSA",
        "labor":        "1 năm — BLLĐ 2019 Điều 190",
        "fraud":        "3–6 năm tùy bang",
    }
    key = case_type.lower().replace(" ", "_")
    if key in limits:
        return f"Thời hiệu khởi kiện cho '{case_type}': {limits[key]}"
    return f"Không tìm thấy. Các loại hỗ trợ: {', '.join(limits.keys())}."
```

**Cải tiến thêm:** Thêm multi-round tool loop (`run_tool_loop`) để LLM có thể gọi nhiều tools liên tiếp trong 1 session thay vì chỉ 1 lượt.

---

## Exercise 3: Single Agent — ReAct (Stage 3)

### 3.1 — Tool `search_case_law`

**File:** `stages/stage_3_single_agent/main.py` (dòng 176–198)

```python
@tool
def search_case_law(keywords: str) -> str:
    """Tìm kiếm án lệ theo từ khóa."""
    cases = {
        "breach":     "Hadley v. Baxendale (1854) — Consequential damages phải foreseeable.",
        "negligence": "Donoghue v. Stevenson (1932) — Duty of care & neighbour principle.",
        "contract":   "Carlill v. Carbolic Smoke Ball Co (1893) — Unilateral contract.",
        "fraud":      "Derry v. Peek (1889) — Fraud cần chứng minh intent to deceive.",
        "privacy":    "Carpenter v. United States (2018) — Warrant cho cell-site data.",
        "tax":        "Cheek v. United States (1991) — Good-faith defense cho tax law.",
    }
    results = [case for key, case in cases.items() if key in keywords.lower()]
    return "\n".join(results) if results else "Không tìm thấy án lệ phù hợp."
```

### 3.2 — Verbose reasoning

Sử dụng `astream(inputs, stream_mode="updates")` để in chi tiết từng bước Think → Act → Observe của ReAct loop. Cho thấy agent tự quyết định gọi tool nào, đánh giá kết quả, rồi gọi thêm tool hoặc trả lời.

---

## Exercise 4: Multi-Agent System (Stage 4)

### 4.1 — Implement `privacy_agent`

**File:** `exercises/exercise_4_multiagent.py` (dòng 118–137)

```python
def privacy_agent(state: State) -> dict:
    """Agent chuyên về bảo vệ dữ liệu cá nhân và GDPR."""
    llm = get_llm()
    prompt = f"""Bạn là chuyên gia về GDPR và luật bảo vệ dữ liệu cá nhân.
    Phân tích các vấn đề về privacy và data protection:
    - GDPR: phạt đến 4% doanh thu toàn cầu hoặc €20M
    - CCPA/CPRA: phạt $7,500/vi phạm cố ý
    - Luật An ninh mạng Việt Nam 2018 + Nghị định 13/2023
    - Quyền của người dùng (right to erasure, right to be informed)
    - Nghĩa vụ thông báo data breach

    Câu hỏi: {state['question']}
    Phân tích pháp lý: {state.get('law_analysis', 'N/A')}
    Giữ phân tích dưới 200 từ."""

    response = llm.invoke([HumanMessage(content=prompt)])
    return {"privacy_analysis": response.content}
```

### 4.2 — Conditional routing cho privacy_agent

**File:** `exercises/exercise_4_multiagent.py` (dòng 57–80)

```python
def route_to_specialists(state: State) -> list[Send]:
    question_lower = state["question"].lower()
    tasks = []

    if any(kw in question_lower for kw in ["tax", "irs", "thuế"]):
        tasks.append(Send("tax_agent", state))

    if any(kw in question_lower for kw in ["compliance", "sec", "regulation", "tuân thủ"]):
        tasks.append(Send("compliance_agent", state))

    # Routing cho privacy_agent
    if any(kw in question_lower for kw in ["data", "privacy", "gdpr", "dữ liệu",
                                            "rò rỉ", "bảo mật", "ccpa", "personal"]):
        tasks.append(Send("privacy_agent", state))

    if not tasks:
        tasks.append(Send("aggregate_results", state))
    return tasks
```

**Graph wiring:**
```python
graph.add_node("privacy_agent", privacy_agent)
graph.add_edge("privacy_agent", "aggregate_results")
```

---

## Exercise 5: Distributed A2A (Stage 5)

### 5.1 — Trace `trace_id` trong logs

Kiểm tra logs khi chạy hệ thống A2A đầy đủ (5 services). Mỗi request có `trace_id` duy nhất được truyền qua tất cả agents:

```
Customer Agent → Law Agent → Tax Agent + Compliance Agent
                                ↑ cùng trace_id
```

Điều này cho phép trace toàn bộ chuỗi xử lý từ đầu đến cuối.

### 5.2 — Dynamic discovery & graceful degradation

Test bằng cách tắt 1 agent (ví dụ Tax Agent) → hệ thống vẫn trả lời được với các agents còn lại. Law Agent catch exception và trả về `"[Tax analysis unavailable: ...]"` thay vì crash.

### 5.3 — Giới hạn `max_tokens=512`

**Files:** `tax_agent/graph.py`, `compliance_agent/graph.py`, `law_agent/graph.py`

```python
llm = get_llm(max_tokens=512)  # Giảm từ 1024 → 512
```

**Lý do:** Output ngắn hơn = ít token generation = giảm latency. Đối với phân tích pháp lý chuyên biệt, 512 tokens (~400 từ) là đủ cho mỗi sub-agent.

---

## Bonus: Tối ưu Latency

### Kết quả đo: 32.27s → 23.36s (giảm 27.6%)

**Các thay đổi tối ưu:**

| Thay đổi | Tiết kiệm | Giải thích |
|----------|-----------|------------|
| `max_tokens=512` cho tất cả agents | ~3-5s | Ít token generation hơn |
| Keyword routing thay LLM routing | ~3-5s | Bỏ 1 LLM call khỏi critical path |
| Parallel sub-agent calls (đã có sẵn) | — | Tax + Compliance chạy song song |

**File test:** `test_client_latency.py` — đo thời gian end-to-end từ client gửi câu hỏi đến nhận response.
