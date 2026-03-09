#!/usr/bin/env python3

"""
MCP Policy Wrapper
------------------

This wrapper sits in front of the real MCP capability execution path.

Main responsibilities:
1. Load a YAML policy configuration file
2. Read an MCP request context from STDIN
3. Validate the incoming request structure
4. Evaluate static policy rules from YAML
5. Optionally invoke an external policy script
6. Return the final decision to STDOUT as JSON

Expected usage:

    python mcp_policy_wrapper.py /path/to/policy.yaml < request.json

Notes:
- Requires PyYAML: pip install pyyaml
- The external policy script is optional
- The external policy script communicates only through STDIN / STDOUT
- The wrapper applies fail-safe deny behavior when configured to do so
- Actor-based directives such as "human_required" and
  "supervised_ai_required" are supported and resolved into a final
  wire-level decision by the wrapper.
"""

import json
import os
import subprocess
import sys
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError:
    print(json.dumps({
        "decision": "deny",
        "reason_code": "MISSING_DEPENDENCY",
        "reason": "PyYAML is required. Install it with: pip install pyyaml"
    }))
    sys.exit(1)

DEFAULT_TIMEOUT_MS = 500
DEFAULT_ACTOR_REQUIREMENT_NON_MATCH_DECISION = "deny"

VALID_DECISIONS_FALLBACK = {
    "allow",
    "deny",
    "require_approval",
    "human_required",
    "supervised_ai_required",
}

VALID_NON_MATCH_DECISIONS = {"deny", "require_approval"}


# ==========================================================
# Request context helper
# ==========================================================
class RequestContext:
    """
    Lightweight wrapper around the incoming request JSON.

    Expected structure:

    {
      "mcp_context": {
        "method": "...",
        "name": "...",
        "parameters": {...},
        "request_hash": "..."
      },
      "identity_context": {
        "actor_type": "human|supervised_ai|ai_agent",
        ...
      },
      "metadata": {...}
    }
    """

    def __init__(self, raw_data: Dict[str, Any]):
        self.raw = raw_data
        self.mcp = raw_data.get("mcp_context", {})
        self.identity = raw_data.get("identity_context", {})
        self.metadata = raw_data.get("metadata", {})

        self.method = self.mcp.get("method", "")
        self.name = self.mcp.get("name", "")
        self.parameters = self.mcp.get("parameters", {})
        self.request_hash = self.mcp.get("request_hash", "")
        self.actor_type = self.identity.get("actor_type", "")


# ==========================================================
# Configuration loading
# ==========================================================
def load_yaml_config(path: str) -> Dict[str, Any]:
    """
    Load the YAML policy configuration file.

    The YAML root must be a mapping/object.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Policy file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        raise ValueError("Policy YAML root must be a mapping/object")

    return data


# ==========================================================
# Request input parsing
# ==========================================================
def read_request_from_stdin() -> Dict[str, Any]:
    """
    Read and parse the incoming request JSON from STDIN.
    """
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("Empty request payload")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON request: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("Request payload must be a JSON object")

    return data


# ==========================================================
# YAML helpers
# ==========================================================
def get_valid_methods(config: Dict[str, Any]) -> set:
    """
    Return the configured valid MCP methods.
    """
    methods = config.get("valid_methods", [])
    if not isinstance(methods, list):
        return set()
    return {m for m in methods if isinstance(m, str)}


def get_valid_decisions(config: Dict[str, Any]) -> set:
    """
    Return the configured valid policy decisions.
    Falls back to a built-in default set if not defined.
    """
    decisions = config.get("valid_decisions", [])
    if not isinstance(decisions, list):
        return VALID_DECISIONS_FALLBACK

    parsed = {d for d in decisions if isinstance(d, str)}
    return parsed or VALID_DECISIONS_FALLBACK


def get_global_policy_script_settings(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return the global script execution settings.

    These settings act as the global baseline for script execution.
    Capability-related settings such as timeout_ms may be overridden
    through default_policy._settings or permissions.<capability>._settings.
    """
    settings = config.get("policy_script_settings", {})
    if not isinstance(settings, dict):
        return {}
    return settings


