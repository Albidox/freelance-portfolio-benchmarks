package com.albidox.security;

import com.albidox.security.security.JwtTokenProvider;
import com.albidox.security.security.TokenValidationStatus;
import com.fasterxml.jackson.databind.JsonNode;
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
import org.springframework.test.web.servlet.MvcResult;

import java.nio.charset.StandardCharsets;
import java.security.Key;
import java.util.Base64;
import java.util.Date;
import java.util.List;

import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.notNullValue;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class SecurityStressProbeTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private JwtTokenProvider jwtTokenProvider;

    private String userToken;
    private String managerToken;
    private String adminToken;

    @BeforeEach
    void setUp() {
        userToken = jwtTokenProvider.generateToken("user_stress", List.of("ROLE_USER"));
        managerToken = jwtTokenProvider.generateToken("manager_stress", List.of("ROLE_MANAGER"));
        adminToken = jwtTokenProvider.generateToken("admin_stress", List.of("ROLE_ADMIN"));
    }

    // -------------------------------------------------------------
    // Probe Set 1: Algorithm Confusion & Forged Tokens
    // -------------------------------------------------------------

    @Test
    @DisplayName("Probe 01: Forged Token with alg:none is Rejected by Parser")
    void probe01_algorithmConfusionNoneRejected() {
        String forgedToken = jwtTokenProvider.generateNoneAlgorithmToken("forged_admin", List.of("ROLE_ADMIN"));

        TokenValidationStatus status = jwtTokenProvider.validateTokenWithStatus(forgedToken);
        assertEquals(TokenValidationStatus.ALGORITHM_CONFUSION, status);
        assertFalse(jwtTokenProvider.validateToken(forgedToken));
    }

    @Test
    @DisplayName("Probe 02: Forged Token with alg:none Returns 401 RFC 7807 on Admin Endpoint")
    void probe02_forgedNoneTokenCannotAccessAdmin() throws Exception {
        String forgedToken = jwtTokenProvider.generateNoneAlgorithmToken("forged_admin", List.of("ROLE_ADMIN"));

        mockMvc.perform(get("/api/v1/admin/dashboard")
                        .header("Authorization", "Bearer " + forgedToken))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(401)))
                .andExpect(jsonPath("$.title", is("Unauthorized")))
                .andExpect(jsonPath("$.detail", notNullValue()));
    }

    @Test
    @DisplayName("Probe 03: Forged Token with Uppercase NONE is Rejected")
    void probe03_algorithmConfusionUppercaseNoneRejected() {
        String header = Base64.getUrlEncoder().withoutPadding().encodeToString("{\"alg\":\"NONE\",\"typ\":\"JWT\"}".getBytes(StandardCharsets.UTF_8));
        String payload = Base64.getUrlEncoder().withoutPadding().encodeToString("{\"sub\":\"hacker\",\"roles\":[\"ROLE_ADMIN\"]}".getBytes(StandardCharsets.UTF_8));
        String forgedToken = header + "." + payload + ".";

        TokenValidationStatus status = jwtTokenProvider.validateTokenWithStatus(forgedToken);
        assertEquals(TokenValidationStatus.ALGORITHM_CONFUSION, status);
        assertFalse(jwtTokenProvider.validateToken(forgedToken));
    }

    @Test
    @DisplayName("Probe 04: Completely Unsigned Payload without alg Field is Rejected")
    void probe04_unsignedTokenWithoutAlgRejected() {
        String unsignedToken = jwtTokenProvider.generateUnsignedToken("hacker_root", List.of("ROLE_ADMIN"));

        TokenValidationStatus status = jwtTokenProvider.validateTokenWithStatus(unsignedToken);
        assertNotEquals(TokenValidationStatus.VALID, status);
        assertFalse(jwtTokenProvider.validateToken(unsignedToken));
    }

    @Test
    @DisplayName("Probe 05: Token Signed with Untrusted Foreign Key is Rejected")
    void probe05_foreignKeySignatureRejected() throws Exception {
        Key rogueKey = Keys.hmacShaKeyFor("ForeignUntrustedAttackerKeyMustBe32Bytes!".getBytes(StandardCharsets.UTF_8));
        String rogueToken = Jwts.builder()
                .setSubject("counterfeit_admin")
                .claim("roles", List.of("ROLE_ADMIN"))
                .setIssuedAt(new Date())
                .setExpiration(new Date(System.currentTimeMillis() + 60000))
                .signWith(rogueKey, SignatureAlgorithm.HS256)
                .compact();

        TokenValidationStatus status = jwtTokenProvider.validateTokenWithStatus(rogueToken);
        assertEquals(TokenValidationStatus.INVALID_SIGNATURE, status);

        mockMvc.perform(get("/api/v1/admin/dashboard")
                        .header("Authorization", "Bearer " + rogueToken))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(401)));
    }

    // -------------------------------------------------------------
    // Probe Set 2: Expired Token Drift & Zero Stack Trace Leakage
    // -------------------------------------------------------------

    @Test
    @DisplayName("Probe 06: Expired Token Rejected with EXPIRED Status")
    void probe06_expiredTokenStatus() {
        String expiredToken = jwtTokenProvider.generateExpiredToken("expired_alice", List.of("ROLE_USER"));
        TokenValidationStatus status = jwtTokenProvider.validateTokenWithStatus(expiredToken);
        assertEquals(TokenValidationStatus.EXPIRED, status);
        assertFalse(jwtTokenProvider.validateToken(expiredToken));
    }

    @Test
    @DisplayName("Probe 07: Expired Token on User Endpoint Returns RFC 7807 Without Stack Trace")
    void probe07_expiredTokenMapsToRfc7807WithoutStackTrace() throws Exception {
        String expiredToken = jwtTokenProvider.generateExpiredToken("expired_alice", List.of("ROLE_USER"));

        MvcResult result = mockMvc.perform(get("/api/v1/user/profile")
                        .header("Authorization", "Bearer " + expiredToken))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(401)))
                .andExpect(jsonPath("$.title", is("Unauthorized")))
                .andReturn();

        String responseBody = result.getResponse().getContentAsString();
        JsonNode root = objectMapper.readTree(responseBody);

        assertTrue(root.has("type"));
        assertTrue(root.has("title"));
        assertTrue(root.has("status"));
        assertTrue(root.has("detail"));
        assertTrue(root.has("instance"));
        assertTrue(root.has("timestamp"));

        // Rigorous check: Zero stack trace leakage
        assertFalse(root.has("stackTrace"));
        assertFalse(root.has("trace"));
        assertFalse(responseBody.contains("at com.albidox"));
        assertFalse(responseBody.contains("io.jsonwebtoken"));
        assertFalse(responseBody.contains("Exception:"));
    }

    @Test
    @DisplayName("Probe 08: Expired Admin Token on Protected Admin Route Returns 401 RFC 7807")
    void probe08_expiredAdminTokenBlocked() throws Exception {
        String expiredAdminToken = jwtTokenProvider.generateExpiredToken("expired_admin", List.of("ROLE_ADMIN"));

        mockMvc.perform(get("/api/v1/admin/dashboard")
                        .header("Authorization", "Bearer " + expiredAdminToken))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(401)));
    }

    // -------------------------------------------------------------
    // Probe Set 3: Strict HttpFirewall & Path Normalization Traversal
    // -------------------------------------------------------------

    @Test
    @DisplayName("Probe 09: Path Traversal Attempt /api/v1/user/../admin Blocked")
    void probe09_pathTraversalDotDotBlocked() throws Exception {
        // Either blocked by StrictHttpFirewall (400) or normalized and blocked by RBAC gate (403/401)
        MvcResult result = mockMvc.perform(get("/api/v1/user/../admin/dashboard")
                        .header("Authorization", "Bearer " + userToken))
                .andReturn();

        int httpStatus = result.getResponse().getStatus();
        assertTrue(httpStatus == 400 || httpStatus == 403 || httpStatus == 401,
                "Path traversal attempt must be blocked with 400, 403, or 401. Received: " + httpStatus);
        assertNotEquals(200, httpStatus, "Path traversal must never bypass RBAC to return 200 OK");
    }

    @Test
    @DisplayName("Probe 10: URL Encoded Slash in Path Blocked by HttpFirewall")
    void probe10_encodedSlashBlockedByFirewall() throws Exception {
        MvcResult result = mockMvc.perform(get("/api/v1%2fadmin/dashboard")
                        .header("Authorization", "Bearer " + userToken))
                .andReturn();

        int httpStatus = result.getResponse().getStatus();
        assertTrue(httpStatus == 400 || httpStatus == 403 || httpStatus == 401,
                "Encoded slash must be blocked with 400, 403, or 401. Received: " + httpStatus);
        assertNotEquals(200, httpStatus, "Encoded slash must never return 200 OK");
    }

    @Test
    @DisplayName("Probe 11: Double Slash Normalized Path Bypass Blocked")
    void probe11_doubleSlashBlockedByFirewall() throws Exception {
        // Authenticated standard user attempting double slash bypass to admin dashboard
        mockMvc.perform(get("/api/v1//admin/dashboard")
                        .header("Authorization", "Bearer " + userToken))
                .andExpect(status().isForbidden())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(403)))
                .andExpect(jsonPath("$.title", is("Forbidden")));

        // Unauthenticated user attempting double slash bypass to admin dashboard
        mockMvc.perform(get("/api/v1//admin/dashboard"))
                .andExpect(status().isUnauthorized())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(401)))
                .andExpect(jsonPath("$.title", is("Unauthorized")));
    }

    @Test
    @DisplayName("Probe 12: Semicolon Parameter Matrix Traversal Blocked")
    void probe12_semicolonMatrixParamBlockedByFirewall() throws Exception {
        MvcResult result = mockMvc.perform(get("/api/v1/admin/dashboard;bypass=true")
                        .header("Authorization", "Bearer " + userToken))
                .andReturn();

        int httpStatus = result.getResponse().getStatus();
        assertTrue(httpStatus == 400 || httpStatus == 403 || httpStatus == 401,
                "Semicolon traversal must be blocked with 400, 403, or 401. Received: " + httpStatus);
        assertNotEquals(200, httpStatus, "Semicolon matrix traversal must never return 200 OK");
    }

    // -------------------------------------------------------------
    // Probe Set 4: Role Privilege Escalation Boundary Enforcement
    // -------------------------------------------------------------

    @Test
    @DisplayName("Probe 13: Standard User Cannot Mutate Admin System Settings (403 Forbidden)")
    void probe13_userCannotMutateAdminSettings() throws Exception {
        mockMvc.perform(post("/api/v1/admin/settings")
                        .header("Authorization", "Bearer " + userToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"maintenance\": true}"))
                .andExpect(status().isForbidden())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(403)))
                .andExpect(jsonPath("$.title", is("Forbidden")));
    }

    @Test
    @DisplayName("Probe 14: Standard User Cannot Delete User Record (403 Forbidden)")
    void probe14_userCannotDeleteUser() throws Exception {
        mockMvc.perform(delete("/api/v1/admin/users/42")
                        .header("Authorization", "Bearer " + userToken))
                .andExpect(status().isForbidden())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(403)))
                .andExpect(jsonPath("$.title", is("Forbidden")));
    }

    @Test
    @DisplayName("Probe 15: Manager Role Cannot Access Admin Dashboard (403 Forbidden)")
    void probe15_managerCannotAccessAdminDashboard() throws Exception {
        mockMvc.perform(get("/api/v1/admin/dashboard")
                        .header("Authorization", "Bearer " + managerToken))
                .andExpect(status().isForbidden())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(403)))
                .andExpect(jsonPath("$.title", is("Forbidden")));
    }

    @Test
    @DisplayName("Probe 16: Manager Role Cannot Delete User Records (403 Forbidden)")
    void probe16_managerCannotDeleteUser() throws Exception {
        mockMvc.perform(delete("/api/v1/admin/users/99")
                        .header("Authorization", "Bearer " + managerToken))
                .andExpect(status().isForbidden())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(403)))
                .andExpect(jsonPath("$.title", is("Forbidden")));
    }

    @Test
    @DisplayName("Probe 17: User Role Cannot Access Manager Audit Endpoint (403 Forbidden)")
    void probe17_userCannotAccessManagerAudit() throws Exception {
        mockMvc.perform(post("/api/v1/manager/audit")
                        .header("Authorization", "Bearer " + userToken)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"metric\": \"tamper\", \"status\": \"FAIL\"}"))
                .andExpect(status().isForbidden())
                .andExpect(content().contentType(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status", is(403)));
    }
}
