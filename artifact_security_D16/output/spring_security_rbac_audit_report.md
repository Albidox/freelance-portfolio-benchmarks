# Spring Security 6 RBAC Architecture & Penetration Fuzzing Audit Report

## 1. Executive Summary

This report documents the security audit, penetration fuzzing, and stress probe results for Artifact D16 (Spring Boot 3.4 / Spring Security 6 Stateless RBAC Gate). The security architecture enforces role-based access control across three discrete tiers (`ROLE_USER`, `ROLE_MANAGER`, `ROLE_ADMIN`), validates JSON Web Tokens statelessly via a custom `OncePerRequestFilter`, complies with RFC 7807 Problem Details for all HTTP 4xx error payloads, and defends against common JWT vulnerabilities and path traversal attacks via `StrictHttpFirewall`.

All penetration probes were executed within the automated JUnit 5 and MockMvc test harness. The verification suite achieved a 100% pass rate across 53 integration test scenarios with zero deprecated DSL warnings and zero stack trace disclosures.

---

## 2. Security Verification & Hero Metrics

| Metric | Specification Gate | Audit Result | Status |
| :--- | :--- | :--- | :--- |
| Integration Test Suite | >= 25 test cases | 53 executed (53 passed, 0 failed, 0 skipped) | PASS |
| Test Pass Rate | 100.0% | 100.0% (53/53) | PASS |
| Spring Security Version | 6.4.2 (Spring Boot 3.4.1) | 6.4.2 / Java 21 LTS | PASS |
| Deprecated DSL Warnings | 0 warnings | 0 warnings (Strict Lambda DSLs) | PASS |
| RFC 7807 Problem Details | Enforced on 401 / 403 / 400 | `application/problem+json` confirmed | PASS |
| Algorithm Confusion Probe | Reject `alg: none` & log warning | Rejected via `TokenValidationStatus.ALGORITHM_CONFUSION` | PASS |
| Expired Token Drift Probe | Clean 401 without trace leakage | Confirmed: Zero stack frames in response | PASS |
| Strict HttpFirewall Probe | Block path normalization attacks | Confirmed: 400 / 403 / 401 blocks across all vectors | PASS |
| Epistemic Integrity | Zero Em Dashes | 0 em dashes detected across repository | PASS |

---

## 3. Real-World Stress Probe Scenarios

### 3.1 Algorithm Confusion Probe (`alg: none`)
* **Attack Vector:** An adversary crafts a forged JWT header with `"alg": "none"` or `"alg": "NONE"` and asserts elevated claims (`sub: "forged_admin"`, `roles: ["ROLE_ADMIN"]`) without a cryptographic signature.
* **Defense Implementation:** `JwtTokenProvider.java` implements pre-parse inspection of the decoded header payload. If `"alg": "none"` is identified, the parser intercepts the token immediately, returns `TokenValidationStatus.ALGORITHM_CONFUSION`, logs an explicit security alert at `WARN` level, and halts claims extraction. Furthermore, JJWT parser configuration enforces signed claims (`parseClaimsJws`), raising `UnsupportedJwtException` if unsigned tokens bypass pre-validation.
* **Verification Proof:**
  * `probe01_algorithmConfusionNoneRejected`: Validates parser returns `TokenValidationStatus.ALGORITHM_CONFUSION`.
  * `probe02_forgedNoneTokenCannotAccessAdmin`: Validates `GET /api/v1/admin/dashboard` returns HTTP 401 with RFC 7807 problem details (`title: "Unauthorized"`).
  * `probe03_algorithmConfusionUppercaseNoneRejected`: Validates uppercase `NONE` variant is blocked.
  * `probe04_unsignedTokenWithoutAlgRejected`: Validates completely unsigned payload without `alg` header is rejected.
  * `probe05_foreignKeySignatureRejected`: Validates token signed by an attacker key returns `TokenValidationStatus.INVALID_SIGNATURE` and HTTP 401.

