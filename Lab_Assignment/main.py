"""
Lab Assignment — Supervisor-Workers Multi-Agent System
======================================================

Cải tiến hệ thống Multi-Agent (Day09) sử dụng pattern Supervisor-Workers.

Supervisor:
    - Phân tích câu hỏi và quyết định gửi cho worker(s) nào
    - Tổng hợp kết quả từ tất cả workers thành câu trả lời cuối cùng
    - Xử lý graceful khi worker gặp lỗi

Workers (3 workers):
    1. LawWorker     — Phân tích hợp đồng, trách nhiệm dân sự
    2. TaxWorker     — Phân tích thuế, hình phạt IRS
    3. ComplianceWorker — Phân tích tuân thủ (SOX, GDPR, CCPA) + privacy

Pattern: Supervisor dispatches → Workers chạy song song → Supervisor tổng hợp
"""

import asyncio
import os
import sys
import time

# Cho phép import common/ từ thư mục cha
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.types import Send
from typing import Annotated, TypedDict

from common.llm import get_llm


# ============================================================================
# STATE
# ============================================================================

def _last_wins(left: str | None, right: str | None) -> str:
    """Reducer: giá trị mới ghi đè giá trị cũ."""
    return right if right is not None else (left or "")


class SupervisorState(TypedDict):
    question: str
    # Supervisor routing decisions
    dispatch_plan: str
    needs_law: bool
    needs_tax: bool
    needs_compliance: bool
    # Worker results (Annotated để nhiều workers ghi song song không conflict)
    law_result: Annotated[str, _last_wins]
    tax_result: Annotated[str, _last_wins]
    compliance_result: Annotated[str, _last_wins]
    # Final output
    final_answer: str


# ============================================================================
# SUPERVISOR NODE: PLAN (phân tích câu hỏi → quyết định workers)
# ============================================================================

async def supervisor_plan(state: SupervisorState) -> dict:
    """
    Supervisor phân tích câu hỏi và quyết định cần gọi worker(s) nào.

    Dùng LLM để phân loại — linh hoạt hơn keyword matching.
    Output: JSON chỉ định workers cần gọi.
    """
    print("\n" + "=" * 70)
    print("🧠 SUPERVISOR: Đang phân tích câu hỏi...")
    print("=" * 70)

    llm = get_llm(max_tokens=256)
    prompt = f"""Bạn là Supervisor của hệ thống multi-agent pháp lý.

Phân tích câu hỏi sau và quyết định cần gọi worker(s) nào:

Câu hỏi: {state["question"]}

Các workers có sẵn:
- law: phân tích hợp đồng, trách nhiệm dân sự, bồi thường
- tax: phân tích thuế, IRS, trốn thuế, offshore
- compliance: phân tích tuân thủ pháp luật, GDPR, CCPA, SOX, bảo mật dữ liệu

Trả lời CHÍNH XÁC theo format (không giải thích thêm):
law=yes/no
tax=yes/no
compliance=yes/no
reason=<lý do ngắn gọn>"""

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    plan = response.content.strip()
    print(f"\n📋 Dispatch Plan:\n{plan}\n")

    # Parse kết quả
    plan_lower = plan.lower()
    needs_law = "law=yes" in plan_lower
    needs_tax = "tax=yes" in plan_lower
    needs_compliance = "compliance=yes" in plan_lower

    # Nếu LLM không chọn worker nào → mặc định gọi law
    if not (needs_law or needs_tax or needs_compliance):
        needs_law = True
        print("  ⚠ Không có worker nào được chọn → mặc định: law")

    selected = []
    if needs_law:
        selected.append("law_worker")
    if needs_tax:
        selected.append("tax_worker")
    if needs_compliance:
        selected.append("compliance_worker")
    print(f"  → Workers được dispatch: {', '.join(selected)}")

    return {
        "dispatch_plan": plan,
        "needs_law": needs_law,
        "needs_tax": needs_tax,
        "needs_compliance": needs_compliance,
    }


# ============================================================================
# ROUTING FUNCTION (Send API để chạy workers song song)
# ============================================================================

