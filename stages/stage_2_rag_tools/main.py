"""Stage 2: LLM + RAG / Tools

Adds retrieval-augmented generation and tool use to ground LLM responses
in external data. The LLM can now search a legal knowledge base, check
statute of limitations, and calculate damages.

Includes all CODELAB exercises:
  - Bài Tập 2.1: Thêm labor_law entry vào LEGAL_KNOWLEDGE
  - Bài Tập 2.2: Tool check_statute_of_limitations
  - Cải tiến: Multi-round tool loop (không giới hạn 1 pass)
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from common.llm import get_llm

# ---------------------------------------------------------------------------
# Simulated legal knowledge base (in production: vector store / pgvector)
# ---------------------------------------------------------------------------

LEGAL_KNOWLEDGE = [
    {
        "id": "ucc_breach",
        "keywords": ["breach", "contract", "remedies", "damages", "ucc"],
        "text": (
            "Under the Uniform Commercial Code (UCC) Article 2, remedies for breach of contract "
            "include: (1) expectation damages — placing the non-breaching party in the position "
            "they would have been in had the contract been performed; (2) consequential damages "
            "for foreseeable losses (Hadley v. Baxendale, 1854); (3) specific performance when "
            "the subject matter is unique; (4) cover damages — the cost of obtaining substitute "
            "performance. The statute of limitations is typically 4 years (UCC § 2-725)."
        ),
    },
    {
        "id": "nda_trade_secret",
        "keywords": ["nda", "non-disclosure", "confidential", "trade secret", "agreement"],
        "text": (
            "NDA breaches may trigger both contractual and statutory liability. Under the Defend "
            "Trade Secrets Act (DTSA, 18 U.S.C. § 1836), misappropriation of trade secrets can "
            "result in: (1) injunctive relief; (2) actual damages plus unjust enrichment; "
            "(3) exemplary damages up to 2x actual damages for willful misappropriation; "
            "(4) attorney's fees. State Uniform Trade Secrets Act (UTSA) versions provide "
            "additional remedies. Criminal prosecution is possible under the Economic Espionage "
            "Act (18 U.S.C. § 1832) with penalties up to $5M for individuals."
        ),
    },
    {
        "id": "dtsa_details",
        "keywords": ["dtsa", "federal", "trade secret", "defend", "statute"],
        "text": (
            "The Defend Trade Secrets Act (2016) created a federal private cause of action for "
            "trade secret misappropriation. Key provisions: (1) ex parte seizure orders in "
            "extraordinary circumstances; (2) 3-year statute of limitations; (3) immunity for "
            "whistleblower disclosures to government officials; (4) employers must notify "
            "employees of whistleblower immunity in any NDA or employment agreement."
        ),
    },
    {
        "id": "liquidated_damages",
        "keywords": ["liquidated", "damages", "penalty", "clause", "contract", "nda"],
        "text": (
            "Liquidated damages clauses in NDAs are enforceable if: (1) actual damages would be "
            "difficult to calculate at the time of contracting; (2) the stipulated amount is a "
            "reasonable estimate of anticipated harm. Courts will void clauses that function as "
            "penalties (Restatement (Second) of Contracts § 356). Typical NDA liquidated damages "
            "range from $10,000 to $500,000 depending on the nature of the confidential information."
        ),
    },
    {
        "id": "injunctive_relief",
        "keywords": ["injunction", "restraining", "order", "equitable", "nda", "breach"],
        "text": (
            "Courts routinely grant temporary restraining orders (TROs) and preliminary injunctions "
            "for NDA breaches because: (1) confidential information, once disclosed, cannot be "
            "'un-disclosed' — making monetary damages inadequate; (2) irreparable harm is presumed "
            "for trade secret misappropriation in many jurisdictions. The movant must show "
            "likelihood of success on the merits, irreparable harm, balance of equities, and "
            "public interest (Winter v. Natural Resources Defense Council, 2008)."
        ),
    },
    # -----------------------------------------------------------------
    # Bài Tập 2.1: Thêm entry về luật lao động Việt Nam
    # -----------------------------------------------------------------
    {
        "id": "labor_law",
        "keywords": ["lao động", "sa thải", "hợp đồng lao động", "labor", "termination",
                     "wrongful", "employment", "fired", "dismiss"],
        "text": (
            "Theo Bộ luật Lao động Việt Nam 2019 (BLLĐ 2019), người sử dụng lao động có thể "
            "đơn phương chấm dứt hợp đồng trong các trường hợp hợp pháp: (1) người lao động "
            "thường xuyên không hoàn thành công việc theo hợp đồng; (2) bị ốm đau, tai nạn đã "
            "điều trị 12 tháng liên tục (hợp đồng không xác định thời hạn) chưa khỏi; "
            "(3) thiên tai, hỏa hoạn, dịch bệnh — bắt buộc thu hẹp sản xuất sau khi đã tìm "
            "mọi biện pháp khắc phục; (4) người lao động đủ tuổi nghỉ hưu (nam 62, nữ 60 theo "
            "lộ trình). Sa thải trái pháp luật (Điều 41 BLLĐ): người lao động được quyền yêu "
            "cầu nhận lại việc làm, bồi thường 2 tháng lương cho mỗi năm làm việc, và các "
            "khoản lương trong thời gian không được làm việc (tối thiểu 2 tháng)."
        ),
    },
]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def search_legal_database(query: str) -> str:
    """Search the legal knowledge base for relevant statutes, case law, and legal principles.

    Args:
        query: Natural language search query about a legal topic.
    """
    query_words = set(query.lower().split())
    scored = []
    for entry in LEGAL_KNOWLEDGE:
        overlap = len(query_words & set(entry["keywords"]))
        if overlap > 0:
            scored.append((overlap, entry))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:2]
    if not top:
        return "No relevant legal sources found for this query."
    results = []
    for _, entry in top:
        results.append(f"[{entry['id']}] {entry['text']}")
    return "\n\n".join(results)


@tool
def calculate_damages(breach_type: str, contract_value: float) -> str:
    """Calculate estimated damages for a contract breach based on type and contract value.

    Args:
        breach_type: Type of breach — 'willful', 'negligent', or 'standard'.
        contract_value: The monetary value of the contract in USD.
    """
    breach_type_lower = breach_type.lower()
    if "willful" in breach_type_lower or "intentional" in breach_type_lower:
        multiplier = 2.0
        label = "Willful/intentional breach (2x multiplier under DTSA)"
    elif "negligent" in breach_type_lower:
        multiplier = 1.0
        label = "Negligent breach (1x actual damages)"
    else:
        multiplier = 1.5
        label = "Standard breach (1.5x estimated multiplier)"

    base_damages = contract_value * multiplier
    attorney_fees = contract_value * 0.15
    total = base_damages + attorney_fees

    return (
        f"Damage Estimate:\n"
        f"  Breach type: {label}\n"
        f"  Contract value: ${contract_value:,.2f}\n"
        f"  Estimated damages: ${base_damages:,.2f}\n"
        f"  Attorney's fees (~15%): ${attorney_fees:,.2f}\n"
        f"  Total estimated exposure: ${total:,.2f}"
    )


# -----------------------------------------------------------------
# Bài Tập 2.2: Tool kiểm tra thời hiệu khởi kiện
# -----------------------------------------------------------------

@tool
def check_statute_of_limitations(case_type: str) -> str:
    """Kiểm tra thời hiệu khởi kiện (statute of limitations) theo loại vụ án.

    Args:
        case_type: Loại vụ án. Ví dụ: 'contract', 'tort', 'property',
                   'trade_secret', 'nda', 'labor'.
    """
    limits = {
        "contract":      "4 năm — UCC § 2-725 (hàng hóa); 6 năm tại một số bang (dịch vụ).",
        "tort":          "2–3 năm tùy bang; 1 năm cho defamation ở nhiều bang.",
        "property":      "5 năm (trespass); 10 năm (adverse possession) tùy bang.",
        "trade_secret":  "3 năm kể từ ngày phát hiện — DTSA (18 U.S.C. § 1836(d)).",
        "nda":           "3 năm theo DTSA; tính từ ngày vi phạm hoặc ngày phát hiện.",
        "labor":         "Theo BLLĐ 2019 Điều 190: 1 năm kể từ ngày phát sinh tranh chấp "
                         "lao động cá nhân (tính dụng tại tòa án); 6 tháng tại hội đồng trọng tài.",
        "discrimination": "180 ngày nộp khiếu nại lên EEOC (300 ngày nếu có cơ quan tiểu bang).",
        "fraud":          "3–6 năm tùy bang; chạy từ ngày phát hiện gian lận.",
    }
    key = case_type.lower().replace(" ", "_").replace("-", "_")
    if key in limits:
        return f"Thời hiệu khởi kiện cho '{case_type}': {limits[key]}"
    close = [k for k in limits if k in key or key in k]
    if close:
        return f"Thời hiệu khởi kiện cho '{close[0]}': {limits[close[0]]}"
    available = ", ".join(limits.keys())
    return (
        f"Không tìm thấy thời hiệu cho loại vụ án '{case_type}'. "
        f"Các loại hỗ trợ: {available}."
    )


TOOLS = [search_legal_database, calculate_damages, check_statute_of_limitations]

# Đặt câu hỏi bằng tiếng Việt để test toàn bộ knowledge base
QUESTION = (
    "Công ty ABC đã vi phạm NDA (thỏa thuận bảo mật) một cách cố ý, "
    "tiết lộ bí mật thương mại trị giá $200,000. "
    "Hậu quả pháp lý là gì và chúng tôi còn bao nhiêu thời gian để khởi kiện?"
)


async def run_tool_loop(llm_with_tools, messages: list, tool_map: dict, max_rounds: int = 5) -> str:
    """
    Multi-round tool-calling loop.

    Thay vì chỉ 1 pass (Stage 2 gốc), hàm này cho phép LLM tiếp tục
    gọi thêm tools cho đến khi không còn tool_calls nào hoặc đạt max_rounds.
    Điều này giúp LLM có thể tự search → tính toán → check SOL trong 1 run.
    """
    for round_num in range(1, max_rounds + 1):
        response = await llm_with_tools.ainvoke(messages)
        messages.append(response)

        if not response.tool_calls:
            # LLM đã ra kết quả cuối — kết thúc loop
            return response.content

        print(f"\n>>> Round {round_num}: LLM gọi {len(response.tool_calls)} tool(s):\n")
        for tc in response.tool_calls:
            print(f"  Tool : {tc['name']}")
            print(f"  Args : {tc['args']}")

            tool_fn = tool_map[tc["name"]]
            result = await tool_fn.ainvoke(tc["args"])
            preview = result[:300] + ("..." if len(result) > 300 else "")
            print(f"  Kết quả: {preview}\n")

            messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))

    # Nếu vẫn còn tool_calls sau max_rounds, ép LLM trả lời
    final = await llm_with_tools.ainvoke(messages)
    return final.content


async def main():
    print("=" * 70)
    print("STAGE 2: LLM + RAG / Tools  (hoàn chỉnh)")
    print("=" * 70)
    print()
    print("[Kiến thức mới so với Stage 1]")
    print("  1. LLM nhận danh sách tools (search_legal_database, calculate_damages,")
    print("                              check_statute_of_limitations)")
    print("  2. LLM TỰ QUYẾT ĐỊNH gọi tool nào, với argument gì")
    print("  3. Tool được execute — kết quả đưa vào context")
    print("  4. Multi-round loop: LLM có thể gọi nhiều tools liên tiếp")
    print("  5. Câu trả lời cuối được ground trong dữ liệu thực")
    print()
    print("[Tools có sẵn]")
    print("  • search_legal_database       — tra cứu knowledge base pháp lý")
    print("  • calculate_damages           — tính ước lượng thiệt hại")
    print("  • check_statute_of_limitations — kiểm tra thời hiệu khởi kiện")
    print()
    print(f"Câu hỏi: {QUESTION}")
    print("-" * 70)

    llm = get_llm()
    llm_with_tools = llm.bind_tools(TOOLS)
    tool_map = {t.name: t for t in TOOLS}

    messages = [
        SystemMessage(
            content=(
                "You are a senior legal expert with access to a legal knowledge base, "
                "a damage calculator, and a statute-of-limitations checker. "
                "When answering:\n"
                "  1. Always call search_legal_database first to ground your answer.\n"
                "  2. Use calculate_damages when monetary exposure is relevant.\n"
                "  3. Use check_statute_of_limitations when timing questions arise.\n"
                "  4. You MAY call multiple tools before giving your final answer.\n"
                "Keep your final response under 400 words. "
                "Respond in the same language as the user's question."
            )
        ),
        HumanMessage(content=QUESTION),
    ]

    print("\n>>> Bắt đầu multi-round tool loop...\n")
    final_answer = await run_tool_loop(llm_with_tools, messages, tool_map)

    print("\n" + "=" * 70)
    print("KẾT QUẢ CUỐI CÙNG")
    print("=" * 70)
    print(final_answer)

    print()
    print("-" * 70)
    print("[So sánh Stage 1 vs Stage 2]")
    print()
    print("  Stage 1 (Direct LLM)          Stage 2 (RAG + Tools)")
    print("  ──────────────────────────    ─────────────────────────────────")
    print("  Chỉ dựa training data         Tra cứu knowledge base thực tế")
    print("  Không tính toán được          Tính thiệt hại chính xác")
    print("  Không biết thời hiệu          Check SOL theo loại vụ án")
    print("  Có thể hallucinate statute    Cite đúng § cụ thể từ KB")
    print("  1 lần gọi LLM                 Multi-round: search → calc → answer")
    print()
    print("[Hạn chế của Stage 2]")
    print("  - Orchestration vẫn manual (chúng ta viết tool loop)")
    print("  - LLM không tự quyết định 'search lại' nếu kết quả chưa đủ")
    print("  - Không có memory giữa các câu hỏi")
    print()
    print("→ Stage 3 giải quyết bằng ReAct Agent loop tự động.")
    print("=" * 70)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())