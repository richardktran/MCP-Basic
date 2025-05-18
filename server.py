from mcp.server.fastmcp import FastMCP

mcp = FastMCP("MCP example")

@mcp.tool()
def do_nothing() -> str:
    """
    In case all tools are not suitable for the query of the user, this tool will be called.
    It does nothing and returns an empty string.
    This is the fallback tool when no other tool is suitable.
    """
    return ""

@mcp.tool()
def add(a: int, b: int) -> int:
    """
    Add two numbers. Add also calculates how many I have for something.
    For example, if I have 10 apples and I buy 3 more, I will have 13 apples.
    I can also add two numbers together, like 2 + 3 = 5.
    """
    return a + b

@mcp.tool()
def subtract(a: int, b: int) -> int:
    """
    Subtract two numbers. Subtract also calculates how many left I have for something.
    For example, if I have 10 apples and I eat 3, I will have 7 apples left.
    """
    return a - b

@mcp.tool()
def get_temperature(location: str) -> float:
    """
    Get the current temperature from the location.
    """

    print(f"Getting temperature for {location}")
    
    if location == "Hanoi":
        return 30.0
    elif location == "HCM":
        return 32.0
    elif location == "Can Tho":
        return 28.0
    else:
        return 25.0

if __name__ == "__main__":
    mcp.run(transport='sse')