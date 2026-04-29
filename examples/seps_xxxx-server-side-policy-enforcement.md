# **SEP-XXXX: Server-Side Policy Enforcement Extension for MCP Servers**

**Title:** Server-Side Policy Enforcement for MCP Servers  
**Status:** Draft  
**Author:** Sebastian Martinez, individual contributor  
**Created:** 2026-04-28  
**Version:** 1.0-draft  
**Extension identifier:** `io.modelcontextprotocol.policy` or equivalent name to be assigned during review

## **Abstract**

This SEP proposes an optional server-side policy enforcement extension for Model Context Protocol servers.

The extension defines a Policy Enforcement Point inside the MCP Server. The Policy Enforcement Point evaluates server-controlled policy before the server exposes or executes tools, resources, prompts, tasks, or future MCP capabilities.

The core idea is simple: **the MCP Server must not trust the MCP Client by default as the authority for authorization, actor validation, approval state, or capability visibility.** Policy must be enforced where the protected capability is exposed or dispatched.

This extension standardizes the enforcement contract, not the policy language. Implementations may use YAML, JSON, Rego, Cedar, OPA, LDAP, PAM, OAuth claims, a database, a REST service, compiled rules, an in-memory structure, or any other backend.

Optional implementation profiles are described in appendices, including a non-normative YAML reference profile, optional static RBAC, optional structured audit, and delegated governance modules. These profiles are not required for minimal conformance unless explicitly advertised by the server.

## **Motivation**

MCP Servers may expose capabilities that read sensitive context, execute privileged operations, trigger infrastructure workflows, or influence downstream systems. In enterprise environments, these actions must be governed at the point where they are exposed or executed.

Client-side controls and gateway-level enforcement are useful, but they are not sufficient as the only governance layer. A gateway can be bypassed, misconfigured, replaced, or absent in local, embedded, air-gapped, administrative, internal-service, or same-machine deployments. A client may be compromised, overly permissive, incorrectly implemented, or operating with stale discovery data.

Therefore, a server that exposes sensitive capabilities should enforce policy locally before discovery and execution. This supports defense in depth and aligns with Zero Trust principles.

This model is especially relevant for AI-assisted operations, agentic workflows, infrastructure management, regulated environments, and multi-tenant enterprise deployments where different actors may interact with the same MCP Server, including humans, AI agents, supervised AI workflows, automation systems, administrative tools, and internal services.

## **Scope**

### **Core extension**

The core extension defines:

1. A server-side policy capability declaration.  
2. A Zero Trust client posture.  
3. Policy evaluation points for discovery and execution methods.  
4. A minimal decision model.  
5. Actor-based governance semantics.  
6. Approval handling semantics.  
7. An external validation contract.  
8. Fail-closed behavior for invalid, unknown, or unverifiable cases.

### **Optional profiles and guidance**

The appendices describe optional, non-normative profiles and implementation patterns:

* **Appendix A:** Non-normative policy format reference profile.  
* **Appendix B:** Optional static RBAC profile.  
* **Appendix C:** Optional structured audit profile.  
* **Appendix D:** Delegated governance modules.  
* **Appendix E:** Request context and decision response examples.  
* **Appendix F:** Reference implementation guidance and pseudocode.  
* **Appendix G:** Capability declaration example.  
* **Appendix H:** Error mapping example.  
* **Appendix I:** Relationship to gateways and authorization.

These profiles are included to make the proposal practical, but they are not required for minimal conformance unless the server advertises the corresponding support.

## **Non-goals**

This extension does not define a universal policy language.

This extension does not require YAML, JSON, Rego, Cedar, OPA, PAM, LDAP, OAuth, a database, a local script, or any specific backend.

This extension does not require static RBAC. Static RBAC is an optional profile for simple deployments only.

This extension does not require structured audit. Structured audit is an optional profile for deployments that want policy decision records, denial records, approval records, or compliance evidence.

This extension does not allow the MCP Client to supply, select, weaken, or override the server policy.

This extension does not replace MCP authorization, authentication, gateways, OAuth, enterprise IdP controls, or client-side safety mechanisms. It complements them by adding an enforcement point inside the MCP Server.

This extension does not define recursive policy enforcement for a dedicated Policy / RBAC / Audit MCP Server. If a protected MCP Server delegates supporting functions to another service, that service is a trusted backend configured by the protected server operator.

