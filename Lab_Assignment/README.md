# Lab Assignment — Supervisor-Workers Pattern

## Mô tả

Cải tiến hệ thống Multi-Agent từ codelab bằng cách áp dụng **Supervisor-Workers pattern** sử dụng LangGraph.

### Kiến trúc

```
User Question
      │
      ▼
┌─────────────┐
│  Supervisor  │  ← Quyết định route + tổng hợp kết quả
└──────┬──────┘
       │ dispatch (song song)
  ┌────┼────┬────────┐
  ▼    ▼    ▼        ▼
┌───┐┌───┐┌────┐┌────────┐
│Law││Tax││Comp││Privacy │  ← Workers chuyên biệt
└───┘└───┘└────┘└────────┘
  │    │    │        │
  └────┴────┴────────┘
       │
       ▼
┌─────────────┐
│  Supervisor  │  ← Tổng hợp & trả lời
└─────────────┘
```

### Workers (3 workers):
1. **LawWorker** — Phân tích pháp lý tổng quát
2. **TaxWorker** — Phân tích thuế
3. **ComplianceWorker** — Phân tích tuân thủ pháp luật & bảo mật dữ liệu

## Cách chạy

```bash
cd Lab_Assignment
uv run python main.py
```

## So sánh với Stage 4 (codelab)

| Tiêu chí | Stage 4 (Flat) | Supervisor-Workers |
|----------|----------------|--------------------|
| Routing | Keyword-based conditional edges | Supervisor LLM quyết định |
| Tổng hợp | Hàm aggregate cố định | Supervisor tổng hợp thông minh |
| Mở rộng | Thêm node + edge thủ công | Chỉ cần thêm worker vào registry |
| Fault tolerance | Crash nếu worker lỗi | Supervisor xử lý graceful |
