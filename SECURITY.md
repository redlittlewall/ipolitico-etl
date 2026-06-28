# Security Policy

## Reporting a Vulnerability

We take the security of iPolitico seriously. If you believe you've found a security vulnerability, please follow these steps:

1. **Do not** open a public issue — vulnerabilities should be reported privately.
2. Send an email to the maintainers or open a [GitHub Security Advisory](https://github.com/redlittlewall/ipolitico-etl/security/advisories/new).
3. Include as much detail as possible:
   - Type of vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

## Scope

This project is an **ETL pipeline for public data** from the Brazilian Chamber of Deputies. It reads from public APIs and produces Parquet files. Security concerns typically relate to:

- Dependency vulnerabilities (supply chain)
- Credential leaks (tokens, keys)
- Injection attacks via API responses
- Denial of service via malformed data

## Response Timeline

- **Acknowledgment:** Within 48 hours
- **Triage:** Within 5 business days
- **Fix:** Timeline depends on severity

## Supported Versions

| Version | Supported |
|---------|-----------|
| latest  | ✅        |

Thank you for helping keep iPolitico and its users safe!