## **Terminology**

**Policy Enforcement Point, PEP**  
The logic inside the MCP Server that enforces policy before exposing or executing a capability.

**Policy Decision Point, PDP**  
The logic, local or external, that returns a policy decision to the Policy Enforcement Point.

**External validation**  
Any implementation-specific mechanism used by the MCP Server to obtain a decision beyond static in-memory policy. Examples include a local script, REST service, database query, PAM, LDAP, OPA, Cedar, in-memory callback, or dedicated Policy / RBAC service.

**Actor**  
The entity on whose behalf a request is made. Examples include `human`, `ai_agent`, `supervised_ai`, `automation`, or implementation-specific actor types.

**Discovery filtering**  
Applying policy to discovery methods so the client only sees capabilities allowed by server-side policy for the current identity, actor, tenant, or context.

**Execution enforcement**  
Applying policy immediately before a capability is executed or retrieved, even if it was previously visible during discovery.

**Static RBAC**  
An optional policy-file-based profile that allows simple deployments to define allowed users and groups for specific MCP methods and capabilities without using an external authorization backend.

**Structured audit**  
An optional profile that allows the MCP Server to emit structured enforcement events for policy evaluation, discovery filtering, access denials, approvals, actor validation failures, static RBAC decisions, and external validation outcomes.

## **Zero Trust client posture**

This extension defines a Zero Trust approach to MCP Server governance.

By default, the MCP Server does not trust the MCP Client to enforce authorization, actor identity, approval state, or capability visibility. The MCP Client may request, display, orchestrate, or participate in approval and elicitation flows, but it is not the authority for policy enforcement.

Policy is evaluated inside the MCP Server before discovery or execution, ensuring that governance is enforced at the point where the protected capability is exposed or dispatched.

Discovery filtering improves least-privilege exposure, but execution-time enforcement remains mandatory. A hidden capability must still be protected if a client attempts to invoke it directly.

### **Trusted local or embedded deployments**

Some deployments may intentionally relax the default Zero Trust assumption. For example, an MCP Server may be embedded in the same process as the host application, linked as a local library, compiled into a trusted system component, or executed inside a controlled same-machine wrapper where identity and actor validation have already been performed by the host.

In these cases, the server may delegate specific validation steps to the trusted local host or wrapper. This behavior must be explicitly enabled by server-side policy and must never be assumed by default.

The exception should be limited to trusted local, embedded, same-process, same-machine, or tightly controlled host environments. It must not be interpreted as permission to trust arbitrary remote MCP Clients.

Example non-normative setting:

default\_policy:  
  \_settings:  
    client\_trust\_mode: "zero\_trust"   \# "zero\_trust" | "trusted\_host"  
    delegate\_actor\_validation: false

permissions:  
  tool.local\_embedded\_action:  
    tools/list: allow  
    tools/call: human\_required  
    \_settings:  
      client\_trust\_mode: "trusted\_host"  
      delegate\_actor\_validation: true

## **Capability declaration**

An MCP Server that supports this extension may declare a policy capability during the `initialize` response.

{  
  "capabilities": {  
    "policy": {  
      "version": "1.0",  
      "supportsDiscoveryFiltering": true,  
      "supportsActorBasedGovernance": true,  
      "supportsExternalValidation": true,  
      "supportsStaticRBAC": false,  
      "supportsAudit": false,  
      "supportsApprovalVia": \["task", "elicitation", "none"\],  
      "policyInfo": {  
        "summary": "Server-side policy enforcement is enabled.",  
        "policyReference": "Contact the server operator or see deployment documentation.",  
        "auditReference": "Audit configuration is managed by the server operator."  
      }  
    }  
  }  
}

### **Capability fields**

`version`  
The version of this policy extension supported by the server.

`supportsDiscoveryFiltering`  
Indicates that the server evaluates policy on discovery methods such as `tools/list`, `resources/list`, `prompts/list`, `tasks/list`, and future list methods.

`supportsActorBasedGovernance`  
Indicates that the server can evaluate actor-based decisions such as `human_required` and `supervised_ai_required` using server-trusted identity context, groups, claims, local users, or other server-controlled validation mechanisms.

`supportsExternalValidation`  
Indicates that the server can invoke external validation logic as part of the policy decision flow. The mechanism is implementation-specific.

`supportsStaticRBAC`  
Indicates that the server supports the optional static RBAC profile described in Appendix B.

