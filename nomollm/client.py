# modified from https://modelcontextprotocol.io/quickstart/client
import asyncio
from contextlib import AsyncExitStack
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()  # load environment variables from .env


class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
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
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    async def process_query(self, query: str) -> str:
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
        # Define user prompt
        messages = [
            types.Content(
                role="user",
                parts=[types.Part(text=query)],
            )
        ]
        response = await self.session.list_tools()
        available_tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema,
            }
            for tool in response.tools
        ]

        # Initial LLM API call
        tools = types.Tool(function_declarations=available_tools)
        config = types.GenerateContentConfig(tools=[tools])
        response = self.llm_client.models.generate_content(
            model="gemini-2.0-flash-001",
            contents=messages,
            config=config,
        )
        # Check for a function call
        if response.candidates[0].content.parts[0].function_call:
            function_call = response.candidates[0].content.parts[0].function_call
            print(f"Function to call: {function_call.name}")
            print(f"Arguments: {function_call.args}")
            #  In a real app, you would call your function here:
            #  result = schedule_meeting(**function_call.args)
        else:
            print("No function call found in the response.")
            print(response.text)
        return response.text

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == "quit":
                    break

                response = await self.process_query(query)
                print("\n" + response)

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()


async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)

    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    import sys

    asyncio.run(main())

    # client = MCPClient()
    # client.run()
