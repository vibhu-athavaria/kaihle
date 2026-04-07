# Security and Privacy

## Secrets
- Secrets MUST NOT be hardcoded or stored in version control.
- All secrets MUST come from environment variables or secrets managers.

## Auth and Authorization
- All endpoints that mutate data or expose non-public information MUST require authentication.
- Role/permission-based authorization checks MUST be applied at the boundary layer.
- Silent privilege escalation or implicit role upgrades are PROHIBITED.

## Sensitive Data
- Passwords, tokens, secrets, and PII MUST NOT be logged or returned in API responses without explicit masking.
- Passwords MUST be stored as secure hashes (bcrypt or argon2). Plaintext is PROHIBITED.

## Input Safety
- Raw query string formatting that risks injection is PROHIBITED.
- All external inputs MUST be validated and sanitized before use.