`supportsAudit`  
Indicates that the server supports the optional structured audit profile described in Appendix C.

`supportsApprovalVia`  
Lists approval mechanisms supported by the server when a decision is `require_approval`.

Supported values:

* `task`  
* `elicitation`  
* `none`

`policyInfo`  
Optional human-readable, non-sensitive information about the server-side policy and audit configuration. This field is for operator and client UX only. It must not expose secrets, raw policy contents, private file paths, credentials, tokens, internal topology, or sensitive audit destinations.

## **Policy loading**

Policy loading is entirely controlled by the MCP Server implementation and is outside the scope of this extension.

A server may load policy from:

* a local file  
* command-line arguments  
* environment variables  
* a mounted configuration file  
* a container secret  
* a database  
* a URL  
* a trusted configuration service  
* an in-memory structure  
* compiled code  
* a policy engine  
* an enterprise identity or authorization service

The MCP Client must not be responsible for loading or supplying the policy.

A server that implements this extension should load and initialize its policy before it responds to `initialize`, or before it exposes protected capabilities. If policy cannot be loaded and the server is configured for fail-closed behavior, the server should deny protected methods rather than start in an unintended permissive state.

A server may expose a non-sensitive policy reference in its capability declaration, such as a documentation link, support contact, or generic operator-facing message. The server should not expose raw policy file paths, raw policy contents, local audit file paths, bearer tokens, webhook URLs with secrets, internal hostnames, or private infrastructure details to arbitrary clients.

## **Policy evaluation points**

A compliant implementation must evaluate policy before any protected MCP capability is exposed or executed.

The following method families should be considered protected evaluation points:

* `tools/list`  
* `tools/call`  
* `resources/list`  
* `resources/read`  
* `prompts/list`  
* `prompts/get`  
* `tasks/*`  
* any future MCP method or extension method exposed by the server

Policy should be evaluated at both discovery and execution time.

Discovery filtering reduces exposure and improves user experience. Execution enforcement is still required because discovery filtering alone is not authorization. A client may call a hidden method directly, use stale discovery results, or bypass normal UI behavior.

## **Decision model**

The policy decision model defines the result returned by policy evaluation or external validation.

### **Required decision values**

`allow`  
The request is allowed to proceed.

`deny`  
The request must be rejected.

`require_approval`  
The request requires approval before it can proceed. The approval mechanism is controlled by the server policy and server capabilities.

`human_required`  
The request is allowed only when the server can validate that the actor satisfies the server-trusted human actor classification.

`supervised_ai_required`  
The request is allowed only when the server can validate that the actor satisfies the server-trusted human or supervised-AI actor classification.

### **Optional decision fields**

A decision response may include:

`reason`  
A human-readable explanation suitable for logging, user feedback, operational audit, or client display.

`reason_code`  
A machine-readable identifier for the reason.

`metadata`  
Optional structured information, such as approval identifiers, remediation links, policy version, trace identifiers, or workflow references.

Implementations must ignore unknown fields in decision responses unless explicitly configured otherwise.

## **Actor-based governance**

Actor-based governance allows a policy to distinguish between requests made by different actor types.

Example actor types include:

* `human`  
* `ai_agent`  
* `supervised_ai`  
* `automation`  
* implementation-specific actor types

Actor validation must be performed by the MCP Server or by server-trusted validation logic. It may be based on LDAP groups, PAM, OAuth claims, JWT claims, local users, service accounts, enterprise identity groups, local configuration, or another trusted backend.

### **`human_required`**

When a policy decision is `human_required`, the server must allow the request only if it can validate that the actor satisfies the server-trusted human actor classification.

If the server cannot validate this, it must fail closed.

### **`supervised_ai_required`**

When a policy decision is `supervised_ai_required`, the server must allow the request only if it can validate that the actor satisfies the server-trusted human or supervised-AI actor classification.

If the server cannot validate this, it must fail closed.

### **Failure to validate actor type**

If actor validation is required and the server cannot reliably validate the actor type, the server must deny the request.

Recommended decision response:

{  
  "decision": "deny",  
  "reason": "Human-in-the-loop or supervised actor validation is required, but the server cannot validate actor type from trusted identity context.",  
  "reason\_code": "ERR\_CANNOT\_VALIDATE\_ACTOR"  
}

## **Approval handling**

The `require_approval` decision means the request must not proceed until an approval workflow grants permission.

