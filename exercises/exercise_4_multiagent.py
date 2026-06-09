"""Bài Tập 4: Thêm Privacy Agent vào Multi-Agent System

Hoàn thành các TODO để thêm privacy agent và conditional routing.
"""

import asyncio
import os
import sys
from typing import Annotated, TypedDict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from common.llm import get_llm


def _last_wins(left: str | None, right: str | None) -> str:
    """Reducer: giá trị mới ghi đè giá trị cũ."""
    return right if right is not None else (left or "")


class State(TypedDict):
    question: str
    law_analysis: Annotated[str, _last_wins]
    tax_analysis: Annotated[str, _last_wins]
    compliance_analysis: Annotated[str, _last_wins]
    privacy_analysis: Annotated[str, _last_wins]
    final_response: str


def law_agent(state: State) -> dict:
    """Agent phân tích pháp lý tổng quát."""
    print("  [Node: law_agent] Đang phân tích pháp lý...")
    llm = get_llm()
    prompt = f"""Bạn là chuyên gia pháp lý. Phân tích câu hỏi sau:

{state['question']}

Tập trung vào: hợp đồng, trách nhiệm dân sự, quyền và nghĩa vụ pháp lý.
Giữ phân tích dưới 200 từ."""

    response = llm.invoke([HumanMessage(content=prompt)])
    print(f"  [Node: law_agent] Hoàn thành ({len(response.content)} ký tự)")
    return {"law_analysis": response.content}


def check_routing(state: State) -> dict:
    """Pass-through node — routing logic is handled by the conditional edge."""
    print("\n  [Node: check_routing] Đang xác định specialists cần thiết...")
    return {}  # Nothing to update, just a routing checkpoint


def route_to_specialists(state: State) -> list[Send]:
    """Conditional edge function: dispatch Send objects to specialist nodes."""
    question_lower = state["question"].lower()
    tasks = []

    if any(kw in question_lower for kw in ["tax", "irs", "thuế"]):
        print("  [Routing] → tax_agent")
        tasks.append(Send("tax_agent", state))

    if any(kw in question_lower for kw in ["compliance", "sec", "regulation", "tuân thủ"]):
        print("  [Routing] → compliance_agent")
        tasks.append(Send("compliance_agent", state))

    # Bài Tập 4.2: Conditional routing cho privacy_agent
    if any(kw in question_lower for kw in ["data", "privacy", "gdpr", "dữ liệu",
                                            "rò rỉ", "bảo mật", "ccpa", "personal"]):
        print("  [Routing] → privacy_agent")
        tasks.append(Send("privacy_agent", state))

    if not tasks:
        print("  [Routing] → aggregate_results (không có specialist nào)")
        tasks.append(Send("aggregate_results", state))

    return tasks


def tax_agent(state: State) -> dict:
    """Agent chuyên về thuế."""
    print("  [Node: tax_agent] Đang phân tích thuế...")
    llm = get_llm()
    prompt = f"""Bạn là chuyên gia thuế. Phân tích khía cạnh thuế trong câu hỏi:

Câu hỏi: {state['question']}
Phân tích pháp lý: {state.get('law_analysis', 'N/A')}

Tập trung: IRS, tax evasion, penalties, FBAR, FATCA.
Giữ phân tích dưới 200 từ."""

    response = llm.invoke([HumanMessage(content=prompt)])
    print(f"  [Node: tax_agent] Hoàn thành ({len(response.content)} ký tự)")
    return {"tax_analysis": response.content}


def compliance_agent(state: State) -> dict:
    """Agent chuyên về compliance."""
    print("  [Node: compliance_agent] Đang phân tích tuân thủ...")
    llm = get_llm()
    prompt = f"""Bạn là chuyên gia compliance. Phân tích khía cạnh tuân thủ:

Câu hỏi: {state['question']}
Phân tích pháp lý: {state.get('law_analysis', 'N/A')}

Tập trung: SEC, SOX, FCPA, AML, regulatory violations.
Giữ phân tích dưới 200 từ."""

    response = llm.invoke([HumanMessage(content=prompt)])
    print(f"  [Node: compliance_agent] Hoàn thành ({len(response.content)} ký tự)")
    return {"compliance_analysis": response.content}


