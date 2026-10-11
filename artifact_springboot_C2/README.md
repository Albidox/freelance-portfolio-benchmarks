# Artifact C2-R1: Spring Security 6 Modernization

## Objective
Modernize legacy Spring Security (`WebSecurityConfigurerAdapter` and `antMatchers`) to Spring Boot 3.4 / Spring Security 6 using `@Bean SecurityFilterChain` and the functional lambda DSL.

## Process & Metrics
1. **Legacy Failure Verified:** Bootstrapped legacy `WebSecurityConfigurerAdapter` and ran compilation. The compiler threw 4 errors: `cannot find symbol WebSecurityConfigurerAdapter` and `antMatchers()`, verifying that these legacy classes are removed in Spring Security 6. (Captured in `output/compile_error.txt`).
2. **Modernization:** Implemented `@Bean SecurityFilterChain` with `authorizeHttpRequests()` and `requestMatchers()` in `SecurityConfig.java`.
3. **Endpoints Implemented:**
   - `/api/public/health` - public
   - `/api/user/profile` - requires `USER` role
   - `/api/admin/metrics` - requires `ADMIN` role
4. **Test Suite Verified:**
   - Created `SecurityEndpointTest.java` with 5 mock tests using `MockMvc` and `@WithMockUser`.
   - Results: **5/5 tests passed**, 0 failures, 0 errors.
   - Build Status: **SUCCESS**

## Artifacts
- `output/compile_error.txt`: Proof of legacy failure.
- `output/surefire_report.txt`: Proof of test suite success.
- `output/fix.patch`: Diff showing modernization of `SecurityConfig.java`.