The approval mechanism is server-controlled. The policy may specify how approval should be handled.

Supported values for approval handling are:

`task`  
The server uses MCP Tasks when supported. This is the preferred mechanism for long-running approval workflows, asynchronous approvals, and approvals that may take minutes, hours, or longer.

`elicitation`  
The server uses MCP elicitation when supported. This is suitable for short, interactive approval flows within an active session.

`none`  
The server does not support an approval mechanism for this policy path. The server must treat `require_approval` as `deny` and return a clear reason.

Recommended response when approval is required but unsupported:

{  
  "decision": "deny",  
  "reason": "Approval is required by policy, but this server does not support an approval mechanism for this capability.",  
  "reason\_code": "ERR\_APPROVAL\_NOT\_SUPPORTED"  
}

When approval is implemented, the server should bind approval to the original request using a stable request hash or equivalent mechanism that includes method, capability name, parameters, identity context, and relevant metadata. The server must not allow approval for one request to be replayed for a different operation.

## **External validation contract**

External validation is the mechanism through which the MCP Server may delegate fine-grained authorization, RBAC, ABAC, audit enrichment, approval decisioning, actor validation, or custom enterprise governance logic.

The extension defines the contract, not the backend.

When external validation is enabled, the server passes a request context to validation logic and receives a decision response.

The external validation mechanism may be:

* a local script  
* a REST service  
* an in-memory function  
* a WebAssembly module  
* a policy engine  
* a PAM check  
* an LDAP lookup  
* a database lookup  
* a local file mapping users to capabilities  
* a dedicated authorization service  
* a dedicated Policy / RBAC MCP Server used as an internal backend

The specific invocation mechanism is implementation-specific and configured by the MCP Server operator.

The server should pass resolved identity attributes, not passwords, OAuth tokens, session secrets, private keys, or raw credentials.

## **Fail-closed behavior**

A server implementing this extension should use fail-closed behavior for policy errors.

Recommended behavior:

* policy load failure: deny protected methods or refuse startup, depending on deployment mode  
* invalid policy syntax: deny or refuse startup  
* unknown method: deny by default unless explicitly configured otherwise  
* invalid decision: deny  
* external validation timeout: deny  
* external validation error: deny  
* actor validation failure: deny  
* approval required but unsupported: deny

Recommended reason codes:

ERR\_POLICY\_LOAD\_FAILED  
ERR\_INVALID\_POLICY  
ERR\_UNKNOWN\_METHOD  
ERR\_INVALID\_POLICY\_DECISION  
ERR\_EXTERNAL\_VALIDATION\_TIMEOUT  
ERR\_EXTERNAL\_VALIDATION\_ERROR  
ERR\_CANNOT\_VALIDATE\_ACTOR  
ERR\_APPROVAL\_NOT\_SUPPORTED  
ERR\_POLICY\_VIOLATION

## **Security considerations**

### **Zero trust in the client**

The MCP Client must not be trusted to enforce server policy.

The client may display policy-related information, request approval, participate in elicitation, or show user feedback, but the server remains the authority for deciding whether a protected action is exposed or executed.

### **Trusted host mode is an exception**

A trusted host mode, if implemented, is an explicit exception for local, embedded, same-machine, same-process, or tightly controlled host environments. It must not be treated as the default, and it must not be used to trust arbitrary remote clients.

### **Discovery filtering is not authorization by itself**

Filtering `tools/list`, `resources/list`, or `prompts/list` reduces exposure and improves UX. It must not replace enforcement on `tools/call`, `resources/read`, `prompts/get`, `tasks/*`, or future execution methods.

### **Policy and audit metadata disclosure**

If the server advertises friendly policy or audit information through `policyInfo`, the information must be non-sensitive.

Safe examples include:

* “Server-side policy enforcement is enabled.”  
* “Policy is managed by the platform team.”  
* “Audit is enabled.”  
* “See internal policy documentation.”

Unsafe examples include:

* raw policy file paths on the host  
* raw audit file paths when they reveal sensitive deployment details  
* secret-bearing URLs  
* bearer tokens or environment variable values  
* full policy contents  
* internal topology or private hostnames  
* identity backend implementation details that would aid an attacker

Servers may provide more detailed policy or audit references only to authenticated and authorized administrators, using implementation-specific mechanisms.

### **External validation must not receive credentials**