# Bài Tập 4.1: Implement privacy_agent
def privacy_agent(state: State) -> dict:
    """Agent chuyên về bảo vệ dữ liệu cá nhân và GDPR."""
    print("  [Node: privacy_agent] Đang phân tích data privacy...")
    llm = get_llm()
    prompt = f"""Bạn là chuyên gia về GDPR và luật bảo vệ dữ liệu cá nhân.

Câu hỏi gốc: {state['question']}
Phân tích pháp lý: {state.get('law_analysis', 'N/A')}

Hãy phân tích các vấn đề về privacy và data protection, bao gồm:
- GDPR (nếu liên quan đến EU): phạt đến 4% doanh thu toàn cầu hoặc €20M
- CCPA/CPRA (nếu liên quan đến California): phạt $7,500/vi phạm cố ý
- Luật An ninh mạng Việt Nam 2018 và Nghị định 13/2023 về bảo vệ dữ liệu cá nhân
- Quyền của người dùng bị ảnh hưởng (right to be informed, right to erasure)
- Nghĩa vụ thông báo vi phạm dữ liệu (data breach notification)
Giữ phân tích dưới 200 từ."""

    response = llm.invoke([HumanMessage(content=prompt)])
    print(f"  [Node: privacy_agent] Hoàn thành ({len(response.content)} ký tự)")
    return {"privacy_analysis": response.content}


def aggregate_results(state: State) -> dict:
    """Tổng hợp kết quả từ tất cả agents."""
    print("\n  [Node: aggregate_results] Đang tổng hợp...")
    llm = get_llm()

    sections = []
    if state.get("law_analysis"):
        sections.append(f"📋 PHÂN TÍCH PHÁP LÝ:\n{state['law_analysis']}")
    if state.get("tax_analysis"):
        sections.append(f"💰 PHÂN TÍCH THUẾ:\n{state['tax_analysis']}")
    if state.get("compliance_analysis"):
        sections.append(f"✅ PHÂN TÍCH TUÂN THỦ:\n{state['compliance_analysis']}")
    # Bài Tập 4: Thêm privacy_analysis vào sections
    if state.get("privacy_analysis"):
        sections.append(f"🔒 PHÂN TÍCH BẢO MẬT DỮ LIỆU:\n{state['privacy_analysis']}")

    combined = "\n\n".join(sections)

    prompt = f"""Tổng hợp các phân tích sau thành một báo cáo pháp lý hoàn chỉnh:

{combined}

Câu hỏi gốc: {state['question']}

Hãy tạo một báo cáo ngắn gọn, có cấu trúc rõ ràng, dưới 500 từ."""

    response = llm.invoke([HumanMessage(content=prompt)])
    print(f"  [Node: aggregate_results] Hoàn thành ({len(response.content)} ký tự)")
    return {"final_response": response.content}


def build_graph() -> StateGraph:
    """Xây dựng multi-agent graph."""
    graph = StateGraph(State)

    # Add nodes
    graph.add_node("law_agent", law_agent)
    graph.add_node("check_routing", check_routing)
    graph.add_node("tax_agent", tax_agent)
    graph.add_node("compliance_agent", compliance_agent)
    # Bài Tập 4: Thêm privacy_agent node
    graph.add_node("privacy_agent", privacy_agent)
    graph.add_node("aggregate_results", aggregate_results)

    # Define edges
    graph.add_edge(START, "law_agent")
    graph.add_edge("law_agent", "check_routing")
    graph.add_conditional_edges(
        "check_routing",
        route_to_specialists,
        ["tax_agent", "compliance_agent", "privacy_agent", "aggregate_results"],
    )
    graph.add_edge("tax_agent", "aggregate_results")
    graph.add_edge("compliance_agent", "aggregate_results")
    # Bài Tập 4: Edge từ privacy_agent đến aggregate_results
    graph.add_edge("privacy_agent", "aggregate_results")
    graph.add_edge("aggregate_results", END)

    return graph.compile()


async def main():
    load_dotenv()

    # Test với câu hỏi có liên quan đến privacy + thuế
    question = "Nếu công ty bị rò rỉ dữ liệu khách hàng, hậu quả pháp lý và thuế là gì?"

    print("=" * 70)
    print("MULTI-AGENT SYSTEM với Privacy Agent")
    print("=" * 70)
    print(f"\nCâu hỏi: {question}\n")

    print("[Graph topology]")
    print("  law_agent → check_routing → [tax + privacy] (song song) → aggregate → END")
    print()
    print("Đang xử lý qua các agents...\n")

    graph = build_graph()

    result = await graph.ainvoke({
        "question": question,
        "law_analysis": "",
        "tax_analysis": "",
        "compliance_analysis": "",
        "privacy_analysis": "",
        "final_response": "",
    })

    print("\n" + "=" * 70)
    print("KẾT QUẢ CUỐI CÙNG")
    print("=" * 70)
    print(result["final_response"])

    print()
    print("-" * 70)
    print("[Agents đã được gọi]")
    if result.get("law_analysis"):
        print("  ✅ law_agent")
    if result.get("tax_analysis"):
        print("  ✅ tax_agent")
    if result.get("compliance_analysis"):
        print("  ✅ compliance_agent")
    if result.get("privacy_analysis"):
        print("  ✅ privacy_agent")
    print("  ✅ aggregate_results")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
