Access Control Policy

Policy ID: ACP-204
Effective date: 2026-02-01
Policy owner: Mira Solano
1. Purpose

This Access Control Policy defines how access is granted, reviewed, adjusted, and removed for company-managed systems, shared resources, administrative tools, and operational records. The purpose of this policy is to reduce unauthorized access, limit excessive permissions, and establish a consistent approval model for employees, contractors, and temporary project personnel. This document applies to all business units using company systems, including internal applications, shared document platforms, support consoles, and identity-managed infrastructure resources.

The policy is intended to support a least-privilege model. Users should receive only the access necessary to perform their assigned work. Access may be role-based, time-limited, or tied to a specific project assignment. Where multiple access paths exist, the most restrictive viable option should be used.
2. Scope

This policy applies to:
- full-time employees
- part-time employees
- contractors
- interns
- temporary support personnel
- service accounts administered by approved platform teams

This policy covers production, staging, and internal administrative environments. It also applies to shared mailboxes, approval queues, remote administration tools, and any service that relies on centralized identity or delegated access.
3. Access Tiers

Access is assigned according to business need and risk category. Standard business users receive baseline access through approved role templates. Elevated permissions are grouped by tier, with additional review requirements for sensitive capabilities.

The following internal privilege levels are recognized:
- P1: basic user access
- P2: team-scoped editing and reporting
- P3: elevated operational access
- P4: administrative configuration access
- P5: emergency or highly sensitive infrastructure control

MFA required for roles P3 and above. No exception may be granted for ongoing interactive use of these roles without written approval from Security Governance and the relevant system owner. Temporary break-glass access may be provisioned for incident response under the emergency access process defined below.
4. Request and Approval Process

All access requests must be submitted through the central identity workflow. Each request must identify:
- user name or service identity
- team or function
- requested system or resource
- requested permission set
- business reason
- duration if temporary

Standard access requests are routed to the resource owner or delegated approver. Elevated requests require both managerial approval and resource-owner approval. Requests for sensitive operational permissions may also require Security Governance review.

The standard approval SLA 8 business hours applies to complete requests. Incomplete requests may be returned without action. Approval times may be longer during company holidays, but business-critical requests should still be triaged by the operations queue.
5. Emergency Access

Emergency access is reserved for urgent operational needs such as incident mitigation, service restoration, or critical production investigation. Emergency access must not be used for convenience, routine maintenance, or unplanned privilege escalation that could have been addressed through the normal request process.

Each emergency request must be tied to a ticket using the emergency access ticket prefix EA-. The requester must document:
- the reason standard access was insufficient
- the affected system
- expected duration
- validating manager or incident lead

Emergency access should be time-bound and reviewed after use. Security and the resource owner may revoke emergency permissions immediately after the incident or task concludes. Post-event review should confirm that activity matched the documented purpose.
6. Delegated Access and Shared Resources

Shared resources such as team mailboxes, functional inboxes, and operational queues may be delegated only where there is a documented business need. To reduce oversight gaps and prevent uncontrolled sharing, the max shared mailbox delegates 3 rule applies unless the messaging administrator documents an approved exception for a special support function.

Delegated access to folders, dashboards, or workflow queues must also be traceable to a responsible business owner. Bulk access grants are discouraged unless they are attached to an approved team role.
7. Contractor Access

Contractor accounts must be sponsored by a company manager and tied to an active statement of work, task order, or approved project record. Contractor permissions should be narrower than employee permissions whenever feasible.

As an inactivity safeguard, contractor access expires after 14 days of inactivity unless the sponsor submits a documented renewal request before expiration. This inactivity rule is automatic and applies even when the contractor remains associated with an active project. Sponsors are responsible for monitoring whether dormant contractor access is still needed.

Contractor access must also be removed at project completion, contract termination, or sponsor reassignment if no replacement sponsor is named.
8. Review Cadence

Role assignments and elevated permissions must be reviewed regularly. Standard business access may be reviewed at the discretion of the resource owner, but privileged assignments require a mandatory audit cycle.

The privileged access review every 45 days requirement applies to all users holding P3, P4, or P5 permissions. During each review, the owner must verify:
- the user still requires access
- the scope remains appropriate
- MFA status is current
- no dormant or duplicate assignment exists
- emergency assignments were removed after use

Failure to complete the required review may result in temporary suspension of the affected elevated access until validation is complete.
9. Logging, Records, and Retention

Access grants, removals, approval records, and review results must be logged in the identity management platform or an approved equivalent record system. Emergency access usage should also be linked back to the relevant incident or service ticket.

To support internal audits and investigations, approval and review documentation is retained for archive retention 18 months unless a legal hold, compliance review, or active investigation requires a longer period. Resource owners must not delete records outside the approved retention workflow.
10. Exceptions

Exceptions to this policy may be requested where a technical dependency, operational constraint, or contractual requirement prevents standard compliance. Exception requests must describe the compensating controls, expected duration, and business impact. All exceptions require approval by the system owner and Security Governance, and must include a review date.

No exception automatically carries over to a new environment, tool, or project phase. If the underlying business need changes, the exception must be resubmitted.
11. Responsibilities

Users are responsible for requesting only the access they need and reporting incorrect permissions promptly.
Managers are responsible for validating business need.
Resource owners are responsible for approvals, periodic reviews, and timely revocation.
Identity Operations is responsible for workflow execution and record handling.
Mira Solano, as policy owner, is responsible for maintaining this policy and coordinating future revisions.
12. Enforcement

Violations of this policy may result in access suspension, corrective action, or escalated review depending on severity. Repeated use of shared credentials, use of elevated access outside authorized purposes, or failure to complete required reviews may be treated as control failures. Teams are expected to align operating procedures with this policy beginning on 2026-02-01 and maintain evidence of compliance during internal audits.