The server should pass resolved identity claims and context, not raw authentication credentials.

### **Timeouts and fail-safe deny**

External validation must have a timeout. If validation fails, times out, crashes, or returns invalid data, the secure default is deny.

### **Least privilege and sandboxing**

When external validation logic runs as a separate process, it should run with minimal privileges, a scrubbed environment, restricted filesystem access, and no unnecessary secrets.

Implementations may use OS-level sandboxing such as SELinux, AppArmor, seccomp, Landlock, containers, restricted users, or equivalent platform controls.

## **Backward compatibility**

This extension is optional.

Servers that do not declare the policy capability continue to behave as before.

Clients that do not understand the policy capability can still interact with the server using normal MCP methods.

Policy-aware clients may use the capability declaration to display better UX, such as showing that a server performs discovery filtering or supports approval workflows.

## **Open questions**

1. Should the capability name be `policy`, `authorizationPolicy`, `serverPolicy`, or a namespaced extension identifier?  
2. Should `supportsApprovalVia` be part of the capability declaration, or should approval support be inferred from existing Tasks and elicitation capabilities?  
3. Should `human_required` and `supervised_ai_required` remain policy decisions, or should they be represented as constraints that resolve to `allow`, `deny`, or `require_approval`?  
4. Should `policyInfo` be standardized as a minimal informational object, or left fully implementation-specific?  
5. Should the non-normative YAML reference profile remain in this SEP, move to a separate implementation guide, or be removed from the SEP entirely?  
6. Should `_rbac` remain an optional reference profile, become a separately versioned profile in a future version of this specification, or become a separate extension?  
7. Should `_audit` remain an optional reference profile, become a separately versioned profile in a future version of this specification, or become a separate extension?  
8. Should delegated governance modules remain non-normative implementation patterns, or should one or more become separately versioned extension profiles?  
9. Should delegated Audit MCP Server behavior define a standard `audit.record_event` tool contract, or remain implementation-specific?

---

# **Appendix A: Non-normative policy format reference profile**

This appendix is illustrative. It does not define a required policy language.

Implementations are not required to use YAML or to support this exact syntax. The YAML profile is provided only as a simple reference model for local or small implementations.

## **Reference naming convention**

Capability entries use the format:

\<domain\>.\<name\>

Examples:

tool.delete\_volume  
resource.server\_metrics  
prompt.code\_review  
task.approval\_workflow  
skill.security\_scan  
trigger.on\_deployment

Method keys use full MCP method names:

tools/list  
tools/call  
resources/list  
resources/read  
prompts/list  
prompts/get  
tasks/list  
tasks/result  
tasks/cancel

Future methods and extensions can use the same format.

## **Reference fallback behavior**

For this non-normative profile, policy evaluation uses this order:

1. `permissions.<capability>.<method>`  
2. `default_policy.<method>`  
3. `default_policy._other`  
4. hard-coded server fail-closed default, recommended `deny`

The special key `_other` is the final catch-all for unknown, unsupported, or future methods.

## **Example YAML policy**

valid\_methods:  
  \- tools/list  
  \- tools/call  
  \- resources/list  
  \- resources/read  
  \- prompts/list  
  \- prompts/get  
  \- tasks/list  
  \- tasks/result  
  \- tasks/cancel

valid\_decisions:  
  \- allow  
  \- deny  
  \- require\_approval  
  \- human\_required  
  \- supervised\_ai\_required

default\_policy:  
  tools/list: deny  
  tools/call: deny  
  resources/list: deny  
  resources/read: deny  
  prompts/list: deny  
  prompts/get: deny  
  tasks/list: deny  
  tasks/result: allow  
  tasks/cancel: require\_approval  
  \_other: deny

  \_settings:  
    timeout\_ms: 500  
    use\_external\_validation: false  
    actor\_requirement\_non\_match\_decision: deny  
    require\_approval\_via: "task"  
    client\_trust\_mode: "zero\_trust"  
    delegate\_actor\_validation: false

permissions:  
  tool.delete\_volume:  
    tools/list: allow  
    tools/call: human\_required  
    \_settings:  
      require\_approval\_via: "none"

  tool.restart\_service:  
    tools/list: allow  
    tools/call: supervised\_ai\_required  
    \_settings:  
      actor\_requirement\_non\_match\_decision: require\_approval  
      require\_approval\_via: "elicitation"

  resource.server\_metrics:  
    resources/list: allow  
    resources/read: allow

  prompt.code\_review:  
    prompts/list: allow  
    prompts/get: allow  
