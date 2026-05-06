"""Agent WebSocket + REST 路由。"""

from __future__ import annotations

import json
import traceback
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from server.agent.graph import get_graph
from server.agent.memory import session_manager
from server.agent.schemas import (
    ChatRequest,
    ChatResponse,
    ServerFrame,
    SessionInfo,
)

router = APIRouter(prefix="/api/agent", tags=["agent"])


# ───────── 辅助函数 ─────────

def _build_human_message(content: str, images: list[dict] | None = None) -> HumanMessage:
    """构造 HumanMessage，支持可选图片附件。"""
    if not images:
        return HumanMessage(content=content)

    # 多模态消息：文本 + 图片
    blocks: list[dict] = []
    for img in images:
        blocks.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{img.get('media_type', 'image/png')};base64,{img['data']}",
            },
        })
    blocks.append({"type": "text", "text": content})
    return HumanMessage(content=blocks)


def _frame(frame_type: str, **kwargs) -> str:
    """构造 ServerFrame JSON 字符串。"""
    return ServerFrame(type=frame_type, **kwargs).model_dump_json(exclude_none=True)


# ───────── WebSocket 端点 ─────────

@router.websocket("/chat")
async def websocket_chat(ws: WebSocket):
    """流式聊天 WebSocket 端点。

    客户端发送 JSON: {type, session_id, content, images}
    服务端流式返回多帧 JSON。
    """
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_text(_frame("error", error="无效的 JSON 格式"))
                continue

            content = data.get("content", "").strip()
            if not content:
                await ws.send_text(_frame("error", error="消息内容不能为空"))
                continue

            # 会话管理
            session_id = data.get("session_id")
            if not session_id or not session_manager.exists(session_id):
                session_id = session_manager.create_session()
            await ws.send_text(_frame("session_init", session_id=session_id))

            session_manager.touch(session_id)

            # 构造消息
            images = data.get("images")
            human_msg = _build_human_message(content, images)

            # LangGraph 配置（thread_id 用于检查点隔离）
            config = {"configurable": {"thread_id": session_id}}

            try:
                # 流式调用 graph
                await _stream_graph_response(ws, session_id, human_msg, config)
            except Exception as e:
                traceback.print_exc()
                await ws.send_text(_frame("error", error=f"Agent 执行出错: {str(e)}"))

    except WebSocketDisconnect:
        pass
    except Exception:
        traceback.print_exc()


async def _stream_graph_response(
    ws: WebSocket,
    session_id: str,
    human_msg: HumanMessage,
    config: dict,
) -> None:
    """流式执行 graph 并将事件推送到 WebSocket。"""
    graph = get_graph()

    # 用 stream 方法获取事件流
    collected_text = ""

    for event in graph.stream(
        {"messages": [human_msg]},
        config=config,
        stream_mode="updates",
    ):
        # event 是 {node_name: state_update} 的 dict
        for node_name, update in event.items():
            messages = update.get("messages", [])
            for msg in messages:
                if isinstance(msg, AIMessage):
                    # Agent 的文本回复
                    if msg.content and isinstance(msg.content, str):
                        collected_text += msg.content
                        await ws.send_text(_frame(
                            "text_delta",
                            content=msg.content,
                            agent=node_name,
                        ))

                    # Tool calls
                    if msg.tool_calls:
                        for tc in msg.tool_calls:
                            await ws.send_text(_frame(
                                "tool_call",
                                agent=node_name,
                                tool=tc["name"],
                                input=tc["args"],
                            ))

                elif isinstance(msg, ToolMessage):
                    # Tool 执行结果
                    try:
                        result_data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                    except (json.JSONDecodeError, TypeError):
                        result_data = {"raw": str(msg.content)}

                    await ws.send_text(_frame(
                        "tool_result",
                        agent=node_name,
                        tool=msg.name,
                        data=result_data if isinstance(result_data, dict) else {"result": result_data},
                    ))

    # 完成
    await ws.send_text(_frame("done", session_id=session_id))


# ───────── REST 端点 ─────────

@router.post("/chat", response_model=ChatResponse)
def rest_chat(req: ChatRequest) -> ChatResponse:
    """非流式聊天接口（回退方案）。"""
    session_id = req.session_id
    if not session_id or not session_manager.exists(session_id):
        session_id = session_manager.create_session()
    session_manager.touch(session_id)

    human_msg = _build_human_message(req.content, req.images)
    config = {"configurable": {"thread_id": session_id}}

    graph = get_graph()
    result = graph.invoke({"messages": [human_msg]}, config=config)

    # 提取最终文本
    final_text = ""
    tool_calls: list[dict] = []
    for msg in result.get("messages", []):
        if isinstance(msg, AIMessage):
            if msg.content and isinstance(msg.content, str):
                final_text = msg.content  # 取最后一个 AI 消息
            if msg.tool_calls:
                tool_calls.extend(msg.tool_calls)

    return ChatResponse(
        session_id=session_id,
        content=final_text,
        tool_calls=tool_calls,
    )


@router.get("/sessions", response_model=list[SessionInfo])
def list_sessions():
    """列出所有活跃会话。"""
    sessions = session_manager.list_sessions()
    return [SessionInfo(**s) for s in sessions]


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """删除指定会话。"""
    if session_manager.delete(session_id):
        return {"status": "deleted"}
    return {"status": "not_found"}