def dispatch_workers(state: SupervisorState) -> list[Send]:
    """Dispatch parallel Send objects đến các workers được chọn."""
    sends: list[Send] = []

    if state.get("needs_law"):
        sends.append(Send("law_worker", state))
    if state.get("needs_tax"):
        sends.append(Send("tax_worker", state))
    if state.get("needs_compliance"):
        sends.append(Send("compliance_worker", state))

    if not sends:
        sends.append(Send("supervisor_aggregate", state))

    return sends


# ============================================================================
# WORKER 1: LAW
# ============================================================================

async def law_worker(state: SupervisorState) -> dict:
    """Worker chuyên phân tích pháp lý tổng quát."""
    print("\n  ⚖️  [LawWorker] Đang phân tích pháp lý...")
    llm = get_llm(max_tokens=512)

    prompt = f"""Bạn là luật sư chuyên về hợp đồng và trách nhiệm dân sự.

Phân tích câu hỏi pháp lý sau:
{state["question"]}

Tập trung vào:
- Các quy định pháp luật liên quan (dẫn chiếu điều luật cụ thể)
- Trách nhiệm dân sự và hình sự
- Quyền và nghĩa vụ của các bên
- Án lệ liên quan (nếu có)

Giữ phân tích dưới 300 từ. Trả lời bằng cùng ngôn ngữ với câu hỏi."""

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    print(f"  ⚖️  [LawWorker] Hoàn thành ({len(response.content)} ký tự)")
    return {"law_result": response.content}


# ============================================================================
# WORKER 2: TAX
# ============================================================================

async def tax_worker(state: SupervisorState) -> dict:
    """Worker chuyên phân tích thuế."""
    print("\n  💰 [TaxWorker] Đang phân tích thuế...")
    llm = get_llm(max_tokens=512)

    prompt = f"""Bạn là chuyên gia thuế có kinh nghiệm với IRS và luật thuế quốc tế.

Phân tích khía cạnh thuế trong câu hỏi sau:
{state["question"]}

Tập trung vào:
- Vi phạm thuế cụ thể (tax evasion, tax fraud, failure to file)
- Hình phạt theo IRC (26 U.S.C.): phạt tiền, phạt tù
- FBAR/FATCA nếu liên quan đến offshore
- Trách nhiệm cá nhân của officers (responsible person liability)
- Các chương trình voluntary disclosure

Giữ phân tích dưới 300 từ. Trả lời bằng cùng ngôn ngữ với câu hỏi."""

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    print(f"  💰 [TaxWorker] Hoàn thành ({len(response.content)} ký tự)")
    return {"tax_result": response.content}


# ============================================================================
# WORKER 3: COMPLIANCE (bao gồm cả Privacy)
# ============================================================================

async def compliance_worker(state: SupervisorState) -> dict:
    """Worker chuyên phân tích tuân thủ pháp luật và bảo mật dữ liệu."""
    print("\n  🔒 [ComplianceWorker] Đang phân tích tuân thủ & bảo mật...")
    llm = get_llm(max_tokens=512)

    prompt = f"""Bạn là chuyên gia compliance và data privacy.

Phân tích khía cạnh tuân thủ pháp luật trong câu hỏi sau:
{state["question"]}

Tập trung vào:
- Regulatory compliance: SOX, SEC, FCPA, AML/BSA
- Data privacy: GDPR (phạt 4% doanh thu), CCPA ($7,500/vi phạm)
- Luật An ninh mạng Việt Nam 2018, Nghị định 13/2023
- Nghĩa vụ báo cáo (reporting obligations)
- Khuyến nghị remediation

Giữ phân tích dưới 300 từ. Trả lời bằng cùng ngôn ngữ với câu hỏi."""

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    print(f"  🔒 [ComplianceWorker] Hoàn thành ({len(response.content)} ký tự)")
    return {"compliance_result": response.content}


# ============================================================================
# SUPERVISOR NODE: AGGREGATE (tổng hợp kết quả từ workers)
# ============================================================================