---

# **Appendix B: Optional static RBAC profile**

Static RBAC is fully optional.

The core extension does not require a static RBAC syntax. The `_rbac` profile is included as an illustrative reference model for simple implementations.

Static RBAC is included as an optional profile because simple and local MCP Servers may need a lightweight way to express user and group restrictions without deploying an external authorization backend. Static RBAC is not required for minimal conformance.

If the community prefers, the `_rbac` profile may be refined, versioned, or split into a future version of this specification or into a separate extension. The core enforcement contract should remain independent of any specific RBAC model.

## **Static RBAC structure**

The key is named `_rbac`, not `rbac`, to avoid collisions with future MCP methods, capabilities, or extension keys.

Example:

permissions:  
  tool.delete\_volume:  
    tools/list: allow  
    tools/call: human\_required

    \_rbac:  
      tools/list:  
        allowed\_groups:  
          \- storage-viewers  
          \- storage-admins

      tools/call:  
        allowed\_groups:  
          \- storage-admins  
        allowed\_users:  
          \- root  
          \- alice

## **Static RBAC evaluation order**

If the server supports `_rbac`, the recommended evaluation order is:

1. Resolve method decision.  
2. Resolve static RBAC for the same method:  
   * `permissions.<capability>._rbac.<method>`  
   * `default_policy._rbac.<method>`  
3. If `_rbac` is defined for the method, authorize only if:  
   * `identity_context.principal` matches one of `allowed_users`, or  
   * at least one value in `identity_context.groups` matches one of `allowed_groups`.  
4. If no `_rbac` rule is defined for the method, no static RBAC restriction is applied by the policy file.

If an `_rbac` rule exists but identity context is missing or cannot be validated, the server should deny by default.

Recommended reason codes:

ERR\_STATIC\_RBAC\_DENY  
ERR\_CANNOT\_VALIDATE\_RBAC\_CONTEXT  
---

# **Appendix C: Optional structured audit profile**

Structured audit is fully optional. The core requirement of this extension is server-side policy enforcement.

Structured audit is included as an optional profile because policy enforcement decisions often need to produce governance evidence. Audit is not required for minimal conformance.

If the community prefers, audit sinks and transport-specific audit behavior may be split into a future version of this specification or into a separate extension. However, this enforcement extension should still define a minimal structured enforcement event so audit implementations can record decisions without relying only on human-readable error messages.

## **Minimal structured enforcement event**

Audit should not depend only on client-visible error strings. The server may return a short, safe error to the MCP Client while internally producing a richer structured enforcement event for audit purposes.

The structured enforcement event should contain enough context to support governance evidence while avoiding unnecessary sensitive data.

Recommended event fields:

{  
  "timestamp": "2026-04-28T15:30:00Z",  
  "event": "access\_denied",  
  "method": "tools/call",  
  "capability": "tool.delete\_volume",  
  "principal": "alice@example.com",  
  "actor\_type": "human",  
  "decision": "deny",  
  "reason\_code": "ERR\_STATIC\_RBAC\_DENY",  
  "request\_hash": "sha256:abc123",  
  "policy\_version": "v1.0"  
}

Audit events may contain more detail than client-facing errors, but they must avoid secrets, credentials, sensitive parameters, raw tokens, private keys, and unnecessary payload data.

## **Illustrative audit modes**

`file`  
The server writes structured audit events to a local file. This is useful for local testing and small deployments.

`url`  
The server sends structured audit events to an HTTP endpoint. This is useful for test collectors, webhooks, simple REST audit services, or integration testing.

`delegated_mcp`  
The server sends structured audit events to a trusted Audit / Logging MCP Server.

`external`  
The server uses an implementation-specific audit backend, such as syslog, journald, OpenTelemetry, SIEM integration, database logging, or a vendor-specific audit service.

## **Illustrative audit configuration**