### 3.2 Expired Token Drift Probe
* **Attack Vector:** A client presents an expired token past its TTL, or an attacker replays a lapsed session credential.
* **Defense Implementation:** `JwtTokenProvider` validates `exp` claims using `Jwts.parserBuilder()`. Upon detecting `ExpiredJwtException`, it maps the condition to `TokenValidationStatus.EXPIRED`. `JwtAuthenticationFilter` binds the reason to the request context, and `JwtAuthenticationEntryPoint` renders a clean RFC 7807 Problem Detail response.
* **Zero Stack Trace Leakage Proof:**
  * `probe06_expiredTokenStatus`: Asserts `TokenValidationStatus.EXPIRED` is returned.
  * `probe07_expiredTokenMapsToRfc7807WithoutStackTrace`: Inspects response JSON payload. Asserts standard RFC 7807 fields (`type`, `title`, `status`, `detail`, `instance`, `timestamp`). Asserts complete absence of `stackTrace`, `trace`, Java package references (`at com.albidox...`), and exception class names (`io.jsonwebtoken...`).
  * `probe08_expiredAdminTokenBlocked`: Asserts expired administrative credentials cannot access `/api/v1/admin/dashboard`.

### 3.3 Role Privilege Escalation & Strict HttpFirewall Probe
* **Attack Vector:** An authenticated user possessing `ROLE_USER` attempts to access administrative endpoints or mutate configuration via normalized path traversal, URL-encoded path separators, double slashes, or parameter matrix injections.
* **Defense Implementation:**
  * `StrictHttpFirewall` bean rejects malicious URI patterns, including un-normalized path components (`/../`), URL-encoded slashes (`%2f`), and matrix semicolons (`;`).
  * `RequestRejectedHandler` formats firewall rejections into HTTP 400 Bad Request RFC 7807 problem details payloads.
  * Spring Security `@PreAuthorize("hasRole('ADMIN')")` and `SecurityFilterChain` route authorization gates enforce strict role boundaries, returning HTTP 403 Forbidden RFC 7807 payloads on unauthorized attempts.
* **Verification Proof:**
  * `probe09_pathTraversalDotDotBlocked`: Traversal vector `/api/v1/user/../admin/dashboard` is blocked (HTTP 403 / 400).
  * `probe10_encodedSlashBlockedByFirewall`: Encoded slash vector `/api/v1%2fadmin/dashboard` is blocked (HTTP 400).
  * `probe11_doubleSlashBlockedByFirewall`: Double slash vector `/api/v1//admin/dashboard` is blocked with HTTP 403 Forbidden for standard users and HTTP 401 Unauthorized for unauthenticated requests.
  * `probe12_semicolonMatrixParamBlockedByFirewall`: Semicolon injection `/api/v1/admin/dashboard;bypass=true` is blocked (HTTP 400).
  * `probe13_userCannotMutateAdminSettings`: Standard user attempting `POST /api/v1/admin/settings` receives HTTP 403 Forbidden.
  * `probe14_userCannotDeleteUser`: Standard user attempting `DELETE /api/v1/admin/users/42` receives HTTP 403 Forbidden.
  * `probe15_managerCannotAccessAdminDashboard`: Manager attempting `GET /api/v1/admin/dashboard` receives HTTP 403 Forbidden.
  * `probe16_managerCannotDeleteUser`: Manager attempting `DELETE /api/v1/admin/users/99` receives HTTP 403 Forbidden.
  * `probe17_userCannotAccessManagerAudit`: Standard user attempting `POST /api/v1/manager/audit` receives HTTP 403 Forbidden.

---

## 4. Test Suite Summary

* **Round 1 Suite (`SecurityIntegrationTest.java`):** 36 test cases covering public endpoints, unauthenticated rejections, tampered signature rejections, insufficient role rejections, and valid multi-role accesses.
* **Round 2 Suite (`SecurityStressProbeTest.java`):** 17 test cases covering algorithm confusion variants, token drift, zero stack trace leakage assertions, firewall normalization probes, and privilege escalation boundaries.
* **Total Executed:** 53 test cases.
* **Total Passed:** 53 (100.0%).
* **Build Time:** ~9.9 seconds.

---

## 5. Artifact Manifest & Cryptographic Integrity

All source files, test fixtures, configuration manifests, and reports have been cataloged with SHA-256 checksums in `output/SHA256SUMS.txt`.
