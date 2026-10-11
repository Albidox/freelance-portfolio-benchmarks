# Artifact D16: Spring Security 6 Stateless RBAC Gate

Production-grade, stateless security architecture built on Spring Boot 3.4 and Spring Security 6 using modern lambda DSLs and method-level security (`@PreAuthorize`). Enforces strict role-based access control (RBAC), validates stateless JWT bearer tokens via a custom `OncePerRequestFilter`, and returns RFC 7807 Problem Details JSON across all authentication and authorization rejections.

## Architecture Highlights

1. **Spring Security 6 Lambda DSL:**
   - SecurityFilterChain configured without deprecated chaining methods (`and()`, `authorizeRequests()`).
   - Pure lambda-based configuration (`authorizeHttpRequests`, `sessionManagement`, `exceptionHandling`).
   - Explicit stateless session management (`SessionCreationPolicy.STATELESS`).

2. **Stateless JWT Authentication Filter:**
   - Custom `JwtAuthenticationFilter` extending `OncePerRequestFilter`.
   - Intercepts Bearer tokens from the `Authorization` header.
   - Cryptographically parses claims via JJWT (HMAC-SHA256).
   - Injects populated `UsernamePasswordAuthenticationToken` into `SecurityContextHolder`.

3. **Three-Tier Role Hierarchy & Method Security:**
   - Active role tiers: `ROLE_USER`, `ROLE_MANAGER`, `ROLE_ADMIN`.
   - Method security enabled globally via `@EnableMethodSecurity(prePostEnabled = true)`.
   - Controller endpoints protected with `@PreAuthorize("hasRole('...')")` and `@PreAuthorize("hasAnyRole(...)")`.

4. **RFC 7807 Problem Details Compliance:**
   - Replaces default Spring Boot HTML error white-labels with structured `application/problem+json`.
   - Custom `JwtAuthenticationEntryPoint` for 401 Unauthorized errors (missing token, invalid signature, expired token).
   - Custom `JwtAccessDeniedHandler` and `SecurityGlobalExceptionHandler` for 403 Forbidden errors (insufficient permissions).
   - Fields: `type`, `title`, `status`, `detail`, `instance`, `timestamp`.

## Project Structure

```
artifact_security_D16/
├── pom.xml
├── README.md
├── requirements.txt
├── src/
│   ├── main/
│   │   ├── java/com/albidox/security/
│   │   │   ├── SecurityApplication.java
│   │   │   ├── config/
│   │   │   │   ├── SecurityConfig.java
│   │   │   │   ├── JwtAuthenticationEntryPoint.java
│   │   │   │   ├── JwtAccessDeniedHandler.java
│   │   │   │   └── SecurityGlobalExceptionHandler.java
│   │   │   ├── controller/
│   │   │   │   ├── AuthController.java
│   │   │   │   ├── UserController.java
│   │   │   │   ├── ManagerController.java
│   │   │   │   └── AdminController.java
│   │   │   ├── dto/
│   │   │   │   ├── ApiResponse.java
│   │   │   │   ├── LoginRequest.java
│   │   │   │   └── LoginResponse.java
│   │   │   └── security/
│   │   │       ├── JwtAuthenticationFilter.java
│   │   │       ├── JwtTokenProvider.java
│   │   │       └── TokenValidationStatus.java
│   │   └── resources/
│   │       └── application.properties
│   └── test/
│       └── java/com/albidox/security/
│           ├── SecurityIntegrationTest.java
│           └── SecurityStressProbeTest.java
└── output/
    ├── security_metrics.json
    ├── spring_security_rbac_audit_report.md
    └── SHA256SUMS.txt
```

## Verification & Test Results

Run the full automated test suite:
```bash
mvn clean test
```

Results:
- Tests run: 53
- Failures: 0
- Errors: 0
- Skipped: 0
- Pass rate: 100.0%
- Deprecated DSL warnings: 0
