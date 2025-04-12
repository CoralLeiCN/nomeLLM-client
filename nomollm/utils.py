def format_available_tools(tools):
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.inputSchema,
        }
        for tool in tools.tools
    ]