default\_policy:  
  \_audit:  
    enabled: true  
    mode: "file"                    \# "file" | "url" | "delegated\_mcp" | "external"  
    fail\_mode: "best\_effort"        \# "best\_effort" | "fail\_closed"  
    events:  
      \- policy\_decision  
      \- access\_denied  
      \- approval\_required  
      \- actor\_validation\_failed  
      \- static\_rbac\_denied  
      \- external\_validation\_error  
    include:  
      \- method  
      \- capability  
      \- principal  
      \- actor\_type  
      \- decision  
      \- reason\_code  
      \- request\_hash  
      \- timestamp  
    redact:  
      \- parameters  
      \- credentials  
      \- secrets  
    file:  
      path: "./mcp-policy-audit.jsonl"  
      format: "jsonl"

The recommended default audit fail mode is `best_effort`. For high-risk or regulated operations, `fail_closed` may be configured explicitly.

---

# **Appendix D: Delegated governance modules**

This extension defines the enforcement contract inside the protected MCP Server. It does not require policy, RBAC, or audit logic to be implemented directly inside the server binary.

Implementations may delegate supporting governance functions to separate modules. These modules are implementation-specific and may be embedded libraries, local processes, sidecars, REST services, databases, SaaS services, or dedicated MCP Servers.

The protected MCP Server remains the Policy Enforcement Point in all cases.

## **Policy Provider module**

A Policy Provider module provides policy material to the MCP Server. It may return a policy bundle, effective policy view, version metadata, or policy references. It does not necessarily evaluate each request.

Examples include:

* local YAML or JSON loader  
* Git-backed policy repository  
* REST configuration service  
* Cedar or Rego bundle provider  
* database-backed policy store  
* dedicated Policy Provider MCP Server

If policy retrieval fails, the enforcing server should use a valid cached policy or fail closed according to its server-side configuration.

## **Policy Decision / RBAC module**

A Policy Decision or RBAC module evaluates a specific request and returns a decision such as `allow`, `deny`, `require_approval`, `human_required`, or `supervised_ai_required`.

Examples include:

* LDAP or PAM check  
* local user/group map  
* OPA or Cedar policy engine  
* REST authorization service  
* database-backed authorization rules  
* dedicated Policy / RBAC MCP Server

If the decision module is unavailable or returns an invalid response, the enforcing server should fail closed.

## **Audit module**

An Audit module records structured events emitted by the MCP Server.

Examples include:

* local JSONL file  
* syslog or journald  
* OpenTelemetry  
* SIEM endpoint  
* REST audit collector  
* dedicated Audit / Logging MCP Server

If the audit module is unavailable, the server should follow the configured audit fail mode: `best_effort` by default, or `fail_closed` for high-risk or regulated operations.

## **Trust model for delegated modules**

These modules are not trusted because they are MCP Clients or MCP Servers. They are trusted only because the protected MCP Server operator configured them as trusted local or backend services.

A delegated module should not weaken the Zero Trust posture toward arbitrary MCP Clients.

Illustrative architecture:

LLM / MCP Client  
        |  
        v  
Protected Zero-Trust MCP Server  
        |  
        | optional delegated governance calls  
        v  
Policy Provider / RBAC / Audit module  
        |  
        v  
LDAP / PAM / database / Git / SIEM / OpenTelemetry / enterprise backend  
---

# **Appendix E: Request and decision examples**

## **External validation request context**

{  
  "mcp\_context": {  
    "method": "tools/call",  
    "name": "tool.delete\_volume",  
    "parameters": {  
      "volume\_id": "vol-12345",  
      "region": "eu-west"  
    },  
    "request\_hash": "sha256:example"  
  },  
  "identity\_context": {  
    "principal": "alice@example.com",  
    "actor\_type": "human",  
    "groups": \["storage-admin", "humans"\],  
    "roles": \["administrator"\],  
    "auth\_source": "LDAP",  
    "is\_impersonated": false  
  },  
  "metadata": {  
    "client\_id": "internal-mcp-host-01",  
    "source\_ip": "10.0.5.42",  
    "timestamp": "2026-04-28T15:30:00Z",  
    "tenant\_id": "prod"  
  }  
}

## **Decision response examples**

### **Allow**

{  
  "decision": "allow",  
  "reason": "User belongs to the storage-admin group.",  
  "reason\_code": "RBAC\_ALLOW"  
}

### **Deny**

{  
  "decision": "deny",  
  "reason": "User does not belong to the storage-admin group required for this operation.",  
  "reason\_code": "RBAC\_DENY"  
}

### **Require approval**

{  
  "decision": "require\_approval",  
  "reason": "Deleting a volume requires human approval.",  
  "reason\_code": "APPROVAL\_REQUIRED",  
  "metadata": {  
    "approval\_scope": "storage-admin",  
    "request\_hash": "sha256:example"  
  }  
}