async def supervisor_aggregate(state: SupervisorState) -> dict:
    """
    Supervisor tổng hợp kết quả từ tất cả workers thành câu trả lời cuối.

    Khác với aggregate thông thường:
    - Supervisor đánh giá chất lượng từng worker result
    - Loại bỏ thông tin trùng lặp
    - Tổng hợp thành báo cáo có cấu trúc
    """
    print("\n" + "=" * 70)
    print("🧠 SUPERVISOR: Đang tổng hợp kết quả từ workers...")
    print("=" * 70)

    llm = get_llm(max_tokens=1024)

    sections = []
    worker_count = 0

    if state.get("law_result"):
        sections.append(f"## Phân tích Pháp lý (LawWorker)\n{state['law_result']}")
        worker_count += 1
    if state.get("tax_result"):
        sections.append(f"## Phân tích Thuế (TaxWorker)\n{state['tax_result']}")
        worker_count += 1
    if state.get("compliance_result"):
        sections.append(f"## Phân tích Tuân thủ & Bảo mật (ComplianceWorker)\n{state['compliance_result']}")
        worker_count += 1

    combined = "\n\n---\n\n".join(sections)
    print(f"  Nhận kết quả từ {worker_count} worker(s)")

    prompt = f"""Bạn là Supervisor tổng hợp kết quả từ các worker agents.

Câu hỏi gốc: {state["question"]}

Kết quả từ các workers:
{combined}

Hãy tổng hợp thành một báo cáo pháp lý hoàn chỉnh:
1. Tóm tắt vấn đề
2. Phân tích chi tiết (gộp các khía cạnh, loại bỏ trùng lặp)
3. Khuyến nghị hành động
4. Disclaimer

Giữ dưới 500 từ. Trả lời bằng cùng ngôn ngữ với câu hỏi."""

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    print(f"  ✅ Supervisor tổng hợp hoàn thành ({len(response.content)} ký tự)")
    return {"final_answer": response.content}


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

def build_supervisor_graph():
    """Xây dựng Supervisor-Workers graph."""
    graph = StateGraph(SupervisorState)

    # Nodes
    graph.add_node("supervisor_plan", supervisor_plan)
    graph.add_node("law_worker", law_worker)
    graph.add_node("tax_worker", tax_worker)
    graph.add_node("compliance_worker", compliance_worker)
    graph.add_node("supervisor_aggregate", supervisor_aggregate)

    # Edges
    graph.set_entry_point("supervisor_plan")

    # Supervisor → dispatch workers (song song qua Send API)
    graph.add_conditional_edges(
        "supervisor_plan",
        dispatch_workers,
        ["law_worker", "tax_worker", "compliance_worker", "supervisor_aggregate"],
    )

    # Workers → Supervisor aggregate
    graph.add_edge("law_worker", "supervisor_aggregate")
    graph.add_edge("tax_worker", "supervisor_aggregate")
    graph.add_edge("compliance_worker", "supervisor_aggregate")
    graph.add_edge("supervisor_aggregate", END)

    return graph.compile()


# ============================================================================
# MAIN
# ============================================================================

async def main():
    load_dotenv()

    questions = [
        "If a company breaks a contract and avoids taxes, what are the legal and regulatory consequences?",
        "Nếu công ty bị rò rỉ dữ liệu khách hàng và trốn thuế, hậu quả pháp lý là gì?",
    ]

    graph = build_supervisor_graph()

    for i, question in enumerate(questions, 1):
        print("\n" + "█" * 70)
        print(f"  TEST {i}/{len(questions)}")
        print("█" * 70)
        print(f"\n❓ Câu hỏi: {question}\n")

        start = time.time()

        result = await graph.ainvoke({
            "question": question,
            "dispatch_plan": "",
            "needs_law": False,
            "needs_tax": False,
            "needs_compliance": False,
            "law_result": "",
            "tax_result": "",
            "compliance_result": "",
            "final_answer": "",
        })

        elapsed = time.time() - start

        print("\n" + "=" * 70)
        print("📝 KẾT QUẢ CUỐI CÙNG")
        print("=" * 70)
        print(result["final_answer"])

        print(f"\n⏱  Thời gian xử lý: {elapsed:.2f}s")
        print("\n[Workers đã gọi]")
        if result.get("law_result"):
            print("  ✅ LawWorker")
        if result.get("tax_result"):
            print("  ✅ TaxWorker")
        if result.get("compliance_result"):
            print("  ✅ ComplianceWorker")
        print("=" * 70)

        if i < len(questions):
            print("\n⏳ Chuyển câu hỏi tiếp theo...\n")


if __name__ == "__main__":
    asyncio.run(main())
