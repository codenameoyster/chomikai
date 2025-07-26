"""
MCP Server for Google Slides Integration.

This module provides a Model Context Protocol (MCP) server that exposes
Google Slides functionality to AI models and other MCP-compatible clients.
The server uses FastMCP to provide a simple interface for accessing and
manipulating Google Slides presentations.

Features:
- MCP tools for mathematical operations (demonstration)
- Dynamic resources for personalized greetings (demonstration)
- Extensible architecture for adding Google Slides operations

The current implementation includes basic demonstration tools and can be
extended to include actual Google Slides API operations like:
- Listing presentations
- Reading slide content
- Creating and modifying slides
- Extracting text and images from presentations

Usage:
    This server can be run independently or integrated with other MCP clients
    that need access to Google Slides functionality.
"""

# server.py
from mcp.server.fastmcp import FastMCP

# Create an MCP server
mcp = FastMCP("Demo")


# Add an addition tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


# Add a dynamic greeting resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"
