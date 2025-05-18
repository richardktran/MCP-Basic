import asyncio
import json
from openai import AsyncOpenAI
from mcp import ClientSession
from mcp.client.sse import sse_client
from contextlib import AsyncExitStack
from mcp.types import Tool as MCPTool
from openai.types.chat import ChatCompletionToolParam as OpenAITool
from openai.types import FunctionDefinition as OpenAIFunctionDefinition


class MCPClient:
    def __init__(self):
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.client = AsyncOpenAI(
            base_url="http://127.0.0.1:1234/v1",
            api_key="not-needed"
        )
        self.model = "gemma-3-4b-it"

    async def connect_to_server(self, server_url: str):
        print(f"Connecting to SSE MCP server at {server_url}")

        self._streams_context = sse_client(url=server_url)
        streams = await self._streams_context.__aenter__()

        self._session_context = ClientSession(*streams)
        self.session = await self._session_context.__aenter__()

        await self.session.initialize()

        response = await self.session.list_tools()
        tools = response.tools
        print(f"Connected to SSE MCP Server at {server_url}. Available tools: {[tool.name for tool in tools]}")

    def parse_tool_for_openai(self, tool: MCPTool) -> OpenAITool:
        return OpenAITool(
            type="function",
            function=OpenAIFunctionDefinition(
                name=tool.name,
                description=tool.description.strip(),
                parameters={
                    "type": "object",
                    "properties": tool.inputSchema.get("properties", {}),
                    "required": tool.inputSchema.get("required", [])
                }
            )
        )

    def format_tool_result(self, tool_name: str, tool_args: dict, raw_result: str) -> str:
        args_string = ", ".join(f"{k}={v}" for k, v in tool_args.items())
        return f"Tool '{tool_name}' was called with arguments ({args_string}) and returned: {raw_result}"

    async def process_query(self, query: str) -> str:
        messages = [
            {
                "role": "user",
                "content": (
                    "You can use one or more tools step by step to solve this problem. "
                    "If you already get a tool result, do not call the same tool again with the same arguments. "
                    "Please give me the final answer when enough information is available. "
                    "Now answer this: " + query
                )
            }
        ]

        response = await self.session.list_tools()
        available_tools = [self.parse_tool_for_openai(tool) for tool in response.tools]

        final_responses = []
        called_tools = set()

        while True:
            # Gọi model
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=available_tools,
                max_tokens=1000,
                tool_choice="auto"
            )

            message = response.choices[0].message

            # Nếu có nội dung văn bản trả lời thì lưu lại
            if message.content:
                final_responses.append(message.content)

            # Nếu không có tool call nào nữa thì thoát vòng lặp
            if not message.tool_calls:
                break

            # Có tool call → xử lý từng cái
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                # Tránh lặp lại cùng một tool với cùng args
                tool_call_key = (tool_name, json.dumps(tool_args, sort_keys=True))
                if tool_call_key in called_tools:
                    print(f"Skipping duplicate tool call: {tool_call_key}")
                    continue
                called_tools.add(tool_call_key)

                print(f"Calling tool: {tool_name} with args: {tool_args}")
                result = await self.session.call_tool(tool_name, tool_args)
                raw_result = result.content[0].text
                tool_result_text = self.format_tool_result(tool_name, tool_args, raw_result)
                print(f"Tool result: {tool_result_text}")

                # Gửi tool result về lại model
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result_text
                })
                
        messages.append({
            "role": "user",
            "content": "Now, based on the previous question and the tool results above, please give me the final answer in natural language."
        })

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=1000
            )
            final_message = response.choices[0].message
            if final_message.content:
                final_responses.append(final_message.content)
        except Exception as e:
            print("Error while summarizing:", e)

        # ✅ Fallback nếu tất cả đều fail
        if not final_responses:
            return "Sorry, I could not find an answer to your question."

        return "\n".join(final_responses)

    async def chat_loop(self):
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == 'quit':
                    break

                response = await self.process_query(query)
                print("\n" + response)

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        await self.client.close()
        await self.exit_stack.aclose()


async def main():
    client = MCPClient()
    try:
        await client.connect_to_server("http://localhost:8000/sse")
        await client.chat_loop()
    finally:
        await client.cleanup()
        print("\nMCP Client Closed!")


if __name__ == "__main__":
    asyncio.run(main())
