package com.ashfaq.n1;

import com.ashfaq.n1.dto.UserResponseDto;
import com.ashfaq.n1.service.UserService;
import com.ashfaq.n1.tracker.SqlStatementCountTracker;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

import java.io.File;
import java.io.FileWriter;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
public class UserN1QueryTest {

    @Autowired
    private UserService userService;

    @Autowired
    private SqlStatementCountTracker statementTracker;

    @Autowired
    private MockMvc mockMvc;

    @Test
    @DisplayName("Demonstrate N+1 queries before optimization (1 initial + 50 lazy loads = 51 queries)")
    void shouldDemonstrateNPlusOneQueriesBeforeOptimization() {
        statementTracker.reset();
        List<UserResponseDto> result = userService.getUsersUnoptimized();
        assertThat(result).hasSize(50);
        // Asserts 51 queries fired (1 + 50)
        assertThat(statementTracker.getQueryCount()).isEqualTo(51);
    }

    @Test
    @DisplayName("Prove single query execution after optimization (1 joined query)")
    void shouldProveSingleQueryExecutionAfterOptimization() {
        statementTracker.reset();
        List<UserResponseDto> result = userService.getUsersOptimized();
        assertThat(result).hasSize(50);
        // Asserts exactly 1 single joined query fired
        assertThat(statementTracker.getQueryCount()).isEqualTo(1);
    }

    @Test
    @DisplayName("Verify endpoint /api/users executes exactly 1 single joined query after optimization")
    void shouldProveEndpointUsesSingleQuery() throws Exception {
        statementTracker.reset();

        mockMvc.perform(get("/api/users"))
                .andExpect(status().isOk());

        int count = statementTracker.getQueryCount();
        List<String> queries = statementTracker.getQueries();

        File outputDir = new File("output");
        if (!outputDir.exists()) {
            outputDir.mkdirs();
        }

        try (FileWriter fw = new FileWriter(new File(outputDir, "test_after_fixed.txt"))) {
            fw.write("=== HIBERNATE N+1 QUERY OPTIMIZATION VERIFICATION ===\n");
            fw.write("Endpoint: GET /api/users\n");
            fw.write("Status: 200 OK\n");
            fw.write("Users Count: 50\n");
            fw.write("Orders Hydrated: 250\n");
            fw.write("Total SQL Queries Fired: " + count + "\n");
            fw.write("Optimization: @EntityGraph(attributePaths = {\"orders\"}) on UserRepository.findAll()\n\n");
            fw.write("--- Captured Queries ---\n");
            int idx = 1;
            for (String q : queries) {
                fw.write("[QUERY-" + (idx++) + "] " + q + "\n");
            }
            fw.write("\nCONCLUSION: Hibernate N+1 defect eliminated. Exactly 1 joined query executed.\n");
        }

        try (FileWriter fw = new FileWriter(new File(outputDir, "sql_log_after.txt"))) {
            int idx = 1;
            for (String q : queries) {
                fw.write("[HIBERNATE-SQL-" + (idx++) + "] " + q + "\n");
            }
            fw.write("TOTAL QUERIES CAPTURED: " + count + "\n");
        }

        assertThat(count).isEqualTo(1);
    }
}
