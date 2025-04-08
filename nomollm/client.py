# modified from https://modelcontextprotocol.io/quickstart/client
from google import genai
from google.genai import types

import asyncio
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from dotenv import load_dotenv


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


if __name__ == "__main__":
    client = MCPClient()
    client.run()