def get_wrapper_settings(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return global wrapper settings.

    These settings control wrapper behavior that is not specific to
    script execution.
    """
    settings = config.get("wrapper_settings", {})
    if not isinstance(settings, dict):
        return {}
    return settings


def get_policy_script_path(config: Dict[str, Any]) -> Optional[str]:
    """
    Return the configured external policy script path if valid.
    """
    path = config.get("policy_script")
    if not isinstance(path, str):
        return None

    path = path.strip()
    if not path:
        return None

    if not os.path.isfile(path):
        return None

    return path


# ==========================================================
# Common response helper
# ==========================================================
def deny(code: str, reason: str) -> Dict[str, Any]:
    """
    Convenience helper for deny responses.
    """
    return {
        "decision": "deny",
        "reason_code": code,
        "reason": reason,
    }


# ==========================================================
# Effective settings resolution
# ==========================================================
def resolve_effective_settings(ctx: RequestContext, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve wrapper execution settings using layered fallback.

    Settings precedence (highest to lowest):
    1. permissions.<capability>._settings
    2. default_policy._settings
    3. wrapper_settings
    4. policy_script_settings

    Implementation note:
    The merge is applied from lowest precedence to highest precedence.

    Important:
    - Settings are merged by key, not as an all-or-nothing block.
    - More specific layers override only the keys they explicitly define.
    """
    resolved: Dict[str, Any] = {}

    global_script_settings = get_global_policy_script_settings(config)
    wrapper_settings = get_wrapper_settings(config)
    default_policy = config.get("default_policy", {})
    permissions = config.get("permissions", {})

    capability_policy = permissions.get(ctx.name, {})
    if capability_policy is None:
        capability_policy = {}

    if not isinstance(default_policy, dict):
        default_policy = {}
    if not isinstance(capability_policy, dict):
        capability_policy = {}

    default_settings = default_policy.get("_settings", {})
    capability_settings = capability_policy.get("_settings", {})

    if not isinstance(default_settings, dict):
        default_settings = {}
    if not isinstance(capability_settings, dict):
        capability_settings = {}

    resolved.update(global_script_settings)
    resolved.update(wrapper_settings)
    resolved.update(default_settings)
    resolved.update(capability_settings)

    return resolved


def get_actor_requirement_non_match_decision(
    ctx: RequestContext,
    config: Dict[str, Any],
) -> str:
    """
    Return the configured fallback decision when an actor requirement
    is not satisfied.

    Supported values:
    - deny
    - require_approval

    If the configured value is missing or invalid, fail safe to deny.
    """
    effective_settings = resolve_effective_settings(ctx, config)
    value = effective_settings.get(
        "actor_requirement_non_match_decision",
        DEFAULT_ACTOR_REQUIREMENT_NON_MATCH_DECISION,
    )
    return value if value in VALID_NON_MATCH_DECISIONS else DEFAULT_ACTOR_REQUIREMENT_NON_MATCH_DECISION


# ==========================================================
# Decision resolution helpers
# ==========================================================
def resolve_actor_based_decision(
    ctx: RequestContext,
    decision: str,
    non_match_decision: str,
) -> str:
    """
    Resolve actor-based policy directives into final decisions.

    Supported actor types:
    - human
    - supervised_ai
    - ai_agent

    Behavior:
    - human_required:
        allow only if actor_type == "human"
        otherwise return non_match_decision
    - supervised_ai_required:
        allow only if actor_type in {"human", "supervised_ai"}
        otherwise return non_match_decision

    If actor_type is missing or unknown, fail safe to the configured
    non_match_decision.
    """
    actor_type = ctx.actor_type

    if decision == "human_required":
        return "allow" if actor_type == "human" else non_match_decision

    if decision == "supervised_ai_required":
        return "allow" if actor_type in {"human", "supervised_ai"} else non_match_decision

    return decision


# ==========================================================
# Transform output to final external response
# ==========================================================
def finalize_decision_result(
    ctx: RequestContext,
    config: Dict[str, Any],
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Convert any internal policy directive decision into a final
    wire-level decision.

    This keeps the external contract simple by ensuring the final
    output decision is one of:
    - allow
    - deny
    - require_approval
    """
    decision = result.get("decision", "deny")
    non_match_decision = get_actor_requirement_non_match_decision(ctx, config)
    resolved_decision = resolve_actor_based_decision(ctx, decision, non_match_decision)

    if resolved_decision != decision:
        result = dict(result)
        result["decision"] = resolved_decision

        actor_type = ctx.actor_type or "unknown"

        if decision == "human_required":
            if resolved_decision == "allow":
                result["reason_code"] = "HUMAN_REQUIRED_ALLOW"
                result["reason"] = (
                    f"Request allowed because actor_type '{actor_type}' satisfies "
                    "the 'human_required' policy."
                )
            elif resolved_decision == "require_approval":
                result["reason_code"] = "HUMAN_REQUIRED_APPROVAL"
                result["reason"] = (
                    f"Request requires approval because actor_type '{actor_type}' does not "
                    "satisfy the 'human_required' policy."
                )
            else:
                result["reason_code"] = "HUMAN_REQUIRED_DENY"
                result["reason"] = (
                    f"Request denied because actor_type '{actor_type}' does not satisfy "
                    "the 'human_required' policy."
                )

        elif decision == "supervised_ai_required":
            if resolved_decision == "allow":
                result["reason_code"] = "SUPERVISED_AI_REQUIRED_ALLOW"
                result["reason"] = (
                    f"Request allowed because actor_type '{actor_type}' satisfies "
                    "the 'supervised_ai_required' policy."
                )
            elif resolved_decision == "require_approval":
                result["reason_code"] = "SUPERVISED_AI_REQUIRED_APPROVAL"
                result["reason"] = (
                    f"Request requires approval because actor_type '{actor_type}' does not "
                    "satisfy the 'supervised_ai_required' policy."
                )
            else:
                result["reason_code"] = "SUPERVISED_AI_REQUIRED_DENY"
                result["reason"] = (
                    f"Request denied because actor_type '{actor_type}' does not satisfy "
                    "the 'supervised_ai_required' policy."
                )

    return result


# ==========================================================
# Request validation
# ==========================================================
def validate_context(ctx: RequestContext, valid_methods: set) -> Optional[Dict[str, Any]]:
    """
    Validate the minimum fields required to evaluate policy.
    """
    if not ctx.method:
        return deny("MISSING_METHOD", "Missing MCP method.")

    if not ctx.name:
        return deny("MISSING_TARGET", "Missing policy target name.")

    if "." not in ctx.name:
        return deny(
            "INVALID_TARGET_FORMAT",
            "Policy target name must use flattened namespace format, for example 'tool.name'."
        )

    if valid_methods and ctx.method not in valid_methods:
        return deny(
            "UNKNOWN_METHOD",
            f"Unknown MCP method '{ctx.method}'."
        )

    return None


# ==========================================================
# Static policy evaluation
# ==========================================================
def evaluate_static_policy(
    ctx: RequestContext,
    config: Dict[str, Any],
    valid_decisions: set
) -> Dict[str, Any]:
    """
    Evaluate the static YAML policy.

    Decision fallback model:
    1. permissions.<capability>.<method>
    2. default_policy.<method>
    3. default_policy.other
    """
    permissions = config.get("permissions", {})
    default_policy = config.get("default_policy", {})

    if not isinstance(permissions, dict):
        return deny("INVALID_CONFIG", "Invalid 'permissions' structure in policy file.")

    if not isinstance(default_policy, dict):
        return deny("INVALID_CONFIG", "Invalid 'default_policy' structure in policy file.")

    capability_policy = permissions.get(ctx.name, {})
    if capability_policy is None:
        capability_policy = {}

    if not isinstance(capability_policy, dict):
        return deny(
            "INVALID_CONFIG",
            f"Invalid policy entry for capability '{ctx.name}'. Expected an object/map."
        )

    decision = capability_policy.get(
        ctx.method,
        default_policy.get(ctx.method, default_policy.get("other", "deny"))
    )

    if decision not in valid_decisions:
        return deny(
            "INVALID_POLICY_DECISION",
            f"Invalid decision '{decision}' configured for '{ctx.name}' and method '{ctx.method}'."
        )

    result = {
        "decision": decision,
        "reason_code": "STANDARD_POLICY_MATRIX",
        "reason": f"Policy evaluated for '{ctx.name}' using method '{ctx.method}'."
    }

    return evaluate_static_policy(ctx, config, result)


# ==========================================================
# Helpers for capability presence / script decision
# ==========================================================
def is_capability_explicitly_listed(ctx: RequestContext, config: Dict[str, Any]) -> bool:
    """
    Return True if the capability is explicitly present in the
    permissions section.
    """
    permissions = config.get("permissions", {})
    if not isinstance(permissions, dict):
        return False
    return ctx.name in permissions


def should_use_policy_script(
    ctx: RequestContext,
    config: Dict[str, Any],
    execution_mode: str
) -> bool:
    """
    Decide whether the external policy script should be invoked.

    Behavior by execution_mode:
    - static_only:
        never invoke the script
    - static_plus_script:
        always invoke the script if configured
    - script_only:
        always invoke the script if configured
    - static_selective_script:
        * if capability is explicitly listed in permissions:
            invoke the script only when effective_settings.use_policy_script is true
        * if capability is not explicitly listed:
            invoke the script by default, unless
            default_policy._settings.use_policy_script is explicitly false
    """
    if execution_mode in {"static_plus_script", "script_only"}:
        return True

    if execution_mode == "static_only":
        return False

    if execution_mode == "static_selective_script":
        effective_settings = resolve_effective_settings(ctx, config)
        explicitly_listed = is_capability_explicitly_listed(ctx, config)

        if explicitly_listed:
            return bool(effective_settings.get("use_policy_script", False))

        # Unknown / unlisted capability:
        # run the script by default unless explicitly disabled.
        return bool(effective_settings.get("use_policy_script", True))

    return False


# ==========================================================
# External policy script invocation
# ==========================================================
def call_external_policy_script(
    script_path: str,
    ctx: RequestContext,
    static_result: Dict[str, Any],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Invoke the optional external policy script.

    The wrapper:
    - resolves effective execution settings
    - applies timeout handling
    - validates the external script response
    - falls back to static_result if configured to do so
    """
    effective_settings = resolve_effective_settings(ctx, config)
    global_settings = get_global_policy_script_settings(config)

    timeout_ms = effective_settings.get("timeout_ms", DEFAULT_TIMEOUT_MS)
    fail_on_script_error = global_settings.get("fail_on_script_error", True)

    try:
        timeout_seconds = max(float(timeout_ms) / 1000.0, 0.001)
    except (TypeError, ValueError):
        timeout_seconds = 0.5

    payload = {
        "request_context": ctx.raw,
        "policy_context": {
            "precomputed_result": static_result,
            "matched_policy": config.get("permissions", {}).get(ctx.name, {}),
            "default_policy": config.get("default_policy", {}),
            "effective_settings": effective_settings,
        }
    }

    # Optional hardening example (SELinux):
    #
    # Deployments using SELinux may choose to execute the policy script
    # inside a restricted security domain to limit its capabilities.
    #
    # For example:
    # runcon -t mcp_policy_script_t ./policy_filter.py
    #
    # This allows the script to run with restricted privileges (for example
    # blocking network access or filesystem writes) while still receiving
    # the request context from the wrapper.
    #
    # This behavior is deployment-specific and therefore not enforced
    # directly by the wrapper implementation.

    try:
        proc = subprocess.run(
            [script_path],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False
        )
    except subprocess.TimeoutExpired:
        if fail_on_script_error:
            return deny("POLICY_SCRIPT_TIMEOUT", "External policy script timed out.")
        return static_result
    except Exception as e:
        if fail_on_script_error:
            return deny("POLICY_SCRIPT_EXEC_ERROR", f"External policy script failed to execute: {e}")
        return static_result

    if proc.returncode != 0:
        if fail_on_script_error:
            stderr = (proc.stderr or "").strip()
            return deny(
                "POLICY_SCRIPT_NONZERO_EXIT",
                f"External policy script exited with code {proc.returncode}"
                + (f": {stderr}" if stderr else ".")
            )
        return static_result

    stdout = (proc.stdout or "").strip()
    if not stdout:
        if fail_on_script_error:
            return deny("POLICY_SCRIPT_EMPTY_RESPONSE", "External policy script returned no output.")
        return static_result

    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        if fail_on_script_error:
            return deny("POLICY_SCRIPT_INVALID_JSON", "External policy script returned invalid JSON.")
        return static_result

    if not isinstance(result, dict):
        if fail_on_script_error:
            return deny("POLICY_SCRIPT_INVALID_RESPONSE", "External policy script response must be a JSON object.")
        return static_result

    decision = result.get("decision")
    valid_decisions = get_valid_decisions(config)
    if decision not in valid_decisions:
        if fail_on_script_error:
            return deny(
                "POLICY_SCRIPT_INVALID_DECISION",
                f"External policy script returned invalid decision '{decision}'."
            )
        return static_result

    return finalize_decision_result(ctx, config, result)


# ==========================================================
# Final result merge strategy
# ==========================================================
def merge_result(base_result: Dict[str, Any], override_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge the static result with the external script result.

    Current strategy:
    - If the external script returns a valid result, it fully
      overrides the static result.
    """
    return override_result


# ==========================================================
# Main entry point
# ==========================================================
def main() -> None:
    """
    Main wrapper flow:

    1. Validate CLI usage
    2. Load YAML config
    3. Read request JSON from STDIN
    4. Validate request
    5. Evaluate static policy
    6. Optionally invoke external policy script
    7. Print final result to STDOUT
    """
    if len(sys.argv) != 2:
        print(json.dumps(
            deny("USAGE_ERROR", "Usage: python mcp_policy_wrapper.py /path/to/policy.yaml")
        ))
        sys.exit(1)

    policy_path = sys.argv[1]

    try:
        config = load_yaml_config(policy_path)
    except Exception as e:
        print(json.dumps(deny("CONFIG_LOAD_ERROR", str(e))))
        sys.exit(1)

    try:
        request_data = read_request_from_stdin()
    except Exception as e:
        print(json.dumps(deny("INVALID_REQUEST", str(e))))
        sys.exit(1)

    ctx = RequestContext(request_data)

    valid_methods = get_valid_methods(config)
    valid_decisions = get_valid_decisions(config)

    validation_error = validate_context(ctx, valid_methods)
    if validation_error:
        print(json.dumps(validation_error))
        return

    static_result = evaluate_static_policy(ctx, config, valid_decisions)

    # execution_mode is intentionally global and not overridable per capability.
    # It controls wrapper behavior, not capability-specific policy behavior.
    global_settings = get_global_policy_script_settings(config)
    execution_mode = global_settings.get("execution_mode", "static_plus_script")

    final_result = static_result
    script_path = get_policy_script_path(config)

    if execution_mode == "script_only":
        if script_path:
            script_result = call_external_policy_script(script_path, ctx, static_result, config)
            final_result = script_result
        else:
            final_result = deny(
                "POLICY_SCRIPT_MISSING",
                "Execution mode is 'script_only' but no valid external policy script is configured."
            )

    elif execution_mode in {"static_only", "static_plus_script", "static_selective_script"}:
        if script_path and should_use_policy_script(ctx, config, execution_mode):
            script_result = call_external_policy_script(script_path, ctx, static_result, config)
            final_result = merge_result(static_result, script_result)
        else:
            final_result = static_result

    else:
        final_result = deny(
            "INVALID_CONFIG",
            f"Unknown execution_mode '{execution_mode}'."
        )

    print(json.dumps(final_result))


if __name__ == "__main__":
    main()
