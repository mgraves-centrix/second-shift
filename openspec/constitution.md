# Project Constitution

Immutable principles that all proposals must comply with. Violations are **CRITICAL BLOCKING FINDINGS** --- proposals cannot proceed until resolved.

## Core Principles

### 1. Multi-Tenant Isolation
All database queries, API endpoints, and background jobs MUST filter by `organization_id`. No cross-tenant data access is permitted.

### 2. No Raw Queries
All database operations MUST use parameterized queries or ORM abstractions. No string interpolation or f-strings in SQL, nGQL, or other query languages.

### 3. Authentication Required
All API endpoints MUST require authentication. No unauthenticated access to any resource except health checks and public documentation.

### 4. Secrets Management
Credentials, API keys, and sensitive data MUST be encrypted at rest and NEVER logged, committed to version control, or included in error responses.

### 5. Test Coverage
All new code MUST include tests. Changes that reduce overall test coverage below the project minimum are not permitted.

### 6. API Backward Compatibility
Existing API contracts MUST NOT be broken. Use versioning for breaking changes. Deprecated fields must have a migration path.

---

## Project-Specific Principles

<!-- Add your project's immutable principles below this line -->