### **Cannot validate actor**

{  
  "decision": "deny",  
  "reason": "Human-in-the-loop or supervised actor validation is required, but the server cannot validate actor type from trusted identity context.",  
  "reason\_code": "ERR\_CANNOT\_VALIDATE\_ACTOR"  
}  
---

# **Appendix F: Non-normative reference implementation guidance**

A minimal implementation may:

1. Load policy at server startup.  
2. Store policy in memory.  
3. Evaluate the requested method and capability.  
4. Resolve actor-based decisions using trusted identity context.  
5. Invoke external validation only when configured.  
6. Apply timeout and fail-safe deny.  
7. Resolve approval handling when the final decision is `require_approval`.  
8. Emit an audit event if supported and enabled.  
9. Execute the MCP capability only when the final decision is `allow`.

## **Illustrative pseudocode**

def evaluate\_policy(request, policy):  
    method \= request.mcp\_context.method  
    name \= request.mcp\_context.name

    decision \= evaluate\_static\_policy\_if\_present(method, name, policy)

    if static\_rbac\_is\_configured(policy, method, name):  
        rbac\_result \= evaluate\_static\_rbac(request, policy, method, name)  
        if rbac\_result.denied:  
            return deny("ERR\_STATIC\_RBAC\_DENY")  
        if rbac\_result.cannot\_validate:  
            return deny("ERR\_CANNOT\_VALIDATE\_RBAC\_CONTEXT")

    decision \= resolve\_actor\_based\_decision(decision, request.identity\_context)

    if external\_validation\_is\_enabled(policy, method, name):  
        decision \= call\_external\_validation(request, decision)

    if decision \== "require\_approval":  
        return handle\_approval(request, policy)

    return decision  
---

# **Appendix G: Example capability declaration**

{  
  "jsonrpc": "2.0",  
  "id": 1,  
  "result": {  
    "protocolVersion": "2025-11-25",  
    "capabilities": {  
      "tools": {  
        "listChanged": true  
      },  
      "resources": {  
        "listChanged": true,  
        "subscribe": true  
      },  
      "prompts": {  
        "listChanged": true  
      },  
      "tasks": {},  
      "policy": {  
        "version": "1.0",  
        "supportsDiscoveryFiltering": true,  
        "supportsActorBasedGovernance": true,  
        "supportsExternalValidation": true,  
        "supportsStaticRBAC": true,  
        "supportsAudit": true,  
        "supportsApprovalVia": \["task", "elicitation", "none"\],  
        "policyInfo": {  
          "summary": "Server-side policy enforcement is enabled.",  
          "policyReference": "Contact the server operator or see deployment documentation.",  
          "auditReference": "Structured audit is enabled and managed by the server operator."  
        }  
      }  
    },  
    "serverInfo": {  
      "name": "example-policy-aware-mcp-server",  
      "title": "Example Policy-Aware MCP Server",  
      "version": "1.0.0"  
    }  
  }  
}  
---

# **Appendix H: Example denied MCP error mapping**

The policy decision is internal to the server. When denying an MCP request, the server should return an MCP-compatible error response or tool result according to the relevant MCP method semantics.

Example JSON-RPC error shape:

{  
  "jsonrpc": "2.0",  
  "id": 42,  
  "error": {  
    "code": \-32001,  
    "message": "Request denied by server-side policy.",  
    "data": {  
      "reason\_code": "RBAC\_DENY",  
      "reason": "User does not belong to the storage-admin group required for this operation."  
    }  
  }  
}

For `tools/call`, an implementation may alternatively return a tool result with `isError: true` when that is more appropriate for the MCP method semantics.

---

# **Appendix I: Relationship to gateways and authorization**

This extension complements gateways and MCP authorization. It does not replace them.

A gateway may authenticate traffic, apply perimeter controls, and enforce organization-wide policies before the request reaches the MCP Server. The MCP Server still enforces policy locally before exposing or executing protected capabilities.

This creates layered governance:

Client / Host / Agent  
        |  
        v  
Gateway or enterprise access layer  
        |  
        v  
MCP Server-side Policy Enforcement Point  
        |  
        v  
Protected capability or backend system

The architectural contribution of this extension is that policy is enforced where the MCP capability is actually exposed or dispatched.

