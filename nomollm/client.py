# modified from https://modelcontextprotocol.io/quickstart/client
import asyncio
import itertools
from contextlib import AsyncExitStack
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from utils import format_available_tools

load_dotenv()  # load environment variables from .env


class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.sessions: list[ClientSession] = []
        self.exit_stack = AsyncExitStack()
        self.llm_client = genai.Client()

    # methods will go here

    def run(self):
        response = self.llm_client.models.generate_content(
            model="gemini-2.0-flash-001", contents="Why is the sky blue?"
        )
        print(response.text)

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        is_python = server_script_path.endswith(".py")
        is_js = server_script_path.endswith(".js")
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command, args=[server_script_path], env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.stdio, self.write = stdio_transport
        self.sessions.append(
            await self.exit_stack.enter_async_context(
                ClientSession(self.stdio, self.write)
            )
        )
        await self.sessions[-1].initialize()

        # List available tools
        response = await self.sessions[-1].list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

        # get all tools, store in a paired dictionary, key: function name, value: session
        available_tools = {}
        for session in self.sessions:
            response = await session.list_tools()
            tools = response.tools
            for tool in tools:
                available_tools[tool.name] = session
        print("\nCurrently available tools", list(available_tools.keys()))

    async def process_query(self, query: str, contents_history=None) -> str:
        """
        https://modelcontextprotocol.io/docs/concepts/tools#tool-definition-structure
        {
        name: string;          // Unique identifier for the tool
        description?: string;  // Human-readable description
        inputSchema: {         // JSON Schema for the tool's parameters
            type: "object",
            properties: { ... }  // Tool-specific parameters
        }


        Process a query using Claude and available tools
        """
        # if not new conversation
        if contents_history:
            contents = contents_history
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part(text=query)],
                )
            )
        # a new conversation
        else:
            # Define user prompt
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part(text=query)],
                )
            ]
        available_tools = []
        for session in self.sessions:
            tools = await session.list_tools()
        available_tools.append(format_available_tools(tools))

        available_tools = list(itertools.chain.from_iterable(available_tools))
        print(f"fetched tools from server: {available_tools}")
        # Initial LLM API call
        tools = types.Tool(function_declarations=available_tools)
        config = types.GenerateContentConfig(tools=[tools])
        response = self.llm_client.models.generate_content(
            model="gemini-2.0-flash-001",
            contents=contents,
            config=config,
        )
        # Check for a function call
        if response.function_calls:
            print("No function call found in the response.")
            print(response.text)

            for tool_call in response.function_calls:
                # for each tool_call
                tool_name = tool_call.name
                tool_args = tool_call.args

                print(f"Function to call: {tool_name}")
                print(f"Arguments: {tool_args}")

                result = await self.sessions.call_tool(tool_name, tool_args)

                function_response_part = types.Part.from_function_response(
                    name=tool_name,
                    response={"result": result},
                )
                # Append function call and result of the function execution to contents
                contents.append(
                    types.Content(
                        role="model", parts=[types.Part(function_call=tool_call)]
                    )
                )  # Append the model's function call message
                contents.append(
                    types.Content(role="user", parts=[function_response_part])
                )  # Append the function response

            final_response = self.llm_client.models.generate_content(
                model="gemini-2.0-flash",
                contents=contents,
                config=config,
            )
            contents.append(
                types.Content(
                    role="model", parts=[types.Part(text=final_response.text)]
                )
            )  # append the final response

        else:
            print("No function call found in the response.")
            print(response.text)
            contents.append(
                types.Content(role="model", parts=[types.Part(text=response.text)])
            )
            return response.text, contents
        return final_response.text, contents

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries, 'new' to start the new chat, or 'quit' to exit.")
        contents_history = None
        while True:
            # try:
            query = input("\nQuery: ").strip()

            if query.lower() == "quit":
                break
            elif query.lower() == "new":
                print("\nStarting a new conversation...")
                contents_history = None
                continue
            else:
                response, contents_history = await self.process_query(
                    query, contents_history
                )

            print("\n" + response)

            # except Exception as e:
            #     print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()


async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)

    client = MCPClient()
    try:
        print(f"there are {len(sys.argv)} mcp servers")
        for i in range(1, len(sys.argv)):
            print(f"connecting to {sys.argv[i]}")
            await client.connect_to_server(sys.argv[i])
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    import sys

    asyncio.run(main())

    # client = MCPClient()
    # client.run()
