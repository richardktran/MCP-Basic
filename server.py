from mcp.server.fastmcp import FastMCP

mcp = FastMCP("MCP example")

@mcp.tool()
def add(a: int, b: int) -> int:
    """
    Add two numbers.
    """
    return a + b

@mcp.tool()
def subtract(a: int, b: int) -> int:
    """
    Subtract two numbers.
    """
    return a - b

@mcp.tool()
def get_temperature(location: str) -> float:
    """
    Get the current temperature from the location.
    """
    return 25.0 

if __name__ == "__main__":
    mcp.run(transport='sse')