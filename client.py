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
            api_key="not-needed"  # Local LLMs typically don't need an API key
        )
        self.model = "gemma-3-4b-it"

    async def connect_to_server(self, server_url: str):
        """Connect to an SSE MCP server."""
        print(f"Connecting to SSE MCP server at {server_url}")

        self._streams_context = sse_client(url=server_url)
        streams = await self._streams_context.__aenter__()

        self._session_context = ClientSession(*streams)
        self.session = await self._session_context.__aenter__()

        # Initialize
        await self.session.initialize()
        
        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print(f"Connected to SSE MCP Server at {server_url}. Available tools: {[tool.name for tool in tools]}")
    def parse_tool_for_openai(self, tool: MCPTool) -> OpenAITool:
        """
        Converts a Tool object into OpenAI API-compatible tool format.
        """
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

    async def process_query(self, query: str) -> str:
        """Process a query using local LLM and available tools"""
        messages = [
            {
                "role": "user",
                "content": query
            }
        ]

        response = await self.session.list_tools()
        available_tools = [self.parse_tool_for_openai(tool) for tool in response.tools]


        # Initial LLM API call
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=available_tools,
            max_tokens=1000,
            tool_choice="auto"
        )


        # Process response and handle tool calls
        final_responses = []
        
        message = response.choices[0].message
        if message.content:
            final_responses.append(message.content)
        
        if message.tool_calls:
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                print(f"Tool call: {tool_name} with args: {tool_args}")
                # Execute tool call
                result = await self.session.call_tool(tool_name, tool_args)
                # final_responses.append(f"[Calling tool {tool_name} with args {tool_args}]")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result.content[0].text
                })


                print(f"Tool result: {result.content[0].text}")
                
                tool_result_text = result.content[0].text
                messages.append({
                    "role": "assistant",
                    "content": f"I retrieved the information you requested. {tool_result_text}"
                })

                # Get next response from LLM
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages+ [{
                        "role": "user",
                        "content": "Please provide a natural language response."
                    }],
                    max_tokens=1000
                )

                message = response.choices[0].message

                if message.content:
                    final_responses.append(message.content)

        return "\n".join(final_responses)

    async def chat_loop(self):
        """Run an interactive chat loop"""
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
        """Clean up resources"""
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