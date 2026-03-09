#!/usr/bin/env python3

"""
Optional MCP External Policy Script
===================================

This script allows administrators to implement custom policy logic
that overrides or extends the static YAML policy evaluated by the MCP wrapper.

The wrapper sends a JSON payload via STDIN containing:

- request_context → original MCP request
- policy_context → precomputed static policy result

This script can:

1. Accept the static decision
2. Override the decision
3. Apply additional checks based on:
   - parameters
   - identity
   - metadata
   - time of day
   - external services
   - approval workflows

Communication model:
STDIN  → request JSON
STDOUT → decision JSON

The returned JSON must include:

{
  "decision": "allow|deny|require_approval",
  "reason": "...",
  "reason_code": "..."
}

Unknown fields are allowed and will be ignored by the wrapper.
"""

import sys
import json


# ==========================================================
# Request context helper
# ==========================================================

class RequestContext:
    """
    Helper class to simplify access to request fields.
    """

    def __init__(self, request_data):

        self.raw = request_data

        self.mcp = request_data.get("mcp_context", {})
        self.identity = request_data.get("identity_context", {})
        self.metadata = request_data.get("metadata", {})

        self.method = self.mcp.get("method", "")
        self.name = self.mcp.get("name", "")
        self.parameters = self.mcp.get("parameters", {})

    def get_parameters(self):
        return self.parameters


# ==========================================================
# Fallback to static decision
# ==========================================================

def process_defaults(static_result):
    """
    Returns the decision already computed by the static YAML policy.

    This keeps the external script simple because it does not need to
    reimplement the static capability matrix.
    """
    return static_result


# ==========================================================
# Main script logic
# ==========================================================

def main():

    try:
        raw_input = sys.stdin.read()
        data = json.loads(raw_input)

    except Exception:

        result = {
            "decision": "deny",
            "reason_code": "INVALID_INPUT",
            "reason": "External policy script received invalid JSON input."
        }

        print(json.dumps(result))
        return


    request_context = data.get("request_context", {})
    policy_context = data.get("policy_context", {})

    static_result = policy_context.get("precomputed_result", {})

    ctx = RequestContext(request_context)


    # ======================================================
    # Custom policy overrides
    # ======================================================

    match ctx.name:


        # --------------------------------------------------
        # Example: emergency override
        # --------------------------------------------------
        # Tool execution allowed only if parameter "priority"
        # is set to "emergency"
        #
        # Example request:
        #
        # {
        #   "method": "tools/call",
        #   "name": "tool.tool_2",
        #   "parameters": {
        #       "priority": "emergency"
        #   }
        # }

        case "tool.tool_2":

            params = ctx.get_parameters()

            if params.get("priority") == "emergency":

                result = {
                    "decision": "allow",
                    "reason_code": "EMERGENCY_OVERRIDE",
                    "reason": "Emergency override granted."
                }

            else:

                result = {
                    "decision": "deny",
                    "reason_code": "NON_EMERGENCY_BLOCKED",
                    "reason": "Tool requires emergency priority."
                }


        # --------------------------------------------------
        # Example: role-based access control
        # --------------------------------------------------

        case "tool.delete_volume":

            groups = ctx.identity.get("groups", [])

            if "storage-admin" in groups:

                result = {
                    "decision": "allow",
                    "reason_code": "RBAC_ALLOW",
                    "reason": "User belongs to storage-admin group."
                }

            else:

                result = {
                    "decision": "deny",
                    "reason_code": "RBAC_DENY",
                    "reason": "User is not authorized to delete volumes."
                }


        # --------------------------------------------------
        # Example: time-based restriction
        # --------------------------------------------------

        case "tool.restart_service":

            from datetime import datetime

            hour = datetime.utcnow().hour

            if 6 <= hour <= 20:

                result = {
                    "decision": "allow",
                    "reason_code": "BUSINESS_HOURS",
                    "reason": "Restart allowed during business hours."
                }

            else:

                result = {
                    "decision": "require_approval",
                    "reason_code": "OUTSIDE_BUSINESS_HOURS",
                    "reason": "Restart outside business hours requires approval."
                }


        # --------------------------------------------------
        # Default behavior
        # --------------------------------------------------

        case _:

            result = process_defaults(static_result)


    # ======================================================
    # Output decision
    # ======================================================

    print(json.dumps(result))


if __name__ == "__main__":
    main()

