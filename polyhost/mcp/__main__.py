"""`python -m polyhost.mcp`: the MCP server over stdio."""
import sys

from polyhost.mcp.server import main

sys.exit(main())
