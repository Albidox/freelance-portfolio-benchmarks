package com.example.security;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
public class SecurityEndpointTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    public void publicHealthEndpoint_isAccessibleByAnyone() throws Exception {
        mockMvc.perform(get("/api/public/health"))
               .andExpect(status().isOk());
    }

    @Test
    public void userProfileEndpoint_isUnauthenticatedForAnonymous() throws Exception {
        mockMvc.perform(get("/api/user/profile"))
               .andExpect(status().isUnauthorized());
    }

    @Test
    @WithMockUser(roles = "USER")
    public void userProfileEndpoint_isAccessibleByUserRole() throws Exception {
        mockMvc.perform(get("/api/user/profile"))
               .andExpect(status().isOk());
    }

    @Test
    @WithMockUser(roles = "USER")
    public void adminMetricsEndpoint_isForbiddenForUserRole() throws Exception {
        mockMvc.perform(get("/api/admin/metrics"))
               .andExpect(status().isForbidden());
    }

    @Test
    @WithMockUser(roles = "ADMIN")
    public void adminMetricsEndpoint_isAccessibleByAdminRole() throws Exception {
        mockMvc.perform(get("/api/admin/metrics"))
               .andExpect(status().isOk());
    }
}
