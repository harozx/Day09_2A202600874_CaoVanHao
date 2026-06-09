"""Bài Tập 2: Thêm Tools và Knowledge Base

Hoàn thành các TODO để thêm tool và knowledge base entry mới.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from common.llm import get_llm

# Knowledge base
LEGAL_KNOWLEDGE = [
    {
        "id": "ucc_breach",
        "keywords": ["breach", "contract", "remedies", "damages", "ucc"],
        "text": (
            "Under the Uniform Commercial Code (UCC) Article 2, remedies for breach of contract "
            "include: (1) expectation damages; (2) consequential damages; (3) specific performance; "
            "(4) cover damages. Statute of limitations is typically 4 years (UCC § 2-725)."
        ),
    },
    # Bài Tập 2.1: Thêm entry về luật lao động Việt Nam
    {
        "id": "labor_law",
        "keywords": ["lao động", "sa thải", "hợp đồng lao động", "labor", "termination",
                     "wrongful", "employment", "fired", "dismiss"],
        "text": (
            "Theo Bộ luật Lao động Việt Nam 2019 (BLLĐ 2019), người sử dụng lao động có thể "
            "đơn phương chấm dứt hợp đồng trong các trường hợp hợp pháp: (1) người lao động "
            "thường xuyên không hoàn thành công việc theo hợp đồng; (2) bị ốm đau, tai nạn đã "
            "điều trị 12 tháng liên tục chưa khỏi; (3) thiên tai, hỏa hoạn, dịch bệnh — bắt "
            "buộc thu hẹp sản xuất; (4) người lao động đủ tuổi nghỉ hưu. Sa thải trái pháp "
            "luật (Điều 41 BLLĐ): người lao động được quyền yêu cầu nhận lại việc làm, bồi "
            "thường 2 tháng lương cho mỗi năm làm việc, và các khoản lương trong thời gian "
            "không được làm việc (tối thiểu 2 tháng)."
        ),
    },
]


@tool
def search_legal_knowledge(query: str) -> str:
    """Tìm kiếm trong knowledge base pháp lý."""
    query_lower = query.lower()
    for entry in LEGAL_KNOWLEDGE:
        if any(kw in query_lower for kw in entry["keywords"]):
            return f"[{entry['id']}] {entry['text']}"
    return "Không tìm thấy thông tin liên quan."


# Bài Tập 2.2: Tool kiểm tra thời hiệu khởi kiện
@tool
def check_statute_of_limitations(case_type: str) -> str:
    """Kiểm tra thời hiệu khởi kiện theo loại vụ án.

    Args:
        case_type: Loại vụ án (contract, tort, property, labor, nda, trade_secret)
    """
    limits = {
        "contract":     "4 năm — UCC § 2-725 (hàng hóa); 6 năm tại một số bang (dịch vụ).",
        "tort":         "2–3 năm tùy bang; 1 năm cho defamation ở nhiều bang.",
        "property":     "5 năm (trespass); 10 năm (adverse possession) tùy bang.",
        "trade_secret": "3 năm kể từ ngày phát hiện — DTSA (18 U.S.C. § 1836(d)).",
        "nda":          "3 năm theo DTSA; tính từ ngày vi phạm hoặc ngày phát hiện.",
        "labor":        "1 năm kể từ ngày phát sinh tranh chấp lao động cá nhân (BLLĐ 2019 Điều 190); "
                        "6 tháng tại hội đồng trọng tài.",
        "fraud":        "3–6 năm tùy bang; tính từ ngày phát hiện gian lận.",
    }
    key = case_type.lower().replace(" ", "_")
    if key in limits:
        return f"Thời hiệu khởi kiện cho '{case_type}': {limits[key]}"
    available = ", ".join(limits.keys())
    return f"Không tìm thấy thời hiệu cho '{case_type}'. Các loại hỗ trợ: {available}."


async def main():
    load_dotenv()
    llm = get_llm()

    # Bài Tập 2.2: Thêm tool mới vào danh sách
    tools = [search_legal_knowledge, check_statute_of_limitations]
    llm_with_tools = llm.bind_tools(tools)
    tool_map = {t.name: t for t in tools}

    question = "Thời hiệu khởi kiện vụ vi phạm hợp đồng là bao lâu?"

    messages = [
        SystemMessage(content=(
            "Bạn là chuyên gia pháp lý. Sử dụng tools để tra cứu thông tin. "
            "Luôn gọi tool trước khi trả lời."
        )),
        HumanMessage(content=question),
    ]

    print(f"Câu hỏi: {question}\n")

    # First LLM call - decide which tools to use
    response = await llm_with_tools.ainvoke(messages)
    messages.append(response)

    # Execute tools if requested
    if response.tool_calls:
        for tool_call in response.tool_calls:
            print(f"🔧 Gọi tool: {tool_call['name']}({tool_call['args']})")

            tool_fn = tool_map[tool_call["name"]]
            tool_result = await tool_fn.ainvoke(tool_call["args"])
            print(f"   Kết quả: {tool_result[:200]}")
            print()

            messages.append(ToolMessage(content=tool_result, tool_call_id=tool_call["id"]))

        # Second LLM call - synthesize final answer
        final_response = await llm_with_tools.ainvoke(messages)
        print(f"\n✅ Kết quả:\n{final_response.content}")
    else:
        print(f"\n✅ Kết quả:\n{response.content}")


if __name__ == "__main__":
    asyncio.run(main())
