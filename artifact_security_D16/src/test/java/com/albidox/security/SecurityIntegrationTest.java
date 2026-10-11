package com.albidox.security;

import com.albidox.security.dto.LoginRequest;
import com.albidox.security.security.JwtTokenProvider;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.SignatureAlgorithm;
import io.jsonwebtoken.security.Keys;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.nio.charset.StandardCharsets;
import java.security.Key;
import java.util.Date;
import java.util.List;

import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.notNullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class SecurityIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private JwtTokenProvider jwtTokenProvider;

    private String userToken;
    private String managerToken;
    private String adminToken;
    private String expiredToken;
    private String untrustedToken;

    @BeforeEach
    void setUp() {
        userToken = jwtTokenProvider.generateToken("test-user", List.of("ROLE_USER"));
        managerToken = jwtTokenProvider.generateToken("test-manager", List.of("ROLE_MANAGER"));
        adminToken = jwtTokenProvider.generateToken("test-admin", List.of("ROLE_ADMIN"));
        expiredToken = jwtTokenProvider.generateExpiredToken("expired-user", List.of("ROLE_USER"));

        Key untrustedKey = Keys.hmacShaKeyFor("UntrustedKeyForTestingDifferentSecret1234567890".getBytes(StandardCharsets.UTF_8));
        untrustedToken = Jwts.builder()
                .setSubject("hacker")
                .claim("roles", List.of("ROLE_ADMIN"))
                .setIssuedAt(new Date())
                .setExpiration(new Date(System.currentTimeMillis() + 60000))
                .signWith(untrustedKey, SignatureAlgorithm.HS256)
                .compact();
    }

    @Test
    @DisplayName("Test 01: Public Auth Login Endpoint Is Accessible Without Authentication")
    void test01_publicAuthLoginEndpointAccessibleWithoutAuth() throws Exception {
        LoginRequest request = new LoginRequest("alice", "Password123", "USER");

        mockMvc.perform(post("/api/v1/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.token", notNullValue()))
                .andExpect(jsonPath("$.tokenType", is("Bearer")))
                .andExpect(jsonPath("$.username", is("alice")))
                .andExpect(jsonPath("$.roles[0]", is("ROLE_USER")));
    }

    @Test
    @DisplayName("Test 02: Public Auth Login Generates Role User Token")
    void test02_publicAuthLoginGeneratesValidRoleUser() throws Exception {
        LoginRequest request = new LoginRequest("bob", "Password123", "ROLE_USER");

        mockMvc.perform(post("/api/v1/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.roles[0]", is("ROLE_USER")));
    }

    @Test
    @DisplayName("Test 03: Public Auth Login Generates Role Admin Token")
    void test03_publicAuthLoginGeneratesValidRoleAdmin() throws Exception {
        LoginRequest request = new LoginRequest("admin", "Admin123", "ADMIN");

        mockMvc.perform(post("/api/v1/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.roles[0]", is("ROLE_ADMIN")));
    }

    @Test
    @DisplayName("Test 04: Public Auth Login Generates Role Manager Token")
    void test04_publicAuthLoginGeneratesValidRoleManager() throws Exception {
        LoginRequest request = new LoginRequest("manager", "Manager123", "MANAGER");

        mockMvc.perform(post("/api/v1/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.roles[0]", is("ROLE_MANAGER")));
    }

    @Test
    @DisplayName("Test 05: Public Info Endpoint Is Accessible Without Authentication")
    void test05_publicEndpointAccessibleWithoutAuth() throws Exception {
        mockMvc.perform(get("/api/v1/auth/public"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success", is(true)))
                .andExpect(jsonPath("$.data.scope", is("PUBLIC")));
    }

    @Test
    @DisplayName("Test 06: Unauthenticated Request to Admin Dashboard Returns 401 RFC 7807")
    void test06_unauthenticatedAdminDashboardReturns401Rfc7807() throws Exception {
        mockMvc.perform(get("/api/v1/admin/dashboard"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.type", is("https://api.albidox.com/errors/unauthorized")))
                .andExpect(jsonPath("$.title", is("Unauthorized")))
                .andExpect(jsonPath("$.status", is(401)))
                .andExpect(jsonPath("$.instance", is("/api/v1/admin/dashboard")))
                .andExpect(jsonPath("$.timestamp", notNullValue()));
    }

    @Test
    @DisplayName("Test 07: Unauthenticated Request to Admin Settings Returns 401 RFC 7807")
    void test07_unauthenticatedAdminSettingsReturns401Rfc7807() throws Exception {
        mockMvc.perform(post("/api/v1/admin/settings")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"key\": \"val\"}"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(401)))
                .andExpect(jsonPath("$.instance", is("/api/v1/admin/settings")));
    }

    @Test
    @DisplayName("Test 08: Unauthenticated Request to Admin Delete User Returns 401 RFC 7807")
    void test08_unauthenticatedAdminDeleteUserReturns401Rfc7807() throws Exception {
        mockMvc.perform(delete("/api/v1/admin/users/100"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(401)))
                .andExpect(jsonPath("$.instance", is("/api/v1/admin/users/100")));
    }

    @Test
    @DisplayName("Test 09: Unauthenticated Request to User Profile Returns 401 RFC 7807")
    void test09_unauthenticatedUserProfileReturns401Rfc7807() throws Exception {
        mockMvc.perform(get("/api/v1/user/profile"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(401)))
                .andExpect(jsonPath("$.instance", is("/api/v1/user/profile")));
    }

    @Test
    @DisplayName("Test 10: Unauthenticated Request to User Data Returns 401 RFC 7807")
    void test010_unauthenticatedUserDataReturns401Rfc7807() throws Exception {
        mockMvc.perform(get("/api/v1/user/data"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(401)))
                .andExpect(jsonPath("$.instance", is("/api/v1/user/data")));
    }

    @Test
    @DisplayName("Test 11: Unauthenticated Request to User Settings Returns 401 RFC 7807")
    void test11_unauthenticatedUserSettingsReturns401Rfc7807() throws Exception {
        mockMvc.perform(put("/api/v1/user/settings")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"theme\": \"dark\"}"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(401)))
                .andExpect(jsonPath("$.instance", is("/api/v1/user/settings")));
    }

    @Test
    @DisplayName("Test 12: Unauthenticated Request to Manager Reports Returns 401 RFC 7807")
    void test12_unauthenticatedManagerReportsReturns401Rfc7807() throws Exception {
        mockMvc.perform(get("/api/v1/manager/reports"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(401)))
                .andExpect(jsonPath("$.instance", is("/api/v1/manager/reports")));
    }

    @Test
    @DisplayName("Test 13: Unauthenticated Request to Manager Audit Returns 401 RFC 7807")
    void test13_unauthenticatedManagerAuditReturns401Rfc7807() throws Exception {
        mockMvc.perform(post("/api/v1/manager/audit")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"action\": \"CHECK\"}"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(401)))
                .andExpect(jsonPath("$.instance", is("/api/v1/manager/audit")));
    }

    @Test
    @DisplayName("Test 14: Malformed Bearer Token Returns 401 RFC 7807")
    void test14_malformedBearerTokenReturns401Rfc7807() throws Exception {
        mockMvc.perform(get("/api/v1/admin/dashboard")
                        .header("Authorization", "Bearer invalid.malformed.token"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(401)));
    }

    @Test
    @DisplayName("Test 15: Invalid Signature Token Returns 401 RFC 7807")
    void test15_invalidSignatureTokenReturns401Rfc7807() throws Exception {
        mockMvc.perform(get("/api/v1/admin/dashboard")
                        .header("Authorization", "Bearer " + untrustedToken))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(401)));
    }

    @Test
    @DisplayName("Test 16: Expired Token Returns 401 RFC 7807")
    void test16_expiredTokenReturns401Rfc7807() throws Exception {
        mockMvc.perform(get("/api/v1/admin/dashboard")
                        .header("Authorization", "Bearer " + expiredToken))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(401)));
    }

    @Test
    @DisplayName("Test 17: Missing Bearer Prefix Returns 401 RFC 7807")
    void test17_missingBearerPrefixReturns401Rfc7807() throws Exception {
        mockMvc.perform(get("/api/v1/admin/dashboard")
                        .header("Authorization", "Token " + adminToken))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(401)));
    }

    @Test
    @DisplayName("Test 18: Empty Bearer Token Returns 401 RFC 7807")
    void test18_emptyBearerTokenReturns401Rfc7807() throws Exception {
        mockMvc.perform(get("/api/v1/admin/dashboard")
                        .header("Authorization", "Bearer "))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(401)));
    }

    @Test
    @DisplayName("Test 19: User Role Accessing Admin Dashboard Returns 403 RFC 7807")
    void test19_userRoleAccessingAdminDashboardReturns403Rfc7807() throws Exception {
        mockMvc.perform(get("/api/v1/admin/dashboard")
                        .header("Authorization", "Bearer " + userToken))
                .andExpect(status().isForbidden())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.type", is("https://api.albidox.com/errors/forbidden")))
                .andExpect(jsonPath("$.title", is("Forbidden")))
                .andExpect(jsonPath("$.status", is(403)))
                .andExpect(jsonPath("$.instance", is("/api/v1/admin/dashboard")))
                .andExpect(jsonPath("$.timestamp", notNullValue()));
    }

    @Test
    @DisplayName("Test 20: User Role Accessing Admin Settings Returns 403 RFC 7807")
    void test20_userRoleAccessingAdminSettingsReturns403Rfc7807() throws Exception {
        mockMvc.perform(post("/api/v1/admin/settings")
                        .header("Authorization", "Bearer " + userToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"key\": \"val\"}"))
                .andExpect(status().isForbidden())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(403)))
                .andExpect(jsonPath("$.instance", is("/api/v1/admin/settings")));
    }

    @Test
    @DisplayName("Test 21: User Role Accessing Admin Delete User Returns 403 RFC 7807")
    void test21_userRoleAccessingAdminDeleteUserReturns403Rfc7807() throws Exception {
        mockMvc.perform(delete("/api/v1/admin/users/42")
                        .header("Authorization", "Bearer " + userToken))
                .andExpect(status().isForbidden())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(403)))
                .andExpect(jsonPath("$.instance", is("/api/v1/admin/users/42")));
    }

    @Test
    @DisplayName("Test 22: User Role Accessing Manager Reports Returns 403 RFC 7807")
    void test22_userRoleAccessingManagerReportsReturns403Rfc7807() throws Exception {
        mockMvc.perform(get("/api/v1/manager/reports")
                        .header("Authorization", "Bearer " + userToken))
                .andExpect(status().isForbidden())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(403)))
                .andExpect(jsonPath("$.instance", is("/api/v1/manager/reports")));
    }

    @Test
    @DisplayName("Test 23: User Role Accessing Manager Audit Returns 403 RFC 7807")
    void test23_userRoleAccessingManagerAuditReturns403Rfc7807() throws Exception {
        mockMvc.perform(post("/api/v1/manager/audit")
                        .header("Authorization", "Bearer " + userToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"event\": \"AUDIT\"}"))
                .andExpect(status().isForbidden())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(403)))
                .andExpect(jsonPath("$.instance", is("/api/v1/manager/audit")));
    }

    @Test
    @DisplayName("Test 24: Manager Role Accessing Admin Dashboard Returns 403 RFC 7807")
    void test24_managerRoleAccessingAdminDashboardReturns403Rfc7807() throws Exception {
        mockMvc.perform(get("/api/v1/admin/dashboard")
                        .header("Authorization", "Bearer " + managerToken))
                .andExpect(status().isForbidden())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(403)))
                .andExpect(jsonPath("$.instance", is("/api/v1/admin/dashboard")));
    }

    @Test
    @DisplayName("Test 25: Manager Role Accessing User Data Returns 403 RFC 7807")
    void test25_managerRoleAccessingUserDataReturns403Rfc7807() throws Exception {
        mockMvc.perform(get("/api/v1/user/data")
                        .header("Authorization", "Bearer " + managerToken))
                .andExpect(status().isForbidden())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(403)))
                .andExpect(jsonPath("$.instance", is("/api/v1/user/data")));
    }

    @Test
    @DisplayName("Test 26: Authorized User Accessing User Profile Returns 200 OK")
    void test26_authorizedUserAccessingUserProfileReturns200() throws Exception {
        mockMvc.perform(get("/api/v1/user/profile")
                        .header("Authorization", "Bearer " + userToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success", is(true)))
                .andExpect(jsonPath("$.data.username", is("test-user")));
    }

    @Test
    @DisplayName("Test 27: Authorized User Accessing User Data Returns 200 OK")
    void test27_authorizedUserAccessingUserDataReturns200() throws Exception {
        mockMvc.perform(get("/api/v1/user/data")
                        .header("Authorization", "Bearer " + userToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success", is(true)))
                .andExpect(jsonPath("$.data.tier", is("STANDARD_USER")));
    }

    @Test
    @DisplayName("Test 28: Authorized User Updating User Settings Returns 200 OK")
    void test28_authorizedUserUpdatingUserSettingsReturns200() throws Exception {
        mockMvc.perform(put("/api/v1/user/settings")
                        .header("Authorization", "Bearer " + userToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"theme\": \"cyberpunk\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success", is(true)))
                .andExpect(jsonPath("$.data.username", is("test-user")));
    }

    @Test
    @DisplayName("Test 29: Authorized Manager Accessing User Profile Returns 200 OK")
    void test29_authorizedManagerAccessingUserProfileReturns200() throws Exception {
        mockMvc.perform(get("/api/v1/user/profile")
                        .header("Authorization", "Bearer " + managerToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success", is(true)))
                .andExpect(jsonPath("$.data.username", is("test-manager")));
    }

    @Test
    @DisplayName("Test 30: Authorized Manager Accessing Manager Reports Returns 200 OK")
    void test30_authorizedManagerAccessingManagerReportsReturns200() throws Exception {
        mockMvc.perform(get("/api/v1/manager/reports")
                        .header("Authorization", "Bearer " + managerToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success", is(true)))
                .andExpect(jsonPath("$.data.department", is("ENGINEERING")))
                .andExpect(jsonPath("$.data.headcount", is(42)));
    }

    @Test
    @DisplayName("Test 31: Authorized Manager Submitting Audit Returns 200 OK")
    void test31_authorizedManagerSubmittingAuditReturns200() throws Exception {
        mockMvc.perform(post("/api/v1/manager/audit")
                        .header("Authorization", "Bearer " + managerToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"metric\": \"compliance\", \"status\": \"PASS\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success", is(true)))
                .andExpect(jsonPath("$.data.auditStatus", is("RECORDED")));
    }

    @Test
    @DisplayName("Test 32: Authorized Admin Accessing Admin Dashboard Returns 200 OK")
    void test32_authorizedAdminAccessingAdminDashboardReturns200() throws Exception {
        mockMvc.perform(get("/api/v1/admin/dashboard")
                        .header("Authorization", "Bearer " + adminToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success", is(true)))
                .andExpect(jsonPath("$.data.systemStatus", is("OPERATIONAL")))
                .andExpect(jsonPath("$.data.securityEnforcement", is("STRICT_RBAC")));
    }

    @Test
    @DisplayName("Test 33: Authorized Admin Updating System Settings Returns 200 OK")
    void test33_authorizedAdminUpdatingSettingsReturns200() throws Exception {
        mockMvc.perform(post("/api/v1/admin/settings")
                        .header("Authorization", "Bearer " + adminToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"maintenance\": false, \"maxConnections\": 500}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success", is(true)))
                .andExpect(jsonPath("$.data.status", is("APPLIED")));
    }

    @Test
    @DisplayName("Test 34: Authorized Admin Deleting User Returns 200 OK")
    void test34_authorizedAdminDeletingUserReturns200() throws Exception {
        mockMvc.perform(delete("/api/v1/admin/users/88")
                        .header("Authorization", "Bearer " + adminToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success", is(true)))
                .andExpect(jsonPath("$.data.deletedUserId", is(88)));
    }

    @Test
    @DisplayName("Test 35: Authorized Admin Accessing User Profile Returns 200 OK")
    void test35_authorizedAdminAccessingUserProfileReturns200() throws Exception {
        mockMvc.perform(get("/api/v1/user/profile")
                        .header("Authorization", "Bearer " + adminToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success", is(true)))
                .andExpect(jsonPath("$.data.username", is("test-admin")));
    }

    @Test
    @DisplayName("Test 36: Authorized Admin Accessing Manager Reports Returns 200 OK")
    void test36_authorizedAdminAccessingManagerReportsReturns200() throws Exception {
        mockMvc.perform(get("/api/v1/manager/reports")
                        .header("Authorization", "Bearer " + adminToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success", is(true)))
                .andExpect(jsonPath("$.data.department", is("ENGINEERING")));
    }
}
